# 이미지 둘을 한 번에 짓는 목록(release-image 티켓 01, .scratch/release-image/spec.md "이미지와 계정").
# 저장소 루트에서 부른다. context 와 dockerfile 은 부르는 자리(저장소 루트) 기준이다.
#
#   docker buildx bake -f deploy/images/docker-bake.hcl --set '*.args.APP_VERSION=...' ...
#   VERSION=0.1.0-rc.1 docker buildx bake -f deploy/images/docker-bake.hcl --load
#
# 두 대상(server, worker)은 같은 Dockerfile 의 두 단계를 짓고, 둘의 층은 모두 같다. 이미지마다의 빌드 인자는
# Dockerfile 머리 주석이 원천이다. CI 의 image 잡이 모든 PR 에서 이 파일로 짓고(APP_VERSION 은 저장소의 0.0.0
# 과 다른 0.0.1-rc.1), 릴리스 워크플로(release-image 08)가 같은 파일을 변수만 바꿔 부른다.
#
# 이름은 둘이다. 짓기 대상 이름(server, worker)은 코드의 이름이고 Dockerfile 단계와 compose 서비스가 따른다.
# Docker Hub 저장소 이름(rag-engine-server, rag-engine-worker)은 아래 tags 의 <이름공간>/<저장소>:<태그> 가 정한다.

# 이미지 이름공간. 시험 짓기는 시험용 이름, 올리는 짓기는 Docker Hub 계정 이름이다.
variable "NAMESPACE" {
  default = "rag-engine-release-test"
}

# 태그. 첫 짓기는 릴리스 번호, 올리는 짓기는 `sha-<커밋 해시 40자>`다.
variable "TAG" {
  default = "unknown"
}

# 릴리스 번호(`v` 없음). 이미지 안의 번호와 OCI 라벨에 들어간다. 비어 있으면 Dockerfile 이 짓기를 실패시킨다.
variable "VERSION" {
  default = ""
}

variable "REVISION" {
  default = "unknown"
}

variable "SOURCE" {
  default = "unknown"
}

group "default" {
  targets = ["server", "worker"]
}

target "_common" {
  context    = "."
  dockerfile = "deploy/images/Dockerfile"
  args = {
    APP_VERSION = VERSION
    REVISION    = REVISION
    SOURCE      = SOURCE
  }
}

target "server" {
  inherits = ["_common"]
  target   = "server"
  tags     = ["${NAMESPACE}/rag-engine-server:${TAG}"]
}

target "worker" {
  inherits = ["_common"]
  target   = "worker"
  tags     = ["${NAMESPACE}/rag-engine-worker:${TAG}"]
}
