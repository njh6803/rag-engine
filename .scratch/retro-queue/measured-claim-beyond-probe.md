# measured-claim-beyond-probe: "쟀다"고 적은 명세 문장 일곱이 프로브 출력에 글자로 없는 사실을 담아 셀프 리뷰가 잡았다

**상태:** 열림
**어디로:** `.claude/skills/to-spec/SKILL.md` 3단계 측정 규칙에 한 줄(근거 문장을 쓰기 전에 그 프로브의 `*_out.txt`에서 그 값과 그 사실을 grep해 글자로 있을 때만 쟀다고 적고, 없으면 프로브를 고쳐 다시 돌리거나 어림으로 표기한다. `docs/agents/issue-tracker.md` 프로브와 근거 절의 "커밋한 프로브가 다시 내는 것에만 쓰고 그 파일을 가리킨다"가 이미 있는 지침이다)
**승인:** 자체 승인 2026-11-10, 1회차(이미 있는 지침을 어긴 사건이라 회차를 센다), 일지 2026-11-10-0118-core-spec.md, ADR 불필요

셀프 리뷰 표준 축 Major 4. 명세 101행(SQLAlchemy·pydantic 수용은 MRO와 `str()`만 봤다), 139행 셋(ZIP 한도 값이 출력에 없었다, 기본 파서 호출과 부딪혔다, "lxml 기본 한도"는 재지 않았다), 157행(5xx는 OpenAPI에 없다), 158행(`truncation_direction`의 enum을 찍지 않았다), 165행(전처리의 효과는 재지 않았다). 프로브 둘(TEI, Kiwi)을 고쳐 다시 돌리고 파서 한도 프로브에 패턴을 더해 값이 찍히게 했다. 계기 훅 `hook_probe_citing_doc`·`hook_measure_word`가 있어도 한 세션에 일곱이 났다.
