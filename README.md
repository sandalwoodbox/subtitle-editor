subtitle-editor
===============

Basic usage:

```bash
# Works with srt files
subtitle-editor video.mp4 subtitles.srt

# Can take plaintext files as input
subtitle-editor video.mp4 subtitles.srt --input lyrics.txt
```

![Demo image](https://github.com/sandalwoodbox/subtitle-editor/blob/main/demo.gif?raw=true)

## Setup (Mac OS)

### Install dependencies

1. Install [Homebrew](https://brew.sh/)
2. Install system dependencies (get a coffee while this runs)
   ```bash
   brew install ffmpeg pyenv portaudio
   ```
   Read the final output of this command and do any required follow-up steps.
3. Install python 3
   ```bash
   pyenv install 3.7.11  # Or another python 3 version
   pyenv global 3.7.11
   ```
4. Update pip (don't skip this)
   ```bash
   pip install -U pip
   ```

### Install subtitle-editor

```bash
pip install subtitle-editor
```

## Using subtitle-editor

The following commands are available within subtitle-editor

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
q         Finish editing subtitles and output results
Ctrl + c  Exit immediately without saving results
?         Display help message
```