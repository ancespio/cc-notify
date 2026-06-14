"""Safe validation for Bark notification icon images."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError


ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class IconValidationError(ValueError):
    """Raised when a remote notification icon is unusable."""


@dataclass(frozen=True)
class IconValidationResult:
    format: str
    size: tuple[int, int]
    sha256: str
    byte_count: int
    data: bytes


def validate_icon_bytes(
    data: bytes,
    *,
    min_dimension: int = 64,
    max_dimension: int = 4096,
) -> IconValidationResult:
    if not data:
        raise IconValidationError("图片内容为空。")
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = str(image.format or "").upper()
            size = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise IconValidationError("下载内容不是可解码的图片。") from exc
    if image_format not in ALLOWED_FORMATS:
        raise IconValidationError(
            "图标仅支持 PNG、JPEG 或 WebP 格式。"
        )
    if (
        min(size) < min_dimension
        or max(size) > max_dimension
    ):
        raise IconValidationError(
            f"图标尺寸应在 {min_dimension} 到 {max_dimension} 像素之间。"
        )
    return IconValidationResult(
        format=image_format,
        size=size,
        sha256=hashlib.sha256(data).hexdigest(),
        byte_count=len(data),
        data=data,
    )


def validate_icon_url(
    url: str,
    *,
    timeout: float = 8,
    max_bytes: int = 2 * 1024 * 1024,
    expected_sha256: str | None = None,
    opener=urlopen,
) -> IconValidationResult:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IconValidationError("图标 URL 必须是有效的 HTTP 或 HTTPS 地址。")
    request = Request(
        url.strip(),
        headers={"User-Agent": "Agents-Notify/1.0.1"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            content_type = str(
                response.headers.get("Content-Type", "")
            ).split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/"):
                raise IconValidationError(
                    "图标响应的 Content-Type 不是图片。"
                )
            data = response.read(max_bytes + 1)
    except IconValidationError:
        raise
    except Exception as exc:
        raise IconValidationError(f"下载图标失败：{exc}") from exc
    if len(data) > max_bytes:
        raise IconValidationError(
            f"图标文件过大，不能超过 {max_bytes // 1024} KB。"
        )
    result = validate_icon_bytes(data)
    if (
        expected_sha256
        and result.sha256.casefold() != expected_sha256.casefold()
    ):
        raise IconValidationError(
            "远程默认图标与本地 Agents-Notify 图标不一致。"
        )
    return result
