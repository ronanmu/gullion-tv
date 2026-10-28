# Handover: Gullion TV

This file describes the repository as of the commit "chore: prepare AI development handover" (28 October 2026). That
commit's parent is `6c032df`, and it changes only documentation (this file and AGENTS.md), so the code is exactly
as it was at `6c032df`. It is for the next developer or coding agent. Read [AGENTS.md](AGENTS.md) for how to work
on the code, and [docs/](docs/README.md) for what each screen looks like and does.

**Keep this file current.** Whenever you complete a significant development milestone, update this file in the
same commit (or the one straight after):
- the feature table (section 2);
- the test results (section 7), with the date, what was run, and on which box;
- the known issues (section 8);
- the task list (section 9).

Also update the first paragraph to name the commit it describes. Never mark something "tried on a box" unless it
was actually run on one.

## 1. Purpose and intended UX

Gullion TV is an enigma2 plugin for OpenATV set-top boxes. It puts a simple, large-text home screen in front of
the box, so someone who just wants to watch TV never meets the box's technical menus. It was made for an older
viewer, but suits anyone who finds set-top box menus hard going.

The UX principles, which every change so far has followed:
- **Four things on Home**, in the remote's colour order: Live TV (RED), TV Guide (GREEN), Recordings (YELLOW),
  Webcams (BLUE). Each colour button opens its card directly.
- **Large, high-contrast text and plain English.** No jargon: "TV Guide", not EPG; "channel list", not bouquet;
  "Tech Support", not admin. Pop-ups ask simple questions with at most three options.
- **One channel list**, numbered as the box numbers it, covering Saorview (Irish terrestrial) and Freesat (UK
  satellite) together.
- **The stock menus are locked** behind a Tech Support PIN, so nothing gets broken by accident.
- **Keep the box's behaviour where it works** (banner timing, channel numbering, the recording player) and replace
  only what's confusing.
- **No surprise questions**: REC records straight away; STOP stops straight away.

## 2. Features and their status

"Tried on the GigaBlue" means deployed to the GigaBlue UHD Quad 4K (OpenATV 7.6, Python 3.13, MetrixHD at
1920×1080) and checked on screen through OpenWebif screenshots during development. Everything below also passes the
offline checks (section 7).

| Feature | Status |
|---|---|
| MENU opens Home; colour buttons open the cards | Tried on the GigaBlue |
| Home: live preview with LIVE marker, now/next, card icons, Settings | Tried on the GigaBlue |
| Weather line on Home (Met Éireann, Open-Meteo backup, Yr icons) | Offline checks only as far as this handover records; treat as unconfirmed on a box |
| Tech Support PIN: chosen on first use; locks the stock menu, plugin browser, extensions, channel-list edit menu, Button setup, quick menu | Tried on the GigaBlue |
| Channel banner: number and name above the panel, picon, Now/Next, access-code, HD/UHD and delivery icons, signal gauge, REC pill | Tried on the GigaBlue |
| Channel numbering matching the box, including Freesat (101 = BBC One NI HD) | Fixed and tried on the GigaBlue |
| Typing a channel number on live TV and in the guide; restyled number-entry and volume pop-ups | Tried on the GigaBlue |
| What's on panel (INFO, or OK twice): now, next five, live tuner details | Tried on the GigaBlue |
| Sound and subtitles pop-up (YELLOW / AUDIO / SUBTITLE) | Tried on the GigaBlue |
| TV Guide: grid, CH+/- paging, day and list switching, number entry, record/cancel, codes stripped into icons, record marks, drive checks | Tried on the GigaBlue |
| GUIDE, arrows, TV, FAV open Gullion TV's guide instead of the stock guide and channel list | Tried on the GigaBlue |
| REC on live TV: records now until the programme ends, no questions, no "recording started" pop-up; REC again asks Stop/Keep; STOP stops | Tried on the GigaBlue |
| Webcams: grid, live status, churchservices.tv next service, player with LIVE marker, tile picture from a link or local file | Tried on the GigaBlue |
| **Recordings screen** (list plus large details, file size, status, sort, MENU options, delete to recycle bin) | **Offline checks and renders only. Never run on a box.** Added in `6c032df` |
| Recording frames via ffmpeg, now 768×432 (older 328×184 ones remade) | Offline checks only for the new size. Whether ffmpeg is installed on the GigaBlue is not recorded |
| Watch again (only when Plex is set up): Continue watching, Recently added, Recorded TV, Browse | Offline checks against sample Plex replies only |
| Plex: linking, Home user, server choice, libraries, Films and TV programmes poster views | Offline checks against sample Plex replies only. No record of testing against a real Plex server |
| Plex playback, opening a film or programme | **Not implemented** (shows "Playing from Plex arrives in the next update") |
| Formuler F1 (OpenATV 6.4, Python 2.7) | Was the first test box. **Not tried since OpenATV 7.x support was added (`752022c`)**, so every later feature is untested on 6.4 |

## 3. Architecture

### How it hooks into enigma2

Everything starts in `plugin/GullionTV/plugin.py`:
- `WHERE_SESSIONSTART` → `sessionstart()` runs, in order:
  1. `hook.install()`, which patches `Screens.InfoBarGenerics` methods;
  2. `lock.install(session)`, the PIN gate;
  3. `recordings.thumbnails.watch_recordings(session)`, frames for finished recordings;
  4. `tv.infobar.install()`, the banner and pop-up skins (if the "Large channel banner" setting is on).

  Each step is wrapped in try/except so a failure falls back to stock behaviour instead of stopping the box.
- `WHERE_PLUGINMENU` → `setup.GullionTVSetup`, the Tech Support settings, reached via Menu → Plugins.

**Monkeypatching (`hook.py`).** It replaces InfoBarGenerics methods:
- MENU → Home;
- INFO, and OK twice → What's on;
- YELLOW / AUDIO / SUBTITLE → Sound and subtitles;
- REC → instant record;
- the guide and channel-list keys → TV Guide.

It also adds a STOP action map to InfoBar via `keymap.xml`. The live InfoBar's action maps already hold bound
methods, so `rebind()` swaps those too. Each patch checks `config.plugins.gulliontv.enabled` and calls the
original when Gullion TV is off.

**PIN lock (`lock.py`).** It wraps `session.open` / `openWithCallback`, and asks for the PIN before any screen
whose class (or a base class) is named in `LOCKED`. `grant()` lets the next locked screen open without asking for
5 seconds after Home's Settings accepted the PIN.

**Skins.** Every screen has its skin as a `%`-formatted XML string designed at 1920×1080, passed through
`ui/scale.skin()`, which scales positions, sizes and fonts to the active skin's resolution. The banner,
NumberZap and Volume skins replace the active skin's own entries in `skin.dom_screens` (7.x) / `skin.domScreens`
(6.4) at session start.

**Custom skin parts.** `tv/converter.py` (GullionServiceInfo) and `tv/renderer.py` (GullionIcon) are registered
in `sys.modules` as `Components.Converter.GullionServiceInfo` and `Components.Renderer.GullionIcon`, so skin XML
can use them like built-in ones.

### Modules

| Path | Role |
|---|---|
| `plugin.py` | plugin descriptors, start-up sequence |
| `settings.py` | `config.plugins.gulliontv.*`: `enabled`, `infobar`, `pin`, `pin_set`, `weather_location` |
| `setup.py` | `GullionTVSetup`, the Tech Support settings screen (BLUE: Plex setup) |
| `hook.py` | all the key redirections, the instant-record logic, STOP key, quieting the "recording started" pop-up |
| `lock.py` | the PIN gate |
| `home.py` | `GullionHome`; `CARDS`; opens `Recordings` without Plex, `WatchAgain` with it |
| `watchagain.py` | `WatchAgain` (Plex mode), `recording_tile`, `plex_tile` |
| `recordings/screen.py` | `Recordings` screen, `play_recording` (a `MoviePlayer` subclass that always returns here), `make_frames`, `read_recordings` |
| `recordings/store.py` | reads `.ts.meta` / `.ts.cuts`, `Recording`, sizes, sorting, drive checks, `forget_position`, `move_to_trash` |
| `recordings/thumbnails.py` | ffmpeg frame grabs (`nice -n 19`), blank-frame retries, JPEG size reading |
| `tv/guide.py` | `Guide`, the TV Guide grid (eListbox multi-content rows) |
| `tv/epg.py` | channel lists, numbering (`number_channels`), `Event`, timers, `zap()` |
| `tv/infobar.py` | banner, NumberZap and Volume skins; `install()`; converter registration |
| `tv/converter.py`, `tv/renderer.py` | GullionServiceInfo converter modes (Number, Name, NumberAndName, Remaining, Icon:N, IsRecording) and the GullionIcon renderer |
| `tv/serviceinfo.py` | HD/UHD, delivery type, access codes (`split_codes`, `badges`, `icon_row`), signal details |
| `tv/nowinfo.py` | `ChannelInfo`, the What's on panel |
| `tv/soundsubs.py` | `SoundAndSubtitles` |
| `tv/picon.py` | picon file lookup |
| `ui/` | `tiles` (picture tiles, `Pictures` decoder cache), `popups` (`GullionChoice`, `EventDetails`), `pin`, `background` (worker threads with results handed back on the main thread), `scale`, `icons`, `live` (LIVE marker), `placeholder` (`ComingSoon`, now unused by any card) |
| `plex/` | `client.py` (HTTP client, linking, users, servers, libraries), `setup.py` (setup screens), `library.py` (poster views) |
| `webcams/` | `config.py` (reads `webcams.yaml`, with a fallback parser if PyYAML is missing), `sources.py` (mcn.live, churchservices.tv, streams, M3U), `screens.py` |
| `weather/forecast.py` | Met Éireann / Open-Meteo forecast and caching |
| `theme.py` | all colours |
| `images/` | `icons/` (Material Symbols, Material Design Icons, REC pills, licences), `weather/` (Yr icons, licence) |
| `keymap.xml` | the `GullionLiveActions` STOP mapping |

Files outside the plugin:
- `config/webcams.yaml`: the sample webcams list.
- `scripts/deploy.sh`: deploys to a box.
- `tools/`: offline checks, enigma2 stand-ins, sample data, renders, icon generation.
- `docs/`: user documentation and rendered screenshots.

### Data on the box

| Path | What it is |
|---|---|
| `/usr/lib/enigma2/python/Plugins/Extensions/GullionTV` | the plugin |
| `/etc/enigma2/gulliontv/webcams.yaml` and `images/` | the webcams list and its pictures |
| `/etc/enigma2/gulliontv/plex.json` | Plex tokens, root-only |
| `/tmp/gulliontv/` | downloaded thumbnails |
| `/media/hdd/movie/*.ts.jpg` | recording frames, next to the recordings (or `config.usage.default_path`) |

## 4. Design decisions and constraints

- **Both OpenATV 6.4 (Python 2.7) and 7.x (Python 3)** from one codebase:
  - no f-strings or other Python-3-only syntax;
  - a `# -*- coding: utf-8 -*-` line in any file with non-ASCII text;
  - `str is bytes` checks where text crosses from files.
- **Method and action names differ between images**, so code looks them up with `hasattr`:
  - `mainMenu`/`mainMenu` (6.4) vs `showMainMenu`/`showMenu` (7.x);
  - `instantRecord` (6.4) vs `keyInstantRecord` (7.x);
  - `nextBouquet`/`prevBouquet` (6.4) vs `nextService`/`prevService` (7.x) for CH+/-;
  - `ConfigPIN`'s length is passed positionally;
  - keymaps load through `Components.ActionMap.loadKeymap`, else `keymapparser.readKeymap`.
- **Designed at 1920×1080 and scaled** to the skin. Text is sharpest with a full-HD skin, which is why the GigaBlue
  was switched to MetrixHD Full HD.
- **Picture widgets need `alphatest="blend"`.** On 7.x, ePicLoad leaves transparent areas clear, and without blend
  live TV shows through them. On 6.4, transparent areas are filled with the card colour (`theme.opaque`).
- **Picture widgets can't scale**, so icons are pre-rendered at several sizes and `ui/icons.py` picks the nearest
  to the skin's scale.
- **Never put a lambda in `onLayoutFinish`.** enigma2 `exec()`s anything that isn't a method there; it crashed What's
  on once. `tools/check.py` greps for it.
- **Screens are touched only on the main thread.** Disk and network work runs through `ui/background.Background`.
- **Live TV is stopped while Recordings / Watch again is open** (so it can't show through pictures) and restored on
  the way out. `Recordings(session, False)` is used from Watch again, which manages live TV itself.
- **Delete moves to the recycle bin** (`Tools.Trashcan` or `.Trash`), never removes recordings outright.
- **The "recording started" pop-up** is suppressed by briefly switching `config.usage.show_message_when_recording_starts`
  off inside `RecordTimerEntry.gotRecordEvent` at `evStart`, then restoring it.
- **The REC pill is a picture** (REC drawn in Open Sans Bold by `tools/make_images.py`), because bold font names
  aren't reliable across skins.
- **Freesat split titles** (e.g. "Programme..." continuing in the description) are deliberately *not* joined; the
  owner decided against it.
- **Icons** are Material Symbols (Apache 2.0) and Material Design Icons (Pictogrammers, Apache 2.0); the owner chose
  MDI's `television-classic` and `television-guide` for Live TV and TV Guide. Licences are in `images/icons/`.

## 5. Dependencies and versions

- **On the box:**
  - OpenATV 6.4 (Python 2.7) or 7.x (Python 3; tried on 7.6 with Python 3.13);
  - OpenWebif, used only by `deploy.sh` for screenshots;
  - optional: ffmpeg for recording frames (`opkg install ffmpeg`), PyYAML (a fallback parser is built in), a
    recording drive, a Plex server.
- **On a computer:**
  - Python 3 for `tools/check.py`, which needs no extra packages;
  - Pillow for `tools/preview.py`, `tools/make_images.py` and `tools/fetch_weather_icons.py`;
  - SSH as root to the box for `scripts/deploy.sh`;
  - `make_images.py` also needs local copies of the Material Symbols font, `@mdi/font` 7.4.47 and Open Sans,
    passed as the `MATERIAL`, `MDI` and `REC_FONT` environment variables.

## 6. Build, install, test, deploy

There is no build step; the plugin is plain Python plus images.

```sh
python3 tools/check.py                 # offline checks
pip install pillow && python3 tools/preview.py   # re-render docs/images/*.png
BOX=<box address> scripts/deploy.sh    # deploy, compile on the box, restart enigma2, screenshot
FORCE_CONFIG=1 BOX=<box address> scripts/deploy.sh   # also replace the box's webcams.yaml
```

`deploy.sh`:
1. copies the plugin to `<dest>.new`;
2. compiles every file with the box's own Python before swapping it in, so a syntax error doesn't break enigma2;
3. copies `config/images/` to the box, and `webcams.yaml` only the first time;
4. restarts enigma2;
5. saves an OpenWebif screenshot to `screenshots/` (gitignored).

Driving the box remotely for testing uses OpenWebif:
- **Key presses:** `/api/remotecontrol?command=<code>`. The codes:
  - MENU 139, EXIT 174, OK 352, INFO 358, EPG 365;
  - RED 398, GREEN 399, YELLOW 400, BLUE 401;
  - UP 103, DOWN 108, LEFT 105, RIGHT 106;
  - CH+ 402, CH- 403, REC 167, STOP 128, TV 377, FAV 364;
  - digits 1–9 are 2–10, and 0 is 11.
- **Screenshot of the on-screen display only:** `/grab?mode=osd`.
- **State:** `/api/timerlist`, `/api/movielist`, `/api/statusinfo`.

## 7. Test results at handover

Run on 28 October 2026 on macOS with Python 3.14.2:

- `python3 tools/check.py` exits 0. All **30 check groups** pass:
  - hook, lock, navigation, PIN, first-use PIN;
  - guide and guide picon, info panel, sound and subtitles, service info, converter, banner (infobar);
  - webcam config, sources, list and player;
  - recordings, recordings screen, recording drive, recording pictures;
  - Plex client, setup, link and library; Plex pictures; Watch again;
  - weather, Python 2 encoding, skin sizes (1280×720, 720×576, 3840×2160), docs.

  It prints `STOP key not set up: No module named 'keymapparser'` three times. That's expected: the stand-ins
  provide neither keymap loader.
- `tools/preview.py` (Pillow, in a venv) renders 41 screenshots, byte-identical to the committed ones.
- `python3 -m py_compile` passes on every plugin file under Python 3.14.
- **Not run:**
  - Python 2.7, which isn't installed here. The only Python 2 check is the coding-line check; `deploy.sh`
    compiles on the box, but only a 6.4 box would catch Python 2 syntax.
  - Any test on a real box since `74aae0b`. No box was reachable for the Recordings screen work.

What the offline checks are: `tools/e2stubs.py` stands in for the enigma2 modules, so the checks exercise screen
logic, skins and data handling. They prove nothing about real rendering, real tuners, timers, the real
`MoviePlayer` or the Plex/weather/webcam services.

## 8. Known bugs, incomplete work, open questions

- **Recordings screen is untested on a box**, including:
  - the outlined rows and the scaled pictures;
  - ffmpeg frames at 768×432, and whether the blank-frame threshold (6000 bytes) suits real broadcasts;
  - the `EPGSelectActions` CH+/- names on this screen;
  - delete to the recycle bin on the box's filesystem.
- **Resuming may still ask.** OK relies on the stock `MoviePlayer`'s resume behaviour. If the box's "on movie start"
  setting is "ask", the stock resume question appears. Not checked.
- **"New" isn't fully reliable.** It means "no saved stop point in `.ts.cuts`":
  - some images clear the stop point at the end of playback, so finished recordings can show as New;
  - playback through OpenWebif or another box doesn't save one;
  - "Watch from the start" deliberately clears it.

  A recording whose `.ts.meta` length is 0 shows no length or progress; the box could measure it via
  `eServiceCenter` but doesn't yet.
- **Plex:** playback and opening a film or programme aren't implemented. The client has never been recorded as
  tested against a real server.
- **The recording player is the stock one**, not Gullion TV-styled.
- **The Formuler / OpenATV 6.4 is untested** with everything since `752022c`.
- **Small things:**
  - `ui/placeholder.ComingSoon` is no longer reachable from any card (kept, documented in `docs/development.md`).
  - The renderer can't draw the ◀ ▶ glyphs in Sound and subtitles (a font gap on the Mac). Not confirmed either way
    on the box.
  - The Volume pop-up isn't in the docs renders.
- **Test recordings to clean up:** four short test recordings were left on the GigaBlue
  (`/media/hdd/movie/20261028 …RTÉ One - The Westies.ts` ×3 and a "Welcome To Moore Street" one). The owner was told
  how to delete them. Don't delete recordings without asking.
- **Open questions for the owner:**
  - Should EXIT or BACK be the label for the back key? (BACK is used everywhere.)
  - Should a "mark as watched when the player closes" fix go ahead?
  - Should GitHub Pages be turned on for `docs/`?

## 9. Recommended next tasks, in priority order

1. **Try the Recordings screen on the GigaBlue.** Deploy, then:
   - check the layout at 1920×1080;
   - check frames from a real recording (install ffmpeg only with the owner's OK);
   - check resume, Watch from the start, sort, CH+/- and delete;
   - capture screenshots into `docs/images/box/`.
2. **Regression-test on the Formuler (OpenATV 6.4, Python 2.7)** once it's reachable, especially Python 2 syntax,
   the 6.4 method names and the 1280×720 scaling.
3. **Make Watched / New reliable**: when `RecordingPlayer` closes, note the stop point (or "watched" if within the
   last few minutes), and fall back to `eServiceCenter` for the length when `.ts.meta` has 0.
4. **Plex playback**: open a film or programme, and play it with resume and the quality and subtitle settings.
5. **A Gullion TV-styled recording player** (the banner and pop-ups in the same style as live TV).
6. **Series link** via the AutoTimer plugin: "Record series" in the TV Guide, an exact title on one channel, and
   a list of series in Recordings. See the README's To do list; check the AutoTimer version on the box first.
7. **Docs site**: turn on GitHub Pages for `/docs` (owner's decision), and add real box captures beside the renders.
