import curses
import math
from datetime import timedelta
from textwrap import TextWrapper

import srt

from ..colors import Pairs
from ..constants import UNSET_TIME, UNSET_FRAME


class SubtitleEntry:
    def __init__(self, subtitle, wrapper, fps):
        self.subtitle = subtitle
        self.wrapper = wrapper
        self.wrapped_content = wrapper.wrap(subtitle.content)
        self.fps = fps

        if subtitle.start == UNSET_TIME:
            self.start_frame = UNSET_FRAME
        else:
            self.start_frame = math.floor(subtitle.start.total_seconds() * fps)
        if subtitle.end == UNSET_TIME:
            self.end_frame = UNSET_FRAME
        else:
            self.end_frame = math.floor(subtitle.end.total_seconds() * fps)

    def nlines(self):
        # Length of an SRT is:
        # - 1 for the number
        # - 1 for the timestamp
        # - 1 for each line of content
        return 2 + len(self.wrapped_content)

    def render(self, pad, is_selected, selected_timestamp, start_line, dim=False):
        default_style = curses.A_NORMAL
        standout_style = curses.A_STANDOUT
        if dim:
            default_style = curses.color_pair(Pairs.DIM)
            standout_style = curses.color_pair(Pairs.DIM_STANDOUT)

        start_style = default_style
        end_style = default_style
        if is_selected:
            if selected_timestamp == "start":
                start_style = standout_style
            else:
                end_style = standout_style
        pad.addstr(start_line, 0, str(self.subtitle.index), default_style)

        start_timestamp = srt.timedelta_to_srt_timestamp(
            max(self.subtitle.start, timedelta(0))
        )
        end_timestamp = srt.timedelta_to_srt_timestamp(
            max(self.subtitle.end, timedelta(0))
        )

        pad.addstr(start_line + 1, 0, start_timestamp, start_style)
        end_of_start = len(start_timestamp)
        pad.addstr(start_line + 1, end_of_start + 1, "-->", default_style)
        pad.addstr(start_line + 1, end_of_start + 5, end_timestamp, end_style)
        pad.addstr(start_line + 2, 0, "\n".join(self.wrapped_content), default_style)

    def set_start(self, frame):
        self.start_frame = max(frame, 0)
        self.subtitle.start = timedelta(seconds=self.start_frame / self.fps)

        # Don't update unset end frames
        if self.end_frame != UNSET_FRAME:
            self.end_frame = max(self.start_frame + 1, self.end_frame)
            self.subtitle.end = timedelta(seconds=self.end_frame / self.fps)

    def set_end(self, frame):
        self.end_frame = max(frame, 1)
        self.subtitle.end = timedelta(seconds=self.end_frame / self.fps)

        self.start_frame = min(self.start_frame, self.end_frame - 1)
        self.subtitle.start = timedelta(seconds=self.start_frame / self.fps)

    def get_start(self):
        return self.start_frame

    def get_end(self):
        return self.end_frame


class SubtitlePad:
    def __init__(self, subtitles, window_start_line, window_end_line, ncols, fps):
        self.wrapper = TextWrapper(width=ncols)
        self.subtitles = [SubtitleEntry(s, self.wrapper, fps) for s in subtitles]
        self.index = 0
        self.selected_timestamp = "start"

        self.window_start_line = window_start_line
        self.window_end_line = window_end_line
        self.displayed_lines = window_end_line - window_start_line
        self.start_line = 0
        self.end_line = self.displayed_lines
        self.ncols = ncols

        self.fps = fps

        self.should_render = True

        self.pad = None
        self.playback_frame = None

    def init_pad(self):
        # Separate function to initialize the curses pad, to simplify testing.
        self.pad = curses.newpad(self.nlines(), self.ncols)

    def nlines(self):
        # The total number of lines is:
        # - number of lines for each subtitle
        # - one line of buffer between subtitles
        # - one full page of empty line after the last subtitle
        return (
            sum(s.nlines() for s in self.subtitles)
            + len(self.subtitles)
            + self.displayed_lines
        )

    def render(self):
        if not self.should_render:
            return

        self.pad.erase()

        # Redraw all subtitles
        start_line = 0
        for index, subtitle in enumerate(self.subtitles):
            # Only dim by default if we're in playback mode
            dim = self.playback_frame is not None
            if index == self.index and self.playback_frame is not None:
                start_frame = subtitle.get_start()
                end_frame = subtitle.get_end()

                # Treat unset as "infinitely" large so that it feels more
                # natural during playback of lyrics
                if end_frame == UNSET_FRAME:
                    end_frame = math.inf

                # Make the selected timestamp dim if it's not in-bounds.
                dim = not (start_frame <= self.playback_frame <= end_frame)
            subtitle.render(
                self.pad,
                index == self.index,
                self.selected_timestamp,
                start_line,
                dim=dim,
            )
            start_line += subtitle.nlines() + 1

        selected_start = (
            sum(s.nlines() for s in self.subtitles[: self.index]) + self.index
        )
        selected_end = selected_start + self.subtitles[self.index].nlines()
        if self.playback_frame is not None:
            # In playback mode, always display the selected subtitle at the top
            self.start_line = selected_start
            self.end_line = self.start_line + self.displayed_lines
        else:
            # In editor mode, only scroll the pad the minimal amount to follow
            # the "cursor"
            if selected_start < self.start_line:
                self.start_line = selected_start
                self.end_line = self.start_line + self.displayed_lines
            elif selected_end > self.end_line:
                self.end_line = selected_end
                self.start_line = selected_end - self.displayed_lines
        self.pad.noutrefresh(
            self.start_line,
            0,
            self.window_start_line,
            0,
            self.window_end_line,
            self.ncols,
        )
        self.should_render = False

    def previous(self):
        if self.index == 0:
            return

        self.index -= 1
        self.should_render = True

    def has_next(self):
        return self.index < len(self.subtitles) - 1

    def next(self):
        if self.has_next():
            self.index += 1
            self.should_render = True

    def toggle_selected_timestamp(self):
        self.selected_timestamp = "start" if self.selected_timestamp == "end" else "end"
        self.should_render = True

    def get_selected_subtitle(self):
        return self.subtitles[self.index]

    def set_frame(self, frame, progress=False):
        subtitle = self.get_selected_subtitle()
        if self.selected_timestamp == "start":
            subtitle.set_start(frame)
            if progress:
                self.selected_timestamp = "end"
        else:
            subtitle.set_end(frame)

        self.should_render = True

    def get_frame(self):
        subtitle = self.get_selected_subtitle()
        if self.selected_timestamp == "start":
            return subtitle.get_start()
        return subtitle.get_end()

    def set_playback_frame(self, frame):
        self.playback_frame = frame

        new_index = self.index

        # Setting playback_frame to None means playback mode is ended
        if frame is None:
            self.should_render = True
            return

        for index, subtitle in enumerate(self.subtitles):
            start_frame = subtitle.get_start()
            # treat unset end as infinite so that it feels more natural during
            # playback of lyrics
            end_frame = subtitle.get_end()
            if end_frame == UNSET_FRAME:
                end_frame = math.inf

            # Select the first index that contains the frame
            if start_frame <= frame <= end_frame:
                new_index = index
                break

            # Or select the first subtitle that starts after the frame
            if start_frame > frame:
                new_index = index
                break

        self.should_render = True
        if new_index != self.index:
            self.selected_timestamp = "start"
            self.index = new_index
