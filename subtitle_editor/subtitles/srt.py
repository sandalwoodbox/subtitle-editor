import curses
from datetime import timedelta
from textwrap import TextWrapper

import srt

from ..colors import Pairs
from ..constants import ONE_FRAME, UNSET_TIME


class SubtitleEntry:
    def __init__(self, subtitle, wrapper):
        self.subtitle = subtitle
        self.wrapper = wrapper
        self.wrapped_content = wrapper.wrap(subtitle.content)

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

    def adjust_start(self, adjustment):
        self.subtitle.start += adjustment
        if self.subtitle.start < timedelta(0):
            self.subtitle.start = timedelta(0)
        if self.subtitle.end <= self.subtitle.start:
            self.subtitle.end = self.subtitle.start + ONE_FRAME

    def adjust_end(self, timedelta):
        self.subtitle.end += timedelta
        if self.subtitle.end < ONE_FRAME:
            self.subtitle.end = ONE_FRAME
        if self.subtitle.start >= self.subtitle.end:
            self.subtitle.start = self.subtitle.end - ONE_FRAME

    def set_start(self, timedelta):
        self.subtitle.start = timedelta

    def set_end(self, timedelta):
        self.subtitle.end = timedelta

    def get_timestamps(self):
        return self.subtitle.start, self.subtitle.end


class SubtitlePad:
    def __init__(self, subtitles, window_start_line, window_end_line, ncols):
        self.ncols = ncols
        self.wrapper = TextWrapper(width=ncols)
        self.subtitles = [SubtitleEntry(s, self.wrapper) for s in subtitles]
        self.index = 0
        self.selected_timestamp = "start"

        self.window_start_line = window_start_line
        self.window_end_line = window_end_line
        self.displayed_lines = window_end_line - window_start_line
        self.start_line = 0
        self.end_line = self.displayed_lines

        self.should_render = True

        self.pad = None
        self.playback_timestamp = None

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
        for i, subtitle in enumerate(self.subtitles):
            # Only dim by default if we're in playback mode
            dim = self.playback_timestamp is not None
            if i == self.index and self.playback_timestamp is not None:
                start_ts, end_ts = subtitle.get_timestamps()

                # Treat unset as "infinitely" large so that it feels more
                # natural during playback of lyrics
                if end_ts == UNSET_TIME:
                    end_ts = timedelta.max

                # Make the selected timestamp dim if it's not in-bounds.
                dim = not (start_ts <= self.playback_timestamp <= end_ts)
            subtitle.render(
                self.pad,
                i == self.index,
                self.selected_timestamp,
                start_line,
                dim=dim,
            )
            start_line += subtitle.nlines() + 1

        selected_start = (
            sum(s.nlines() for s in self.subtitles[: self.index]) + self.index
        )
        selected_end = selected_start + self.subtitles[self.index].nlines()
        if self.playback_timestamp is not None:
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
            self.ncols - 5,
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

    def adjust_timestamp(self, timedelta):
        subtitle = self.subtitles[self.index]
        if self.selected_timestamp == "start":
            subtitle.adjust_start(timedelta)
        else:
            subtitle.adjust_end(timedelta)
        self.should_render = True

    def set_timestamp(self, timedelta):
        subtitle = self.subtitles[self.index]
        if self.selected_timestamp == "start":
            subtitle.set_start(timedelta)
        else:
            subtitle.set_end(timedelta)
        self.should_render = True

    def get_timestamps(self, index=None):
        if index is None:
            index = self.index
        subtitle = self.subtitles[index]
        return subtitle.get_timestamps()

    def playback_set_frame(self, frame_num):
        self.set_timestamp(frame_num * ONE_FRAME)
        if self.selected_timestamp == "start":
            self.selected_timestamp = "end"
            self.should_render = True
        elif self.index < len(self.subtitles) - 1:
            self.selected_timestamp = "start"
            self.index += 1
            self.should_render = True

    def playback_set_timestamp(self, timestamp):
        if timestamp is None and self.playback_timestamp is None:
            return

        if timestamp is None or self.playback_timestamp is None:
            self.should_render = True
            self.playback_timestamp = timestamp
            return

        start_ts, end_ts = self.get_timestamps()

        # Treat unset as "infinitely" large so that it feels more
        # natural during playback of lyrics
        if end_ts == UNSET_TIME:
            end_ts = timedelta.max
        old_in_bounds = start_ts <= self.playback_timestamp <= end_ts
        new_in_bounds = start_ts <= timestamp <= end_ts
        if old_in_bounds != new_in_bounds:
            self.should_render = True
        self.playback_timestamp = timestamp
