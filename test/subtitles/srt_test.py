from datetime import timedelta

from subtitle_editor.subtitles.srt import SubtitlePad

from ..factories import SubtitleFactory


def test_playback_set_frame__start_to_end():
    subtitles = [SubtitleFactory() for i in range(1)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    _, old_end = pad.get_timestamps()
    pad.playback_set_frame(1)
    new_start, new_end = pad.get_timestamps()
    assert new_end == old_end
    assert new_start == timedelta(milliseconds=40)
    assert pad.index == 0
    assert pad.selected_timestamp == "end"


def test_playback_set_frame__end_to_next_start():
    subtitles = [SubtitleFactory() for i in range(2)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    pad.selected_timestamp = "end"
    old_start, _ = pad.get_timestamps()
    pad.playback_set_frame(1)
    new_start, new_end = pad.get_timestamps(0)
    assert new_start == old_start
    assert new_end == timedelta(milliseconds=40)
    assert pad.index == 1
    assert pad.selected_timestamp == "start"


def test_playback_set_frame__end_to_next_start__at_end():
    subtitles = [SubtitleFactory() for i in range(1)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    pad.selected_timestamp = "end"
    old_start, _ = pad.get_timestamps()
    pad.playback_set_frame(1)
    new_start, new_end = pad.get_timestamps(0)
    assert new_start == old_start
    assert new_end == timedelta(milliseconds=40)
    assert pad.index == 0
    assert pad.selected_timestamp == "end"


def test_playback_undo__end_to_start():
    subtitles = [SubtitleFactory() for i in range(1)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    pad.selected_timestamp = "end"
    old_start, old_end = pad.get_timestamps()
    pad.playback_undo()
    new_start, new_end = pad.get_timestamps()
    assert (new_start, new_end) == (old_start, old_end)
    assert pad.index == 0
    assert pad.selected_timestamp == "start"


def test_playback_undo__start_to_prev_end():
    subtitles = [SubtitleFactory() for i in range(2)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    pad.index = 1
    pad.selected_timestamp = "start"
    old_start, old_end = pad.get_timestamps()
    pad.playback_undo()
    new_start, new_end = pad.get_timestamps(1)
    assert (new_start, new_end) == (old_start, old_end)
    assert pad.index == 0
    assert pad.selected_timestamp == "end"


def test_playback_undo__start_to_prev_end__at_start():
    subtitles = [SubtitleFactory() for i in range(1)]

    pad = SubtitlePad(subtitles, 20, 80, 80)
    old_start, old_end = pad.get_timestamps()
    pad.playback_undo()
    new_start, new_end = pad.get_timestamps()
    assert (new_start, new_end) == (old_start, old_end)
    assert pad.index == 0
    assert pad.selected_timestamp == "start"
