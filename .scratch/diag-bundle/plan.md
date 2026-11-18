# diag-bundle: 진단 묶음 명령. 판, 색인 상태, 원천의 동기화 기록, 검색 지연을 비밀 없이 한 파일로 묶는다
**슬라이스:** 2
**Blocked by:** source-sync

판, 색인 상태(문서 수, 조각 수), 원천마다의 마지막 동기화와 실패, 최근 검색 지연을 한 파일로 묶는다. 원본 문서의 내용, 연결 정보, 비밀 값은 싣지 않는다.

release-image 명세(`.scratch/release-image/spec.md`, 2026-11-18)가 넘긴 것: 진단 묶음에 싣는 번호는 `rag-engine --version`의 출력이다. 첫 줄이 릴리스 번호이고 이어서 계약마다 판을 한 줄씩 찍으며, 필수 설정 없이 돈다. 이미지의 OCI 라벨 가운데 `org.opencontainers.image.version`은 `--version`의 첫 줄과 같은 릴리스 번호를, `org.opencontainers.image.revision`은 그 이미지를 지은 커밋을 알린다. 수락의 "임베딩 모델 파일 없음"은 단독 compose에서 `models/embedding/`이 비었는데 바깥으로 나가는 길이 없는 경우와, 그 폴더를 uid 10001이 쓸 수 없는 경우다. uid 10001이 가진 빈 폴더는 바깥 길이 있으면 첫 시작이 모델을 내려받아 뜨므로 이 경우가 아니다. 그때 임베딩 서버는 첫 시작에서 모델을 내려받으려 하다 `Permission denied`나 이름 풀기 실패로 멈춘다(release-image 프로브 `standalone/run_download_out.txt`, `standalone/run_out.txt`의 `offline` 줄).

수락: 일부러 깨뜨린 설치(데이터베이스 꺼짐, 색인 없음, 임베딩 모델 파일 없음, 원천 폴더 없음)에서 묶음만 보고 원인을 가를 수 있다.
