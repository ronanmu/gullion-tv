# Gullion TV documentation

Gullion TV puts a large-text home screen in front of an [OpenATV](https://opena.tv) enigma2 box, so someone who
just wants to watch TV never meets the box's technical menus. These pages show each part of it and how to set it up.

The pictures are rendered on a computer by `tools/preview.py` from the plugin's real screen layouts and code with
sample data, so fonts and the TV picture are approximations of what the box draws. Captures from a real box are
marked as such.

## Using it

- [Home](features/home.md): the four cards, the live preview, the weather line and Settings
- [Live TV](features/live-tv.md): the channel banner, typing a channel number, What's on, Sound and subtitles, recording
- [TV Guide](features/tv-guide.md): the grid, moving around, recording from the guide
- [Recordings](features/recordings.md): the list of recordings, sorting, resuming and deleting
- [Webcams](features/webcams.md): local cameras and church services
- [Plex and experimental Media](features/plex.md): the preserved combined recorded TV and Plex design

## Setting it up

- [Install](setup/install.md): what the box needs, copying Gullion TV to it, channel lists, recording pictures
- [Tech Support](setup/tech-support.md): the PIN, what it locks, the settings, weather, turning Gullion TV off
- [Webcams list](setup/webcams-config.md): editing `webcams.yaml`
- [Plex setup](setup/plex-setup.md): linking an account, choosing the user, server and libraries

## Working on it

- [Development](development.md): the code layout, the offline checks, the screenshot renders, the icons
