import curses
import hashlib
import math
import os
import tempfile
import time
import wave

import cv2
import ffmpeg
import numpy
import pyaudio
from video_to_ascii.render_strategy.ascii_strategy import AsciiStrategy
from video_to_ascii.render_strategy.image_processor import (
    brightness_to_ascii, increase_saturation, rgb_to_brightness)

from .colors import rgb_to_color_pair

ascii_strategy = AsciiStrategy()
PIXEL_DTYPE = numpy.dtype([("ord", numpy.int16), ("color_pair", numpy.int16)])


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


def pixel_to_ascii(pixel, density=0):
    rgb = tuple(float(x) for x in reversed(pixel[:3]))
    bright = rgb_to_brightness(*rgb)
    rgb = increase_saturation(*rgb)
    char = brightness_to_ascii(bright, density)
    pair_number = rgb_to_color_pair(*rgb)
    return char * 2, pair_number


def frame_to_curses(frame):
    height, width, _ = frame.shape
    curses_frame = numpy.empty((height, width), dtype=PIXEL_DTYPE)
    for y, row in enumerate(frame):
        for x, pixel in enumerate(row):
            char, pair_number = pixel_to_ascii(pixel, density=2)
            curses_frame[y][x] = (ord(char[0]), pair_number)
    return curses_frame


class VideoWindow:
    def __init__(self, video):
        self.video = video

        # Calculate md5 hash of video content (for temp files)
        hash_md5 = hashlib.md5()
        with open(video, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        self.video_hash = hash_md5.hexdigest()

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

        # Pads are the full size of the video - it's just a question of how
        # we display and crop them.
        self.left_pad = curses.newpad(self.video_height, curses.COLS)
        self.right_pad = curses.newpad(self.video_height, curses.COLS)

        self.start_frame_num = None
        self.end_frame_num = None
        self.should_render = True

        # Structure: [rendered_frame, ...]
        self._cache = numpy.empty(
            (self.frame_count, self.video_height, self.video_width),
            dtype=PIXEL_DTYPE,
        )

    def set_timestamps(self, timestamps):
        start_ts, end_ts = timestamps
        # Round to frames
        start_frame_num = math.floor(start_ts.total_seconds() * self.fps)
        end_frame_num = math.floor(end_ts.total_seconds() * self.fps)
        self.set_frames(start_frame_num, end_frame_num)

    def set_frames(self, start_frame, end_frame):
        # Clamp to the available frames
        self.start_frame_num = numpy.clip(start_frame, 0, self.frame_count - 1)
        self.end_frame_num = numpy.clip(end_frame, 0, self.frame_count - 1)
        self.should_render = True

    def refresh_full(self, pad, nout=False):
        refresh = pad.noutrefresh if nout else pad.refresh
        height, width = pad.getmaxyx()
        refresh(
            0,  # Pad area to start display
            0,
            0,  # Upper left of window area
            0,
            height - 1,  # Lower right of window area
            width - 1,
        )

    def refresh_left(self, pad, nout=False):
        refresh = pad.noutrefresh if nout else pad.refresh
        height, width = pad.getmaxyx()
        refresh(
            0,  # Pad area to start display
            width // 4,
            0,  # Upper left of window area
            0,
            height - 1,  # Lower right of window area
            width // 2 - 1,
        )

    def refresh_right(self, pad, nout=False):
        refresh = pad.noutrefresh if nout else pad.refresh
        height, width = pad.getmaxyx()
        refresh(
            0,  # Pad area to start display
            width // 4,
            0,  # Upper left of window area
            width // 2 + 1,
            height - 1,  # Lower right of window area
            width - 1,
        )

    def load_frames(self):
        self.left_pad.erase()

        temp_dir = tempfile.gettempdir()
        frame_cache = os.path.join(
            temp_dir,
            f"subtitle-editor-frames-{self.video_hash}-{self.video_width}x{self.video_height}.npy",
        )

        if os.path.exists(frame_cache):
            self.left_pad.addstr(
                0, 0, f"Loading cached {self.video_width}x{self.video_height} frames..."
            )
            self.refresh_full(self.left_pad)
            try:
                with open(frame_cache, "rb") as fp:
                    numpy.copyto(self._cache, numpy.load(fp, allow_pickle=False))
            except (IOError, ValueError, TypeError):
                # IOError: couldn't read file
                # ValueError: Shape doesn't match
                # TypeError: Unable to convert types
                self.left_pad.erase()
            else:
                return

        self.left_pad.addstr(
            0, 0, f"Rendering {self.video_width}x{self.video_height} frames..."
        )
        self.left_pad.addstr(1, 0, ascii_strategy.build_progress(0, self.frame_count))
        self.refresh_full(self.left_pad)
        frame_num = 0
        width, height = self.video_width, self.video_height

        while self.cap.isOpened():
            _, frame = self.cap.read()
            if frame is None:
                break

            resized_frame = resize_frame(frame, width, height)
            curses_frame = frame_to_curses(resized_frame)
            self._cache[frame_num] = curses_frame
            self.left_pad.addstr(
                1, 0, ascii_strategy.build_progress(frame_num, self.frame_count)
            )
            self.refresh_full(self.left_pad)
            frame_num += 1

        self.left_pad.addstr(
            0, 0, f"Caching {self.video_width}x{self.video_height} frames..."
        )
        self.refresh_full(self.left_pad)
        with open(frame_cache, "wb") as fp:
            numpy.save(fp, self._cache, allow_pickle=False)

    def render_frame(self, pad, frame_num):
        curses_frame = self._cache[frame_num]
        it = numpy.nditer(curses_frame, flags=["multi_index"])
        for pixel in it:
            y, x = it.multi_index
            # 1 pixel = 2 cols
            x *= 2
            chars = chr(pixel["ord"]) * 2
            color_pair = curses.color_pair(pixel["color_pair"])
            try:
                pad.addstr(
                    y,
                    x,
                    chars,
                    color_pair,
                )
            except curses.error:
                raise Exception(
                    f"Unable to print pixel `{chars}` at y={y} x={x} (color pair {color_pair}; maxyx={pad.getmaxyx()})"
                )

    def render(self):
        if not self.should_render:
            return

        self.left_pad.erase()
        self.right_pad.erase()

        self.render_frame(self.left_pad, self.start_frame_num)
        self.render_frame(self.right_pad, self.end_frame_num)

        self.refresh_left(self.left_pad, nout=True)
        self.refresh_right(self.right_pad, nout=True)
        self.should_render = False

    def play(self):
        self.left_pad.erase()
        self.right_pad.erase()
        start_ts = self.start_frame_num / self.fps
        end_ts = self.end_frame_num / self.fps
        input_kwargs = {
            "ss": start_ts,
            "t": end_ts - start_ts,
        }

        # Set up audio clip
        temp_dir = tempfile.gettempdir()
        audio_filename = os.path.join(
            temp_dir,
            # Always use the same file because we only play one at a time.
            "subtitle-editor-audio.wav",
        )
        stream = ffmpeg.input(self.video, **input_kwargs)
        stream = ffmpeg.output(stream, audio_filename)
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream, quiet=True)
        wave_file = wave.open(audio_filename, "rb")
        audio_chunk = int(wave_file.getframerate() / self.fps)
        p = pyaudio.PyAudio()

        audio_stream = p.open(
            format=p.get_format_from_width(wave_file.getsampwidth()),
            channels=wave_file.getnchannels(),
            rate=wave_file.getframerate(),
            output=True,
        )

        frame_delta = 1 / self.fps
        for frame_num in range(self.start_frame_num, self.end_frame_num + 1):
            t0 = time.process_time()
            audio_data = wave_file.readframes(audio_chunk)
            audio_stream.write(audio_data)
            self.render_frame(self.left_pad, frame_num)
            self.refresh_full(self.left_pad, nout=True)

            yield frame_num

            t1 = time.process_time()
            remaining = frame_delta - (t1 - t0)

            if remaining > 0:
                time.sleep(remaining)

        p.terminate()
        self.should_render = True
