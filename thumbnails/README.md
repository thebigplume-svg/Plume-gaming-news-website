# Shorts thumbnail generator

Turns a folder of 9:16 Shorts into eye-catching 1080×1920 thumbnails in one
command. For each video it:

1. samples ~24 frames with ffmpeg and scores them (sharpness, colour,
   exposure, contrast) — black/blurry/washed-out frames are skipped,
2. punches up the best frame (contrast, saturation, sharpening, glow,
   vignette, darker band behind the text),
3. stamps a huge outlined headline with one word in the accent colour, an
   optional red sticker ("BREAKING", "LEAKED"…) and the Plume logo,
4. saves `<video name>.jpg` (well under YouTube's 2 MB limit).

Text sits in the upper-middle of the frame so it isn't covered by the
Shorts UI (title/caption at the bottom, buttons on the right).
Landscape clips get a blurred 9:16 backdrop instead of being cropped hard.

## Setup

Needs `ffmpeg` and Python 3 with Pillow + numpy:

```bash
pip install pillow numpy        # ffmpeg: brew install ffmpeg / apt install ffmpeg
```

For the best look, drop a bold condensed font such as **Anton** into
`thumbnails/fonts/`.

## Use

```bash
# every video in a folder -> ~/Shorts/thumbnails/*.jpg
python3 thumbnails/make_thumbnails.py ~/Shorts

# one video with a custom headline + sticker
python3 thumbnails/make_thumbnails.py clip.mp4 --title "GTA 6 *DELAYED* again" --badge "Breaking"
```

Re-running only makes thumbnails for new videos (pass `--force` to redo
all). `--keep-candidates` also saves the top 5 frames per video so you can
see what it chose from.

## Headlines

Picked automatically, in this order:

1. `titles.json` in the video folder:
   ```json
   { "switch-price.mp4": { "title": "Switch 2 price *LEAKED*?!", "badge": "Breaking" },
     "boss.mp4": "This boss is *IMPOSSIBLE*" }
   ```
2. a text file with the same name as the video (`boss.txt`): line 1 is the
   headline, optional line 2 the sticker,
3. the file name (`gta-6-trailer-delayed.mp4` → GTA 6 TRAILER DELAYED).

Wrap words in `*asterisks*` to colour them; otherwise the longest word is
highlighted. Short punchy headlines (3–6 words) come out biggest.

## Customising

Colours, logo, text zone, saturation etc. live in `thumbnails/config.json`.
