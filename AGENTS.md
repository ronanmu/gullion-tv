# Instructions for coding agents

Gullion TV is an enigma2 plugin for OpenATV boxes: a large-text, plain-English home screen with Live TV, TV Guide,
Recordings and Webcams, and the stock menus locked behind a Tech Support PIN. Start with
[HANDOVER.md](HANDOVER.md), which covers the current state, architecture, known issues and next tasks. User-facing
behaviour is documented in [docs/](docs/README.md).

## Before you finish any change

1. `python3 tools/check.py` must pass (exit 0, ending `docs ok`).
2. If a screen's look changed, re-render with `python3 tools/preview.py` (needs Pillow), look at the affected
   pictures in `docs/images/`, and keep the docs pages in step. A new picture must be shown on a docs page, or
   the check fails.
3. Update the docs page for any feature whose behaviour changed, and the README's To do list if relevant.
4. **At every significant milestone, update HANDOVER.md**: the feature status, test results (date, what ran, which
   box), known issues and next tasks, and the commit named in its first paragraph.
5. Never describe something as working on a box unless it was run on one. Offline checks run against stand-ins,
   not enigma2.

## Project structure

- `plugin/GullionTV/`: the plugin. Everything here is copied to the box.
  - `plugin.py`: start-up;
  - `hook.py`: key redirections;
  - `lock.py`: the PIN gate;
  - `home.py`: Home;
  - `recordings/`, `tv/`, `webcams/`, `plex/`, `weather/`: the features;
  - `ui/`: shared widgets and helpers;
  - `theme.py`: colours;
  - `images/`: icons.
- `tools/`: `check.py` (offline checks), `e2stubs.py` (enigma2 stand-ins), `sample_*.py` (sample data),
  `preview.py` (renders), `make_images.py` and `fetch_weather_icons.py` (icons).
- `docs/`: documentation pages; `docs/images/` holds the rendered screenshots.
- `config/`: `webcams.yaml` sample; `config/images/` holds webcam pictures (some gitignored, deliberately).
- `scripts/deploy.sh`: deploy to a box (`BOX=<address> scripts/deploy.sh`).

## Hard constraints

- **Python 2.7 and Python 3 from one codebase** (OpenATV 6.4 and 7.x):
  - no f-strings, `nonlocal`, keyword-only arguments, walrus, type hints or other Python-3-only syntax;
  - `print("...")` with a single argument only;
  - put `# -*- coding: utf-8 -*-` on the first line of any file with non-ASCII text.
- **Image differences:** look methods and action names up with `hasattr`/`getattr`, never assume one image. See
  HANDOVER.md section 4 for the known pairs (`mainMenu`/`showMainMenu`, `instantRecord`/`keyInstantRecord`,
  `nextBouquet`/`nextService`, …).
- **Skins** are XML strings designed at **1920×1080** and passed through `ui/scale.skin()`:
  - use colours from `theme.py`;
  - every `widget name` in a skin must exist on the screen (checked);
  - every screen must fit 1280×720, 720×576 and 3840×2160 once scaled (checked).
- **Picture widgets** need `alphatest="blend"`, and can't scale: add icon sizes via `tools/make_images.py` and
  pick them with `ui/icons.py`.
- **Never `onLayoutFinish.append(lambda ...)`**: enigma2 execs non-methods. Use a bound method (checked).
- **Only touch screens on the main thread.** Disk and network work goes through `ui/background.Background`.
- **Fail safe at start-up:** anything that patches enigma2 must catch its own errors and fall back to stock
  behaviour. A broken plugin must never stop the box starting.
- **Respect `config.plugins.gulliontv.enabled`**: every patched key calls the original when it's off.
- **Never delete recordings outright.** Use `recordings/store.move_to_trash`.
- **New enigma2 APIs:** when you use one, extend `tools/e2stubs.py` so the checks can drive it, and add checks.

## Conventions

- **Indentation:** tabs.
- **Naming:** `snake_case` for functions and variables, `CapWords` for screens. Screen skin names start with
  `Gullion` (e.g. `GullionRecordings`).
- **Comments:** short, plain English, explaining *why*, matching the surrounding density. Docstrings describe
  behaviour in user terms.
- **UI wording** is plain English, for a non-technical viewer:
  - "TV Guide", not EPG; "channel list", not bouquet;
  - "Tech Support", not admin; "Recordings", not movies;
  - pop-ups have at most three options (`ui/popups.GullionChoice`);
  - key hints are drawn as outlined keys or the coloured circles from `ui/icons.key_icon`.
- **Commit messages:** a plain-English summary line, then a short body of what changed and why. Use conventional
  prefixes (`chore:`, `fix:`) only when the owner asks for them.
- **Tests:** add or extend checks in `tools/check.py` next to the related section, with assertion messages that
  say what should be true. Don't write filler bytes into files named `.jpg`/`.png`: the owner's antivirus
  quarantines them. Use `e2stubs.TINY_JPEG`, or read bytes from memory.

## Working with the owner and the boxes

- **Pushing:** commit when asked; push to GitHub only with the owner's explicit OK.
- **Private details stay out of the repository:**
  - box IP addresses: pass them as `BOX=`;
  - PINs and Plex tokens;
  - pictures that aren't ours to publish (e.g. `config/images/armagh-cathedral.png`, which is gitignored but
    still deployed).
- **On a box:**
  - don't type the owner's Tech Support PIN;
  - don't delete recordings;
  - ask before installing packages (`opkg`);
  - ask before changing the box's own settings or skin.
- **Driving a box for testing:** OpenWebif `/api/remotecontrol?command=<code>` and `/grab?mode=osd`. The key
  codes are in HANDOVER.md section 6.
