# standalone-models-symlink-note: Windows 개발 PC에서 단독 compose 시험이 모델 폴더의 심볼릭 링크 때문에 마당에서 25개 오류로 끝났다

**상태:** 열림
**어디로:** `tests/standalone/test_standalone_compose.py`의 머리 독스트링(`RAG_STANDALONE_MODELS` 설명에 한 문장)이나 모델 폴더를 복사하는 마당(링크를 따라가 복사하게 하거나 링크가 있을 때 까닭을 밝히며 실패하게 한다)
**승인:** 자체 승인 2026-11-20, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-20-1455-release-image-04-install-guide-walks-operator.md, ADR 불필요

release-image 04에서 `deploy/`를 고친 뒤 단독 compose 시험을 개발 PC(Windows, Docker Desktop)에서 모델이 든 폴더를 그대로 넘겨 돌렸더니 마당(fixture)이 `WinError 3`으로 `25 errors in 46.81s`를 냈다. 모델 폴더는 Hugging Face 캐시 모양이라 심볼릭 링크가 들어 있고, 링크를 푼 복사본(`cp -rL`)으로 다시 돌리자 `25 passed in 206.86s`였다. 03이 같은 처치를 한 것과 맞아 링크가 원인이라고 본다(링크 하나하나를 짚어 확인하지는 않았다). 이 처치는 03의 티켓 Comments와 03 일지의 "확인한 것"에 적혀 있었지만 시험 파일의 독스트링에는 없고, 04로 넘긴 일지의 "다음"에도 없었다. 처음 돌리는 세션은 실패를 보고서야 알게 된다.
