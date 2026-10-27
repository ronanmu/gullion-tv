# Gullion TV for OpenATV 6.4

A simplified, large-text home screen for enigma2 on a Formuler F1 (OpenATV 6.4, Python 2.7, 1920x1080).

## What it does so far

- MENU on the remote opens **Gullion TV** instead of the stock menu.
- Home shows the date and clock, a live picture of the current channel with now and next, and four cards:
  Watch TV (red), TV guide (green), Watch again (yellow) and Webcams (blue), in remote order.
  The matching colour button opens each card directly.
- **Settings** (press down from the cards) asks for the Tech Support PIN, then opens the stock OpenATV menu.
- **TV guide** (green): the selected channel's picon, programme details and the live picture on top, a day bar, and a two-hour grid of six
  channels. Arrows move, CH +/- pages, red/green jump a day, yellow switches channel list, blue returns to now.
  OK watches a programme that's on now, or offers to record a later one. REC records, INFO shows full details.
  Each time it opens, the guide checks the recording drive (mounted, writable, at least 2 GB free). If the box
  can't record, the REC hint and record options go and REC explains why; under 10 GB it warns that space is low.
- **Channel banner** over live TV: picon, channel number and name, HD or SD, satellite (with position) or
  terrestrial, a Recording badge while anything is recording, signal strength, and now/next with time left.
  It replaces the skin's own banner, so it still appears on every channel change and hides as usual.
- **Webcams** (blue): tiles for each camera in `/etc/enigma2/gulliontv/webcams.yaml`, with a picture, its name and
  whether it's live (and, for churchservices.tv, the next service). OK plays it full screen; BACK puts the previous
  channel back. Pages are checked in the background, so the grid shows straight away.
- **Watch again** (yellow), subtitled "Recorded TV & Plex" once Plex is set up: Continue watching (Plex and
  part-watched recordings, most recent first), Recently added to Plex, Recorded TV, then Browse: Films, TV
  programmes and All recordings. Plex tiles carry a Plex badge and use landscape art (an episode's still, a film's
  background), falling back to the poster at the left of the tile. Recordings show a frame from the recording with
  the channel's picon in the corner (made with ffmpeg if it's installed), or the picon on its own. Recordings play
  in the box's player; RED in All recordings moves one to the recycle bin.
- **Films** and **TV programmes**: Plex posters, 16 a page, A to Z or newest first (GREEN), everything or unwatched
  only (YELLOW), with Watched and "8 to watch" badges. Opening a film or programme, and playing from Plex, come next.

## Layout

```
plugin/GullionTV/        the enigma2 plugin (copied to /usr/lib/enigma2/python/Plugins/Extensions/GullionTV)
  plugin.py              plugin descriptors: session-start hook and the Plugins menu entry
  hook.py                redirects MENU to Gullion TV and keeps the stock menu for Tech Support
  settings.py            the box settings: on/off, channel banner, Tech Support PIN
  setup.py               Tech Support settings screen
  home.py                the Home screen
  watchagain.py          Watch again and the All recordings grid (recordings and Plex together)
  theme.py               shared colours
  images/                small icons (rec_clock.png marks recordings in the guide)
  ui/                    shared building blocks
    tiles.py             picture tiles for Watch again, All recordings and the Plex views
    popups.py            themed choice and programme-details pop-ups
    pin.py               PIN prompts, including choosing the Tech Support PIN on first use
    placeholder.py       stand-in screen for parts still to come
    background.py        runs network and disk work off the screen thread
  tv/                    live TV
    guide.py             the TV guide
    epg.py               channel lists, programme data, record timers and channel switching
    picon.py             finds the picon (channel logo) file for any channel
    infobar.py           the channel banner, swapped in for the skin's InfoBar at start-up
    converter.py         GullionServiceInfo skin converter: Delivery, Number, IsHD, Remaining
    serviceinfo.py       HD, satellite/terrestrial and channel numbers from service references
  recordings/            the box's own recordings
    store.py             reads recordings and resume points, checks the drive, deletes to the recycle bin
    thumbnails.py        a frame from each recording, via ffmpeg, saved as <recording>.ts.jpg
  plex/
    client.py            a small Plex client (Python 2.7): linking, Home users, servers, libraries, artwork
    setup.py             Tech Support's Plex setup screens
    library.py           the Films and TV programmes poster views
  webcams/
    screens.py           the Webcams grid and full-screen player
    config.py            reads webcams.yaml (PyYAML if the box has it, otherwise a small built-in reader)
    sources.py           streams, pictures and live status for mcn.live, churchservices.tv, streams and M3U lists
config/webcams.yaml      sample webcams list, installed on the box the first time you deploy
scripts/deploy.sh        copy to the box, restart enigma2, save a screenshot
tools/check.py           offline check against stub enigma2 modules (python3 tools/check.py)
tools/e2stubs.py         stand-ins for the enigma2 modules, used by check.py and preview.py
tools/sample_*.py        made-up channels, Plex replies, recordings and webcam pages for the checks and renders
tools/make_images.py     regenerate images/ from the theme colours (needs Pillow)
tools/preview.py         render sample screenshots to screenshots/samples/ (needs Pillow)
```

The sample renders use the real skin layouts and screen code with sample data. Fonts and the
live TV picture are approximations of what the box draws.

## Deploy

```sh
BOX=192.168.1.50 scripts/deploy.sh
```

## Webcams

Edit `/etc/enigma2/gulliontv/webcams.yaml` on the box (over SSH, or with a file manager), then reopen Webcams. The
sample in [config/webcams.yaml](config/webcams.yaml) explains every field. Each webcam needs a `name` and a `url`:

| Link | What Gullion TV does |
|---|---|
| an mcn.live camera page | reads the stream and the church's photo from the page |
| a churchservices.tv church page | reads the stream, the church photo and the next service time |
| a direct stream (`.m3u8`, `rtsp://`, `.mp4`) | plays it as it is; add `image:` for a tile picture |
| an `.m3u` list (`type: playlist`) | makes a tile for every camera in the list |

Deploying never overwrites the box's copy; use `FORCE_CONFIG=1 BOX=... scripts/deploy.sh` to replace it.

## Plex

Plugins → Gullion TV → BLUE (Plex), behind the Tech Support PIN:

1. **Link a Plex account**: the TV shows a code; enter it at plex.tv/link on a phone or computer.
2. **Who the TV watches as**: pick the Plex Home user (and their PIN if they have one). The TV always uses them.
3. **The server**: pick it, and Gullion TV finds the best way in: the last one that worked, then the local network,
   then the internet, and Plex's relay only as a last resort. Setup shows which it's using.
4. **The libraries**: only film and TV libraries are offered; all are ticked to start.

Then "Quality away from home" (8 Mbps to start) and subtitles (off) can be changed. Everything is saved in
`/etc/enigma2/gulliontv/plex.json`, readable only by root because it holds the Plex tokens. Streaming from a server
outside the home needs Plex Pass on the server owner's account (or a Remote Watch Pass for the viewer).

## Recording pictures

Install ffmpeg on the box once (`opkg update && opkg install ffmpeg`). Gullion TV then saves one frame from each
recording when it finishes, and catches up on older ones when Watch again opens, at the lowest priority. Without
ffmpeg, recordings show their channel's picon.

## Tech Support notes

- There's no default PIN. The first time Settings is opened, Gullion TV asks for a 4-digit Tech Support PIN
  (twice, and not an easy one like 0000 or 1234). Change it later in Menu → Plugins → Gullion TV.
- To go back to the skin's own channel banner, set "Large channel banner" to No and restart.
- To turn Gullion TV off, set "Open Gullion TV with MENU" to No in the same place.

## Licence

Gullion TV is free software under the [GNU General Public License, version 2](LICENSE), the same licence as
enigma2. It isn't affiliated with Plex, Freesat, Saorview, mcn.live or churchservices.tv; their names appear only
to describe what Gullion TV works with.
