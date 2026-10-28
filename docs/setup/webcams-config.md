# Webcams list

[Documentation](../README.md) › Webcams list

[Webcams](../features/webcams.md) shows the cameras listed in `/etc/enigma2/gulliontv/webcams.yaml` on the box.
Edit it over SSH or with a file manager, then reopen Webcams. The sample in
[config/webcams.yaml](../../config/webcams.yaml) explains every field.

```yaml
webcams:
  - name: St Malachy's Parish
    url: https://mcn.live/Camera/st-malachys-parish-belfast
    group: Church

  - name: Armagh Cathedral
    url: https://www.churchservices.tv/armaghcathedral
    image: images/armagh-cathedral.png
```

| Field | What it's for |
|---|---|
| `name` | what the tile says (needed) |
| `url` | the web page or stream link (needed) |
| `type` | only to override the guess: `mcn`, `churchservices`, `stream` or `playlist` |
| `image` | a picture for the tile instead of the page's own (see below) |
| `group` | a small label on the tile, such as Church or Local |
| `player` | `4097` (the box's standard player) or `5002` if ServiceApp is installed |

## Kinds of link

| Link | What Gullion TV does |
|---|---|
| an mcn.live camera page | reads the stream and the church's photo from the page |
| a churchservices.tv church page | reads the stream, the church photo and the next service time |
| a direct stream (`.m3u8`, `rtsp://`, `.mp4`) | plays it as it is; add `image:` for a tile picture |
| an `.m3u` list (`type: playlist`) | makes a tile for every camera in the list |

## Tile pictures

`image:` can be:
- a link to a picture;
- a full path on the box;
- a file in the `images` folder next to `webcams.yaml`, such as `image: images/armagh-cathedral.png`.

Pictures in `config/images/` are copied there on every deploy. If a picture isn't on the box, the page's own is
used. The Armagh Cathedral photo isn't in this repository, so a fresh copy shows the photo from churchservices.tv
instead.
