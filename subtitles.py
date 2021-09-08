import os
import sys
import tempfile
from datetime import timedelta

import click
import ffmpeg
import srt
import vlc
from video_to_ascii.video_engine import VideoEngine

MODIFY_HELP = """
p Play the video between the start/end timestamps
s Select the start timestamp
e Select the end timestamp
+ Increase the selected timestamp by one frame
- Decrease the selected timestamp by one frame
n Move to the next subtitle
d Finish editing subtitles and output results
q Abort without outputting results
? Display this message
"""

ONE_FRAME = timedelta(milliseconds=40)
SELECTED_STYLE = {"fg": "black", "bg": "white"}


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


def modify_sub(subtitle, video):
    cmd = None
    selected = "start"
    message = None

    while cmd != "n":
        click.clear()
        if selected == "start":
            start_kwargs = SELECTED_STYLE
            end_kwargs = {}
        else:
            start_kwargs = {}
            end_kwargs = SELECTED_STYLE
        click.echo(subtitle.index)
        click.secho(
            srt.timedelta_to_srt_timestamp(subtitle.start), nl=False, **start_kwargs
        )
        click.echo(" --> ", nl=False)
        click.secho(srt.timedelta_to_srt_timestamp(subtitle.end), **end_kwargs)
        click.echo(f"{subtitle.content}\n")

        if message:
            click.echo(f"{message}\n")
            message = None

        click.echo("Enter p, s/e, +/-, n, q, ?")
        cmd = click.getchar()
        if cmd == "?":
            click.echo(MODIFY_HELP)
        elif cmd == "p":
            play(subtitle.start, subtitle.end, video)
        elif cmd == "s":
            selected = "start"
        elif cmd == "e":
            selected = "end"
        elif cmd == "\t":
            selected = "start" if selected == "end" else "end"
        elif cmd == "+" or cmd == "=":
            setattr(subtitle, selected, getattr(subtitle, selected) + ONE_FRAME)
        elif cmd == "-" or cmd == "_":
            setattr(subtitle, selected, getattr(subtitle, selected) - ONE_FRAME)
        elif cmd == "n":
            pass
        elif cmd == "d":
            return True
        elif cmd == "q":
            sys.exit(0)
        else:
            message = f"Unknown command: {cmd}"


@click.command()
@click.argument("srt_in", type=click.File("r"))
@click.argument("video", type=click.Path(exists=True))
def modify_subs(srt_in, video):
    subtitles = srt.parse(srt_in)
    for subtitle in subtitles:
        done = modify_sub(subtitle, video)
        if done:
            break
    click.echo(srt.compose(subtitles))


if __name__ == "__main__":
    modify_subs()
