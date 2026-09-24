"""Photos: read an image file once and hand the same bytes to every format.

The file is embedded exactly as it is. Nothing is decoded, scaled or
re-encoded: every JPEG round trip costs sharpness, and the owner of the
photo has usually picked its size and quality deliberately. Chrome passes
an unmodified JPEG straight into the PDF, and the DOCX stores it as a
media part, so the recipient gets the original pixels in both formats.
Only the pixel size is read from the header, because the DOCX has to state
the picture's extent.
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass
from pathlib import Path

from .config import PHOTO_TYPES, ConfigError


@dataclass(frozen=True)
class Photo:
    data: bytes
    mime: str
    width: int
    height: int

    @property
    def extension(self) -> str:
        return "png" if self.mime == "image/png" else "jpeg"

    @property
    def ratio(self) -> float:
        """Height divided by width."""
        return self.height / self.width

    def data_uri(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode('ascii')}"


#: JPEG start-of-frame markers that carry the image size (all SOFn except
#: DHT 0xC4, JPG 0xC8 and DAC 0xCC).
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            pos += 1 if marker == 0xFF else 2
            continue
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        if marker in _SOF and pos + 9 <= len(data):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height
        pos += 2 + length
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def load_photo(path: Path) -> Photo:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ConfigError(f"photo: cannot read {path}: {exc}") from None
    mime = PHOTO_TYPES.get(Path(path).suffix.lower())
    size = _png_size(data) if mime == "image/png" else _jpeg_size(data)
    if mime is None or size is None or 0 in size:
        raise ConfigError(f"photo: {path} is not a readable JPEG or PNG file")
    return Photo(data, mime, *size)
