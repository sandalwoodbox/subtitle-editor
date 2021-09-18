from setuptools import setup

setup(
    name="subtitle-editor",
    version="0.1.0",
    py_modules=["subtitle_editor"],
    install_requires=[
        "click",
        "ffmpeg-python",
        "opencv-python",
        "pyaudio",
        "srt",
        "video-to-ascii",
    ],
    entry_points={
        "console_scripts": [
            "subtitle-editor = subtitle_editor.cli:cli",
        ],
    },
)
