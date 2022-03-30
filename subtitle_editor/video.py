import math
import os
import tempfile
import wave

import cv2
import ffmpeg
import numpy
import pyaudio


class Video:
    def __init__(self, path):
        self.path = path

        self.cap = cv2.VideoCapture(path)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

        self.start_frame = None
        self.end_frame = None

    def set_timestamps(self, timestamps):
        start_ts, end_ts = timestamps
        # Round to frames
        start_frame = math.floor(start_ts.total_seconds() * self.fps)
        end_frame = math.floor(end_ts.total_seconds() * self.fps)
        self.set_frames(start_frame, end_frame)

    def set_frames(self, start_frame, end_frame):
        # Clamp to the available frames
        self.start_frame = numpy.clip(start_frame, 0, self.frame_count - 1)
        self.end_frame = numpy.clip(end_frame, 0, self.frame_count - 1)

    def set_current_frame(self, frame):
        # Set `frame - 1` to force reading of `frame`
        return self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame - 1)

    def get_current_frame(self):
        return self.cap.get(cv2.CAP_PROP_POS_FRAMES)

    def play(self):
        start_ts = self.start_frame / self.fps
        end_ts = self.end_frame / self.fps
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
        stream = ffmpeg.input(self.path, **input_kwargs)
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

        self.set_current_frame(self.start_frame)
        while self.cap.isOpened():
            ok, frame_data = self.cap.read()
            if ok:
                audio_data = wave_file.readframes(audio_chunk)
                audio_stream.write(audio_data)
                cv2.imshow("Video", frame_data)
                cv2.waitKey(1)
                # The current frame has just been read and displayed
                # to the user. Exit if that's the end frame.
                current_frame = self.get_current_frame()
                yield current_frame
                if current_frame >= self.end_frame:
                    break
            else:
                break

        wave_file.close()
        p.terminate()
