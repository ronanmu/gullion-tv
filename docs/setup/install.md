# Install

[Documentation](../README.md) › Install

## What the box needs

- An enigma2 box on **OpenATV 6.4** (Python 2.7) or **OpenATV 7.x** (Python 3). It's been tried on a Formuler F1
  on 6.4 and a GigaBlue UHD Quad 4K on 7.6; see Status in the [main README](../../README.md#status).
- Gullion TV is designed at 1920×1080 and fits itself to the skin's size, so it works with HD skins such as
  MetrixHD at 1280×720 as well as full-HD and 4K ones. Text is sharpest with a full-HD skin.
- **Optional:**
  - a USB or eSATA drive for recordings;
  - **ffmpeg**, for [recording pictures](#recording-pictures);
  - a **Plex** server with film and TV libraries. Streaming from a Plex server outside the home needs Plex Pass on
    the server owner's account.

## Copying it to the box

From a computer on the same network as the box, with SSH access to it as root:

```sh
BOX=192.168.1.50 scripts/deploy.sh
```

This:
1. copies `plugin/GullionTV` to `/usr/lib/enigma2/python/Plugins/Extensions/GullionTV`;
2. checks every file compiles with the box's own Python before swapping it in;
3. installs the sample `webcams.yaml` the first time, and copies any pictures in `config/images/`;
4. restarts enigma2 and saves a screenshot from OpenWebif into `screenshots/`.

Without the script, copy the `plugin/GullionTV` folder to that place yourself and restart enigma2.

Deploying never overwrites the box's copy of `webcams.yaml`. To replace it, use
`FORCE_CONFIG=1 BOX=... scripts/deploy.sh`.

## Channel lists

Set up the channel lists in the box's own menus as usual: scan Saorview and Freesat, and put the channels that get
watched into one list at the top, so it's the first list the [TV Guide](../features/tv-guide.md) shows. Channel
numbers in Gullion TV follow the box's own numbering.

## Recording pictures

Install ffmpeg on the box once:

```sh
opkg update && opkg install ffmpeg
```

Gullion TV then saves one picture from each recording when it finishes (a 768×432 frame, about a tenth of the way
in, saved next to the recording as `<recording>.ts.jpg`). It catches up on older ones when Recordings opens. It
runs at the lowest priority, so watching TV isn't slowed. Without ffmpeg, recordings show their channel's logo.
