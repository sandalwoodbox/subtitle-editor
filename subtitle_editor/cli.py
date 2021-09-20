import curses

import click
import srt

from .colors import Pairs, setup_colors
from .constants import ONE_FRAME, ONE_SECOND, UNSET_TIME
from .subtitles.srt import SubtitlePad
from .video import VideoWindow

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


def run_editor(stdscr, subtitles, video):
    curses.curs_set(0)

    # Set up ANSI colors
    setup_colors()

    stdscr.addstr(
        curses.LINES - 1,
        0,
        "Enter p, <tab>, +/-, n, d, q, ?".ljust(curses.COLS - 1),
        curses.color_pair(Pairs.STATUS),
    )

    video_window = VideoWindow(video, 0)
    video_window.load_frames()
    subtitle_pad = SubtitlePad(
        subtitles, video_window.window.getmaxyx()[0] + 1, curses.LINES - 2
    )

    video_window.set_timestamps(subtitle_pad.get_timestamps())

    cmd = None

    while cmd != "q":
        stdscr.noutrefresh()
        subtitle_pad.render()
        video_window.render()
        curses.doupdate()
        cmd = stdscr.getkey()
        if cmd == "?":
            message = MODIFY_HELP
        elif cmd == "KEY_UP":
            subtitle_pad.previous()
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd == "KEY_DOWN":
            subtitle_pad.next()
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd in ("\t", "KEY_LEFT", "KEY_RIGHT"):
            subtitle_pad.toggle_selected_timestamp()
        elif cmd == "=":
            subtitle_pad.adjust_timestamp(ONE_FRAME)
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd == "+":
            subtitle_pad.adjust_timestamp(ONE_SECOND)
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd == "-":
            subtitle_pad.adjust_timestamp(-1 * ONE_FRAME)
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd == "_":
            subtitle_pad.adjust_timestamp(-1 * ONE_SECOND)
            video_window.set_timestamps(subtitle_pad.get_timestamps())
        elif cmd == "p":
            start, end = subtitle_pad.get_timestamps()
            video_window.set_timestamps(subtitle_pad.get_timestamps())
            for _ in video_window.play():
                pass
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
