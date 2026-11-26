---
status: accepted
date: 2026-11-26
---

# 원칙 II(타입 우회 금지)는 TypeScript에도 걸리고, 그 판정은 typescript-eslint가 한다

헌법 원칙 II는 파이썬의 타입 우회 넷(`Any`, `cast`, `type: ignore`, `pyright: ignore`)을 금지하고 판정자를 `tools/check_type_escapes.py` 하나로 적는다. 관리자 페이지를 웹 워크스페이스로 짓기로 하면서(ADR 0026) 이 저장소에 TypeScript 코드가 들어온다. TypeScript의 기본 엄격 검사는 `any`와 타입 단언을 막지 않아, 서버 계약에서 만든 타입을 `as` 하나로 덮어도 검사가 지나간다. agent-os는 같은 원칙(그 저장소의 원칙 III)을 TypeScript로 넓혔고(그 저장소의 ADR 0020 `docs/adr/0020-principle-iii-covers-typescript.md`), 설계 인터뷰(일지 `docs/journal/2026-11-26-1534-admin-design.md`)에서 사용자가 "원칙 II를 TypeScript까지 넓힌다"를 골랐다. 그래서 **원칙 II는 TypeScript 코드에도 걸린다.** 금지하는 것과 판정자는 agent-os ADR 0020과 같다.

- **금지하는 것.** `any`, 타입 단언(`as`와 꺾쇠 꼴. `as const`는 된다), 값이 있다고 우기는 `!`, `@ts-ignore`, `@ts-nocheck`다. `@ts-expect-error`는 타입을 시험하는 파일(`*.test-d.ts`)에서만, 까닭을 적은 설명과 함께 쓴다. 시험 코드도 대상이다.
- **판정자.** 린터 typescript-eslint의 규칙이 판정하고, 타입 정보를 읽어 판정하는 규칙(`no-unsafe-*`. `any`가 다른 값으로 번지는 자리를 잡는다)까지 켠다. 줄마다 규칙을 끄는 주석은 ESLint 설정(`linterOptions.noInlineConfig`)으로 막는다. `tsconfig`의 `strict`를 끄는 것도 우회로 보고 검사한다. 만든 코드(서버 계약에서 만든 API 코드)와 타입 선언 파일(`.d.ts`)도 판정 범위이고, git이 추적하지 않는 빌드 산출물만 뺀다(그 ADR의 이력 2026-09-30). agent-os에서는 openapi-typescript가 만든 코드의 한 자리(재귀하는 `Json` 타입)에 `any`가 남아, 만드는 스크립트가 그 자리를 `unknown`으로 바꿔 만든 코드의 우회를 0으로 맞췄다고 그 ADR이 적는다. 이 저장소의 계약 파일에서도 그런 자리가 나는지는 web 뼈대를 짓는 티켓이 본다.
- **헌법을 고치는 때.** 원칙의 문장이 바뀌므로 원칙 변경이고, 헌법 버전은 앞자리가 올라 2.0.0이 된다. 문장을 고치고 버전을 올리는 일은 판정하는 린터가 서는 web 뼈대 티켓이 한다. 그 티켓이 첫 TypeScript 코드, 린터 설정, 원칙 II의 새 문장을 같은 PR에 싣는다. 이 ADR이 그 개정의 근거이고, 사용자의 승인은 이 ADR의 승인이다. 지금 고치지 않는 까닭은 둘이다. 판정자가 서기 전에 원칙에 적으면 판정자 없는 금지가 헌법에 남고, 설계 PR은 `docs/constitution/principles.md`를 바꿀 수 없다(커밋 검사가 면제하는 파일이 아니다). 그때까지 이 저장소에 TypeScript 코드는 없으므로 원칙이 걸리지 않는 틈은 생기지 않는다.

## Considered Options

- **헌법은 그대로 두고 린트 설정에만 둔다.** 린터가 같은 것을 똑같이 막지만 헌법 원칙이 아니어서, 그 설정을 느슨하게 고치는 일이 ADR과 승인이 필요한 개정이 아니라 보통 변경이 된다. 고르지 않았다.
- **TypeScript의 기본 엄격 검사만 켠다.** 새 규칙을 두지 않는다. `any`와 `as`가 막히지 않는다. 고르지 않았다.

## Consequences

- **헌법.** web 뼈대 티켓이 `docs/constitution/principles.md`의 원칙 II를 고치고 헌법 버전을 2.0.0으로 올린다. 판정자를 "하나"라고 적은 문장도 그때 파이썬과 TypeScript의 판정자 둘로 바뀐다. `CLAUDE.md`가 그 파일을 임포트하므로 고친 문장은 그날부터 모든 세션에 실린다. 그 사이에 다른 변경이 헌법 버전을 먼저 올리면 번호는 그때의 가장 높은 버전에서 앞자리를 올려 정한다.
- **화면 코드.** 서버가 준 값의 타입은 만든 API 코드의 타입대로 좁혀 써야 하고, 단언으로 덮을 수 없다. 바깥 라이브러리의 타입이 맞지 않을 때 쓰던 지름길(`as`, `!`)도 없어, 그런 자리는 값을 검사하는 코드로 푼다.
- **TypeScript의 버전.** typescript-eslint가 받는 TypeScript의 범위 안에서만 올릴 수 있다(ADR 0026 Consequences).
- **원칙 III.** agent-os를 드는 것은 하네스의 원천으로서다(ADR 0016).
