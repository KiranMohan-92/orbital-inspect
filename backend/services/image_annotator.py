"""
Satellite image annotator — renders bounding box damage overlays onto
satellite images for embedding in PDF reports.
"""
from PIL import Image, ImageDraw, ImageFont
import io
import logging

log = logging.getLogger(__name__)

# Prevent decompression bombs — max 25 megapixels (5000x5000)
Image.MAX_IMAGE_PIXELS = 25_000_000

SEVERITY_COLORS: dict[str, tuple[int, int, int]] = {
    "CRITICAL": (239, 68, 68),    # Red
    "SEVERE":   (249, 115, 22),   # Orange
    "MODERATE": (234, 179, 8),    # Yellow
    "MINOR":    (132, 204, 22),   # Lime
}


def annotate_satellite_image(
    image_bytes: bytes,
    damages: list[dict],
    image_mime: str = "image/jpeg",
) -> bytes:
    """
    Render damage bounding boxes onto a satellite image.

    Args:
        image_bytes: Raw image data (JPEG, PNG, or any Pillow-supported format).
        damages: List of damage dicts, each containing:
                   - bounding_box: [ymin, xmin, ymax, xmax] in 0-1000 range
                   - severity: one of CRITICAL, SEVERE, MODERATE, MINOR
                   - label: human-readable damage label
                   - confidence: float 0-1
        image_mime: MIME type hint (currently unused; Pillow auto-detects format).

    Returns:
        PNG bytes of the annotated image.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = img.size

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            max(12, h // 40),
        )
        font_small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            max(10, h // 50),
        )
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_small = font

    for damage in damages:
        bbox = damage.get("bounding_box", [0, 0, 0, 0])
        if len(bbox) != 4:
            log.warning("Skipping damage with invalid bounding_box length: %s", bbox)
            continue

        ymin, xmin, ymax, xmax = bbox
        # Convert 0-1000 coordinates to pixel coordinates
        x1 = int(xmin / 1000 * w)
        y1 = int(ymin / 1000 * h)
        x2 = int(xmax / 1000 * w)
        y2 = int(ymax / 1000 * h)

        # Skip degenerate boxes
        if x2 <= x1 or y2 <= y1:
            log.warning("Skipping degenerate bounding_box: %s", bbox)
            continue

        severity = damage.get("severity", "MINOR").upper()
        color = SEVERITY_COLORS.get(severity, (132, 204, 22))
        label = damage.get("label", "")
        confidence = damage.get("confidence", 0)

        # Semi-transparent fill (~12% opacity)
        fill_color = (*color, 30)
        draw.rectangle(
            [x1, y1, x2, y2],
            fill=fill_color,
            outline=(*color, 200),
            width=2,
        )

        # Label tag above box
        tag_text = f"{label} ({confidence * 100:.0f}%)"
        text_bbox = draw.textbbox((0, 0), tag_text, font=font_small)
        tag_w = text_bbox[2] - text_bbox[0] + 8
        tag_h = text_bbox[3] - text_bbox[1] + 4

        tag_y = max(0, y1 - tag_h - 2)
        draw.rectangle(
            [x1, tag_y, x1 + tag_w, tag_y + tag_h],
            fill=(*color, 180),
        )
        draw.text(
            (x1 + 4, tag_y + 2),
            tag_text,
            fill=(255, 255, 255, 255),
            font=font_small,
        )

    # Composite overlay onto original image
    result = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    result.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf.read()
