# release-image: 판마다 검색 서버와 수집 작업자의 이미지를 내고, 자기 PostgreSQL을 띄우는 단독 compose로 깨끗한 VM에 설치된다
**슬라이스:** 2
**Blocked by:** core

검색 서버와 수집 작업자의 이미지를 판 태그로 내고, 자기 PostgreSQL을 함께 띄우는 단독 compose와 설치 안내를 낸다. 관리자 페이지의 이미지와 서버 경로 원천의 볼륨은 admin과 source-sync가 이 행의 규칙으로 더한다. 단독 compose에서도 밖으로 여는 포트는 하나로 하고, MCP 경로, 수집 API, 관리 API(admin 뒤에는 관리자 페이지도)는 경로로 나눈다. 컨테이너는 root가 아닌 사용자로 돌고, 이미지마다 취약점 점검 결과(SBOM과 CVE 스캔)를 낸다. 폐쇄망 설치를 위해 이미지를 파일로 내보내는 방법(`docker save`)과, 임베딩 모델 파일을 함께 옮기는 절차를 안내에 적는다.

공개 시연(core, search-eval, release-image)의 한 축이다. 판을 고정한 이미지가 있어야 클라이언트가 실제 서버로 시험할 수 있다.

수락: 깨끗한 VM에서 단독 compose로 띄워 관리 명령으로 표본 문서를 넣은 뒤 MCP 클라이언트로 검색할 수 있고, 그 VM에서 밖으로 열린 포트가 하나다.
