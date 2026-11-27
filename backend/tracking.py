"""Bounding-box conversion and OpenCV tracker construction."""
import cv2


def pixel_box(box: list[int], width: int, height: int) -> tuple[int, int, int, int]:
    """Convert normalized edges to an inclusive-exclusive pixel rectangle."""
    x1, y1, x2, y2 = box
    left, top = x1 * width // 1000, y1 * height // 1000
    right = min(width, (x2 * width + 999) // 1000)
    bottom = min(height, (y2 * height + 999) // 1000)
    return left, top, right - left, bottom - top


def create_tracker():
    """Construct the CSRT tracker from the contrib build."""
    factory = getattr(cv2, 'TrackerCSRT_create', None)
    if factory is None:
        raise RuntimeError('Установите opencv-contrib-python-headless')
    return factory()
