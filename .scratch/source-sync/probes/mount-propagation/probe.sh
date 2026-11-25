#!/usr/bin/env bash
# 컨테이너가 뜬 뒤에 서버 기계에서 붙인 공유 폴더가 컨테이너에 보이는지를 잰다(ADR 0021 "서버 경로
# 원천의 폴더"가 명세에 넘긴 물음, source-sync 명세).
#
# ADR 0021 은 서버 기계의 부모 폴더 하나를 서버와 작업자 컨테이너의 `/sources` 에 읽기 전용으로 붙이게
# 했고, 그 아래에 나중에 붙인 공유 폴더가 Docker 의 기본 전파 설정(`rprivate`)에서는 보이지 않을
# 것이라고 어림했다. 보는 것은 다음과 같다.
# 0. 서버 기계의 루트가 shared 가 아닐 때 `rslave` 로 붙이면 컨테이너가 뜨는지.
# 1~2. 컨테이너가 뜬 뒤에 붙인 하위 폴더가 기본 설정, `rslave`(`docker run`), `rslave`(compose 의 긴
#      문법)에서 보이는지.
# 3. 읽기 전용으로 붙였을 때 처음부터 있던 폴더와 나중에 전해진 폴더에 쓰기가 되는지.
# 4. 붙인 뒤에 새로 띄운 컨테이너는 기본 설정으로도 보는지(설치 안내의 "다시 띄운다"). 붙이기 전에
#    뜬 컨테이너를 지우지 않고 `docker restart` 로 다시 띄워도 보는지.
# 5~6. 서버 기계에서 떼어 냈다가 다시 붙였을 때 컨테이너가 따라가는지, 따라가지 못한 컨테이너를
#      `docker restart` 로 다시 띄우면 새 내용을 보는지.
# 7. 하위 폴더가 아니라 부모 폴더 자체가 나중에 붙은 경우.
# 8. Docker Desktop(이 개발 기계)에서 `rslave` 를 적으면 오류가 나는지.
# 9. 단독 compose 가 붙일 모양(짧은 문법, `.env` 의 변수, 서비스 둘, uid 10001)에서 설치 안내가 적을
#    명령 `docker compose restart server worker` 로 다시 띄워도 4 와 6 처럼 보이는지.
# 10. 설치 폴더에 `sources/` 가 없고 변수도 적지 않았을 때 컨테이너가 뜨는지와 만들어진 폴더의 주인.
#
# 0~7 과 9~10 은 리눅스 dockerd 가 필요해 특권 Docker-in-Docker 컨테이너 안에서 돈다(0~7 은
# `inner.sh`, 9~10 은 `inner_compose.sh`). 그 컨테이너의 커널은 Docker Desktop 의 WSL2 커널이라 배포판
# 리눅스 서버의 커널과 버전이 다르다.
#
# 실행(저장소 루트에서, Git Bash. Docker Desktop 이 켜져 있어야 한다):
#     bash .scratch/source-sync/probes/mount-propagation/probe.sh \
#         > .scratch/source-sync/probes/mount-propagation/probe_out.txt 2>&1
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
DIND=rag-probe-dind
DIND_IMAGE=docker:29.9.2-dind
export MSYS_NO_PATHCONV=1

echo "== 바깥 Docker"
docker version --format '  server {{.Server.Version}} {{.Server.Os}} / kernel {{.Server.KernelVersion}}'
docker info --format '  {{.OperatingSystem}}'

docker rm -f "$DIND" >/dev/null 2>&1
docker run -d --privileged --name "$DIND" -e DOCKER_TLS_CERTDIR= "$DIND_IMAGE" >/dev/null
ready=no
for _ in $(seq 1 60); do
    if docker exec "$DIND" docker info >/dev/null 2>&1; then
        ready=yes
        break
    fi
    sleep 1
done
echo "  안쪽 dockerd 준비: $ready($DIND_IMAGE)"
docker save alpine:3.22 | docker exec -i "$DIND" docker load >/dev/null
docker exec -i "$DIND" sh -s < "$HERE/inner.sh"

echo "== 8. Docker Desktop 에서 rslave"
WORK="$(mktemp -d)"
mkdir -p "$WORK/rules"
echo local > "$WORK/rules/a.txt"
HOST_PATH="$(cygpath -w "$WORK" 2>/dev/null || echo "$WORK")"
# compose 파일의 경로도 Windows 꼴로 넘긴다. 경로 변환을 꺼 두어(MSYS_NO_PATHCONV) `/tmp/...` 를
# 그대로 넘기면 Windows 의 docker 가 `C:\tmp\...` 로 읽는다.
COMPOSE_FILE="$(cygpath -w "$WORK/compose.yml" 2>/dev/null || echo "$WORK/compose.yml")"
echo "  기본 설정으로 붙이기:"
docker run --rm -v "$HOST_PATH:/sources:ro" alpine:3.22 ls /sources 2>&1 | sed 's/^/    /'
echo "    종료 코드: ${PIPESTATUS[0]}"
echo "  rslave 로 붙이기(docker run):"
docker run --rm -v "$HOST_PATH:/sources:ro,rslave" alpine:3.22 ls /sources 2>&1 | sed 's/^/    /'
echo "    종료 코드: ${PIPESTATUS[0]}"
cat > "$WORK/compose.yml" <<EOF
services:
  c_rslave:
    image: alpine:3.22
    command: ls /sources
    volumes:
      - type: bind
        source: ${HOST_PATH//\\/\/}
        target: /sources
        read_only: true
        bind:
          propagation: \${PROBE_PROPAGATION:-rprivate}
EOF
echo "  compose 의 긴 문법, 전파 설정을 변수로 두고 적지 않았을 때(rprivate):"
docker compose -f "$COMPOSE_FILE" -p rag-probe-dd run --rm c_rslave 2>&1 | sed 's/^/    /'
echo "    종료 코드: ${PIPESTATUS[0]}"
echo "  compose 의 긴 문법, 변수에 rslave 를 적었을 때:"
PROBE_PROPAGATION=rslave docker compose -f "$COMPOSE_FILE" -p rag-probe-dd run --rm c_rslave 2>&1 \
    | sed 's/^/    /'
echo "    종료 코드: ${PIPESTATUS[0]}"
docker compose -f "$COMPOSE_FILE" -p rag-probe-dd down >/dev/null 2>&1
rm -rf "$WORK"

docker exec -i "$DIND" sh -s < "$HERE/inner_compose.sh"
docker rm -f "$DIND" >/dev/null 2>&1
