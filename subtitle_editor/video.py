import curses
import math
import numpy
import os
import tempfile
from textwrap import TextWrapper

import cv2
import ffmpeg
from video_to_ascii.render_strategy.image_processor import (
    brightness_to_ascii,
    increase_saturation,
    rgb_to_brightness,
)
from video_to_ascii.render_strategy.ascii_strategy import AsciiStrategy
from video_to_ascii.video_engine import VideoEngine

from .colors import rgb_to_color_pair


ascii_strategy = AsciiStrategy()


def calculate_frame_resize(frame_w, frame_h, target_w, target_h, crop=False):
    """
    Calculate what the final result of a frame resize operation should be.
    Returns a tuple of (resize_w, resize_h, crop_x, crop_y)
    """
    frame_ratio = frame_w / frame_h
    crop_x, crop_y = 0, 0

    # We can constrain by width or height; one would be cropped, one would not.
    constrained_h = math.ceil(target_w / frame_ratio)
    constrained_w = math.ceil(target_h * frame_ratio)
    if crop:
        # Take the larger overall size
        if target_w * constrained_h > target_h * constrained_w:
            resize_w, resize_h = target_w, constrained_h
        else:
            resize_w, resize_h = constrained_w, target_h
    else:
        # Take the smaller overall size
        if target_w * constrained_h < target_h * constrained_w:
            resize_w, resize_h = target_w, constrained_h
        else:
            resize_w, resize_h = constrained_w, target_h

    # Crop to center
    if resize_w > target_w:
        crop_x = math.ceil((resize_w - target_w) / 2)
    if resize_h > target_h:
        crop_y = math.ceil((resize_h - target_h) / 2)

    return (resize_w, resize_h, crop_x, crop_y)


def resize_frame(frame, target_w, target_h, crop=False):
    """
    Resize frame to the given width and height. If crop=True,
    fill the entire space with the frame; otherwise, show the
    entire frame.
    """
    frame_h, frame_w, _ = frame.shape
    resize_w, resize_h, crop_x, crop_y = calculate_frame_resize(
        frame_w, frame_h, target_w, target_h, crop
    )
    resized_frame = cv2.resize(
        frame, (resize_w, resize_h), interpolation=cv2.INTER_LINEAR
    )
    return resized_frame[crop_y : crop_y + resize_h, crop_x : crop_x + resize_w]


def pixel_to_ascii(pixel, colored=True, density=0):
    rgb = tuple(float(x) for x in reversed(pixel[:3]))
    bright = rgb_to_brightness(*rgb)
    rgb = increase_saturation(*rgb)
    char = brightness_to_ascii(bright, density)
    pair_number = rgb_to_color_pair(*rgb)
    return char * 2, pair_number


def frame_to_curses(frame):
    height, width, _ = frame.shape
    curses_frame = numpy.empty((height, width, 2), dtype=numpy.int16)
    for y, row in enumerate(frame):
        for x, pixel in enumerate(row):
            char, pair_number = pixel_to_ascii(pixel, colored=True, density=2)
            curses_frame[y][x] = [ord(char[0]), pair_number]
    return curses_frame


def play(start, end, video):
    filename, file_extension = os.path.splitext(video)
    input_kwargs = {
        "ss": start.total_seconds(),
        "t": (end - start).total_seconds(),
    }
    temp_dir = tempfile.gettempdir()

    # Set up video clip
    clip_filename = os.path.join(
        temp_dir,
        "subtitle-editor",
        f'{filename}-{input_kwargs["ss"]}-{input_kwargs["t"]}{file_extension}',
    )
    if not os.path.exists(clip_filename):
        stream = ffmpeg.input(video, **input_kwargs)
        stream = ffmpeg.output(stream, clip_filename, c="copy")
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream)

    engine = VideoEngine()
    engine.load_video_from_file(clip_filename)

    # Set up audio clip
    audio_filename = os.path.join(
        temp_dir,
        "temp-audiofile-for-vta.wav",
    )
    stream = ffmpeg.input(video, **input_kwargs)
    stream = ffmpeg.output(stream, audio_filename)
    stream = ffmpeg.overwrite_output(stream)
    ffmpeg.run(stream)
    engine.with_audio = True
    engine.play()
    os.remove(clip_filename)


class VideoWindow:
    def __init__(self, video, start_line):
        self.cap = cv2.VideoCapture(video)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

        self.video_width, self.video_height, _, _ = calculate_frame_resize(
            frame_w=self.cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            frame_h=self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            # Width is 1/2 COLS because each pixel is 2 columns
            target_w=curses.COLS // 2,
            # Leave at least 1/4 the screen for the rest of the interface
            target_h=curses.LINES * 3 // 4,
            crop=False,
        )

        self.window = curses.newwin(
            # Lines. Add an extra line of buffer.
            self.video_height + 1,
            # Cols. Multiply by 2 to get cols from pixels.
            self.video_width * 2,
            0,
            0,
        )
        self.start_ts = None
        self.end_ts = None
        self.should_render = True

        # Structure: {frame_num: rendered_frame}
        self._cache = {frame_num: None for frame_num in range(self.frame_count)}

    def precache(self):
        self.window.clear()
        self.window.addstr(0, 0, f"Caching rendered frames...")
        self.window.addstr(1, 0, ascii_strategy.build_progress(0, self.frame_count))
        self.window.refresh()
        frame_num = 0
        width, height = self.video_width, self.video_height

        while self.cap.isOpened():
            _, frame = self.cap.read()
            if frame is None:
                break

            resized_frame = resize_frame(frame, width, height)
            curses_frame = frame_to_curses(resized_frame)
            self._cache[frame_num] = curses_frame
            self.window.addstr(
                1, 0, ascii_strategy.build_progress(frame_num, self.frame_count)
            )
            self.window.refresh()
            frame_num += 1

    def set_timestamps(self, timestamps):
        self.start_ts, self.end_ts = timestamps
        self.should_render = True

    def get_curses_frame(self, frame_num, crop_w=None, crop_h=None):
        """
        Get a cached curses frame and center-crop it to the given dimensions
        """

        curses_frame = self._cache[frame_num]
        frame_h, frame_w, _ = curses_frame.shape
        if crop_w is None:
            crop_w = frame_w
        if crop_h is None:
            crop_h = frame_h
        crop_x = (frame_w - crop_w) // 2
        crop_y = (frame_h - crop_h) // 2
        return curses_frame[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]

    def render_frame(self, curses_frame, start_x, start_y):
        for i, row in enumerate(curses_frame):
            for j, (char, pair_number) in enumerate(row):
                y = start_y + i
                # Double x offset because 1 pixel = 2 cols
                x = start_x + j * 2
                try:
                    self.window.addstr(
                        y, x, chr(char) * 2, curses.color_pair(pair_number)
                    )
                except curses.error:
                    raise Exception(
                        f"Unable to print pixel `{char}` at y={y} x={x} (color pair {pair_number}; maxyx={self.window.getmaxyx()})"
                    )

    def render(self):
        if not self.should_render:
            return

        self.window.clear()

        curses_frame = self.get_curses_frame(
            math.floor(self.start_ts.total_seconds() * self.fps),
            # Crop video to half width for display
            # self.video_width // 2,
        )
        self.render_frame(curses_frame, 0, 0)

        self.window.noutrefresh()
        self.should_render = False

    def refresh(self):
        self.window.refresh()
