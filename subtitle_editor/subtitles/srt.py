import curses
from datetime import timedelta
from textwrap import TextWrapper

import srt

from ..constants import ONE_FRAME


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

    def render(self, pad, is_selected, selected_timestamp, start_line):
        index_style = curses.A_NORMAL
        start_style = curses.A_NORMAL
        end_style = curses.A_NORMAL
        if is_selected:
            if selected_timestamp == "start":
                start_style = curses.A_STANDOUT
            else:
                end_style = curses.A_STANDOUT
        pad.addstr(start_line, 0, str(self.subtitle.index), index_style)

        start_timestamp = srt.timedelta_to_srt_timestamp(self.subtitle.start)
        end_timestamp = srt.timedelta_to_srt_timestamp(self.subtitle.end)

        pad.addstr(start_line + 1, 0, start_timestamp, start_style)
        end_of_start = len(start_timestamp)
        pad.addstr(start_line + 1, end_of_start + 1, "-->")
        pad.addstr(start_line + 1, end_of_start + 5, end_timestamp, end_style)
        pad.addstr(start_line + 2, 0, "\n".join(self.wrapped_content))

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

    def get_timestamps(self):
        return self.subtitle.start, self.subtitle.end


class SubtitlePad:
    def __init__(self, subtitles):
        self.wrapper = TextWrapper(width=self.ncols())
        self.subtitles = [SubtitleEntry(s, self.wrapper) for s in subtitles]
        self.selected_subtitle = 0
        self.selected_timestamp = "start"
        self.pad = curses.newpad(self.nlines(), self.ncols())

        self.start_line = 0
        self.end_line = curses.LINES - 2
        self.displayed_lines = self.end_line

    def nlines(self):
        # The total number of lines is:
        # - number of lines for each subtitle
        # - one line of buffer between subtitles (but not after the last one)
        return sum(s.nlines() for s in self.subtitles) + len(self.subtitles) - 1

    def ncols(self):
        return curses.COLS

    def render(self):
        self.pad.clear()
        start_line = 0
        for i, subtitle in enumerate(self.subtitles):
            subtitle.render(
                self.pad,
                i == self.selected_subtitle,
                self.selected_timestamp,
                start_line,
            )
            start_line += subtitle.nlines() + 1

    def refresh(self):
        selected_start = (
            sum(s.nlines() for s in self.subtitles[: self.selected_subtitle])
            + self.selected_subtitle
        )
        selected_end = selected_start + self.subtitles[self.selected_subtitle].nlines()

        if selected_start < self.start_line:
            self.start_line = selected_start
            self.end_line = self.start_line + self.displayed_lines
        elif selected_end > self.end_line:
            self.end_line = selected_end
            self.start_line = selected_end - self.displayed_lines
        self.pad.refresh(self.start_line, 0, 0, 0, curses.LINES - 2, self.ncols() - 1)

    def previous(self):
        if self.selected_subtitle > 0:
            self.selected_subtitle -= 1

    def next(self):
        if self.selected_subtitle < len(self.subtitles) - 1:
            self.selected_subtitle += 1

    def toggle_selected_timestamp(self):
        self.selected_timestamp = "start" if self.selected_timestamp == "end" else "end"

    def adjust_timestamp(self, timedelta):
        subtitle = self.subtitles[self.selected_subtitle]
        if self.selected_timestamp == "start":
            subtitle.adjust_start(timedelta)
        else:
            subtitle.adjust_end(timedelta)

    def get_timestamps(self):
        subtitle = self.subtitles[self.selected_subtitle]
        return subtitle.get_timestamps()
