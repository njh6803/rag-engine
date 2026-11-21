#!/bin/sh
# 리눅스 dockerd 안에서 도는 둘째 쪽이다. `probe.sh` 가 `inner.sh` 와 8 단계 뒤에 같은 Docker-in-Docker
# 컨테이너의 표준 입력으로 넘긴다. 단독 compose 가 부모 폴더를 붙일 모양(짧은 문법, `.env` 의 변수,
# 서비스 `server` 와 `worker`, uid 10001)을 그대로 적은 compose 파일로 두 가지를 본다.
# 9. 설치 안내가 적을 명령 `docker compose restart server worker` 가 뜬 뒤에 붙인 폴더와 떼었다 다시
#    붙인 폴더를 보이게 하는지(4 와 6 은 `docker restart` 로 쟀다).
# 10. 설치 폴더에 `sources/` 가 없고 변수도 적지 않았을 때(이 기능이 없던 묶음에서 올린 설치)
#     컨테이너가 뜨는지, 만들어진 폴더의 주인과 권한, uid 10001 이 그 폴더를 읽는지. 같은 볼륨을 긴
#     문법으로 적으면 어떻게 되는지도 함께 본다.
# 운영자가 설치 폴더에서 명령을 치는 것과 같게 compose 는 그 폴더로 옮겨 가서 부른다.
set -u

APP="app-server-1 app-worker-1"
OLD="old-server-1 old-worker-1"

show() {
    # $1: 컨테이너 목록, $2: 컨테이너 안에서 돌릴 명령
    for name in $1; do
        printf '  %s: ' "$name"
        docker exec "$name" sh -c "$2" 2>&1 | tr '\n' ' '
        echo
    done
}

echo "== 9. 단독 compose 가 붙일 모양에서 docker compose restart server worker"
mkdir -p /srv/app-sources/rules /tmp/app
echo local > /srv/app-sources/rules/a.txt
cat > /tmp/app/compose.yml <<'EOF'
services:
  server:
    image: alpine:3.22
    user: "10001:10001"
    command: sleep 900
    volumes:
      - ${RAG_ENGINE_SOURCES_DIR:-./sources}:/sources:ro
  worker:
    image: alpine:3.22
    user: "10001:10001"
    command: sleep 900
    volumes:
      - ${RAG_ENGINE_SOURCES_DIR:-./sources}:/sources:ro
EOF
echo 'RAG_ENGINE_SOURCES_DIR=/srv/app-sources' > /tmp/app/.env
(cd /tmp/app && docker compose -p app up -d >/dev/null 2>&1)
echo "  compose up 종료 코드: $?"
for name in $APP; do
    printf '  %s 가 붙인 폴더: ' "$name"
    docker inspect "$name" --format '{{range .Mounts}}{{.Source}} {{.Propagation}} rw={{.RW}}{{end}}'
done
show "$APP" 'id -u; ls -A /sources'

mkdir /srv/app-sources/share
mount -t tmpfs tmpfs /srv/app-sources/share
echo shared > /srv/app-sources/share/b.txt
echo "  뜬 뒤에 /srv/app-sources/share 를 붙였다. docker compose restart 앞의 ls /sources/share:"
show "$APP" 'ls -A /sources/share; echo "(끝)"'
(cd /tmp/app && docker compose -p app restart -t 1 server worker >/dev/null 2>&1)
echo "  docker compose restart server worker 종료 코드: $?"
echo "  docker compose restart 뒤:"
show "$APP" 'ls -A /sources/share; echo "(끝)"'
show "$APP" 'touch /sources/share/w 2>&1 && echo 쓰였다'

umount /srv/app-sources/share
mount -t tmpfs tmpfs /srv/app-sources/share
echo again > /srv/app-sources/share/c.txt
echo "  떼었다 다시 붙였다(내용이 달라졌다). docker compose restart 앞:"
show "$APP" 'ls -A /sources/share; echo "(끝)"'
(cd /tmp/app && docker compose -p app restart -t 1 server worker >/dev/null 2>&1)
echo "  docker compose restart server worker 종료 코드: $?"
echo "  docker compose restart 뒤:"
show "$APP" 'ls -A /sources/share; echo "(끝)"'

echo "== 10. 설치 폴더에 sources/ 가 없고 변수도 적지 않았을 때"
mkdir -p /tmp/old-install
cp /tmp/app/compose.yml /tmp/old-install/compose.yml
printf '  띄우기 전의 sources/: '
ls -d /tmp/old-install/sources 2>&1
(cd /tmp/old-install && docker compose -p old up -d >/tmp/old-up.txt 2>&1)
code=$?
echo "  짧은 문법으로 적은 compose up 종료 코드: $code"
[ "$code" -ne 0 ] && tail -n 2 /tmp/old-up.txt | sed 's/^/    /'
printf '  만들어진 폴더(이름 주인:그룹(uid:gid) 권한): '
stat -c '%n %U:%G(%u:%g) %a' /tmp/old-install/sources 2>&1
show "$OLD" 'id -u; ls -A /sources; echo "(끝)"'

mkdir -p /tmp/old-long
cat > /tmp/old-long/compose.yml <<'EOF'
services:
  server:
    image: alpine:3.22
    user: "10001:10001"
    command: sleep 900
    volumes:
      - type: bind
        source: ${RAG_ENGINE_SOURCES_DIR:-./sources}
        target: /sources
        read_only: true
EOF
(cd /tmp/old-long && docker compose -p oldlong up -d >/tmp/old-long-up.txt 2>&1)
code=$?
echo "  긴 문법으로 적은 compose up 종료 코드: $code"
[ "$code" -ne 0 ] && tail -n 2 /tmp/old-long-up.txt | sed 's/^/    /'
printf '  긴 문법 뒤의 sources/: '
ls -d /tmp/old-long/sources 2>&1
