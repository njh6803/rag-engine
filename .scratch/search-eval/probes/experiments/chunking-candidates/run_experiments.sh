#!/usr/bin/env bash
# 설정 실험(search-eval 16)을 차례로 돈다. 저장소 루트에서 부른다.
#   bash .scratch/search-eval/probes/experiments/chunking-candidates/run_experiments.sh <작업 폴더> [구성 이름 ...]
# 작업 폴더에는 데이터베이스마다의 원본 파일 폴더(`data/rag_eval_<이름>`. 후보 수만 다른 구성은 c512-64 의 것을 함께 쓴다)와
# 로그(`logs/`)를 둔다(저장소 밖에 둔다. 커밋하지 않는다).
# 구성 이름을 주지 않으면 여섯을 모두 돈다. 보고서는 `reports/<이름>/`에, 단계마다의 시작·끝·걸린 시간은
# `timings.tsv`에 쌓인다(둘 다 이 스크립트가 있는 폴더 아래).
#
# 환경 변수(없으면 아래 기본값):
#   RAG_EVAL_EMBEDDING_URL  임베딩 TEI 끝점. 기본 http://127.0.0.1:18093 (turing-1.9.4 GPU 이미지)
#   EXP_PG_CONTAINER        compose-postgres.yml 이 띄운 PostgreSQL 컨테이너 이름. 기본 rag-engine-eval-exp16-postgres-1
#   EXP_PG_PORT             그 컨테이너의 호스트 포트. 기본 55463
#   EXP_TEI_DEVICE          timings.tsv 에 적는 장치 이름. 기본 gpu
#
# 실험은 묶음의 config.json 을 고치지 않고 `--config` 로 구성 파일을 주며, 추론 기록은 쓰지도 읽지도 않는다(`--records off`).
# 조각 크기가 다른 구성(c256-32, c512-64, c512-128, c1024-128)은 데이터베이스를 새로 만들어 색인하고, 후보 수만
# 다른 구성(c512-64-k20, c512-64-k100)은 c512-64 의 데이터베이스에서 `run` 만 다시 돈다.
set -u

WORK="${1:?작업 폴더를 준다}"
shift
EXP_DIR=".scratch/search-eval/probes/experiments/chunking-candidates"
BUNDLE="evals/public-docs"
EMBED_URL="${RAG_EVAL_EMBEDDING_URL:-http://127.0.0.1:18093}"
PG_CONTAINER="${EXP_PG_CONTAINER:-rag-engine-eval-exp16-postgres-1}"
PG_PORT="${EXP_PG_PORT:-55463}"
DEVICE="${EXP_TEI_DEVICE:-gpu}"
TIMINGS="$EXP_DIR/timings.tsv"

mkdir -p "$WORK/logs" "$WORK/data" "$EXP_DIR/reports"
[ -f "$TIMINGS" ] || printf 'name\tstep\tstart\tend\tseconds\texit\tdevice\n' > "$TIMINGS"

# 이름 -> 조각 크기가 같은 데이터베이스의 이름(구성 파일이 가리키는 색인 쪽)
db_for() {
  case "$1" in
    c512-64-k20|c512-64-k100) echo "rag_eval_c512_64" ;;
    *) echo "rag_eval_$(echo "$1" | tr '-' '_')" ;;
  esac
}

timed() { # timed <이름> <단계> <명령...>
  local name="$1" step="$2"; shift 2
  local s e rc
  s=$(date +%s); local si; si=$(date -Iseconds)
  "$@" > "$WORK/logs/$name.$step.log" 2>&1
  rc=$?
  e=$(date +%s)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$step" "$si" "$(date -Iseconds)" "$((e - s))" "$rc" "$DEVICE" >> "$TIMINGS"
  return $rc
}

run_config() {
  local name="$1" db; db=$(db_for "$name")
  local cfg="$EXP_DIR/configs/$name.json"
  local url="postgresql://rag_eval:rag_eval@127.0.0.1:$PG_PORT/$db"
  local data="$WORK/data/$db"
  export RAG_EVAL_DATABASE_URL="$url" RAG_EVAL_DATA_DIR="$data" RAG_EVAL_EMBEDDING_URL="$EMBED_URL"
  mkdir -p "$data"

  case "$name" in
    c512-64-k20|c512-64-k100) ;; # c512-64 의 색인을 그대로 쓴다
    *)
      docker exec "$PG_CONTAINER" psql -U rag_eval -d rag_eval -c "CREATE DATABASE $db" > "$WORK/logs/$name.createdb.log" 2>&1 || {
        echo "[$name] 데이터베이스를 만들지 못했다(이미 있으면 지우고 다시 시작한다)"; return 1; }
      timed "$name" index uv run python tools/search_eval.py index "$BUNDLE" --config "$cfg" --records off || {
        echo "[$name] index 실패"; return 1; }
      ;;
  esac

  mkdir -p "$EXP_DIR/reports/$name"
  timed "$name" run uv run python tools/search_eval.py run "$BUNDLE" --through fused --records off \
    --config "$cfg" --out "$EXP_DIR/reports/$name" || { echo "[$name] run 실패"; return 1; }
  echo "[$name] 끝"
}

NAMES=("$@")
if [ ${#NAMES[@]} -eq 0 ]; then
  NAMES=(c512-64 c512-64-k20 c512-64-k100 c256-32 c512-128 c1024-128)
fi
for n in "${NAMES[@]}"; do
  run_config "$n"
done
