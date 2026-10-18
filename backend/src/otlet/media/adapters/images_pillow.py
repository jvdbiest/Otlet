# SPDX-License-Identifier: AGPL-3.0-or-later
"""Images decoded and re-encoded with Pillow (TECH_CHOICES, « Médias »). The bytes a person sends
are never kept: what is stored is a new file, without the metadata of the original (EXIF with
the GPS position, XMP, comments), turned upright, no larger than MAX_SIDE."""

import io
import warnings

from PIL import Image as PilImage
from PIL import ImageOps, UnidentifiedImageError

from otlet.media.domain.media import MAX_PIXELS, MAX_SIDE, Image, MediaError

# Formats Otlet accepts, and the one each is stored in. A GIF keeps its first image only.
STORED = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WEBP", "GIF": "PNG"}
MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
PilImage.MAX_IMAGE_PIXELS = MAX_PIXELS


class PillowImages:
    def normalize(self, data: bytes) -> Image:
        try:
            with warnings.catch_warnings():
                # A decompression bomb is an error, not a warning.
                warnings.simplefilter("error", PilImage.DecompressionBombWarning)
                with PilImage.open(io.BytesIO(data)) as probe:
                    kind = probe.format
                    probe.verify()
                if kind is None or kind not in STORED:
                    raise MediaError("not_an_image")
                with PilImage.open(io.BytesIO(data)) as opened:
                    opened.seek(0)
                    image = ImageOps.exif_transpose(opened)
                    image.load()
        except (
            UnidentifiedImageError,
            PilImage.DecompressionBombError,
            OSError,
            SyntaxError,
            ValueError,
            Warning,
        ) as error:
            if isinstance(error, MediaError):
                raise
            raise MediaError("not_an_image") from error
        if image.width * image.height > MAX_PIXELS:
            raise MediaError("not_an_image")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        stored = STORED[kind]
        if stored == "JPEG":
            image = image.convert("RGB")
        elif image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert(
                "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
            )
        out = io.BytesIO()
        # No exif, no xmp, no comment: Pillow writes only what it is given.
        options: dict[str, object] = {"optimize": True}
        if stored in ("JPEG", "WEBP"):
            options["quality"] = 88
        icc = image.info.get("icc_profile")
        if icc:
            options["icc_profile"] = icc  # colours, not personal data
        # Pillow writes back some of what it read (a JPEG's comment, its EXIF once turned
        # upright): nothing of the original is kept but the pixels.
        image.info = {}
        image.save(out, stored, **options)
        return Image(out.getvalue(), MIMES[stored], image.width, image.height)
