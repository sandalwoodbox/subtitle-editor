import curses
import os
import sys
import tempfile

import click
import ffmpeg
import srt
from video_to_ascii.video_engine import VideoEngine

from .constants import ONE_FRAME, ONE_SECOND, UNSET_TIME
from .subtitles.srt import SubtitlePad

MODIFY_HELP = """
p     Play the video between the start/end timestamps
<tab> Select the start timestamp
e     Select the end timestamp
=/+   Increase the selected timestamp by one frame / 1 sec
-/_   Decrease the selected timestamp by one frame / 1 sec
n     Move to the next subtitle
d     Finish editing subtitles and output results
q     Abort without outputting results
?     Display this message
"""

INTERFACE_STYLE = 1


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


def run_editor(stdscr, subtitles, video):
    curses.curs_set(0)
    curses.init_pair(INTERFACE_STYLE, curses.COLOR_WHITE, curses.COLOR_BLUE)
    stdscr.addstr(
        curses.LINES - 1,
        0,
        "Enter p, <tab>, +/-, n, d, q, ?".ljust(curses.COLS - 1),
        curses.color_pair(INTERFACE_STYLE),
    )

    pad = SubtitlePad(subtitles)

    cmd = None

    while cmd != "q":
        stdscr.refresh()
        pad.render()
        pad.refresh()
        cmd = stdscr.getkey()
        if cmd == "?":
            message = MODIFY_HELP
        elif cmd == "KEY_UP":
            pad.previous()
        elif cmd == "KEY_DOWN":
            pad.next()
        elif cmd == "\t":
            pad.toggle_selected_timestamp()
        elif cmd == "=":
            pad.adjust_timestamp(ONE_FRAME)
        elif cmd == "+":
            pad.adjust_timestamp(ONE_SECOND)
        elif cmd == "-":
            pad.adjust_timestamp(-1 * ONE_FRAME)
        elif cmd == "_":
            pad.adjust_timestamp(-1 * ONE_SECOND)
        elif cmd == "p":
            start, end = pad.get_timestamps()
            play(start, end, video)
        else:
            message = f"Unknown command: {cmd}"


@click.command()
@click.argument("subs_in", type=click.File("r"))
@click.argument("video", type=click.Path(exists=True))
@click.option("-o", "--output", "srt_out", required=True, type=click.File("w"))
def cli(subs_in, video, srt_out):
    try:
        subtitles = list(srt.parse(subs_in))
    except srt.SRTParseError:
        # Assume each line is a subtitle that needs a time associated
        subs_in.seek(0)
        subtitles = [
            srt.Subtitle(i + 1, UNSET_TIME, UNSET_TIME, line)
            for i, line in enumerate(subs_in)
        ]

    curses.wrapper(run_editor, subtitles, video)
    srt_out.write(srt.compose(subtitles))
