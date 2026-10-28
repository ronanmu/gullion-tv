# Handover: Gullion TV

This file describes the working tree after `37fa30f` ("Add experimental unified Media design") and the following
restoration of the dedicated Recordings route. The experimental combined screen is preserved by the
`experimental-media-design` tag. Read [AGENTS.md](AGENTS.md) for how to work on the code, and
[docs/](docs/README.md) for what each screen looks like and does. The experimental tree was
deployed to the GigaBlue on 28 October 2026 after the owner said it was available; only compilation, restart and
post-restart live-TV banner screenshots have been checked so far. The latest deployment at 16:41 includes the
playback and Recordings refinements described below; the 16:52 follow-up adds the compact transport layout and
revised Sort behaviour, and the 17:10 deployment adds silent resume, overlay edge navigation and the recorded
date/time label. The 22:09 deployment adds the unified Media screen and was opened with real recording and Plex data;
the 22:24 follow-up adds the padded, three-wide Media layout and six-item horizontal rows. The 22:50 deployment
replaces that with four landscape Continue watching cards and five portrait Recently added cards. The 23:01
deployment restores the YELLOW Home card to the dedicated Recordings screen.

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
| TV Guide update: continuous bouquet scrolling, YELLOW list selector, bouquet heading above channels, footer-only action hints, full-details icons | Offline checks and renders only, 28 October 2026; not deployed |
| GUIDE, arrows, TV, FAV open Gullion TV's guide instead of the stock guide and channel list | Tried on the GigaBlue |
| REC on live TV: records now until the programme ends, no questions, no "recording started" pop-up; REC again asks Stop/Keep; STOP stops | Tried on the GigaBlue |
| Webcams: grid, live status, churchservices.tv next service, player with LIVE marker, tile picture from a link or local file | Tried on the GigaBlue |
| **Recordings screen** (list plus large details, file size, status, sort, MENU options, delete to recycle bin) | Opened with real recordings on the GigaBlue, 28 October 2026; playback and deletion were not driven |
| Safe recording deletion: active-timer guard, background moves, separate recycle-bin folders, rollback and failure messages | Offline checks only, 28 October 2026; not deployed |
| Gullion recording playback panel: title/description, scrub-able progress, icon-only pause/play and 30-second skips, conditional subtitles, auto-hide | Latest refinements have offline checks and renders only, 28 October 2026; the earlier panel was deployed but never driven on the box |
| Recording frames via ffmpeg, now 768×432 (older 328×184 ones remade) | Offline checks only for the new size. Whether ffmpeg is installed on the GigaBlue is not recorded |
| Experimental Media screen: All, Recorded TV, Movies on Plex and TV Shows on Plex | Preserved by `experimental-media-design`; tried on the GigaBlue with real data, 28 October 2026 |
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
| `home.py` | `GullionHome`; `CARDS`; opens the dedicated `Recordings` screen from YELLOW |
| `watchagain.py` | experimental `WatchAgain` Media screen preserved by the tag; four filters and two rows |
| `recordings/screen.py` | `Recordings` screen, `play_recording` (opens the Gullion recording player), `make_frames`, `read_recordings` |
| `recordings/player.py` | `RecordingPlayer`, a skinned stock `MoviePlayer` subclass: transport controls, progress timer, subtitles and overlay lifecycle |
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
| `keymap.xml` | live STOP and dedicated `GullionPlaybackActions` keys, loaded at session start by `hook.py` |

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
  Each deletion reserves a unique `gullion-` subfolder, retaining original filenames. Companions move first,
  the programme last. Failed moves attempt rollback; files that cannot be restored remain recoverable in that
  subfolder. The screen queues moves through `Background`, prevents playback/repeated deletion during the move,
  binds confirmation to its original recording, and checks active timers before and after confirmation.
  Leaving the screen does not cancel an in-flight move; its completion pop-up is then suppressed.
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

Latest milestone, 28 October 2026:

- Committed the unified Media experiment as `37fa30f` and tagged it `experimental-media-design`. The following
  local change restores the Home card name to Recordings and makes YELLOW open the dedicated list shown in
  `22-recordings.png`. Deployed at 23:01 and confirmed with 25 real recordings on the GigaBlue.

- Aligned Media to the TV Guide/Webcams 90 px side margins. Continue watching now shows four landscape cards and
  scrolls through at most eight; Recently added shows five portrait cards and scrolls through at most ten.
- Recently added prefers Plex poster art and uses the channel picon for recorded TV. Separate checks cover both
  shelf limits, scrolling to item ten, poster choice and recording picons. Re-rendered the Media examples and
  inspected both layouts locally. Deployed at 22:50 and opened with real recording and Plex data at 22:55; all
  four landscape and five portrait positions rendered correctly at 1920×1080.

Deployed on 28 October 2026 to the GigaBlue UHD Quad 4K at the owner's supplied address:

- At 23:01, deployed commit `1e8d920`. Box compilation, install, retained configuration, enigma2 restart and the
  post-restart screenshot succeeded (`screenshots/20261028-230113.png`, gitignored). YELLOW from Home opened the
  dedicated Recordings screen with 25 real programmes, picons and the selected programme's detail panel. No
  recording was played, sorted or deleted during this route/layout check.
- At 22:50, deployed the four-landscape/five-portrait Media layout. Box compilation, install, retained configuration,
  enigma2 restart and the post-restart screenshot succeeded (`screenshots/20261028-225055.png`, gitignored). The
  real Media screen was then captured with four Continue watching cards and five Recently added cards; recording
  picons and Plex poster art rendered correctly and the screen remained responsive.
- At 22:24, deployed the Media spacing and navigation follow-up. Box compilation, install, retained configuration,
  enigma2 restart and the post-restart screenshot succeeded (`screenshots/20261028-222413.png`, gitignored).
  Opened Media with real data and selected Recorded TV: the filter labels had the intended inset, three cards fitted
  each row, the section headings were clearly separated, and moving right to the fourth Recently added recording
  scrolled the three-card window correctly. Filter-row movement and the six-item boundary also pass offline checks.
- At 22:09, deployed the Home rename and unified Media screen. Compilation, install, retained configuration,
  enigma2 restart and live-TV screenshot succeeded. Then opened Home and Media through OpenWebif: the real All
  view showed two part-watched recordings, one Plex movie and one Plex TV episode in Continue watching, plus
  three recordings, one movie and one TV episode in Recently added. All four equal colour tabs and panel artwork
  rendered correctly at 1920×1080. Returned the box to live TV afterward. Filter switching and playback were not
  driven during this check.
- At 17:10, deployed silent resume, directional overlay hiding and the recorded date/time label. Box compilation,
  install, retained configuration, enigma2 restart and post-restart live-TV screenshot succeeded
  (`screenshots/20261028-171015.png`, gitignored). Actual resumed playback still needs an owner-driven check.
- At 16:52, deployed the follow-up Sort/footer and compact player-control changes. Box compilation, install,
  retained configuration, enigma2 restart and post-restart screenshot all succeeded
  (`screenshots/20261028-165249.png`, gitignored). The screenshot confirms start-up and live TV; the changed
  Recordings and playback screens still need to be driven by the owner on the box.
- At 16:41, `BOX=<address> scripts/deploy.sh` deployed the current working tree with the icon-only recording
  controls, progress scrubbing, year display and revised Recordings footer. The box compiled every plugin file,
  installed it, retained its existing `webcams.yaml`, copied webcam pictures, restarted enigma2 and returned a
  1920×1080 live-TV screenshot successfully (`screenshots/20261028-164130.png`, gitignored).
- This confirms deployment and start-up for the latest tree. The Recordings and playback screens have not yet
  been opened or driven on the box, so their behaviour remains verified only by offline checks and renders.
- `BOX=<address> scripts/deploy.sh` copied the working tree, compiled every plugin file with the box's Python,
  installed it, retained the existing `webcams.yaml`, copied webcam pictures and restarted enigma2 successfully.
- OpenWebif returned a 1920×1080 screenshot after restart showing live TV with the Gullion channel banner on
  BBC Two NI HD. The screenshot is `screenshots/20261028-161851.png` (gitignored).
- This confirms deployment/start-up and the live banner only. The updated TV Guide, Recordings screen, safe
  deletion and recording playback controls have not yet been driven on the box. No recordings were deleted and
  no box settings or packages were changed.

Latest milestone, 28 October 2026:

- Media spacing follow-up: added 24 px left padding inside every filter tab, increased the gap before Recently
  added, and enlarged the layout to three panels per row. Each row holds up to six items and scrolls its three-item
  window with LEFT/RIGHT. UP from Continue watching focuses the filters, LEFT/RIGHT changes the focused filter,
  and DOWN returns to Continue watching; colour-key shortcuts still select filters directly.
- Added checks for filter-row navigation and scrolling exactly to item six. Local checks pass through `docs ok`;
  re-rendered Media for visual inspection. Deployed at 22:24 and checked with real recordings on the GigaBlue.

Previous Media milestone, 28 October 2026:

- Renamed the Home card from Recordings to Media and made it open one Media screen with or without Plex.
- Rebuilt the old Watch Again screen as four equal tabs: All, Recorded TV, Movies on Plex and TV Shows on Plex.
  RED/GREEN/YELLOW/BLUE select them directly, with matching circular hints at the right of each tab.
- Media has fixed Continue watching and Recently added rows of up to five panels. All takes up to three box
  recordings, then one Plex movie and one Plex TV item in each row. The other filters show only their media type.
  Panels are labelled Recorded TV, Movie or TV Show. MENU from All or Recorded TV retains access to the full
  recording list and its sort/delete actions.
- Added checks for Home routing without Plex, all four colour filters, exact mixed-row limits/order, missing Plex,
  missing recording storage, panel badges, artwork/poster fallback and playback selection. Re-rendered and
  inspected Home, All and Movies on Plex. `python3 tools/check.py` passes through `docs ok`; deployed and opened
  successfully with real recording and Plex data at 22:09.

Previous playback milestone, 28 October 2026:

- Inspected the GigaBlue's installed OpenATV 7.6 `InfoBarCueSheetSupport.triggerResumeLogic` bytecode before
  changing resume behaviour (the image ships `.pyc` files without sources). Gullion's player now overrides that
  exact hook: it retains cue-sheet loading, seeks to the saved point and runs the stock post-resume hide step,
  while omitting OpenATV's notification callback and resume question.
- Added the recording date/time beneath the progress bar, opposite the subtitle icon. UP from an already selected
  progress bar hides the overlay; DOWN from the transport row does the same. The first UP/DOWN still switches rows.
- Extended the player stand-ins and checks for silent exact-position resume, cue-sheet lifecycle, no opened prompt,
  and both directional hide paths. Re-rendered and inspected playing, scrubbing and no-subtitle states. Local
  `python3 tools/check.py` passes through `docs ok`; this follow-up is ready for the available GigaBlue.

Previous Sort/player layout follow-up, 28 October 2026:

- Follow-up from the first box review: moved BLUE Sort beside RED Delete. Sorting now resets to the first item
  after each BLUE press, so the new order is immediately visible instead of following the previously selected
  recording to a different viewport position.
- Tightened the three transport icons around the player centre. Removed their contrasting selection tiles and
  replaced the selected state with a short blue underline; the subtitle icon remains separate at the far right.
- Re-rendered and inspected the Recordings footer, normal playback and selected progress bar. Local checks pass,
  ending `docs ok`. This follow-up is ready for redeployment to the available GigaBlue.

Previous playback/Recordings refinement milestone, 28 October 2026:

- Refined recording playback to use official Material Symbols for play, pause, replay 30 and forward 30. Removed
  the boxed key-hint footer and all transport labels; subtitles remains an icon at the far right.
- UP selects the progress bar, LEFT/RIGHT scrub in one-percent steps through enigma2's absolute `seekTo` API,
  held LEFT/RIGHT repeats, and DOWN returns to the transport icons. Added the API stand-in and checks for exact
  absolute targets, focus changes, missing seek support and every generated icon size.
- Recordings now shows a year for programmes outside the current year. Removed the OK/MENU/BACK footer hints,
  added RED Delete at the left, and moved BLUE Sort to the right. Checks invoke both colour actions through the
  screen ActionMap; RED retains the active-recording guard and recycle-bin confirmation.
- Fetched the official Google Material Symbols variable font and codepoints to a temporary directory, then used
  `tools/make_images.py` to generate the new assets. The downloaded font itself is not kept in the repository.
- Re-rendered and inspected the Recordings list, playing, paused, no-subtitle, subtitle-choice and new progress
  selection examples. `python3 tools/check.py` passes, ending `docs ok` (28 October 2026, local macOS only).
  These refinements have not been redeployed; the owner must request the next box deployment.

Previous playback milestone, 28 October 2026, local offline checks only:

- Added the recording playback panel with title, cleaned description, live position/length/progress, centred
  pause/play, adjacent 30-second skips, and a subtitle button only when file subtitle tracks are reported.
- Dedicated playback keymap consumes both press/release edges ahead of stock mappings. The overlay shows at
  startup, hides after six seconds while playing, stays visible on pause, and is recalled with OK/INFO.
  LEFT/RIGHT choose a button, OK activates it; transport keys act directly. STOP uses the stock resume-saving
  leave path and the existing forced-quit policy. BACK hides, then exits when already hidden.
- Preserves stock resume/subtitle APIs; uses `getattr` for optional playback APIs. New seek, subtitle, pause and
  timer stand-ins drive checks for transport actions, bounds, absent metadata/APIs, subtitle changes and cleanup.
- `python3 tools/check.py` passes, ending `docs ok`. Player skin included in all three scaled-size checks.
  Rendered and inspected playing, paused, no-subtitle and subtitle-choice examples in the recordings docs.
- No box access, deployment or box setting changes. Python 2.7 and actual enigma2 playback remain untested.

Previous TV Guide milestone, 28 October 2026, local offline checks only:

- TV Guide: flattened enabled/non-empty bouquets into one grid in box order, retaining channel numbers.
  Arrow/page movement crosses boundaries; YELLOW opens a three-choice-per-page selector and jumps to a list.
  The selected channel's bouquet is shown above the channel column. Removed the old top selector and outlined
  OK/REC/INFO hints; the footer now includes REC and INFO explicitly.
- Guide Details uses the same description parser and icon row as What's on, with the selected channel's service
  reference (not the live preview's picture height). A is accepted alongside AD for audio description.
- Added local checks for 20-to-101 navigation in both directions, cross-bouquet paging/zapping, selector paging
  and cancellation, empty lists, raw-code handoff and detail icons. `python3 tools/check.py` passes, ending `docs ok`.
- Re-rendered the guide variants and details, and added selector and boundary examples to the guide docs.
  Inspected the updated renders. No box accessed; these changes remain untested on enigma2.

Previous deletion milestone, 28 October 2026, local offline checks only:

- `python3 tools/check.py` passes (exit 0, ending `docs ok`) after the deletion changes.
- Added checks for active recordings, a timer starting during confirmation, confirmation target stability,
  background dispatch, blocking playback/repeated actions during a move, failure messages, duplicate filenames,
  successful rollback and failed rollback retaining recoverable files.
- `tools/preview.py` rendered all 41 pictures using the bundled Python/Pillow runtime (system Python lacks Pillow).
  Inspected the Recordings and delete-confirmation renders. No skin layout changed; retained the existing images
  rather than replacing all screenshots with this runtime's rendering differences.
- No deployment, real-box tests or package installation. Python 2.7 and real recycle-bin integration remain untested.

Earlier handover baseline, run on 28 October 2026 on macOS with Python 3.14.2:

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

- **Latest TV Guide changes are untested on a box.** Confirm cross-bouquet navigation, the YELLOW selector,
  selected-bouquet heading, details icons and scaled layout when the owner says a box is available.
- **Recordings screen is untested on a box**, including:
  - the outlined rows and the scaled pictures;
  - ffmpeg frames at 768×432, and whether the blank-frame threshold (6000 bytes) suits real broadcasts;
  - the `EPGSelectActions` CH+/- names on this screen;
  - delete to the recycle bin on the box's filesystem, including recovery from the new `gullion-` subfolders
    and compatibility with the stock recycle-bin cleanup.
  - deletion failures after leaving the screen have no pop-up; inspect the recycle bin if recovery is needed.
  - rollback is best effort, not crash-atomic: power loss can leave files split between the original folder and
    the recycle bin. No files are intentionally discarded in that case.
- **"New" isn't fully reliable.** It means "no saved stop point in `.ts.cuts`":
  - some images clear the stop point at the end of playback, so finished recordings can show as New;
  - playback through OpenWebif or another box doesn't save one;
  - "Watch from the start" deliberately clears it.

  A recording whose `.ts.meta` length is 0 shows no length or progress; the box could measure it via
  `eServiceCenter` but doesn't yet.
- **Plex:** playback and opening a film or programme aren't implemented. The client has never been recorded as
  tested against a real server.
- **Recording playback now has a Gullion panel over the stock engine**, but is untested on hardware. Check
  actual key dispatch, progress-bar focus and absolute scrubbing, the six-second hide timer, pause, cue saving/EOF,
  30-second seek accuracy and recorded
  subtitle rendering on 7.6 and 6.4. Seeking depends on the box having a usable seek index/length.
  Silent resume now bypasses the stock prompt; this milestone does not change Watched/New persistence.
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

1. **When the owner requests the next deployment, try the updated guide and Recordings on the GigaBlue.** Deploy, then:
   - verify guide navigation from Saorview 20 to Freesat 101 and back, paging, YELLOW selection, numeric jumps,
     and zapping into the selected bouquet; check Guide Details icons and the new layout;
   - check the layout at 1920×1080;
   - check frames from a real recording (install ffmpeg only with the owner's OK);
   - check silent resume, Watch from the start, sort and CH+/-;
   - check the new playback overlay, pause/play, selected progress-bar scrubbing including held LEFT/RIGHT,
     30-second skips near both ends, subtitles, BACK/STOP and EOF;
   - with explicit permission for a test recording, check deletion and restoration from a `gullion-` recycle-bin
     subfolder, active-recording protection, and stock recycle-bin compatibility;
   - capture screenshots into `docs/images/box/`.
2. **Regression-test on the Formuler (OpenATV 6.4, Python 2.7)** once it's reachable, especially Python 2 syntax,
   the 6.4 method names and the 1280×720 scaling.
3. **Make Watched / New reliable**: when `RecordingPlayer` closes, note the stop point (or "watched" if within the
   last few minutes), and fall back to `eServiceCenter` for the length when `.ts.meta` has 0.
4. **Plex playback**: open a film or programme, and play it with resume and the quality and subtitle settings.
5. **Validate the new recording player on both images**, then refine it from actual playback feedback. The
   styled panel is implemented; stock resume prompts and reliable Watched/New state remain separate work.
6. **Series link** via the AutoTimer plugin: "Record series" in the TV Guide, an exact title on one channel, and
   a list of series in Recordings. See the README's To do list; check the AutoTimer version on the box first.
7. **Docs site**: turn on GitHub Pages for `/docs` (owner's decision), and add real box captures beside the renders.
