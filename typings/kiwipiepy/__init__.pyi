"""kiwipiepy 0.24의 우리 쪽 타입 스텁(ADR 0006).

배포판에 py.typed가 없어 pyright strict가 import를 거부한다. 이 저장소가 부르는 것만 적는다. 문자열
하나를 주면 `list[Token]`과 `list[Sentence]`가 돌아온다(배포판 주석의 반환형은 문자열 목록을 줄
때와의 합집합이라 쓸 수 없다). 매개변수는 우리가 넘기는 것만 열어 둔다. kiwipiepy를 올릴 때 이
모양이 아직 맞는지는 `tests/adapters/test_kiwi.py`가 실제 Kiwi를 불러 확인한다.
"""

class Token:
    @property
    def form(self) -> str: ...
    @property
    def tag(self) -> str: ...
    @property
    def start(self) -> int: ...
    @property
    def len(self) -> int: ...

class Sentence:
    text: str
    start: int
    end: int

class Kiwi:
    def __init__(self) -> None: ...
    def tokenize(self, text: str, *, normalize_coda: bool = False) -> list[Token]: ...
    def split_into_sents(self, text: str) -> list[Sentence]: ...
