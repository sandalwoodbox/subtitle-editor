import curses
from datetime import timedelta

import click
import srt

from .colors import Pairs, setup_colors
from .constants import ONE_FRAME, ONE_SECOND, UNSET_TIME
from .subtitles.srt import SubtitlePad
from .video import VideoWindow

EDITOR_HELP = """
NAVIGATION
<tab>/←/→ Switch between start/end timestamps
↑/↓       Select a subtitle
=/+       Increase the selected timestamp by one frame / 1 sec
-/_       Decrease the selected timestamp by one frame / 1 sec

PLAYBACK
P         Enter / leave playback mode
<space>   In playback mode, set the current timestamp and move to the next one
u         In playback mode, "undo" by moving back one timestamp (does not actually undo the change)
p         In standard mode, play the video between the start/end timestamps of the current subtitle

OTHER
q         Finish editing subtitles and output results
Ctrl + c  Exit immediately without saving results
?         Display this message
"""

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


def handle_navigation_cmd(cmd, subtitle_pad, video_window=None):
    set_timestamps = False
    if cmd == "KEY_UP":
        subtitle_pad.previous()
        set_timestamps = True
    elif cmd == "KEY_DOWN":
        subtitle_pad.next()
        set_timestamps = True
    elif cmd in ("\t", "KEY_LEFT", "KEY_RIGHT"):
        subtitle_pad.toggle_selected_timestamp()
    elif cmd == "=":
        subtitle_pad.adjust_timestamp(ONE_FRAME)
        set_timestamps = True
    elif cmd == "+":
        subtitle_pad.adjust_timestamp(ONE_SECOND)
        set_timestamps = True
    elif cmd == "-":
        subtitle_pad.adjust_timestamp(-1 * ONE_FRAME)
        set_timestamps = True
    elif cmd == "_":
        subtitle_pad.adjust_timestamp(-1 * ONE_SECOND)
        set_timestamps = True

    if video_window and set_timestamps:
        video_window.set_timestamps(subtitle_pad.get_timestamps())


def display_help(stdscr, video_window, subtitle_pad, help_text):
    stdscr.clear()
    stdscr.addstr(0, 0, EDITOR_HELP)
    stdscr.addstr(
        curses.LINES - 1,
        0,
        "Press any key to continue...".ljust(curses.COLS - 1),
        curses.color_pair(Pairs.STATUS),
    )
    stdscr.getkey()
    stdscr.clear()
    subtitle_pad.should_render = True
    video_window.should_render = True
    stdscr.noutrefresh()


def run_playback_mode(stdscr, video_window, subtitle_pad):
    start, end = timedelta(0), timedelta(
        seconds=video_window.frame_count / video_window.fps
    )
    video_window.set_timestamps((start, end))
    stdscr.nodelay(True)

    cmd = ""
    for frame_num in video_window.play():
        stdscr.addstr(
            curses.LINES - 1,
            0,
            "P: Exit playback  <space>: set timestamp & go to next  u: undo  ?: help".ljust(
                curses.COLS - 1
            ),
            curses.color_pair(Pairs.STATUS),
        )
        subtitle_pad.render()
        curses.doupdate()
        try:
            cmd = stdscr.getkey()
        except curses.error:
            continue

        if cmd in NAVIGATION_COMMANDS:
            # Don't pass a video_window because we don't
            # need to set video timestamps during playback
            handle_navigation_cmd(cmd, subtitle_pad)
        elif cmd == "?":
            stdscr.nodelay(False)
            display_help(stdscr, video_window, subtitle_pad, EDITOR_HELP)
            stdscr.nodelay(True)
        elif cmd == " ":
            subtitle_pad.playback_set_frame(frame_num)
        elif cmd == "u":
            subtitle_pad.playback_undo()
        elif cmd in ("P", "q"):
            break
    stdscr.nodelay(False)
    video_window.set_timestamps(subtitle_pad.get_timestamps())


def run_editor(stdscr, subtitles, video):
    curses.curs_set(0)

    # Set up ANSI colors
    setup_colors()

    video_window = VideoWindow(video, 0)
    video_window.load_frames()
    subtitle_pad = SubtitlePad(
        subtitles, video_window.window.getmaxyx()[0] + 1, curses.LINES - 2, curses.COLS
    )
    subtitle_pad.init_pad()

    video_window.set_timestamps(subtitle_pad.get_timestamps())

    cmd = None

    while cmd != "q":
        stdscr.addstr(
            curses.LINES - 1,
            0,
            "↑/↓/←/→: navigate  +/-: adjust time  p/P: playback ?: help".ljust(
                curses.COLS - 1
            ),
            curses.color_pair(Pairs.STATUS),
        )
        stdscr.noutrefresh()
        subtitle_pad.render()
        video_window.render()
        curses.doupdate()
        cmd = stdscr.getkey()
        if cmd in NAVIGATION_COMMANDS:
            handle_navigation_cmd(cmd, subtitle_pad, video_window=video_window)
        elif cmd == "?":
            display_help(stdscr, video_window, subtitle_pad, EDITOR_HELP)
        elif cmd == "p":
            subtitle_pad.disable()
            subtitle_pad.render()
            start, end = subtitle_pad.get_timestamps()
            start_timestamp = srt.timedelta_to_srt_timestamp(start)
            end_timestamp = srt.timedelta_to_srt_timestamp(end)
            stdscr.addstr(
                curses.LINES - 1,
                0,
                f"Playing video: {start_timestamp} --> {end_timestamp}".ljust(
                    curses.COLS - 1
                ),
                curses.color_pair(Pairs.STATUS),
            )
            stdscr.noutrefresh()
            video_window.set_timestamps(subtitle_pad.get_timestamps())
            for _ in video_window.play():
                curses.doupdate()
            subtitle_pad.enable()
        elif cmd == "P":
            run_playback_mode(stdscr, video_window, subtitle_pad)


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
                for i, line in enumerate(fp)
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
