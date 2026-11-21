#!/bin/sh
# 한 칸(붙이는 방식 하나와 서버를 끊는 법 하나)을 "서버 기계" 안에서 돈다. `probe.sh` 가
# Docker-in-Docker 컨테이너에 복사해 `sh /probe/inner.sh` 로 부르고, 칸의 설정은 환경 변수로 넘긴다.
# 이 컨테이너가 "서버 기계" 노릇을 한다. 공유 폴더를 `/srv/stuckmnt/<칸>/sources/share` 에 붙이고,
# 그 부모 폴더(`.env` 에 적는 부모 폴더 노릇)를 안쪽 컨테이너의 `/sources` 에 읽기 전용으로 붙인다
# (ADR 0021 의 모양). 안쪽 컨테이너는 제품의 작업자 이미지다(tini 가 1번 프로세스, uid 10001).
#
# 서버 컨테이너는 바깥 Docker 에 있다. 바깥 Docker 의 소켓(`/var/run/outer.sock`)으로 서버를 끊고
# 다시 잇는다. 끊는 법은 셋이다. pause(서버 프로세스를 얼린다. TCP 연결은 커널이 계속 받아 준다),
# disconnect(서버 컨테이너를 네트워크에서 뗀다. 패킷이 사라진다), kill(서버 컨테이너를 죽인다).
#
# 차례는 다음과 같다.
# 1. 붙이고, 실제로 걸린 옵션을 적고, 서버가 살아 있을 때 한 번 읽는다.
# 2. `reader.py suite` 를 띄워 두고 서버를 끊는다. suite 가 호출의 시간표를 낸다(끊긴 뒤 처음 읽는
#    대상의 os.listdir, os.stat, open().read(), 막힌 프로세스에 보내는 SIGTERM 과 SIGKILL, daemon
#    스레드가 막힌 채 주 스레드가 끝나는 프로세스, 같은 폴더를 함께 보는 프로세스, 나중에 새로 부르는
#    호출).
# 3. 그동안 서버 기계에서 `ps` 로 막힌 프로세스의 상태 글자와 커널 안에서 기다리는 자리
#    (`/proc/<pid>/stack` 의 위 여덟. 커널이 주소에서 가장 가까운 이름을 적는 것이라 엉뚱한 이름이
#    섞인다)를 적는다. 끊고 9초, 22초, (한도가 270초 이상이면) 198초에 적는다.
# 4. 그동안 컨테이너의 주 프로세스가 막힌 모양에 `docker stop` 과 `docker restart` 를 친다.
#    w1 은 daemon 스레드가 막힌 것, w2 는 주 스레드가 막힌 것, w4 는 다른 컨테이너의 프로세스가 먼저
#    보던 폴더를 daemon 스레드가 보는 것, w3 은 w1 과 같은 모양을 끊고 205초에 멈춰 보는 것이다(한도가
#    270초 이상일 때만).
# 5. suite 가 청하면(한도에 닿았거나 호출이 모두 돌아왔다) 서버를 다시 잇는다.
# 6. 끊은 뒤의 커널 로그에서 이 서버에 닿는 줄을 적고, 컨테이너를 지우고 마운트를 뗀다.
set -u

: "${CELL:?}" "${FSTYPE:?}" "${FAIL:?}" "${SERVER:?}" "${SERVER_IP:?}" "${LIMIT:?}" "${IMAGE:?}"
: "${NET:?}"
MOUNT_OPTS="${MOUNT_OPTS:-}"
BASE=/srv/stuckmnt/$CELL
SOURCES=$BASE/sources
MNT=$SOURCES/share
CTL=$BASE/ctl
READER=stuckmnt-$CELL-reader
W1=stuckmnt-$CELL-w1
W2=stuckmnt-$CELL-w2
W3=stuckmnt-$CELL-w3
W4=stuckmnt-$CELL-w4
RESTORED=no
LATE=no
if [ "$LIMIT" -ge 270 ]; then
    LATE=yes
fi

outer() {
    docker -H unix:///var/run/outer.sock "$@"
}

reader() {
    # 안쪽 컨테이너에서 reader.py 의 명령 하나를 돌린다.
    docker exec "$READER" python -u /probe/reader.py "$CELL" "$@"
}

worker() {
    # $1: 컨테이너 이름, $2: 대상, $3: daemon-thread 나 main-thread
    docker run -d --name "$1" -v "$SOURCES:/sources:ro" -v /probe:/probe:ro "$IMAGE" \
        python -u /probe/reader.py "$CELL" worker "/sources/share/$2" "$3" >/dev/null
}

uptime_now() {
    cut -d' ' -f1 /proc/uptime
}

elapsed() {
    awk -v a="$1" -v b="$(uptime_now)" 'BEGIN { printf "%.2f", b - a }'
}

sleep_until() {
    # $1: 서버를 끊은 뒤 몇 초까지 잘지
    sleep "$(awk -v t0="$T0" -v now="$(uptime_now)" -v off="$1" \
        'BEGIN { d = t0 + off - now; if (d < 0) d = 0; printf "%.2f", d }')"
}

wait_file() {
    # $1: 파일, $2: 기다릴 초
    tries=0
    while [ ! -e "$1" ]; do
        tries=$((tries + 1))
        if [ "$tries" -gt $(($2 * 5)) ]; then
            return 1
        fi
        sleep 0.2
    done
}

timed() {
    # $1: 설명, 나머지: 명령. 걸린 시간과 명령의 종료 코드를 적고, 실패했으면 명령이 낸 줄도 적는다.
    label=$1
    shift
    started=$(uptime_now)
    "$@" > "$BASE/command.out" 2>&1
    code=$?
    echo "  $label: $(elapsed "$started")초(명령의 종료 코드 $code)"
    if [ "$code" -ne 0 ]; then
        sed 's/^/    명령이 낸 줄: /' "$BASE/command.out"
    fi
}

show_container() {
    # $1: 안쪽 컨테이너 이름. 상태와 그 컨테이너가 지금까지 낸 줄을 적는다.
    printf '    상태: '
    docker inspect "$1" --format \
        '{{.State.Status}}, 종료 코드 {{.State.ExitCode}}, 주 프로세스 pid {{.State.Pid}}'
    docker logs "$1" 2>&1 | sed 's/^/    | /'
}

fail_server() {
    case "$FAIL" in
    pause) outer pause "$SERVER" ;;
    disconnect) outer network disconnect "$NET" "$SERVER" ;;
    kill) outer kill "$SERVER" ;;
    esac >/dev/null
}

restore_server() {
    if [ "$RESTORED" = yes ]; then
        return
    fi
    RESTORED=yes
    case "$FAIL" in
    pause) outer unpause "$SERVER" ;;
    disconnect) outer network connect --ip "$SERVER_IP" "$NET" "$SERVER" ;;
    kill) outer start "$SERVER" ;;
    esac >/dev/null
}

snapshot() {
    # 이 칸의 프로세스와 스레드를 적는다(suite 자신과 docker 클라이언트는 뺀다). 상태가 D 인 것은
    # 커널 안에서 기다리는 자리도 적는다.
    echo "  끊고 $(elapsed "$T0")초에 서버 기계에서 본 ps -T -o pid,ppid,stat,args(이 칸의 것만):"
    COLUMNS=220 ps -T -o pid,ppid,stat,args | grep "reader.py $CELL " \
        | grep -v -e grep -e 'docker ' -e " $CELL suite " > "$BASE/ps.now"
    while read -r pid ppid stat args; do
        echo "    $pid $ppid $stat $args"
        if [ "$stat" = D ]; then
            printf '      커널 안에서 기다리는 자리(위에서 여덟): '
            head -n 8 "/proc/$pid/stack" 2>/dev/null | sed -e 's/^\[<[0-9a-f]*>\] //' -e 's/+0x.*//' \
                | tr '\n' ' '
            echo
        fi
    done < "$BASE/ps.now"
}

restart_stopped() {
    # $1: 안쪽 컨테이너 이름. docker stop 이 멈춘 컨테이너를 docker restart 로 다시 띄워 본다. 멈추지
    # 못했으면 건너뛴다(멈추지 못한 컨테이너의 restart 는 같은 실패를 한 번 더 기다릴 뿐이다).
    if [ "$(docker inspect "$1" --format '{{.State.Status}}')" != exited ]; then
        echo "  docker stop 이 멈추지 못해 docker restart 는 치지 않는다"
        return 1
    fi
    timed "멈춘 컨테이너에 docker restart" docker restart "$1"
    sleep 2
    show_container "$1"
}

container_tests() {
    echo "  (나-1) daemon 스레드 하나가 읽기에 막힌 컨테이너($W1, 대상 t101), 끊고 $(elapsed "$T0")초"
    show_container "$W1"
    timed "docker stop(유예 10초)" docker stop "$W1"
    show_container "$W1"
    if restart_stopped "$W1"; then
        timed "돌고 있는 컨테이너에 docker restart(유예 10초)" docker restart "$W1"
        sleep 2
        show_container "$W1"
    fi

    echo "  (나-2) 주 스레드가 읽기에 막힌 컨테이너($W2, 대상 t102), 끊고 $(elapsed "$T0")초"
    show_container "$W2"
    timed "docker stop(유예 10초)" docker stop "$W2"
    show_container "$W2"
    restart_stopped "$W2"

    echo "  (나-3) 읽는 컨테이너의 프로세스가 먼저 보던 폴더(t060)를 daemon 스레드가 보는 컨테이너($W4)," \
        "끊고 $(elapsed "$T0")초"
    show_container "$W4"
    timed "docker stop(유예 10초)" docker stop "$W4"
    show_container "$W4"
    first=$(COLUMNS=220 ps -o pid,args | grep "reader.py $CELL call stat /sources/share/t060/b.txt" \
        | grep -v grep | awk '{ print $1 }')
    if [ -n "$first" ]; then
        kill -9 $first
        echo "  t060 을 먼저 보던 프로세스(읽는 컨테이너 안, 서버 기계의 pid $first)에 SIGKILL 을 보냈다"
        sleep 2
        show_container "$W4"
        timed "다시 docker stop" docker stop "$W4"
        show_container "$W4"
    else
        echo "  t060 을 먼저 보던 프로세스는 이미 끝나 있었다"
    fi
}

late_container_test() {
    echo "  (나-4) (나-1)과 같은 모양을 끊고 3초에 띄워 두었다가 늦게 멈춘다($W3, 대상 t103)," \
        "끊고 $(elapsed "$T0")초"
    show_container "$W3"
    timed "docker stop(유예 10초)" docker stop "$W3"
    show_container "$W3"
    restart_stopped "$W3"
}

kernel_lines() {
    # 끊을 때 커널 로그에 적어 둔 표지 뒤의 줄 가운데 이 칸의 파일 시스템(CIFS 나 NFS)의 줄을, 끊은 뒤
    # 몇 초인지로 바꿔 낸다. 다른 칸의 서버 주소가 적힌 줄은 뺀다. 주소가 없는 줄(NFS 서버 쪽의 NFSD
    # 줄이 그렇다)은 어느 칸의 것인지 가를 수 없어 NFS 칸마다 나온다.
    case "$FSTYPE" in
    cifs) pattern='CIFS|cifs|SMB|smb|soft lockup' ;;
    *) pattern='NFS|nfs|RPC|rpc|soft lockup' ;;
    esac
    dmesg | awk -v mark="stuckmnt $CELL T0" -v ip="$SERVER_IP" -v pattern="$pattern" '
        function stamp(line) { return substr(line, 2, index(line, "]") - 2) + 0 }
        index($0, mark) { n = 0; t0 = stamp($0); on = 1; next }
        on && $0 ~ pattern {
            if ($0 ~ /10\.213\.77\./ && index($0, ip) == 0) next
            kept[n++] = sprintf("    [끊고 %6.1f초] %s", stamp($0) - t0, substr($0, index($0, "]") + 2))
        }
        END { for (i = 0; i < n; i++) print kept[i]; if (n == 0) print "    (없다)" }'
}

teardown() {
    restore_server
    timed "남은 컨테이너를 docker rm -f" docker rm -f "$W1" "$W2" "$W3" "$W4" "$READER"
    started=$(uptime_now)
    umount "$MNT" 2>&1 | sed 's/^/    /'
    if grep -q " $MNT " /proc/mounts; then
        echo "  umount 가 $(elapsed "$started")초에 실패했다. umount -f 와 umount -l 을 차례로 친다"
        umount -f "$MNT" 2>&1 | sed 's/^/    /'
        if grep -q " $MNT " /proc/mounts; then
            umount -l "$MNT" 2>&1 | sed 's/^/    /'
        fi
    else
        echo "  umount: $(elapsed "$started")초"
    fi
    if grep -q " $MNT " /proc/mounts; then
        echo "  마운트가 남았다: $MNT"
    fi
}

echo "== 칸 $CELL: $FSTYPE, 붙이는 옵션 ${MOUNT_OPTS:-(더하지 않음)}, 서버를 끊는 법 $FAIL, 한도 ${LIMIT}초"
mkdir -p "$MNT" "$CTL"
chmod 777 "$CTL"
case "$FSTYPE" in
cifs) mount -t cifs "//$SERVER_IP/share" "$MNT" -o "ro,guest${MOUNT_OPTS:+,$MOUNT_OPTS}" ;;
nfs) mount -t nfs "$SERVER_IP:/" "$MNT" -o "ro${MOUNT_OPTS:+,$MOUNT_OPTS}" ;;
esac
code=$?
echo "  mount 종료 코드: $code"
if [ "$code" -ne 0 ]; then
    echo "  붙이지 못해 이 칸은 잴 수 없었다"
    exit 1
fi
echo "  실제로 걸린 옵션: $(awk -v m="$MNT" '$2 == m { print $3, $4 }' /proc/mounts)"

docker run -d --name "$READER" -v "$SOURCES:/sources:ro" -v /probe:/probe:ro -v "$CTL:/ctl" \
    "$IMAGE" sleep infinity >/dev/null
printf '  서버가 살아 있을 때: '
reader once read /sources/share/warm/ok.txt 200

reader suite /sources/share /ctl "$LIMIT" > "$BASE/suite.out" 2>&1 &
SUITE=$!
if ! wait_file "$CTL/ready" 60; then
    echo "  suite 가 준비되지 않았다"
    sed 's/^/    /' "$BASE/suite.out"
    T0=$(uptime_now)
    teardown
    exit 1
fi

fail_server
T0=$(uptime_now)
: > "$CTL/t_fail"
echo "stuckmnt $CELL T0" > /dev/kmsg

(
    sleep_until 9
    snapshot
    sleep_until 22
    snapshot
    if [ "$LATE" = yes ]; then
        sleep_until 198
        snapshot
    fi
) > "$BASE/ps.out" 2>&1 &
SNAPSHOTS=$!

sleep_until 3
worker "$W1" t101/a.txt daemon-thread
worker "$W2" t102/a.txt main-thread
worker "$W4" t060/a.txt daemon-thread
if [ "$LATE" = yes ]; then
    worker "$W3" t103/a.txt daemon-thread
fi
sleep_until 10
container_tests > "$BASE/containers.out" 2>&1
if [ "$LATE" = yes ]; then
    sleep_until 205
    late_container_test >> "$BASE/containers.out" 2>&1
fi

if ! wait_file "$CTL/want_restore" $((LIMIT + 60)); then
    echo "  suite 가 서버를 다시 이으라고 청하지 않았다(한도 + 60초). 그냥 잇는다"
fi
T1=$(elapsed "$T0")
: > "$CTL/t_restore"
restore_server
wait "$SUITE"
wait "$SNAPSHOTS"

echo "-- 호출의 시간표(reader.py suite). 서버를 끊고 ${T1}초에 다시 잇는 명령을 쳤다"
cat "$BASE/suite.out"
echo "-- 서버 기계에서 본 ps(셋째 칸이 상태 글자다. 스레드도 한 줄씩 나와 같은 명령이 두 줄일 수 있다)"
cat "$BASE/ps.out"
echo "-- 컨테이너의 주 프로세스일 때(tini 가 1번, 그 아래 파이썬)"
cat "$BASE/containers.out"
echo "-- 커널 로그(끊은 뒤, 이 서버에 닿는 줄)"
kernel_lines
echo "-- 정리"
teardown
