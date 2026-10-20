# SPDX-License-Identifier: AGPL-3.0-or-later
"""Images imported into an article (X03b, ADR-0036 §6): re-encoded without their metadata,
checked by decoding, never kept as sent; their files addressed by content."""

import io
from pathlib import Path

import pytest
from PIL import Image as PilImage

from otlet.media.adapters.files_disk import DiskFiles
from otlet.media.adapters.images_pillow import PillowImages
from otlet.media.domain.media import MAX_SIDE, MediaError


def picture(
    kind: str, size: tuple[int, int] = (64, 48), mode: str | None = None, **options: object
) -> bytes:
    out = io.BytesIO()
    mode = mode or ("RGB" if kind in ("JPEG", "BMP") else "RGBA")
    PilImage.new(mode, size, 120 if mode == "L" else (200, 30, 30)).save(out, kind, **options)
    return out.getvalue()


def test_a_photo_loses_its_metadata_and_is_turned_upright() -> None:
    exif = PilImage.Exif()
    exif[0x0112] = 6  # orientation: turned 90° clockwise
    exif[0x013B] = "Alice Martin"  # artist
    sent = picture("JPEG", (64, 48), exif=exif.tobytes(), comment=b"secret")
    image = PillowImages().normalize(sent)
    assert image.mime == "image/jpeg" and (image.width, image.height) == (48, 64)
    with PilImage.open(io.BytesIO(image.data)) as kept:
        assert not kept.getexif() and "comment" not in kept.info and "exif" not in kept.info
    assert b"Alice Martin" not in image.data and image.data != sent


def test_formats_kept_converted_or_refused() -> None:
    images = PillowImages()
    assert images.normalize(picture("PNG")).mime == "image/png"
    assert images.normalize(picture("WEBP")).mime == "image/webp"
    gif = images.normalize(picture("GIF"))  # its first image, as a PNG
    assert gif.mime == "image/png"
    for refused in (b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"%PDF-1.7", b"", b"\x89PNG\r\n"):
        with pytest.raises(MediaError) as error:
            images.normalize(refused)
        assert error.value.code == "not_an_image"
    # TIFF and BMP decode, but are not formats of the web.
    with pytest.raises(MediaError):
        images.normalize(picture("BMP"))


def test_a_large_image_is_scaled_down_and_a_bomb_refused() -> None:
    big = PillowImages().normalize(picture("PNG", (MAX_SIDE * 2, 100)))
    assert (big.width, big.height) == (MAX_SIDE, 50)
    # 7,000 pixels a side, one colour: tiny on disk, 49 million pixels once decoded.
    bomb = picture("PNG", (7_000, 7_000), mode="L", optimize=True)
    assert len(bomb) < 200_000
    with pytest.raises(MediaError):
        PillowImages().normalize(bomb)


def test_files_are_addressed_by_their_content_and_written_once(tmp_path: Path) -> None:
    files = DiskFiles(tmp_path)
    first = files.put(b"abc", "png")
    assert first == files.put(b"abc", "png")
    assert files.get(first, "png") == b"abc"
    assert (tmp_path / first[:2] / first[2:4] / f"{first}.png").exists()
    assert files.get("0" * 64, "png") is None
    with pytest.raises(ValueError):
        files.get("../../etc/passwd", "png")
