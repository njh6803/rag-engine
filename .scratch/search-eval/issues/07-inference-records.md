# 07: 추론 기록: 모델이 계산한 결과를 저장해 다시 쓰고, 요청 지문으로 어댑터의 변경을 잡는다

**What to build:** 평가 도구의 조립이 `Embedder`와 `Reranker` 포트를 추론 기록 어댑터로 감싸, 기록에 있는 글은 TEI를 부르지 않고 기록의 값을 쓴다(스토리 16). 기록에 없는 글이 많으면 까닭과 다시 돌릴 명령을 알리며 실패한다(스토리 17). `index`와 `run`이 `--records read|write|off`를 받고, 기록 파일은 명령마다 주인이 하나다. 서버와 작업자의 조립은 기록을 쓰지 않는다(명세 "추론 기록").

**Blocked by:** 05 (전체 실행. 리랭크 기록의 주인이 전체 실행의 `run`이다)

**Status:** done

- [x] 감싸는 어댑터 둘: 감싼 포트를 부르기 전에 기록을 보고, 없으면 감싼 포트를 불러 결과를 쓴다. 토큰 세기(`count_tokens`, `special_token_count`, `token_spans`)는 기록하지 않고 그대로 넘긴다. 열쇠는 임베딩이 `sha256(모델 이름, NUL, 글의 UTF-8 바이트)`, 리랭크가 `sha256(모델 이름, NUL, 질의, NUL, 글)`이고 모델 이름은 `config.json`의 것이다. 모델 이름이 다르면 기록의 값을 쓰지 않는다.
- [x] 기록 파일(명세 "추론 기록"): `records/chunk-embeddings.keys`·`.f32`(주인 `index`), `records/query-embeddings.keys`·`.f32`(주인 `run`), `records/rerank.jsonl`(주인 전체 실행의 `run`), `records/records.json`(`format_version` `"1.0.0"`, 기록 파일마다 모델 이름, 차원, 수, 만든 TEI의 판과 장치, 요청 지문). 정렬해 쓰므로 같은 내용은 같은 바이트다. 쓰기는 02의 경로 판정을 거친다.
- [x] `--records read`(기본): 기록 파일을 고치지 않는다. 새로 계산한 임베딩이 100개를 넘으면 계산을 멈추고 종료 코드 1과, 어느 명령을 `--records write`로 다시 돌려 어느 파일을 커밋할지를 알린다. 리랭커의 끝점이 없는 전체 실행은 기록에 없는 쌍 하나에도 같은 방식으로 실패한다(05가 둔 끝점 필수를 이 티켓이 이 동작으로 바꾼다).
- [x] `--records write`: 그 명령이 주인인 파일만, 명령이 종료 코드 0으로 끝날 때만 이번 실행이 쓴 열쇠 전부로 다시 쓴다. 기록에 이미 있는 열쇠의 값은 옮기고 없는 글만 계산한다. 그 파일에 적힌 요청 지문이 지금 것과 다르거나 `records.json`에 적힌 그 파일의 TEI 판이 `config.json`의 `tei_version`과 다르면 옛 값을 옮기지 않고 다시 계산한다. `index --records write`는 문서가 하나도 없는 데이터베이스에서만 돌고, 문서가 든 데이터베이스에서는 아무것도 쓰지 않고 1과 데이터베이스를 새로 만들라는 안내를 낸다. 빠른 실행의 `run`은 `rerank.jsonl`을 건드리지 않는다.
- [x] `--records off`: 기록을 읽지도 쓰지도 않는다(설정 실험용).
- [x] 요청 지문(명세 "추론 기록"의 어댑터 변경 항목): TEI 어댑터가 추론 요청의 경로와, 본문에서 글·질의·모델 이름을 뺀 칸을 임베딩과 리랭크마다 한 자리에 두고 요청을 그것으로 짓는다. 지문은 경로와 그 칸을 정렬한 JSON의 sha256이다. 어댑터 시험(`tests/adapters/test_tei_embedder.py`, `test_tei_reranker.py`)이 실제로 보낸 요청의 경로와 칸이 그 자리의 값과 같은지 본다.
- [x] `validate`가 기록을 본다: `records.json`의 판, 기록의 합 20MB 이하, 요청 지문이 이 체크아웃의 어댑터가 내는 것과 같은지(다르면 다시 만들 기록 파일을 알린다), `records.json`의 TEI 판과 `compose.eval.yml`의 이미지 태그(장치 머리를 뗀 것)가 `config.json`의 `tei_version`과 같은지. 요청 지문은 끝점 없이 읽는다.
- [x] 보고서의 `records` 칸: 기록에서 읽은 수, 새로 계산한 수, 읽은 기록 파일마다의 sha256.
- [x] 시험(명세 "추론 기록의 시험"): 기록에 있는 글은 스텁을 부르지 않는다(스텁의 요청 횟수), `read`에서 상한을 넘으면 1과 안내가 나오고 기록 파일이 그대로다, 리랭커의 끝점 없는 전체 실행이 기록에 없는 쌍 하나에 실패한다, `write`가 주인 파일만 다시 쓰고 다른 파일은 바이트 그대로다(`index`와 빠른 실행의 `run` 뒤에 `rerank.jsonl`이 그대로다), `write`가 쓰이지 않은 열쇠를 지우고 같은 내용이면 같은 바이트를 쓴다, `index --records write`가 문서가 든 데이터베이스에서 기록 파일을 바이트 그대로 두고 1을 낸다, `index --records write`가 문서 목록과 해시가 다른 문서 파일이 있으면 스키마를 올리지 않고 기록 파일을 바이트 그대로 두며 1을 낸다, `off`가 기록을 읽지도 쓰지도 않는다, 모델 이름이 다르면 기록의 값을 쓰지 않는다, `validate`가 요청 지문이 다르면 실패하고 다시 만들 파일을 알린다, `write`가 요청 지문이 다른 파일의 옛 값을 옮기지 않는다(스텁의 요청 횟수), `tei_version`만 바꾼 뒤의 `write`가 그 파일의 옛 값을 옮기지 않는다(스텁의 요청 횟수가 그 실행이 쓴 열쇠의 수다), `write`로 돈 명령이 1로 끝나면 주인 파일이 바이트 그대로다, 보고서가 읽은 기록 파일의 해시를 싣는다, `records/`나 기록 파일이 묶음 밖을 가리키는 링크이면 `index`와 `run`이 쓰지 않고 1을 내며 링크가 가리킨 파일이 그대로다, `validate`가 TEI 판과 compose 태그가 다를 때와 20MB를 넘을 때 실패한다.
- [x] `compose.eval.yml`의 머리 주석에 TEI의 판을 올리는 PR은 기록을 다시 만든다는 것이 있는지 본다(03이 적었다).
- [x] 검사 넷이 초록이다.

## Comments

- 시험 순서를 솔직히 적는다. 앱 계층의 기록기 시험(`tests/adapters/test_inference_records.py`, `test_inference_record_files.py`)은 구현 전에 쓰고 빨강을 봤다. 표면 시험(`tests/tools/test_search_eval_records.py`, 30개)은 구현 전에 먼저 썼다(05에서 대기열에 오른 "표면 시험은 구현 전에" 항목을 지켰다).
- 결정: `--records off`의 보고서 `records` 칸은 `{read: 0, computed: 0, files: {}}`이다. off는 기록 계층을 거치지 않으므로 계산 수를 세지 않는다.
- `--tei-device cpu|gpu`는 `write`에서 필수다(없으면 종료 코드 2). 장치를 도구가 알아내는 길은 두지 않고 사람이 알려 준다(TEI `/info`로 알 수 있는지는 재 보지 않았다). 티켓 10과 14가 `records.json`의 `device`를 읽을 때 이 값이 들어 있다고 가정해도 된다.
- 구조: `adapters/inference_records.py`의 `EmbeddingRecorder`와 `RerankRecorder`가 감싸는 어댑터이고, `inference_record_files.py`가 파일 읽기와 쓰기(자료 파일을 먼저, `records.json`을 마지막에 임시 파일과 `os.replace`로)를 맡는다. 작업자는 기록을 모르고, `domain/ports.py`의 `EmbedderWrapper` 걸이만 열려 있다(`run_once_with_settings(settings, wrap_embedder_for)`).
- 상한을 넘으면 기록기가 `PermanentFailure(EMBEDDING_REJECTED)`를 올려 계산을 멈추고 `exceeded` 표지를 남긴다. 명령이 끝난 뒤 `notices()`가 까닭과 다시 돌릴 명령을 낸다. 기록은 종료 코드 0일 때만 커밋한다.
- `validate`의 compose 태그 검사는 기록 파일이 없는 묶음에도 적용된다(`compose.eval.yml`의 태그에서 장치 머리를 뗀 것을 `config.json`의 `tei_version`과 견준다).
- 변이 표: `.scratch/search-eval/probes/eval_records_mutations.toml`(26개. 전부 기대한 빨강과 표지로 나왔다).
- 셀프 리뷰(표준·명세 두 축, 기준 `a495e80`, 수정 17개와 미추적 7개)에서 Critical은 없었다. 고친 것: ① 기록 파일의 임시 파일(`<이름>.tmp`)이 묶음 밖 링크여도 그 링크로 쓰던 틈(`inference_record_files.py`의 `_target`이 임시 경로도 경로 판정에 건다). ② `write`가 종류가 여럿일 때 앞 종류를 쓴 뒤 뒤 종류의 경로에서 거부할 수 있던 순서(`RecordsRun`이 시작할 때 주인 파일 전부의 경로를 `check_writable`로 본다. 명령줄로는 묶음 검사가 먼저 링크를 거부해 닿지 않고, `RecordsRun`을 직접 부를 때만 드러난다). ③ 쓰다 끊겨 남은 `.tmp`가 20MB 합에 들던 것(`records_size`가 뺀다). ④ 모듈 독스트링 "읽고 쓰는 모든 경로는 경로 판정을 지난다"와 `eval_records_check.py`의 "다시 만들 기록 파일을 알린다"가 과장이던 것. ⑤ `compose.eval.yml`의 "요청 지문과 응답이 TEI의 판에 묶여 있다"(요청 지문에는 TEI의 판이 들지 않는다). ⑥ 재 보지 않은 "TEI `/info`에는 장치가 없다"를 사실처럼 적은 문장. ⑦ 05의 변이 표가 가리키던 옛 시험 이름. ⑧ `_reason` 중복. ⑨ `pytest.raises`에 까닭(`match`)을 더했다.
- 셀프 리뷰에서 남긴 것(Minor 이하): `index --records read`에서 새로 계산할 임베딩이 100개를 넘는 길은 시험이 없다(같은 기록기와 안내를 `run` 시험이 덮고, `index`는 101조각짜리 묶음이 필요하다). 리랭커 끝점 없음과 임베딩 상한 초과가 같은 `EMBEDDING_REJECTED` 코드를 쓴다(영구 실패 코드는 닫힌 목록이라 새 코드는 도메인 계약 변경이다). `RecordKind.RERANK` 분기가 여러 함수에 반복되는 것, 두 기록기의 조회 루프가 닮은 것. `.keys` 교체와 `.f32` 교체 사이에서 `os.replace`가 실패하면 열쇠 수가 같을 때 어긋난 채 읽힌다(`records.json`에 파일 해시를 두는 판 변경이 필요하다). `index`와 `run`을 같은 묶음에서 겹쳐 `write`로 돌리면 `records.json`의 항목이 서로를 덮을 수 있다(잠금을 두지 않았다. 기록은 사람이 한 명령씩 돌려 커밋하는 것으로 전제한다). 이 가운데 어긋난 기록(자료 파일은 썼는데 `records.json`을 못 쓴 상태)은 `validate`가 통과시키고 `read`·`write`가 형식 오류로 막는다.
- 08이 받을 것: `run` 보고서의 `records.files`에는 그 명령이 읽은 기록 파일의 해시만 있다. 조각 임베딩의 해시를 견주는 길은 08 본문에 적었다.
- PR 직전 리뷰(CodeRabbit CLI 0.7.5, `--committed --base origin/dev`, 지적 7건, Critical 없음)의 판정. 고친 것: 임시 파일 경로가 묶음 안의 다른 자리(최종 파일이나 문서 파일)로 풀리는 링크이면 그 자리에 쓰고 끝의 `unlink`가 지우던 것(`_target`이 임시 경로가 최종 경로 바로 옆의 `<이름>.tmp`가 아니면 거부한다. 시험과 변이 26). 남긴 것: 교체 중간의 실패로 파일 세트가 서로 다른 세대가 되는 것(위 `.keys`·`.f32` 항목과 같다), `run`이 기록을 읽기 전에 크기 상한을 보지 않는 것과 `records.json` 읽기에 상한이 없는 것(명세 `[정함]` 기록 파일 항목이 20MB를 `validate`의 몫으로 정했고, 둘 다 사람이 커밋한 묶음을 읽는 개발 도구의 길이다), `write`가 장치가 달라도 옛 값을 옮기고 `device`를 이번 값으로 적는 것(티켓 14에 적었다), `run --records read`가 요청 지문과 TEI 판의 불일치를 보지 않는 것(빠른 게이트가 `validate`를 먼저 돌려 막는 설계이고, 티켓 08에 적었다).
- 알려진 한계: 장치(cpu·gpu)는 사람이 준 값을 믿는다. 요청 지문은 어댑터의 요청 모양만 잡고, 같은 모양에서 TEI의 수치가 바뀌는 경우는 `tei_version` 견줌에 기댄다. 06·12와 `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`가 겹치므로 나중에 병합되는 쪽이 충돌을 푼다.
