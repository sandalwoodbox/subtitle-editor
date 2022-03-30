import curses
import math
from datetime import timedelta

import click
import srt

from .colors import Pairs, setup_colors
from .constants import UNSET_TIME
from .subtitles.srt import SubtitlePad
from .video import Video

EDITOR_HELP = """
NAVIGATION
<tab>/←/→ Switch between start/end timestamps
↑/↓       Select a subtitle
=/+       Increase the selected timestamp by one frame / 1 sec
-/_       Decrease the selected timestamp by one frame / 1 sec

PLAYBACK
P         Enter / leave playback mode
<space>   In playback mode, set the current timestamp and move to the next one
p         In standard mode, play the video between the start/end timestamps of the current subtitle

OTHER
q         Save and exit
Ctrl + c  Exit without saving
?         Display this message
"""

TIMESTAMP_STRING = "00:00:00,000 --> 00:00:00,000"
STANDARD_STATUS_BAR = "↑/↓/←/→: navigate  +/-: adjust time  p/P: playback ?: help"
STANDARD_STATUS_BAR_SHORT = "↑/↓/←/→   +/-   p/P  ?: help"
PLAYBACK_STATUS_BAR = (
    "p: pause  <space>: set & go to next  <tab>: toggle start/end  ?: help"
)
PLAYBACK_STATUS_BAR_SHORT = "p  <space>  <tab>  ?: help"

NAVIGATION_COMMANDS = frozenset(
    (
        "KEY_UP",
        "KEY_DOWN",
        "\t",
        "KEY_LEFT",
        "KEY_RIGHT",
        "=",
        "+",
        "-",
        "_",
    )
)

TOGGLE_COMMANDS = frozenset(
    (
        "\t",
        "KEY_LEFT",
        "KEY_RIGHT",
    )
)


def handle_navigation_cmd(cmd, subtitle_pad, video):
    if cmd == "KEY_UP":
        subtitle_pad.previous()
    elif cmd == "KEY_DOWN":
        subtitle_pad.next()
    elif cmd in TOGGLE_COMMANDS:
        subtitle_pad.toggle_selected_timestamp()
    elif cmd == "=":
        subtitle_pad.set_frame(subtitle_pad.get_frame() + 1)
    elif cmd == "+":
        subtitle_pad.set_frame(subtitle_pad.get_frame() + math.floor(subtitle_pad.fps))
    elif cmd == "-":
        subtitle_pad.set_frame(subtitle_pad.get_frame() - 1)
    elif cmd == "_":
        subtitle_pad.set_frame(subtitle_pad.get_frame() - math.floor(subtitle_pad.fps))

    video.display_frame(subtitle_pad.get_frame())


def display_help(stdscr, video, subtitle_pad, help_text):
    stdscr.erase()
    stdscr.addstr(0, 0, EDITOR_HELP)
    stdscr.addstr(
        curses.LINES - 1,
        0,
        "Press any key to continue...".ljust(curses.COLS - 1),
        curses.color_pair(Pairs.STATUS),
    )
    stdscr.getkey()
    stdscr.erase()
    subtitle_pad.should_render = True
    video.should_render = True
    stdscr.noutrefresh()


def run_playback_mode(stdscr, video, subtitle_pad, start_frame, end_frame):
    stdscr.nodelay(True)
    status_bar = (
        PLAYBACK_STATUS_BAR
        if curses.COLS >= len(PLAYBACK_STATUS_BAR)
        else PLAYBACK_STATUS_BAR_SHORT
    )
    stdscr.addstr(
        curses.LINES - 1,
        0,
        status_bar.ljust(curses.COLS - 1),
        curses.color_pair(Pairs.STATUS),
    )

    cmd = ""
    for frame_num in video.play(start_frame, end_frame):

        current_ts = timedelta(seconds=frame_num / video.fps)
        stdscr.addstr(
            1,
            0,
            srt.timedelta_to_srt_timestamp(current_ts),
        )
        subtitle_pad.set_playback_frame(frame_num)
        subtitle_pad.render()
        curses.doupdate()

        try:
            cmd = stdscr.getkey()
        except curses.error:
            continue

        if cmd == "?":
            stdscr.nodelay(False)
            display_help(stdscr, video, subtitle_pad, EDITOR_HELP)
            stdscr.nodelay(True)
        elif cmd == " ":
            subtitle_pad.set_frame(frame_num, progress=True)
        elif cmd in TOGGLE_COMMANDS:
            # Allow toggling so that users can move on from a start
            # timestamp without setting it.
            subtitle_pad.toggle_selected_timestamp()
        elif cmd in ("P", "p", "q"):
            break

    stdscr.nodelay(False)
    video.set_current_frame(subtitle_pad.get_frame())
    subtitle_pad.set_playback_frame(None)

    stdscr.addstr(
        1,
        0,
        " " * curses.COLS,
    )


def run_editor(stdscr, subtitles, video_path):
    curses.curs_set(0)
    min_cols = 1 + max(
        len(STANDARD_STATUS_BAR_SHORT),
        len(PLAYBACK_STATUS_BAR_SHORT),
        len(TIMESTAMP_STRING),
    )
    if curses.COLS < min_cols:
        raise click.ClickException(
            f"Window must be at least {min_cols} columns wide (currently {curses.COLS})"
        )

    # Set up ANSI colors
    setup_colors()

    video = Video(video_path)
    subtitle_pad = SubtitlePad(
        subtitles, 2, curses.LINES - 2, curses.COLS, fps=video.fps
    )
    subtitle_pad.init_pad()

    video.set_current_frame(subtitle_pad.get_frame())

    cmd = None

    while cmd != "q":
        status_bar = (
            STANDARD_STATUS_BAR
            if curses.COLS >= len(STANDARD_STATUS_BAR)
            else STANDARD_STATUS_BAR_SHORT
        )
        stdscr.addstr(
            curses.LINES - 1,
            0,
            status_bar.ljust(curses.COLS - 1),
            curses.color_pair(Pairs.STATUS),
        )
        stdscr.noutrefresh()
        subtitle_pad.render()
        curses.doupdate()
        cmd = stdscr.getkey()
        if cmd in NAVIGATION_COMMANDS:
            handle_navigation_cmd(cmd, subtitle_pad, video)
        elif cmd == "?":
            display_help(stdscr, video, subtitle_pad, EDITOR_HELP)
        elif cmd == "p":
            # Play just the video behind the current subtitle
            subtitle = subtitle_pad.get_selected_subtitle()
            run_playback_mode(
                stdscr,
                video,
                subtitle_pad,
                start_frame=subtitle.get_start(),
                end_frame=subtitle.get_end(),
            )
        elif cmd == "P":
            # Start at the current subtitle and continue to the
            # end of the video
            subtitle = subtitle_pad.get_selected_subtitle()
            run_playback_mode(
                stdscr,
                video,
                subtitle_pad,
                start_frame=subtitle.get_start(),
                end_frame=video.frame_count - 1,
            )


@click.command()
@click.argument("video", type=click.Path(exists=True))
@click.argument("subtitles", type=click.Path())
@click.option("-i", "--input", "input_", type=click.Path(exists=True))
def cli(video, subtitles, input_):
    if input_:
        # For plain-input files, each line is a subtitle that needs a time associated
        with open(input_, "r") as fp:
            subs = [
                srt.Subtitle(i + 1, UNSET_TIME, UNSET_TIME, line)
                for i, line in enumerate(filter(lambda l: l.strip(), fp))
            ]
    else:
        with open(subtitles, "r") as fp:
            try:
                subs = list(srt.parse(fp))
            except srt.SRTParseError:
                raise click.ClickException("Could not parse srt file.")

    curses.wrapper(run_editor, subs, video)

    with open(subtitles, "w") as fp:
        fp.write(srt.compose(subs))
