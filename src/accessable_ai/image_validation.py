from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MIN_IMAGE_DIMENSION = 64

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    """Raised when an uploaded image fails validation."""


@dataclass(frozen=True)
class ValidatedImage:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int


def validate_and_normalize_image(image_bytes: bytes) -> ValidatedImage:
    """Validate image bytes, apply orientation, and re-encode without metadata."""
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ImageValidationError("The uploaded file is empty or invalid.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageValidationError("The image exceeds the 10 MB upload limit.")

    try:
        # Verify the encoded file and inspect its actual format and dimensions.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(image_bytes)) as probe:
                image_format = probe.format
                width, height = probe.size

                if image_format not in SUPPORTED_FORMATS:
                    raise ImageValidationError(
                        "Unsupported image format. Upload a JPEG, PNG, or WebP."
                    )

                if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                    raise ImageValidationError(
                        "The image must be at least 64 × 64 pixels."
                    )

                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageValidationError(
                        "The image exceeds the 20-megapixel limit."
                    )

                probe.verify()

            # Reopen after verify(), then fully decode the image.
            with Image.open(BytesIO(image_bytes)) as source:
                has_transparency = (
                    "A" in source.getbands()
                    or "transparency" in source.info
                )

                source.load()
                oriented = ImageOps.exif_transpose(source)
                normalized = oriented.convert(
                    "RGBA" if has_transparency else "RGB"
                )

                output = BytesIO()

                if has_transparency:
                    normalized.save(output, format="PNG", optimize=True)
                    mime_type = "image/png"
                else:
                    normalized.save(
                        output,
                        format="JPEG",
                        quality=90,
                        optimize=True,
                    )
                    mime_type = "image/jpeg"

                result = output.getvalue()
                result_width, result_height = normalized.size

                normalized.close()
                if oriented is not source:
                    oriented.close()

        return ValidatedImage(
            image_bytes=result,
            mime_type=mime_type,
            width=result_width,
            height=result_height,
        )

    except ImageValidationError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        ValueError,
        SyntaxError,
    ) as exc:
        raise ImageValidationError(
            "The image is invalid, damaged, or cannot be safely decoded."
        ) from exc
