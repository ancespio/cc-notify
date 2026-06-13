import hashlib
import io
import unittest

from PIL import Image

from agent_notify.icon_validation import (
    IconValidationError,
    validate_icon_bytes,
    validate_icon_url,
)


def png_bytes(size=(128, 128), color=(38, 49, 46, 255)):
    stream = io.BytesIO()
    Image.new("RGBA", size, color).save(stream, format="PNG")
    return stream.getvalue()


class FakeResponse:
    def __init__(self, body, content_type="image/png"):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, amount=-1):
        if amount < 0:
            return self.body
        body, self.body = self.body[:amount], self.body[amount:]
        return body


class IconValidationTests(unittest.TestCase):
    def test_valid_png_reports_format_size_and_sha256(self):
        body = png_bytes()

        result = validate_icon_bytes(body)

        self.assertEqual(result.format, "PNG")
        self.assertEqual(result.size, (128, 128))
        self.assertEqual(result.sha256, hashlib.sha256(body).hexdigest())

    def test_rejects_non_image_and_out_of_range_dimensions(self):
        with self.assertRaisesRegex(IconValidationError, "图片"):
            validate_icon_bytes(b"not an image")
        with self.assertRaisesRegex(IconValidationError, "尺寸"):
            validate_icon_bytes(png_bytes((32, 32)))

    def test_url_validation_limits_download_and_checks_expected_hash(self):
        body = png_bytes()

        result = validate_icon_url(
            "https://example.com/icon.png",
            opener=lambda *_args, **_kwargs: FakeResponse(body),
            expected_sha256=hashlib.sha256(body).hexdigest(),
        )

        self.assertEqual(result.byte_count, len(body))
        with self.assertRaisesRegex(IconValidationError, "不一致"):
            validate_icon_url(
                "https://example.com/icon.png",
                opener=lambda *_args, **_kwargs: FakeResponse(body),
                expected_sha256="0" * 64,
            )

    def test_url_validation_rejects_non_image_content_type_and_large_body(self):
        body = png_bytes()
        with self.assertRaisesRegex(IconValidationError, "Content-Type"):
            validate_icon_url(
                "https://example.com/icon.png",
                opener=lambda *_args, **_kwargs: FakeResponse(
                    body, "text/html"
                ),
            )
        with self.assertRaisesRegex(IconValidationError, "过大"):
            validate_icon_url(
                "https://example.com/icon.png",
                opener=lambda *_args, **_kwargs: FakeResponse(
                    body + b"x" * 64
                ),
                max_bytes=len(body),
            )


if __name__ == "__main__":
    unittest.main()
