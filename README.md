subtitle-editor
===============

Basic usage:

```bash
# Works with srt files
subtitle-editor video.mp4 subtitles.srt

# Can take plaintext files as input
subtitle-editor video.mp4 subtitles.srt --input lyrics.txt
```

See the [Tutorial](#tutorial) for details.

![Demo image](https://github.com/sandalwoodbox/subtitle-editor/blob/main/demo.gif?raw=true)

## Setup (Mac OS)

### Install dependencies

1. Install [Homebrew](https://brew.sh/)
2. Install system dependencies (get a coffee while this runs)
   ```bash
   brew install ffmpeg pyenv portaudio
   ```
3. [Finalize your pyenv installation](https://github.com/pyenv/pyenv#homebrew-in-macos) For zsh (standard in newer Macs) this will be:
   ```bash
   echo 'eval "$(pyenv init --path)"' >> ~/.zprofile

   echo 'eval "$(pyenv init -)"' >> ~/.zshrc
   ```
4. Install python 3
   ```bash
   pyenv install 3.7.11  # Or another python 3 version
   pyenv global 3.7.11
   ```
5. Update pip (don't skip this)
   ```bash
   pip install -U pip
   ```

### Install subtitle-editor

```bash
pip install subtitle-editor
```

<a name="tutorial"></a>

## Tutorial: Add subtitles to a video

1. Create a [plain text](https://en.wikipedia.org/wiki/Plain_text) file that contains each subtitle on a separate line. Blank lines will be ignored. For example:

   ```txt
   This is the first line
   This is the second line

   And so on
   ```

2. Import this file into subtitle-editor

   ```bash
   cd /path/to/video/project
   subtitle-editor video.mp4 video.srt --input input.txt
   ```

   The subtitle-editor will pre-render the frames of your video. _Note: if video.srt already exists it will be overwritten._

3. Now you will create a rough cut of the subtitles. The idea here is to get your timestamps more or less right; you'll do a second pass to clean everything up later.

   Type `P` to start playback, then press the spacebar to set the currently-selected timestamp and move to the next one. Keep going until you get to the end.

4. Type `q` to save your work and exit to the terminal. `video.srt` now exists with your rough cut of subtitles!

5. Run subtitle-editor again, but without passing an input. This will allow you to edit the existing subtitle file.

   ```bash
   subtitle-editor video.mp4 video.srt
   ```

6. For each subtitle, type `p` to play the video & audio for that subtitle. Use `↑/↓/←/→` to navigate between subtitles and start/end times. Use `-/_` and `=/+` to modify the times until they are correct.

7. Navigate back to the beginning and type `P` to play back the whole video with subtitles. If there are any issues, type `p` to pause and make adjustments, then press `P` to resume playback.

8. Type `q` to save your work and exit!


## Command Reference

When you are using subtitle-editor, you have the following commands available.

### Navigation

```
<tab>/←/→ Switch between start/end timestamps
↑/↓       Select a subtitle
=/+       Increase the selected timestamp by one frame / 1 sec
-/_       Decrease the selected timestamp by one frame / 1 sec
```


### Playback

```
P         Enter / leave playback mode
<space>   In playback mode, set the current timestamp and move to the next one
u         In playback mode, "undo" by moving back one timestamp (does not
          actually undo the change)
p         In standard mode, play the video between the start/end timestamps
          of the current subtitle
```

### Other

```
q         Save and exit
Ctrl + c  Exit without saving
?         Display help message
```