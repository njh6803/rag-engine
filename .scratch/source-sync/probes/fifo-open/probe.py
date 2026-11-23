"""서버 경로 커넥터가 링크를 따르지 않는 열기로 파일을 열 때, 그 자리에 이름 있는 파이프(FIFO)가
있으면 여는 호출이 돌아오는지를 잰다(source-sync 명세 "서버 경로 커넥터와 원천 폴더"의 확인과 열기
항목, 2026-11-22 명세 검토가 낸 물음).

명세는 마지막에 연 파일이 보통 파일인지 그 연 파일로 확인한 뒤 읽게 정했다. 쓰는 쪽이 없는 FIFO는
읽기로 여는 호출 자체가 돌아오지 않을 수 있어, 그렇다면 확인에 닿기 전에 멈춘다. 연 폴더를 기준으로
그 아래 이름을 여는 열기(`dir_fd`)로 보는 것 넷.
A. FIFO를 `O_RDONLY | O_NOFOLLOW`로 연다. 다른 스레드에서 열고 3초 기다린다.
B. FIFO를 `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`으로 연다. 돌아오면 `fstat`로 종류를 본다.
C. 보통 파일을 `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`으로 열어 끝까지 읽는다. 읽은 바이트가 쓴 것과
   같은지 본다.
D. 심볼릭 링크를 `O_RDONLY | O_NOFOLLOW | O_NONBLOCK`으로 연다. 어떤 오류가 나는지 본다.
A에서 열기를 기다리던 스레드는 daemon이라 이 프로세스가 내려가는 것을 붙잡지 않는다. 끝에서 그
FIFO를 쓰기로 한 번 열어 그 스레드를 풀어 준다.

리눅스에서만 돈다(`O_NOFOLLOW`와 `dir_fd`의 열기가 개발 PC의 Windows에는 없다). 지어 둔 제품 작업자
이미지에서 돈다(Git Bash 에서는 `MSYS_NO_PATHCONV=1` 을 앞에 둔다. 커밋한 출력은
`rag-engine-test/rag-engine-worker:0.1.0-rc.1` 에서 받았다):
    docker run --rm --entrypoint python \
        -v "<저장소>/.scratch/source-sync/probes/fifo-open:/probe:ro" \
        <작업자 이미지> -I -X utf8 /probe/probe.py \
        > .scratch/source-sync/probes/fifo-open/probe_out_linux.txt
네트워크는 쓰지 않는다. 한 번에 5초쯤 걸린다.
"""

from __future__ import annotations

import os
import platform
import stat
import sys
import tempfile
import threading
import time

WAIT_SECONDS = 3.0
PAYLOAD = "규정집 본문".encode() * 1000


def emit(line: str) -> None:
    """한 줄을 UTF-8 과 LF 로 적는다."""
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "보통 파일"
    if stat.S_ISFIFO(mode):
        return "FIFO"
    return oct(stat.S_IFMT(mode))


def main() -> None:
    emit(f"Python {platform.python_version()} {sys.platform} {platform.release()}")
    with tempfile.TemporaryDirectory() as root:
        os.mkfifo(os.path.join(root, "pipe.pdf"))
        with open(os.path.join(root, "doc.pdf"), "wb") as handle:
            handle.write(PAYLOAD)
        os.symlink(os.path.join(root, "doc.pdf"), os.path.join(root, "link.pdf"))
        folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            measure(folder, root)
        finally:
            os.close(folder)


def measure(folder: int, root: str) -> None:
    opened: list[int] = []
    errors: list[str] = []

    def open_blocking() -> None:
        try:
            opened.append(os.open("pipe.pdf", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder))
        except OSError as error:
            errors.append(type(error).__name__)

    thread = threading.Thread(target=open_blocking, daemon=True)
    started = time.perf_counter()
    thread.start()
    thread.join(WAIT_SECONDS)
    waited = time.perf_counter() - started
    emit(
        f"A FIFO, O_RDONLY|O_NOFOLLOW: {waited:.2f}초 뒤 스레드 살아 있음={thread.is_alive()}, "
        f"연 것={len(opened)}, 오류={errors}"
    )

    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    started = time.perf_counter()
    descriptor = os.open("pipe.pdf", flags, dir_fd=folder)
    took = time.perf_counter() - started
    emit(
        f"B FIFO, O_RDONLY|O_NOFOLLOW|O_NONBLOCK: {took:.2f}초에 돌아옴, "
        f"fstat 종류={kind(os.fstat(descriptor).st_mode)}"
    )
    os.close(descriptor)

    descriptor = os.open("doc.pdf", flags, dir_fd=folder)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 65536):
        chunks.append(chunk)
    os.close(descriptor)
    emit(
        f"C 보통 파일, O_RDONLY|O_NOFOLLOW|O_NONBLOCK: 읽은 바이트 {len(b''.join(chunks))}, "
        f"쓴 것과 같음={b''.join(chunks) == PAYLOAD}"
    )

    try:
        os.open("link.pdf", flags, dir_fd=folder)
        emit("D 심볼릭 링크, O_RDONLY|O_NOFOLLOW|O_NONBLOCK: 열렸다")
    except OSError as error:
        emit(
            f"D 심볼릭 링크, O_RDONLY|O_NOFOLLOW|O_NONBLOCK: {type(error).__name__} "
            f"errno={error.errno}"
        )

    writer = os.open(os.path.join(root, "pipe.pdf"), os.O_WRONLY | os.O_NONBLOCK)
    thread.join(WAIT_SECONDS)
    os.close(writer)
    for descriptor in opened:
        os.close(descriptor)
    emit(f"끝: 쓰기로 연 뒤 A의 스레드 살아 있음={thread.is_alive()}")


main()
