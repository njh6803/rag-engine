#!/bin/sh
# 리눅스 dockerd 안에서 도는 쪽이다. `probe.sh` 가 Docker-in-Docker 컨테이너의 표준 입력으로 넘긴다.
# 이 컨테이너가 "서버 기계" 노릇을 하고 `/srv/sources` 가 `.env` 에 적는 부모 폴더 노릇을 한다.
# 공유 폴더(NFS, SMB)를 붙이는 일은 `mount -t tmpfs` 로 흉내 낸다. 전파는 파일 시스템의 종류와
# 무관하게 마운트 단위로 정해지므로 tmpfs 로 본 것이 공유 폴더에도 같다고 보지만, 공유 폴더로 직접
# 재지는 않았다.
set -u

ALL="p_default p_rslave probe-c_rslave-1"

root_propagation() {
    # 이미지에 findmnt 가 없어 mountinfo 의 일곱째 칸(shared:N, master:N, 없으면 "-")을 읽는다.
    awk '$5 == "/" {print ($7 == "-") ? "private" : $7}' /proc/self/mountinfo
}

show() {
    # $1: 컨테이너 목록, $2: 컨테이너 안에서 돌릴 명령
    for name in $1; do
        printf '  %s: ' "$name"
        docker exec "$name" sh -c "$2" 2>&1 | tr '\n' ' '
        echo
    done
}

echo "== 안쪽 dockerd"
docker version --format '  server {{.Server.Version}} / kernel {{.Server.KernelVersion}}'
printf '  compose %s\n' "$(docker compose version --short)"
printf '  루트의 전파: %s\n' "$(root_propagation)"

mkdir -p /srv/sources/rules
echo local > /srv/sources/rules/a.txt

echo "== 0. 루트가 shared 가 아닐 때 rslave 로 띄우기"
mount --make-rprivate /
printf '  루트의 전파: %s\n' "$(root_propagation)"
docker run --rm -v /srv/sources:/sources:ro,rslave alpine:3.22 ls /sources 2>&1 | sed 's/^/  /'
mount --make-rshared /
printf '  make-rshared 뒤 루트의 전파: %s\n' "$(root_propagation)"

docker run -d --name p_default -v /srv/sources:/sources:ro alpine:3.22 sleep 900 >/dev/null
docker run -d --name p_rslave -v /srv/sources:/sources:ro,rslave alpine:3.22 sleep 900 >/dev/null
# 4 와 6 에서 `docker restart` 로 다시 띄워 볼 컨테이너다. 전파 설정을 적지 않았다.
docker run -d --name p_restart -v /srv/sources:/sources:ro alpine:3.22 sleep 900 >/dev/null
cat > /tmp/compose.yml <<'EOF'
services:
  c_rslave:
    image: alpine:3.22
    command: sleep 900
    volumes:
      - type: bind
        source: /srv/sources
        target: /sources
        read_only: true
        bind:
          propagation: rslave
EOF
docker compose -f /tmp/compose.yml -p probe up -d >/dev/null 2>&1
echo "  compose up 종료 코드: $?"
for name in $ALL; do
    printf '  %s 의 /sources 전파 설정: ' "$name"
    docker inspect "$name" --format '{{range .Mounts}}{{.Propagation}} rw={{.RW}}{{end}}'
done

echo "== 1. 컨테이너가 뜬 직후(공유 폴더를 붙이기 전)"
show "$ALL" 'ls /sources'

mkdir /srv/sources/share
mount -t tmpfs tmpfs /srv/sources/share
echo shared > /srv/sources/share/b.txt
echo "== 2. 컨테이너가 뜬 뒤에 서버 기계에서 /srv/sources/share 를 붙인 뒤의 ls /sources/share"
show "$ALL" 'ls -A /sources/share; echo "(끝)"'

echo "== 3. 쓰기가 되는지(읽기 전용으로 붙였다)"
echo "  처음부터 있던 폴더 /sources/rules:"
show "$ALL" 'touch /sources/rules/w 2>&1 && echo 쓰였다'
echo "  나중에 전해진 /sources/share:"
show "p_rslave probe-c_rslave-1" 'touch /sources/share/w 2>&1 && echo 쓰였다'
echo "  컨테이너가 보는 마운트:"
show "$ALL" "awk '\$5 ~ /^\\/sources/ {print \$5, \$6, \$7}' /proc/self/mountinfo"

echo "== 4. 붙인 뒤에 새로 띄운 컨테이너(전파 설정을 적지 않았다)"
docker run -d --name p_after -v /srv/sources:/sources:ro alpine:3.22 sleep 900 >/dev/null
show "p_after" 'ls -A /sources/share; echo "(끝)"'
show "p_after" 'touch /sources/share/w 2>&1 && echo 쓰였다'
show "p_after" "awk '\$5 ~ /^\\/sources/ {print \$5, \$6, \$7}' /proc/self/mountinfo"
echo "  붙이기 전에 뜬 컨테이너(전파 설정을 적지 않았다), docker restart 앞:"
show "p_restart" 'ls -A /sources/share; echo "(끝)"'
docker restart -t 1 p_restart >/dev/null
echo "  같은 컨테이너, docker restart 뒤:"
show "p_restart" 'ls -A /sources/share; echo "(끝)"'
show "p_restart" 'touch /sources/share/w2 2>&1 && echo 쓰였다'

echo "== 5. 서버 기계에서 공유 폴더를 떼어 낸 뒤의 ls /sources/share"
umount /srv/sources/share
show "$ALL p_after" 'ls -A /sources/share; echo "(끝)"'

echo "== 6. 다시 붙인 뒤(내용이 달라졌다)의 ls /sources/share"
mount -t tmpfs tmpfs /srv/sources/share
echo again > /srv/sources/share/c.txt
show "$ALL p_after" 'ls -A /sources/share; echo "(끝)"'
docker restart -t 1 p_after >/dev/null
echo "  p_after 를 docker restart 로 다시 띄운 뒤:"
show "p_after" 'ls -A /sources/share; echo "(끝)"'

echo "== 7. 부모 폴더 자체가 나중에 붙은 경우"
umount /srv/sources/share
mkdir -p /srv/whole
docker run -d --name w_default -v /srv/whole:/sources:ro alpine:3.22 sleep 900 >/dev/null
docker run -d --name w_rslave -v /srv/whole:/sources:ro,rslave alpine:3.22 sleep 900 >/dev/null
mount -t tmpfs tmpfs /srv/whole
mkdir /srv/whole/rules
echo late > /srv/whole/rules/d.txt
show "w_default w_rslave" 'ls -A /sources; echo "(끝)"'
