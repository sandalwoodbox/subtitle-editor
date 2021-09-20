subtitle-editor
===============

Basic usage:

```bash
# Works with srt files
subtitle-editor video.mp4 subtitles.srt

# Can take plaintext files as input
subtitle-editor video.mp4 subtitles.srt --input lyrics.txt
```

![alt text](https://github.com/sandalwoodbox/subtitle-editor/blob/main/demo.gif?raw=true)

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