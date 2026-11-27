"""Geometry helpers for experimental visual attention."""
import cv2
import numpy as np

from backend.tracking import pixel_box


def crop_region(frame: bytes, box: list[int]) -> tuple[bytes, tuple[int, int, int, int], tuple[int, int]]:
    """Crop with 50 percent padding per side and enlarge for localization."""
    image = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Invalid JPEG')
    height, width = image.shape[:2]
    x, y, w, h = pixel_box(box, width, height)
    left, top = max(0, x-w//2), max(0, y-h//2)
    right, bottom = min(width, x+w+(w+1)//2), min(height, y+h+(h+1)//2)
    region = image[top:bottom, left:right]
    scale = min(4.0, 640 / max(region.shape[:2]))
    if scale > 1:
        region = cv2.resize(region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    ok, encoded = cv2.imencode('.jpg', region)
    if not ok:
        raise ValueError('Cannot encode crop')
    return encoded.tobytes(), (left, top, right, bottom), (width, height)


def restore_box(box: list[int], region: tuple[int, int, int, int], size: tuple[int, int]) -> list[int]:
    """Map crop-normalized edges back to full-frame normalized edges."""
    l, t, r, b = region
    w, h = size
    return [(l*1000+box[0]*(r-l))//w, (t*1000+box[1]*(b-t))//h,
            (l*1000+box[2]*(r-l)+w-1)//w, (t*1000+box[3]*(b-t)+h-1)//h]


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Return intersection over union for pixel rectangles."""
    x, y, w, h = a
    u, v, s, t = b
    intersection = max(0, min(x+w, u+s)-max(x, u))*max(0, min(y+h, v+t)-max(y, v))
    union = w*h+s*t-intersection
    return intersection/union if union > 0 else 0.0
