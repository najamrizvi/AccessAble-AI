from io import BytesIO

import pytest
from PIL import Image

from src.accessable_ai.image_validation import (
    MAX_IMAGE_BYTES,
    ImageValidationError,
    validate_and_normalize_image,
)


def make_image_bytes(
    image_format="PNG",
    size=(128, 128),
    mode="RGB",
):
    image = Image.new(mode, size, color="red")
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    image.close()
    return buffer.getvalue()


def test_valid_png_is_normalized_to_jpeg():
    result = validate_and_normalize_image(make_image_bytes())

    assert result.mime_type == "image/jpeg"
    assert result.width == 128
    assert result.height == 128
    assert result.image_bytes.startswith(b"\xff\xd8")


def test_transparency_is_preserved():
    image_bytes = make_image_bytes(mode="RGBA")

    result = validate_and_normalize_image(image_bytes)

    assert result.mime_type == "image/png"
    with Image.open(BytesIO(result.image_bytes)) as image:
        assert image.mode == "RGBA"


def test_empty_input_is_rejected():
    with pytest.raises(ImageValidationError, match="empty or invalid"):
        validate_and_normalize_image(b"")


def test_oversized_file_is_rejected_before_decoding():
    with pytest.raises(ImageValidationError, match="10 MB"):
        validate_and_normalize_image(b"x" * (MAX_IMAGE_BYTES + 1))


def test_unsupported_format_is_rejected():
    image_bytes = make_image_bytes(image_format="GIF")

    with pytest.raises(ImageValidationError, match="Unsupported image format"):
        validate_and_normalize_image(image_bytes)


def test_too_small_image_is_rejected():
    image_bytes = make_image_bytes(size=(63, 128))

    with pytest.raises(ImageValidationError, match="64"):
        validate_and_normalize_image(image_bytes)


def test_image_over_pixel_limit_is_rejected():
    image_bytes = make_image_bytes(size=(5001, 4000))

    with pytest.raises(ImageValidationError, match="20-megapixel"):
        validate_and_normalize_image(image_bytes)


def test_corrupt_image_is_rejected():
    with pytest.raises(ImageValidationError, match="invalid, damaged"):
        validate_and_normalize_image(b"not an image")



def test_exif_orientation_is_applied():
    image = Image.new("RGB", (128, 64), color="blue")
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise for display.
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    image.close()

    result = validate_and_normalize_image(buffer.getvalue())

    assert (result.width, result.height) == (64, 128)


def test_embedded_exif_metadata_is_removed():
    image = Image.new("RGB", (128, 128), color="green")
    exif = Image.Exif()
    exif[270] = "AccessAble AI metadata-removal test"
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    image.close()

    result = validate_and_normalize_image(buffer.getvalue())

    with Image.open(BytesIO(result.image_bytes)) as normalized:
        assert not normalized.getexif()
