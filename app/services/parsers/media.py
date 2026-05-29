"""Media file metadata extraction."""

from PIL import Image
from io import BytesIO


def get_image_info(content: bytes) -> dict:
    img = Image.open(BytesIO(content))
    return {
        "width": img.width,
        "height": img.height,
        "format": img.format,
        "mode": img.mode,
    }
