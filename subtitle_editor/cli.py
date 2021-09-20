import curses
from datetime import timedelta

import click
import srt

from .colors import Pairs, setup_colors
from .constants import ONE_FRAME, ONE_SECOND, UNSET_TIME
from .subtitles.srt import SubtitlePad
from .video import VideoWindow

MODIFY_HELP = """
P         Enter playback mode to set timestamps while watching
p         Play the video between the start/end timestamps
<tab>/←/→ Switch between start/end timestamps
↑/↓       Select a subtitle
=/+       Increase the selected timestamp by one frame / 1 sec
-/_       Decrease the selected timestamp by one frame / 1 sec
q         Finish editing subtitles and output results
Ctrl + C  Exit without saving results
?         Display this message
"""


def run_editor(stdscr, subtitles, video):
    curses.curs_set(0)

    # Set up ANSI colors
    setup_colors()

    video_window = VideoWindow(video, 0)
    video_window.load_frames()
    subtitle_pad = SubtitlePad(
        subtitles, video_window.window.getmaxyx()[0] + 1, curses.LINES - 2
    )

    video_window.set_timestamps(subtitle_pad.get_timestamps())

    cmd = None

    while cmd != "q":
        stdscr.addstr(
            curses.LINES - 1,
            0,
            "Enter p/P, <tab>, +/-, ↑/↓, q, ?".ljust(curses.COLS - 1),
            curses.color_pair(Pairs.STATUS),
        )
        stdscr.noutrefresh()
        subtitle_pad.render()
        video_window.render()
        curses.doupdate()
        cmd = stdscr.getkey()
        if cmd == "?":
            stdscr.clear()
            stdscr.addstr(0, 0, MODIFY_HELP)
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
            video_window.set_timestamps(subtitle_pad.get_timestamps())
            for _ in video_window.play():
                pass
        elif cmd == "P":
            start, end = timedelta(0), timedelta(
                seconds=video_window.frame_count / video_window.fps
            )
            video_window.set_timestamps((start, end))
            stdscr.nodelay(True)

            subtitle_pad.start_playback()
            subtitle_pad.render()
            stdscr.addstr(
                curses.LINES - 1,
                0,
                "Press <space> to go to the next timestamp, u to undo, or q to stop".ljust(
                    curses.COLS - 1
                ),
                curses.color_pair(Pairs.STATUS),
            )
            selected_timestamp = "start"
            selected_subtitle = 0
            play_cmd = ""
            for frame_num in video_window.play():
                subtitle_pad.render()
                curses.doupdate()
                try:
                    play_cmd = stdscr.getkey()
                except curses.error:
                    continue

                if play_cmd == " ":
                    done = subtitle_pad.playback_mark(frame_num)
                    if done:
                        break
                elif play_cmd == "u":
                    subtitle_pad.playback_undo()
                elif play_cmd == "q":
                    break
            stdscr.nodelay(False)
            subtitle_pad.end_playback()
            video_window.set_timestamps(subtitle_pad.get_timestamps())


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
