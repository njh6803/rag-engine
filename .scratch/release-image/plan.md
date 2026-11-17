# release-image: 판마다 검색 서버와 수집 작업자의 이미지를 내고, 자기 PostgreSQL을 띄우는 단독 compose로 깨끗한 VM에 설치된다
**슬라이스:** 2
**Blocked by:** core
**설계:** ADR 0020. 일지 `docs/journal/2026-11-17-1716-release-image-design.md`

설계(ADR 0020, 2026-11-17)가 정한 것: 판 내기는 agent-os의 ADR 0056을 따른다. main이 움직일 때 CI가 제품 판을 내고, 정식 판 0.1.0 전에는 출시 후보(`0.1.0-rc.N`)만 난다. 이미지 둘은 Docker Hub의 `njh6803/rag-engine-server`와 `njh6803/rag-engine-worker`에 올린다. 단독 compose는 프록시(nginx)를 더해 443 하나만 밖으로 연다. 올릴 때 운영자가 손댈 것이 있는 변경은 PR 제목에 느낌표를 붙이고, 마이그레이션, 재색인이 필요한 변경, 계약의 앞자리를 올리는 변경은 언제나 그렇게 한다. 단독 compose를 띄우는 느린 시험은 agent-os와 같이 main으로 가는 PR과 main 푸시에서만 돈다. 워크플로와 도구는 agent-os의 것을 복사해 이 저장소의 값으로 고친다. 첫 정식 판은 release-0-1이 낸다. 사람 몫 가운데 Docker Hub 저장소 둘, 접근 토큰, GitHub 환경 `release`는 판 내기 워크플로를 처음 main에 싣는 출시 PR(차례대로면 이 기능의 출시 PR)을 병합하기 전에, squash 제목 설정은 PR 제목 검사를 옮기는 티켓을 병합하기 전에 끝나 있어야 한다(ADR 0020 Consequences "사람 몫"). 아래의 넘긴 것 문단들은 명세의 입력이다.

검색 서버와 수집 작업자의 이미지를 판 태그로 내고, 자기 PostgreSQL을 함께 띄우는 단독 compose와 설치 안내를 낸다. 관리자 페이지의 이미지와 서버 경로 원천의 볼륨은 admin과 source-sync가 이 행의 규칙으로 더한다. 단독 compose에서도 밖으로 여는 포트는 하나로 하고, MCP 경로, 수집 API, 관리 API(admin 뒤에는 관리자 페이지도)는 경로로 나눈다. 컨테이너는 root가 아닌 사용자로 돌고, 이미지마다 취약점 점검 결과(SBOM과 CVE 스캔)를 낸다. 폐쇄망 설치를 위해 이미지를 파일로 내보내는 방법(`docker save`)과, 임베딩 모델 파일을 함께 옮기는 절차를 안내에 적는다.

core 명세(`.scratch/core/spec.md`, 2026-11-10)가 넘긴 것: 서버와 작업자 이미지를 둘로 가르는 Dockerfile 변경(core는 킥오프의 Dockerfile 하나에서 `rag-engine worker` 명령이 돌게만 한다), 임베딩·리랭커 TEI 컨테이너 둘과 마이그레이션 서비스의 compose 항목(리랭커 TEI는 기본 설치에서 켜지 않고 켜는 설치가 compose 프로필로 더한다. 켜는 설치의 후보 수와 검색 시간 제한 안내도 설치 안내에 적는다. search-eval 티켓 17이 정했고 ADR 0010 이력 2026-11-17이 적는다. 기본 컨테이너는 그때 서버, 작업자, PostgreSQL, 임베딩 TEI 넷이었고, 이 기능의 설계가 프록시를 더해 다섯으로 정했다. ADR 0020), 모델 파일의 폐쇄망 반입, 메모리 예산(32GB 기준, 16GB 최소)의 문서화.

core 티켓 세션(2026-11-10)의 명세 검토가 넘긴 것: TEI 컨테이너 자체의 로그가 입력 글(질의, 문서 조각)을 남기는지 재고, 남기면 compose의 TEI 로그 설정으로 끈다(원칙 V. core는 우리 프로세스의 로그만 맡는다).

dev-branch(ADR 0016, 2026-11-12)가 넘긴 것: 단독 compose를 띄워 보는 시험처럼 느린 검사를 CI에 더하면, 그 잡을 main PR(출시 PR과 핫픽스 PR)과 main 푸시에서만 돌릴지 dev PR에서도 돌릴지 정한다. 지금은 main PR에만 도는 잡이 없어 dev PR과 main PR이 같은 잡을 돈다. 판을 어느 브랜치의 어느 사건에서 낼지도 이 기능이 정한다. 둘 다 ADR 0020이 정했다(느린 시험은 main으로 가는 PR과 main 푸시에서만 돌고, 제품 판은 main이 움직일 때 난다).

search-eval 설계(ADR 0019, 2026-11-12)가 넘긴 것: search-eval이 구현되면 운영 의존성에 Anthropic SDK(`anthropic`)와 전이 의존 셋(docstring-parser, jiter, sniffio)이 더해져 이미지에 실린다. 부품 목록(SBOM)과 CVE 스캔의 대상이 그만큼 는다. 평가를 부르는 입구는 admin이 열 때까지 이미지 안에 없다.

설계 세션(2026-11-17)이 넘긴 것: 설계 PR이 고칠 수 없던 파일의 낡은 문장을 이 기능의 티켓이 고친다. `Dockerfile` 1줄의 주석은 판 태그와 단독 compose를 "release-image 가 정한다"고 적으며 `tech.md`를 가리키는데, 그 칸은 이제 ADR 0020의 결정을 적는다. `next-session` `merge.md` "출시 PR"의 "이 저장소에서는 아직 출시 PR을 열어 본 적이 없어"는 출시 PR 32와 62가 병합된 뒤로 사실이 아니고, 병합 절차를 옮기는 티켓이 그 절을 고칠 때 함께 고친다. `docs/constitution/operations.md` 8줄의 "판 태그를 붙여 내는 것은 release-image다"는 운영 문서의 두 절을 옮기는 티켓이 판 내기 절을 가리키게 고치고, `.github/workflows/ci.yml` 82줄의 같은 주석도 워크플로를 옮기는 티켓이 함께 고친다. PR 직전 리뷰가 명세에 넘긴 물음 넷(제품 변경의 경로 목록에 `pyproject.toml`의 칸을 넣을지, 프록시가 서버에 넘기는 머리, 프록시의 접근 로그가 남기는 것, 프록시가 받는 TLS의 가장 낮은 판)은 ADR 0020 Consequences "명세가 재거나 정하는 것"에 더했다.

공개 시연(core, search-eval, release-image)의 한 축이다. 판을 고정한 이미지가 있어야 클라이언트가 실제 서버로 시험할 수 있다.

수락: 깨끗한 VM에서 단독 compose로 띄워 관리 명령으로 표본 문서를 넣은 뒤 MCP 클라이언트로 검색할 수 있고, 그 VM에서 밖으로 열린 포트가 하나다.
