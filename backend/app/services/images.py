from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_AI_IMAGE_EDGE = 2048
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "JPEG"),
    "PNG": ("image/png", "PNG"),
    "WEBP": ("image/webp", "WEBP"),
}


class InvalidSolutionImage(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    media_type: str
    width: int
    height: int
    sha256: str


def normalize_solution_image(raw: bytes) -> NormalizedImage:
    """Validate an image, apply EXIF orientation, and strip private metadata."""
    if not raw:
        raise InvalidSolutionImage("The selected image is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise InvalidSolutionImage("Images must be 8 MB or smaller.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as probe:
                source_format = probe.format
                probe.verify()
            if source_format not in ALLOWED_FORMATS:
                raise InvalidSolutionImage("Use a JPEG, PNG, or WebP image.")

            with Image.open(BytesIO(raw)) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise InvalidSolutionImage("The image dimensions are too large.")
                media_type, output_format = ALLOWED_FORMATS[source_format]
                output = BytesIO()
                if output_format == "JPEG":
                    if image.mode not in ("RGB", "L"):
                        background = Image.new("RGB", image.size, "white")
                        if image.mode in ("RGBA", "LA"):
                            background.paste(image, mask=image.getchannel("A"))
                        else:
                            background.paste(image.convert("RGB"))
                        image = background
                    image.save(output, format="JPEG", quality=92, optimize=True)
                elif output_format == "PNG":
                    image.save(output, format="PNG", optimize=True)
                else:
                    image.save(output, format="WEBP", quality=92, method=4)
                data = output.getvalue()
    except InvalidSolutionImage:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as error:
        raise InvalidSolutionImage("The file is not a valid solution image.") from error

    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidSolutionImage("The processed image is larger than 8 MB.")
    return NormalizedImage(
        data=data,
        media_type=media_type,
        width=image.width,
        height=image.height,
        sha256=sha256(data).hexdigest(),
    )


def prepare_ai_image(raw: bytes) -> NormalizedImage:
    """Create the immutable, size-bounded image that is sent to the vision model."""
    with Image.open(BytesIO(raw)) as opened:
        image = opened.convert("RGB")
        image.thumbnail((MAX_AI_IMAGE_EDGE, MAX_AI_IMAGE_EDGE), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        data = output.getvalue()
    return NormalizedImage(
        data=data,
        media_type="image/jpeg",
        width=image.width,
        height=image.height,
        sha256=sha256(data).hexdigest(),
    )
