"""시험이 만드는 ZIP 픽스처. 압축 폭탄과 암호 항목은 저장소에 두지 않고 시험이 만든다(티켓 08)."""

import io
import zipfile
from collections.abc import Mapping


def zip_bytes(entries: Mapping[str, bytes], *, encrypted: tuple[str, ...] = ()) -> bytes:
    """항목마다 deflate로 압축한 ZIP. `encrypted`에 든 항목은 중앙 디렉터리에 암호 표지를 켠다."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        for info in archive.filelist:
            if info.filename in encrypted:
                info.flag_bits |= 0x1
    return buffer.getvalue()
