"""
PDF generation engine.

All image-to-PDF conversion and PDF merging is performed in memory.
No intermediate files are written to disk.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# Maximum dimension (in pixels) for a single image side before downscaling.
# This prevents out-of-memory errors for very large images while keeping
# high quality for typical photos.
MAX_IMAGE_DIMENSION = 4096

# JPEG quality used when encoding images into the PDF page stream.
IMAGE_JPEG_QUALITY = 92


@dataclass
class FileItem:
    """Represents one entry in the file list (image or PDF)."""

    path: Path
    display_name: str = field(init=False)
    is_pdf: bool = field(init=False)

    def __post_init__(self) -> None:
        self.display_name = self.path.name
        self.is_pdf = self.path.suffix.lower() == ".pdf"


class GenerationError(Exception):
    """Raised when PDF generation fails for a user-visible reason."""


class ConflictError(GenerationError):
    """Raised when the destination file already exists."""


def generate_pdf(
    items: list[FileItem],
    destination: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> None:
    """
    Combine *items* into a single PDF saved at *destination*.

    Parameters
    ----------
    items:
        Ordered list of files to combine (left-to-right).
    destination:
        Full path of the output PDF file.
    progress_callback:
        Optional callable(current, total, label) for progress reporting.

    Raises
    ------
    ConflictError
        If the destination file already exists.
    GenerationError
        On any other processing failure.
    """
    if not items:
        raise GenerationError("No files to combine.")

    if destination.exists():
        raise ConflictError(
            f'A file named "{destination.name}" already exists in the selected folder.\n\n'
            "Please choose a different destination folder or rename the existing file."
        )

    total = len(items)
    writer = PdfWriter()
    output_buffer = io.BytesIO()

    try:
        for idx, item in enumerate(items):
            label = f"Processing {item.display_name}…"
            if progress_callback:
                progress_callback(idx, total, label)
            logger.debug("Processing item %d/%d: %s", idx + 1, total, item.path)

            if item.is_pdf:
                _merge_pdf(writer, item)
            else:
                _add_image(writer, item)

        if progress_callback:
            progress_callback(total, total, "Saving PDF…")

        writer.write(output_buffer)
        pdf_bytes = output_buffer.getvalue()

        # Atomic-ish write: only create the file if everything succeeded.
        _write_file(destination, pdf_bytes)

    except (ConflictError, GenerationError):
        raise
    except MemoryError as exc:
        raise GenerationError(
            "Not enough memory to process these files.\n\n"
            "Try splitting the files into smaller groups."
        ) from exc
    except PermissionError as exc:
        raise GenerationError(
            f"Permission denied when saving to:\n{destination}\n\n"
            "Please choose a folder where you have write access."
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during PDF generation")
        raise GenerationError(
            "An unexpected error occurred while creating the PDF.\n\n"
            "Please check that all selected files are valid and try again."
        ) from exc
    finally:
        output_buffer.close()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _merge_pdf(writer: PdfWriter, item: FileItem) -> None:
    """Append all pages of an existing PDF into *writer*."""
    try:
        reader = PdfReader(str(item.path))
        if reader.is_encrypted:
            raise GenerationError(
                f'"{item.display_name}" is password-protected.\n\n'
                "Password-protected PDFs cannot be combined.\n"
                "Please remove the password first and try again."
            )
        if len(reader.pages) == 0:
            raise GenerationError(
                f'"{item.display_name}" appears to be empty (no pages found).'
            )
        for page in reader.pages:
            writer.add_page(page)
        logger.debug("Merged %d page(s) from %s", len(reader.pages), item.path)
    except GenerationError:
        raise
    except Exception as exc:
        logger.exception("Failed to read PDF: %s", item.path)
        raise GenerationError(
            f'Could not read "{item.display_name}".\n\n'
            "The file may be corrupted or in an unsupported format."
        ) from exc


def _add_image(writer: PdfWriter, item: FileItem) -> None:
    """Convert an image file into a PDF page and add it to *writer*."""
    try:
        img = Image.open(item.path)
        img.verify()  # Detect truncated/corrupted files early
        img = Image.open(item.path)  # Re-open after verify (verify closes stream)

        # Apply EXIF orientation so portrait photos aren't rotated.
        img = ImageOps.exif_transpose(img)

        # Convert to RGB so we can write JPEG into the PDF page.
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Downscale extremely large images to avoid memory exhaustion.
        w, h = img.size
        if max(w, h) > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)
            logger.debug("Downscaled image from %dx%d to %dx%d", w, h, *new_size)

        # Encode the image into JPEG bytes in memory.
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        img_buffer.seek(0)
        img_bytes = img_buffer.getvalue()

        # Build a minimal PDF page that contains the image at its natural size.
        # PDF user units default to 1/72 inch; we target 150 DPI for a good
        # balance of size and quality.
        dpi = 150
        pts_w = img.width * 72 / dpi
        pts_h = img.height * 72 / dpi

        from pypdf import PdfWriter as _PdfWriter
        from pypdf.generic import (
            ArrayObject,
            DecodedStreamObject,
            DictionaryObject,
            FloatObject,
            NameObject,
            NumberObject,
            RectangleObject,
        )

        # Build a minimal single-page PDF in memory via a temporary writer,
        # then copy that page into the main writer.
        tmp_writer = _PdfWriter()
        page = tmp_writer.add_blank_page(width=pts_w, height=pts_h)

        tmp_writer.add_page(page)

        # Use pypdf's image embedding helper (available since pypdf 3.x).
        # This embeds the JPEG bytes as an XObject.
        from pypdf import PageObject

        page_obj = _build_image_page(img_bytes, img.width, img.height, pts_w, pts_h)
        writer.add_page(page_obj)

        logger.debug(
            "Added image page %dx%d px → %.1f×%.1f pt", img.width, img.height, pts_w, pts_h
        )
        img_buffer.close()

    except GenerationError:
        raise
    except FileNotFoundError:
        raise GenerationError(f'Could not find the file "{item.display_name}".')
    except Exception as exc:
        logger.exception("Failed to process image: %s", item.path)
        raise GenerationError(
            f'Could not process "{item.display_name}".\n\n'
            "The file may be corrupted, in an unsupported format, or too large."
        ) from exc


def _build_image_page(
    jpeg_bytes: bytes,
    px_w: int,
    px_h: int,
    pts_w: float,
    pts_h: float,
):
    """
    Build a pypdf PageObject that contains a single JPEG image filling the page.
    Uses low-level PDF object construction so no temporary files are needed.
    """
    from pypdf import PageObject
    from pypdf.generic import (
        ArrayObject,
        ByteStringObject,
        DecodedStreamObject,
        DictionaryObject,
        EncodedStreamObject,
        FloatObject,
        NameObject,
        NumberObject,
        RectangleObject,
        StreamObject,
    )

    # --- Image XObject (DCTDecode / JPEG) ---
    image_obj = EncodedStreamObject()
    image_obj.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(px_w),
            NameObject("/Height"): NumberObject(px_h),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/Filter"): NameObject("/DCTDecode"),
        }
    )
    image_obj._data = jpeg_bytes  # type: ignore[attr-defined]

    # --- Content stream: scale image to fill the page ---
    content_stream = f"{pts_w:.4f} 0 0 {pts_h:.4f} 0 0 cm /Im0 Do"
    content_obj = DecodedStreamObject()
    content_obj.set_data(content_stream.encode())

    # --- Resources dictionary ---
    resources = DictionaryObject(
        {
            NameObject("/XObject"): DictionaryObject(
                {NameObject("/Im0"): image_obj}
            )
        }
    )

    # --- Page dictionary ---
    page_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Page"),
            NameObject("/MediaBox"): ArrayObject(
                [FloatObject(0), FloatObject(0), FloatObject(pts_w), FloatObject(pts_h)]
            ),
            NameObject("/Contents"): content_obj,
            NameObject("/Resources"): resources,
        }
    )

    page = PageObject()
    page.update(page_dict)
    return page


def _write_file(destination: Path, data: bytes) -> None:
    """Write *data* to *destination*, ensuring no partial file on failure."""
    try:
        destination.write_bytes(data)
    except Exception:
        # Remove partial file if writing failed mid-way.
        try:
            if destination.exists():
                os.remove(destination)
        except OSError:
            pass
        raise


def get_page_count_estimate(items: list[FileItem]) -> int:
    """
    Return an estimated page count for the combined PDF.
    Images count as 1 page each; PDFs count their actual pages.
    Returns -1 if any file cannot be read.
    """
    total = 0
    for item in items:
        if item.is_pdf:
            try:
                reader = PdfReader(str(item.path))
                total += len(reader.pages)
            except Exception:
                return -1
        else:
            total += 1
    return total
