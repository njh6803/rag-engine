#!/usr/bin/env bash
# 끊긴 네트워크 공유 폴더(SMB/CIFS, NFS)에서 파이썬의 읽기 호출이 어떻게 되는지를 잰다(source-sync 명세
# "동기화의 차례"의 돌아오지 않는 호출 규칙, 2026-11-21 설계 인터뷰).
#
# 명세는 "공유 폴더가 끊기면 파일을 읽는 호출이 돌아오지 않을 수 있고, 그때는 작업자 컨테이너를 다시
# 띄우면 끝난다"는 어림 위에 서 있다. 같은 폴더의 `stuck-calls/probe.py` 는 막힘을 빈 파이프 읽기로
# 흉내 냈다. 이 프로브는 진짜 네트워크 파일 시스템을 붙여 놓고 서버를 끊어 본다.
#
# 칸 하나는 붙이는 방식 하나와 서버를 끊는 법 하나다. 붙이는 방식은 CIFS 기본(soft), CIFS `hard`,
# NFS 기본(hard, NFSv4.2), NFS `soft` 넷이다. 끊는 법은 pause(서버 프로세스를 얼린다), disconnect
# (서버를 네트워크에서 뗀다), kill(서버 컨테이너를 죽인다) 셋이다. NFS 서버는 커널 스레드라 pause 로
# 얼지 않아, 얼지 않는다는 것만 한 칸으로 본다. 칸마다 보는 것은 다음과 같다.
# 1. 끊긴 뒤, 그 전에 한 번도 읽지 않은 대상의 `os.listdir`, `os.stat`, `open(...).read()` 가 오류로
#    돌아오는지(errno 와 걸린 초), 한도 안에 돌아오지 않는지. 미리 열어 둔 파일의 `read()` 도 본다.
#    hard 는 120초 시점에 한 번 적고 270초까지, soft 는 400초까지 본다(호출이 모두 돌아오면 그 전에
#    서버를 다시 잇는다).
# 2. 읽기에 막힌 파이썬 프로세스에 SIGTERM 과 SIGKILL 을 보냈을 때 끝나는지와 걸린 시간. 끊고 5초에
#    한 번, 200초에 한 번 본다. SIGTERM 은 처리기를 달지 않은 프로세스와 단 프로세스를 따로 본다.
# 3. 제품이 쓰려는 모양. (가) daemon 스레드 하나가 읽기에 막힌 채 주 스레드가 그냥 끝나는 프로세스가
#    사라지는지와 `ps` 의 상태 글자. (나) 그 모양이 컨테이너의 주 프로세스일 때 `docker stop` 이 몇 초에
#    끝나는지와 종료 코드, `docker restart` 뒤에 새 프로세스가 뜨는지. 주 스레드가 막힌 모양과, 다른
#    컨테이너의 프로세스가 먼저 보던 폴더를 보는 모양도 본다.
# 4. 서버를 다시 이었을 때 막혀 있던 호출이 성공으로 돌아오는지와 걸린 시간.
# 5. 막힌 동안 같은 마운트의 다른 파일을 새로 읽으면 그 호출도 막히는지(끊고 30초, 90초, 첫 호출이
#    돌아온 직후와 30초 뒤와 90초 뒤). 한 번도 본 적 없는 같은 폴더를 여러 프로세스가 함께 볼 때도 본다.
#
# 모양은 `mount-propagation/probe.sh` 와 같다. 특권 Docker-in-Docker 컨테이너(`stuckmnt-host`)가 "서버
# 기계" 노릇을 한다. 그 안에서 공유 폴더를 붙이고(`inner.sh`), 그 부모 폴더를 제품의 작업자 이미지로
# 띄운 컨테이너의 `/sources` 에 붙여 `reader.py` 를 돌린다. 파일 서버는 바깥 Docker 의 컨테이너다
# (`server_smb.sh`, `server_nfs.sh`. `alpine:3.22` 에 Alpine 공식 저장소의 samba 와 nfs-utils 를 깐다).
# 서버 기계 컨테이너에는 바깥 Docker 의 소켓을 붙여, 안에서 서버를 끊고 다시 잇는다. 같은 파일 시스템의
# 칸들은 서버와 붙이는 자리를 따로 쓰며 함께 돈다(CIFS 칸들이 먼저, NFS 칸들이 그다음).
#
# 커널 모듈 cifs, nfs, nfsv4, nfsd 와 그것들이 기대는 모듈은 mount 가 스스로 올린다(modprobe 를 치지
# 않는다). 한 번 올라간 모듈은 Docker Desktop 의 가상 기계가 다시 뜰 때까지 남는다. 커널은 Docker
# Desktop 의 WSL2 커널이라 배포판 리눅스 서버의 커널과 버전이 다르다. NFS 는 붙이는 쪽이 컨테이너의
# 네트워크 이름공간 안이라, 실제로 걸린 옵션의 `fatal_neterrors` 가 서버 기계에서 바로 붙일 때와 다를
# 수 있다.
#
# 만드는 것(컨테이너, 네트워크, 볼륨)은 모두 이름이 `stuckmnt-` 로 시작하고 끝에 지운다. 끝에 서버를
# 먼저 다시 답하게 한 뒤 마운트를 떼고 지운다.
#
# 주의. 2026-11-21 의 첫 실행(`probe_out.txt`)에서 CIFS 칸 여섯을 함께 돌리던 중, 서버가 답하지 않은 지
# 190초쯤에 커널의 작업 스레드 하나(`smb2_deferred_work_close`. 닫기를 미뤄 둔 파일을 닫는 일)가 CPU
# 하나를 쥐고 17분 넘게 헛돌았다(커널 로그의 soft lockup). 그동안 그 CPU 에 걸린 커널의 다른 일이 밀려
# Docker 의 네트워크 명령(바깥 Docker 의 start, network connect, unpause 까지)과 CIFS 의 umount 가
# 돌아오지 않았고, 가상 기계의 디스크 저널 스레드도 막혔다고 커널이 적었다. Docker Desktop 의 가상 기계
# 전체가 겪는 일이라 이 프로브와 상관없는 컨테이너도 함께 겪는다. 그때 손으로 친 명령과 출력은
# `lockup_seen.txt` 에 있다. 헛돈 것은 `hard` 로 붙인 CIFS 에서 서버가 TCP 로도 닿지 않게 된 칸
# (cifs-hard-disconnect, cifs-hard-kill) 가운데 하나로 보인다. 얼린 서버를 녹인 뒤에도 계속 헛돌았고,
# 닿지 않던 그 두 서버의 주소로 가는 연결을 살아 있는 서버로 돌리는 규칙을 손으로 넣은 지 3초 뒤에
# 풀렸기 때문이다(`lockup_seen.txt` 8절). 어느 쪽인지는 가르지 못했고, 다시 일으켜 확인하지도 않았다.
# 그래서 이 두 칸은 `STUCKMNT_LOCKUP_CELLS=1` 을 줄 때만 돈다. 주지 않으면 이름을 인자로 줘도 돌지
# 않는다. 물결(같은 파일 시스템의 칸들)마다 커널 로그에 soft lockup 이 생겼는지 적고, 도는 동안 생기면
# 서버를 모두 다시 잇는 명령을 친다. 다만 첫 실행에서 start 와 network connect 는 헛도는 동안 돌아오지
# 않았으니, 이 명령으로 풀린다고 볼 수는 없다.
#
# 출력은 넷이다. `probe_out.txt` 는 열한 칸을 모두 돈 첫 실행이다. 위 두 칸을 가리기 전의 스크립트로
# 돌았다. 그 실행의 CIFS 칸들은 끊고 190초쯤부터 위의 헛도는 상태에서 잰 값이고, 뗀 서버와 죽인 서버를
# 다시 잇는 명령은 헛도는 동안 돌아오지 않아 그 칸들의 "서버를 다시 이은 뒤" 줄은 실제로는 이어지지
# 않은 채 잰 값이다. `probe_out_cifs_soft.txt` 는 헛돌지 않는 상태에서 CIFS 기본(soft) 세 칸만 다시 돈
# 출력이다. 두 칸을 가리고 soft lockup 을 적게 고친 뒤의 스크립트로 돌았는데, 그때는 물결을 시작한 때를
# `/proc/uptime` 으로 읽었다. 이 PC 에서 그 값은 커널 로그의 시각보다 58.6초 앞서 있어서, 그 출력의
# "soft lockup 줄은 없었다"는 물결의 첫 58.6초를 보지 않은 판정이다(그 사이에 줄이 없었다는 것은 손으로
# 봤다. `lockup_seen.txt` 9절). `probe_out_cifs_pause.txt` 는 시작한 때를 커널 로그의 시각으로 읽게 고친
# 지금의 스크립트로 서버를 얼리는 CIFS 두 칸(soft, hard)을 다시 돈 출력이다. `lockup_seen.txt` 는
# 헛도는 동안 손으로 친 명령과 그 출력이다.
#
# `probe_out.txt` 와 `probe_out_cifs_soft.txt` 에서 컨테이너 로그의 "읽기가 돌아왔다" 줄에 찍힌 시각은
# 호출이 돌아온 때가 아니라 호출을 시작한 때다(`reader.py` 의 `read_once` 가 그때는 그렇게 찍었다).
# `probe_out_cifs_pause.txt` 부터는 돌아온 때다. 걸린 초를 적은 줄은 이것과 상관없다.
#
# 실행(저장소 루트에서, Git Bash. Docker Desktop 이 켜져 있어야 하고 제품의 작업자 이미지가 있어야
# 한다. 다른 이미지로 돌리려면 READER_IMAGE 를 준다. 파이썬 3.12 와 /usr/bin/tini 가 든 이미지여야
# 한다). 20분쯤 걸린다. 칸 이름을 인자로 주면 그 칸만 돈다.
#     bash .scratch/source-sync/probes/stuck-mount/probe.sh \
#         > .scratch/source-sync/probes/stuck-mount/probe_out.txt 2>&1
#     bash .scratch/source-sync/probes/stuck-mount/probe.sh \
#         cifs-soft-pause cifs-soft-disconnect cifs-soft-kill \
#         > .scratch/source-sync/probes/stuck-mount/probe_out_cifs_soft.txt 2>&1
#     bash .scratch/source-sync/probes/stuck-mount/probe.sh cifs-soft-pause cifs-hard-pause \
#         > .scratch/source-sync/probes/stuck-mount/probe_out_cifs_pause.txt 2>&1
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
HERE_W="$(cygpath -w "$HERE" 2>/dev/null || echo "$HERE")"
export MSYS_NO_PATHCONV=1
NET=stuckmnt-net
SUBNET=10.213.77
HOST=stuckmnt-host
HOST_IMAGE=docker:29.9.2-dind
SERVER_IMAGE=alpine:3.22
READER_IMAGE="${READER_IMAGE:-rag-engine-test/rag-engine-worker:0.1.0-rc.1}"
OUT="$(mktemp -d)"

# 칸: 이름, 파일 시스템, 더하는 옵션(없으면 -), 끊는 법, 한도(초), 서버 주소의 끝자리
CELLS="cifs-soft-pause cifs - pause 400 11
cifs-hard-pause cifs hard pause 270 12
cifs-soft-disconnect cifs - disconnect 400 13
cifs-hard-disconnect cifs hard disconnect 270 14
cifs-soft-kill cifs - kill 400 15
cifs-hard-kill cifs hard kill 270 16
nfs-hard-disconnect nfs - disconnect 270 21
nfs-soft-disconnect nfs soft disconnect 400 22
nfs-hard-kill nfs - kill 270 23
nfs-soft-kill nfs soft kill 400 24
nfs-hard-pause nfs - pause 270 25"

# 커널을 헛돌게 한 것으로 보이는 칸(머리 주석의 "주의"). STUCKMNT_LOCKUP_CELLS=1 을 줄 때만 돈다.
RISKY=" cifs-hard-disconnect cifs-hard-kill "

selected() {
    # $1: 칸 이름. 인자를 주지 않았으면 위험한 칸을 뺀 모든 칸이 고른 칸이다.
    if [ "${STUCKMNT_LOCKUP_CELLS:-0}" != 1 ] && [[ "$RISKY" == *" $1 "* ]]; then
        return 1
    fi
    if [ "${#WANTED[@]}" -eq 0 ]; then
        return 0
    fi
    for each in "${WANTED[@]}"; do
        if [ "$each" = "$1" ]; then
            return 0
        fi
    done
    return 1
}

modules() {
    docker exec "$HOST" sh -c \
        "awk '\$1 ~ /^(cifs|cifs_md4|cifs_arc4|libarc4|nls_ucs2_utils|dns_resolver|netfs|nfs|nfsv4|nfsd|nfs_acl|lockd|grace|sunrpc|auth_rpcgss|rpcsec_gss_krb5|krb5)\$/ { printf \"%s(%s) \", \$1, \$3 }' /proc/modules"
    echo
}

start_server() {
    # $1: 칸 이름, $2: 파일 시스템, $3: 서버 주소의 끝자리
    local server="stuckmnt-$1-srv"
    if [ "$2" = cifs ]; then
        docker create --name "$server" --network "$NET" --ip "$SUBNET.$3" "$SERVER_IMAGE" \
            sh /server.sh >/dev/null
        docker cp "$HERE_W/server_smb.sh" "$server:/server.sh" >/dev/null
    else
        docker create --name "$server" --privileged --network "$NET" --ip "$SUBNET.$3" \
            -v "stuckmnt-$1-export:/export" "$SERVER_IMAGE" sh /server.sh >/dev/null
        docker cp "$HERE_W/server_nfs.sh" "$server:/server.sh" >/dev/null
    fi
    docker start "$server" >/dev/null
}

wait_server() {
    # $1: 칸 이름, $2: 파일 시스템. 서버가 포트를 열 때까지 기다린다.
    local server="stuckmnt-$1-srv" port=445
    if [ "$2" = nfs ]; then
        port=2049
    fi
    for _ in $(seq 1 180); do
        if docker exec "$server" sh -c "netstat -ltn 2>/dev/null | grep -q ':$port '" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    echo "  서버 $server 가 3분 안에 뜨지 않았다"
    docker logs "$server" 2>&1 | tail -n 5 | sed 's/^/    /'
    return 1
}

restore_all() {
    # 서버를 모두 다시 답하게 한다(얼린 것은 녹이고, 죽은 것은 띄우고, 뗀 것은 다시 붙인다).
    while read -r name fstype opts fail limit suffix; do
        docker unpause "stuckmnt-$name-srv" >/dev/null 2>&1
        docker start "stuckmnt-$name-srv" >/dev/null 2>&1
        docker network connect --ip "$SUBNET.$suffix" "$NET" "stuckmnt-$name-srv" >/dev/null 2>&1
    done <<< "$CELLS"
}

kmsg_now() {
    # 커널 로그의 시계로 지금이 몇 초인지 낸다. 표지 한 줄을 커널 로그에 적고 그 줄에 찍힌 시각을 읽는다.
    # /proc/uptime 은 다른 시계라 쓰지 않는다(이 PC 에서 커널 로그의 시각보다 58.6초 앞서 있었다).
    local mark="stuckmnt wave mark $$ $RANDOM"
    docker exec "$HOST" sh -c "echo '$mark' > /dev/kmsg; dmesg | grep -F '$mark' | tail -n 1" \
        | sed -n 's/^\[ *\([0-9.]*\)\].*/\1/p'
}

lockup_since() {
    # $1: 커널 로그의 시각(초). 그 뒤의 커널 로그에 soft lockup 줄이 있으면 0 으로 끝난다.
    docker exec "$HOST" sh -c \
        "dmesg | awk -v t0='$1' '/soft lockup/ && substr(\$0, 2, index(\$0, \"]\") - 2) + 0 > t0 { found = 1 } END { exit !found }'"
}

guard() {
    # $1: 물결이 시작한 때의 커널 로그 시각. 그 뒤의 커널 로그에 soft lockup 이 보이면 서버를 모두 다시
    # 잇는 명령을 치고 그 사실을 적는다. 5초마다 본다.
    while sleep 5; do
        if lockup_since "$1"; then
            echo "  지킴이: 커널 로그에 soft lockup 이 보여 $(date +%H:%M:%S) 에 서버를 모두 다시 잇는 명령을 쳤다." \
                "그 뒤의 값은 끊긴 상태에서 잰 값이 아니다" > "$OUT/guard.out"
            restore_all
            return
        fi
    done
}

run_wave() {
    # $1: 파일 시스템. 그 파일 시스템의 고른 칸들을 함께 돌리고, 출력은 칸의 차례대로 낸다.
    local names=() pids=() since guard_pid=
    while read -r name fstype opts fail limit suffix; do
        if [ "$fstype" = "$1" ] && selected "$name"; then
            names+=("$name")
            start_server "$name" "$fstype" "$suffix"
        fi
    done <<< "$CELLS"
    if [ "${#names[@]}" -eq 0 ]; then
        return
    fi
    echo "== $1 칸 ${#names[@]}개를 함께 돈다: ${names[*]}"
    since="$(kmsg_now)"
    while read -r name fstype opts fail limit suffix; do
        if [ "$fstype" != "$1" ] || ! selected "$name"; then
            continue
        fi
        if ! wait_server "$name" "$fstype"; then
            echo "== 칸 $name: 서버가 뜨지 않아 잴 수 없었다" > "$OUT/$name.out"
            continue
        fi
        if [ "$opts" = - ]; then
            opts=
        fi
        docker exec -e CELL="$name" -e FSTYPE="$fstype" -e MOUNT_OPTS="$opts" -e FAIL="$fail" \
            -e LIMIT="$limit" -e SERVER="stuckmnt-$name-srv" -e SERVER_IP="$SUBNET.$suffix" \
            -e IMAGE="$READER_IMAGE" -e NET="$NET" "$HOST" sh /probe/inner.sh \
            < /dev/null > "$OUT/$name.out" 2>&1 &
        pids+=("$!")
    done <<< "$CELLS"
    # 시각을 읽지 못했으면 지킴이를 띄우지 않는다. 옛 줄을 새 줄로 보거나 새 줄을 놓치지 않으려는 것이다.
    if [ -n "$since" ]; then
        guard "$since" &
        guard_pid=$!
    fi
    if [ "${#pids[@]}" -gt 0 ]; then
        wait "${pids[@]}"
    fi
    if [ -n "$guard_pid" ]; then
        kill "$guard_pid" 2>/dev/null
        wait "$guard_pid" 2>/dev/null
    fi
    for name in "${names[@]}"; do
        cat "$OUT/$name.out"
    done
    echo "== $1 칸들이 도는 동안의 커널 로그"
    if [ -e "$OUT/guard.out" ]; then
        cat "$OUT/guard.out"
        rm -f "$OUT/guard.out"
    fi
    if [ -z "$since" ]; then
        echo "  물결을 시작한 때의 커널 로그 시각을 읽지 못해 soft lockup 이 있었는지 가리지 못했다"
    elif lockup_since "$since"; then
        echo "  커널 로그의 시각 $since 초 뒤에 soft lockup 줄이 있었다(커널이 한 CPU 에서 헛돌았다)"
    else
        echo "  커널 로그의 시각 $since 초(물결을 시작한 때) 뒤에 soft lockup 줄은 없었다"
    fi
    echo "== $1 칸들이 끝난 뒤 올라와 있는 커널 모듈(이름과 쓰는 수)"
    printf '  '
    modules
}

cleanup() {
    echo "== 정리"
    # 서버를 먼저 다시 답하게 한다.
    restore_all
    docker exec "$HOST" sh /probe/host_cleanup.sh
    # NFS 서버는 SIGTERM 으로 멈춰 커널의 nfsd 스레드를 내리게 한 뒤 지운다.
    local left
    left="$(docker ps -a --format '{{.Names}}' | grep '^stuckmnt-.*-srv$')"
    if [ -n "$left" ]; then
        # shellcheck disable=SC2086
        docker stop -t 10 $left >/dev/null 2>&1
    fi
    left="$(docker ps -a --format '{{.Names}}' | grep '^stuckmnt-')"
    if [ -n "$left" ]; then
        # shellcheck disable=SC2086
        docker rm -f -v $left >/dev/null 2>&1
    fi
    left="$(docker volume ls --format '{{.Name}}' | grep '^stuckmnt-')"
    if [ -n "$left" ]; then
        # shellcheck disable=SC2086
        docker volume rm $left >/dev/null 2>&1
    fi
    docker network rm "$NET" >/dev/null 2>&1
    rm -rf "$OUT"
    echo "  남은 컨테이너(docker ps -a 의 stuckmnt-): $(docker ps -a --format '{{.Names}}' | grep -c '^stuckmnt-')"
    echo "  남은 네트워크(docker network ls 의 stuckmnt-): $(docker network ls --format '{{.Name}}' | grep -c '^stuckmnt-')"
    echo "  남은 볼륨(docker volume ls 의 stuckmnt-): $(docker volume ls --format '{{.Name}}' | grep -c '^stuckmnt-')"
}

WANTED=("$@")
trap 'cleanup; exit 130' INT TERM

echo "== 바깥 Docker"
docker version --format '  server {{.Server.Version}} {{.Server.Os}} / kernel {{.Server.KernelVersion}}'
docker info --format '  {{.OperatingSystem}}'
if [ "${STUCKMNT_LOCKUP_CELLS:-0}" != 1 ]; then
    echo "  돌지 않는 칸(STUCKMNT_LOCKUP_CELLS=1 을 줄 때만 돈다):$RISKY"
fi

docker network create --subnet "$SUBNET.0/24" "$NET" >/dev/null
docker run -d --privileged --name "$HOST" --network "$NET" --ip "$SUBNET.2" -e DOCKER_TLS_CERTDIR= \
    -v /var/run/docker.sock:/var/run/outer.sock "$HOST_IMAGE" >/dev/null
ready=no
for _ in $(seq 1 90); do
    if docker exec "$HOST" docker info >/dev/null 2>&1; then
        ready=yes
        break
    fi
    sleep 1
done
echo "== 서버 기계 노릇의 컨테이너($HOST_IMAGE)"
echo "  안쪽 dockerd 준비: $ready"
docker exec "$HOST" docker version --format '  안쪽 server {{.Server.Version}} / kernel {{.Server.KernelVersion}}'
printf '  측정 전에 올라와 있는 커널 모듈(이름과 쓰는 수): '
modules
docker exec "$HOST" apk add --no-cache cifs-utils nfs-utils mount >/dev/null 2>&1
printf '  붙이는 도구: '
docker exec "$HOST" sh -c "apk info -v 2>/dev/null | grep -E '^(cifs-utils|nfs-utils|mount)-[0-9]' | tr '\n' ' '"
echo
docker save "$READER_IMAGE" | docker exec -i "$HOST" docker load >/dev/null
printf '  읽는 쪽 이미지 %s: ' "$READER_IMAGE"
docker exec "$HOST" docker run --rm "$READER_IMAGE" python -c \
    'import os, platform; print("Python", platform.python_version(), platform.platform(), "uid", os.getuid())'
docker exec "$HOST" mkdir -p /probe
for file in reader.py inner.sh host_cleanup.sh; do
    docker cp "$HERE_W/$file" "$HOST:/probe/$file" >/dev/null
done

run_wave cifs
run_wave nfs
cleanup
