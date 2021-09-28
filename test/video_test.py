import cv2
import numpy
import pytest

from subtitle_editor.video import calculate_frame_resize, resize_frame


@pytest.mark.parametrize(
    "frame_dim,target_dim,crop,expected",
    [
        [(100, 100), (50, 50), True, (50, 50, 0, 0)],
        [(100, 100), (50, 50), False, (50, 50, 0, 0)],
        [(200, 200), (100, 50), True, (100, 100, 0, 25)],
        [(200, 200), (100, 50), False, (50, 50, 0, 0)],
        [(200, 200), (50, 100), True, (100, 100, 25, 0)],
        [(200, 200), (50, 100), False, (50, 50, 0, 0)],
        [(150, 50), (25, 25), True, (75, 25, 25, 0)],
        [(150, 50), (25, 25), False, (25, 9, 0, 0)],
        [(1920, 1080), (58, 104), True, (185, 104, 64, 0)],
        [(1920, 1080), (58, 104), False, (58, 33, 0, 0)],
        [(1920, 1080), (186, 104), True, (186, 105, 0, 1)],
        [(1920, 1080), (186, 104), False, (185, 104, 0, 0)],
    ],
)
def test_calculate_frame_resize(frame_dim, target_dim, crop, expected):
    frame_w, frame_h = frame_dim
    target_w, target_h = target_dim
    result = calculate_frame_resize(frame_w, frame_h, target_w, target_h, crop)
    assert result == expected
