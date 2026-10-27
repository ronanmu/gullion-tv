"""Offline check: import GullionTV against stub enigma2 modules, parse every
skin as XML, and drive the MENU hook, home navigation and PIN logic.

	python3 tools/check.py
"""
import os
import sys
import tempfile
import time
import types
import xml.etree.ElementTree as ET

import e2stubs
import sample_epg

e2stubs.install()
from GullionTV import hook, home, plugin, setup, watchagain  # noqa: E402
from GullionTV.plex import client as plex, library as plexlibrary, setup as plexsetup  # noqa: E402
from GullionTV.recordings import store as recordings, thumbnails  # noqa: E402
from GullionTV.tv import converter, guide, infobar as banner, picon, renderer, serviceinfo  # noqa: E402
from GullionTV.ui import icons as ui_icons  # noqa: E402
from GullionTV.ui import background, pin, placeholder, popups, tiles  # noqa: E402
from GullionTV.webcams import config as webcamconfig, screens as webcams, sources  # noqa: E402
from GullionTV.weather import forecast  # noqa: E402
from GullionTV.ui import scale  # noqa: E402
import sample_weather  # noqa: E402
import sample_plex  # noqa: E402
import sample_webcams  # noqa: E402


def theme_rgb(name):
	return guide.theme.rgb(getattr(guide.theme, name))

timers = sample_epg.install()
time.time = lambda: sample_epg.NOW

# A recording drive with plenty of room, unless a test says otherwise.
from GullionTV.recordings import store as drive  # noqa: E402
drive.DEFAULT_FOLDER = tempfile.mkdtemp()
drive.mount_point = lambda path: "/media/hdd"
drive.free_space = lambda path: 500 * drive.GB
drive.mount_type = lambda mount: "ext4"

config = e2stubs.config

for cls in (home.GullionHome, guide.Guide, popups.GullionChoice, popups.EventDetails, pin.TechSupportPin,
		setup.GullionTVSetup, placeholder.ComingSoon):
	root = ET.fromstring(cls.skin)
	print("skin ok: %-22s %d widgets" % (root.get("name"), len(list(root.iter("widget")))))
assert len(plugin.Plugins()) == 2

# MENU opens Gullion TV only while it's enabled.
opened = []
hook.open_home = lambda session: opened.append("home")
hook.install()
infobar = e2stubs.InfoBarMenu()
infobar.session = None
e2stubs.InfoBarMenu.mainMenu(infobar)
assert opened == ["home"], opened
config.plugins.gulliontv.enabled.value = False
e2stubs.InfoBarMenu.mainMenu(infobar)
assert infobar.opened == "stock"
opened[:] = []
info_bar = e2stubs.InfoBarEPG()
info_bar.session = types.SimpleNamespace(open=lambda cls, *a: opened.append(cls.__name__))
config.plugins.gulliontv.enabled.value = True
e2stubs.InfoBarEPG.InfoPressed(info_bar)
assert opened == ["ChannelInfo"], opened
config.plugins.gulliontv.enabled.value = False
e2stubs.InfoBarEPG.InfoPressed(info_bar)
assert info_bar.opened == "stock info"
# OK twice on live TV: the first shows the banner, the second opens the INFO panel.
config.plugins.gulliontv.enabled.value = True
live = e2stubs.InfoBarShowHide()
live.session = info_bar.session
import Screens.InfoBar  # noqa: E402  the stub
Screens.InfoBar.InfoBar.instance = live
opened[:] = []
live._InfoBarShowHide__state = live.STATE_HIDDEN
e2stubs.InfoBarShowHide.toggleShow(live)
assert live.toggled and opened == [], "OK with the banner hidden shows it as normal"
live.toggled = False
live._InfoBarShowHide__state = live.STATE_SHOWN
e2stubs.InfoBarShowHide.toggleShow(live)
assert opened == ["ChannelInfo"] and not live.toggled and live._InfoBarShowHide__state == live.STATE_HIDDEN
player = e2stubs.InfoBarShowHide()
player._InfoBarShowHide__state = player.STATE_SHOWN
e2stubs.InfoBarShowHide.toggleShow(player)
assert player.toggled, "only live TV's banner, not the recordings player's"
Screens.InfoBar.InfoBar.instance = None
opened[:] = []
listener = e2stubs.InfoBarAudioSelection()
listener.session = types.SimpleNamespace(open=lambda cls, *a: opened.append((cls.__name__,) + a[1:]))
e2stubs.InfoBarAudioSelection.audioSelection(listener)
e2stubs.InfoBarSubtitleSupport.subtitleSelection(listener)
assert opened == [("SoundAndSubtitles", "audio"), ("SoundAndSubtitles", "subtitles")], opened
# GUIDE, the arrows, TV and FAV on live TV open Gullion TV's guide, not the stock ones.
opened[:] = []
zapper = e2stubs.InfoBarChannelSelection()
zapper.session = types.SimpleNamespace(open=lambda cls, *a: opened.append(cls.__name__))
modes = []
zapper.servicelist = types.SimpleNamespace(setModeTv=lambda: modes.append("tv"))
Screens.InfoBar.InfoBar.instance = zapper
e2stubs.InfoBarChannelSelection.switchChannelUp(zapper)
e2stubs.InfoBarChannelSelection.showTvChannelList(zapper, True)
e2stubs.InfoBarEPG.EPGPressed(zapper)
assert opened == ["Guide", "Guide", "Guide"] and not hasattr(zapper, "opened"), opened
assert modes == ["tv", "tv", "tv"], "the channel list goes back to TV mode, as the stock TV key does"
config.plugins.gulliontv.enabled.value = False
e2stubs.InfoBarChannelSelection.switchChannelUp(zapper)
assert zapper.opened == "stock channel list", "the stock list while Gullion TV is off"
config.plugins.gulliontv.enabled.value = True
Screens.InfoBar.InfoBar.instance = None
hook.install()
assert not hasattr(e2stubs.InfoBarChannelSelection.switchChannelUp.gullion_original, "gullion_original"), "installing twice doesn't wrap twice"
Screens.InfoBar.InfoBar.instance = None
print("hook ok")
config.plugins.gulliontv.enabled.value = True

# Stock settings and plugin screens ask for the Tech Support PIN, whichever key opens them.
from GullionTV import lock  # noqa: E402


class FakeSession(object):
	def __init__(self):
		self.opened = []

	def open(self, cls, *args, **kwargs):
		dialog = types.SimpleNamespace(cls=cls, onClose=[], callback=None)
		self.opened.append(dialog)
		return dialog

	def openWithCallback(self, callback, cls, *args, **kwargs):
		dialog = self.open(cls, *args, **kwargs)  # as enigma2 does: through self.open
		dialog.callback = callback
		return dialog


Menu = type("Menu", (), {})
PluginBrowser = type("PluginBrowser", (), {})
MainMenu = type("MainMenu", (Menu,), {})
Harmless = type("EventView", (), {})
locked_session = FakeSession()
lock.install(locked_session)
assert lock.is_locked(MainMenu) and not lock.is_locked(Harmless)
locked_session.open(Harmless)
assert locked_session.opened[-1].cls is Harmless, "ordinary screens open as normal"
config.plugins.gulliontv.pin_set.value = True
config.plugins.gulliontv.pin.value = 2580
locked_session.openWithCallback(lambda *a: None, PluginBrowser)
asking = locked_session.opened[-1]
assert asking.cls is pin.TechSupportPin, asking.cls
asking.callback(False)
assert locked_session.opened[-1] is asking, "a wrong PIN opens nothing"
locked_session.openWithCallback(lambda *a: None, PluginBrowser)
locked_session.opened[-1].callback(True)
browser = locked_session.opened[-1]
assert browser.cls is PluginBrowser and browser.callback is not None
locked_session.open(Menu)
assert locked_session.opened[-1].cls is Menu, "screens opened from an unlocked one don't ask again"
for fnc in browser.onClose:
	fnc()
locked_session.open(Menu)
assert locked_session.opened[-1].cls is pin.TechSupportPin, "locked again once it closes"
lock._open_unlocked[0] = 0
lock.grant()
locked_session.open(MainMenu)
assert locked_session.opened[-1].cls is MainMenu, "Home's PIN lets the stock menu straight in"
lock._open_unlocked[0] = 0
locked_session.open(MainMenu)
assert locked_session.opened[-1].cls is pin.TechSupportPin, "the grant is used once"
lock._granted[:] = [time.time() - 60]
locked_session.open(MainMenu)
assert locked_session.opened[-1].cls is pin.TechSupportPin, "an old grant has expired"
extensions = e2stubs.InfoBarExtensions()
extensions.session = locked_session
extensions.showExtensionSelection()
assert locked_session.opened[-1].cls is pin.TechSupportPin and not hasattr(extensions, "opened")
locked_session.opened[-1].callback(True)
assert extensions.opened == "extensions"
config.plugins.gulliontv.enabled.value = False
lock._open_unlocked[0] = 0
locked_session.open(PluginBrowser)
assert locked_session.opened[-1].cls is PluginBrowser, "no lock while Gullion TV is off"
config.plugins.gulliontv.enabled.value = True
config.plugins.gulliontv.pin_set.value = False
print("lock ok")

session = e2stubs.fake_session(now=(0, 3600, "Nationwide"), upcoming=(3600, 1800, "Fair City"))
screen = home.GullionHome(session)
for widget in ET.fromstring(home.GullionHome.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in screen, "skin widget %s missing from screen" % name
screen.layout()
screen.refresh()
for _ in range(5):
	screen.right()
assert screen.selected == 3
screen.down()
assert screen.selected == home.SETTINGS
screen.left()
assert screen.selected == home.SETTINGS
screen.up()
assert screen.selected == 3
screen.down()
screen.ok()
assert session.opened[-1][:2] == ("PinEntry", "Choose a Tech Support PIN"), "no PIN yet, so one is chosen first"
config.plugins.gulliontv.pin_set.value = True
screen.ok()
assert session.opened[-1] == ("TechSupportPin",)
screen.open_item(1)
assert session.opened[-1] == ("Guide",)
screen.open_item(2)
assert session.opened[-1] == ("WatchAgain",)
screen.open_item(0)
assert screen.closed == ("tv",)
assert [card[2] for card in home.CARDS] == ["red", "green", "yellow", "blue"], "cards follow the remote's colour order"
keys = screen["actions"].args[1]
keys["green"]()
assert session.opened[-1] == ("Guide",)
keys["red"]()
assert screen.closed == ("tv",)
from GullionTV.tv import epg as guide_epg  # noqa: E402
zaps, real = [], (guide_epg.channel_lists, guide_epg.zap)
guide_epg.channel_lists = lambda: [("bouquet1", "Saorview", [guide_epg.Channel("ref1", "RTÉ One", 1), guide_epg.Channel("ref2", "RTÉ2", 2)])]
guide_epg.zap = lambda session, ref, bouquet: zaps.append((ref, bouquet))
hook.watch_first_channel(None)
assert zaps == [("ref1", "bouquet1")], "Watch TV goes to channel 1"
guide_epg.channel_lists, guide_epg.zap = real

# Numbering matches the box's: placeholders and hidden lists still take numbers.
real_service = 0
marker, numbered_marker = guide_epg.eServiceReference.isMarker, 256
numbered = guide_epg.number_channels([
	("b1", "Saorview", False, [("m", marker, "Saorview"), ("rte1", real_service, "RTÉ One"), ("p", numbered_marker, "")] + [("p", numbered_marker, "")] * 98),
	("b101", "Entertainment", False, [("m", marker, "Entertainment"), ("bbc1", real_service, "BBC One NI HD"), ("p", numbered_marker, "")]),
	("b400", "Lifestyle", True, [("p", numbered_marker, "")] * 100 + [("hidden", real_service, "Hidden")]),
	("b600", "Children", False, [("cbbc", real_service, lambda: "CBBC")]),
])
assert [name for _, name, _ in numbered] == ["Saorview", "Entertainment", "Children"], "hidden lists aren't shown"
assert [(c.name, c.number) for _, _, channels in numbered for c in channels] == [("RTÉ One", 1), ("BBC One NI HD", 101), ("CBBC", 204)]
print("navigation ok")

config.plugins.gulliontv.pin.value = 1234
prompt = pin.TechSupportPin(session)
for digit in (1, 2, 3, 5):
	prompt.digit(digit)
assert prompt.closed is None and prompt["message"].text
for digit in (1, 2, 3, 4):
	prompt.digit(digit)
assert prompt.closed == (True,)
prompt = pin.TechSupportPin(session)
for _ in range(pin.MAX_TRIES):
	for digit in (9, 9, 9, 9):
		prompt.digit(digit)
assert prompt.closed == (False,)
print("pin ok")

# TV guide.
session = e2stubs.fake_session()
g = guide.Guide(session)
for widget in ET.fromstring(guide.Guide.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in g, "skin widget %s missing from guide" % name
g.layout()
assert g.channels[g.row].name == "RTÉ One" and g.selected_event().title == "Nationwide"
assert g["hints"].text == "OK  Watch          REC  Record          INFO  More details", g["hints"].text
assert g["footer"].text.endswith("OK to watch or record   ·   BACK for home") and g["storage_note"].text == ""
assert time.strftime("%H:%M", time.localtime(g.window_start)) == "19:30"
assert len(g["grid"].list) == guide.ROWS

g.next_event()
assert g.selected_event().title == "Fair City" and g["ev_rec"].text == "Will record"
icons = [entry for entry in g["grid"].list[0][1:] if "png" in entry]
assert len(icons) == 1 and icons[0]["png"] == guide.rec_icon_path() and guide.rec_icon_path().endswith("rec_clock_26.png") and os.path.isfile(guide.rec_icon_path()), "Fair City gets the red clock"
g.next_event()
assert g.selected_event().title == "Prime Time"
g.next_event()
assert g.selected_event().title == "Nine O'Clock News"
assert time.strftime("%H:%M", time.localtime(g.window_start)) == "20:00", "window scrolls to show 21:30"
g.previous_event()
g.previous_event()
assert g.selected_event().title == "Fair City"
g.move_row(1)
assert g.channels[g.row].name == "RTÉ2" and g.selected_event().title == "Champions League Highlights"
g.move_row(guide.ROWS)
assert g.row == 7 and g.top == 2
g.move_row(-100)
assert g.row == 0 and g.top == 0

g.next_event()
g.ok()
assert session.opened[-1][0] == "GullionChoice", session.opened[-1]
before = len(timers)
g.choice_made("record")
assert len(timers) == before + 1
g.record_key()
assert session.opened[-1][0] == "GullionChoice"
g.choice_made("remove")
assert len(timers) == before

g.shift_day(1)
assert g["day1"].instance.background == guide.theme.rgb(guide.theme.CARD)
assert not getattr(g["now_line"], "visible", True)
g.shift_day(-1)
g.jump_to_now()
assert g["now_line"].visible and g["day0"].instance.background == guide.theme.rgb(guide.theme.CARD)
g.next_list()
assert g["list_name"].text == "Saorview" and g.row == 0
g.next_list()
g.next_list()
guide.Guide.last_list = 0

# Picon in the guide: the logo when there is one, otherwise a name card.
picon._found.clear()
picon_dir = tempfile.mkdtemp()
open(os.path.join(picon_dir, "1_0_19_1_1_1_EEEE0000_0_0_0.png"), "wb").close()
picon._system_lookup = lambda channel: os.path.join(picon_dir, "%s.png" % channel.replace(":", "_").strip("_")) if "EEEE" in channel else None
g = guide.Guide(session)
g.layout()
assert g["picon"].instance.pixmap.endswith("1_0_19_1_1_1_EEEE0000_0_0_0.png") and g["picon"].visible
assert not g["picon_fallback"].visible and g["chan_num"].text == "1  RTÉ One"
g.move_row(4)
assert not g["picon"].visible and g["picon_fallback"].visible and g["picon_fallback"].text == "BBC One NI"
assert picon._search("1:0:19:1:1:1:NOPE:0:0:0:") is None
hints = [el.get("text") for el in ET.fromstring(guide.Guide.skin).iter("eLabel") if el.get("text") in ("-24h", "+24h", "List", "Now")]
assert hints == ["-24h", "+24h", "List", "Now"], hints
print("guide picon ok")

# Typing a channel number jumps to it.
g = guide.Guide(session)
g.layout()
assert not g["number_entry"].visible
numbers = [c.number for _, _, channels in g.lists for c in channels]
target = numbers[-1]
for digit in str(target):
	g.type_digit(int(digit))
if g.typed:
	g.go_to_number()  # the 2-second pause
assert g.channels[g.row].number == target and not g["number_entry"].visible, (g.channels[g.row].number, target)
g.type_digit(0)
assert g.typed == "", "a leading 0 is ignored"
missing = max(numbers) + 1
for digit in str(missing):
	g.type_digit(int(digit))
if g.typed:
	g.go_to_number()
assert g["number_entry"].text == "No channel %d" % missing and g["number_entry"].visible
g.hide_number()
assert not g["number_entry"].visible
g.type_digit(1)
g.cancel()
assert g.typed == "" and not getattr(g, "closed", None), "BACK clears a half-typed number first"
guide.Guide.last_list = 0

g = guide.Guide(session)
g.layout()
g.ok()
assert session.zapped == [g.channels[0].ref] and g.closed == ("watch",)
# Access codes in the guide: taken out of the description, shown as icons instead.
g = guide.Guide(session)
g.layout()
coded = guide.epg.Event(1, sample_epg.NOW - 600, 3600, "Blue Lights", "", "Sandra enlists help. [S,AD] [HD]")
g.selected_event = lambda: coded
g.draw_details()
assert g["ev_desc"].text == "Sandra enlists help.", g["ev_desc"].text
shown = [os.path.basename(g["code%d" % i].instance.pixmap).rsplit("_", 1)[0] for i in range(guide.CODE_ICONS) if g["code%d" % i].visible]
assert shown == ["audio_description", "subtitles"], shown
details = []
g.session = types.SimpleNamespace(open=lambda cls, *a: details.append(a), nav=session.nav)
g.show_details()
assert details and details[-1][2] == "Sandra enlists help.", details
print("guide ok")

# INFO on live TV: now, and what's coming up.
from GullionTV.tv import nowinfo  # noqa: E402
info = nowinfo.ChannelInfo(session)
for widget in ET.fromstring(nowinfo.ChannelInfo.skin).iter("widget"):
	assert widget.get("name") in info, "skin widget %s missing from the info panel" % widget.get("name")
info.ref = g.channels[0].ref
info.layout()
coming = [info["next%d" % i].text for i in range(nowinfo.COMING_UP)]
assert info["title"].text and info["title"].text != "No programme information", info["title"].text
assert coming[0], "the next programme is listed"
assert info["channel"].text.startswith("1  "), info["channel"].text
assert info["signal0_label"].text == "", "no tuner details from the stub service"
info.ref = "1:0:19:1:1:1:EEEE0000:0:0:0:"
info.draw_icons("Kay gives Dom an ultimatum. (HD, S, AD)")
shown = [info["icon%d" % i].instance.pixmap if info["icon%d" % i].visible else None for i in range(nowinfo.ICON_SLOTS)]
assert [os.path.basename(p).rsplit("_", 1)[0] if p else None for p in shown] == ["terrestrial", "hd", "audio_description", "subtitles", None, None], shown
assert "(HD" not in info["description"].text, info["description"].text
print("info panel ok")

# YELLOW: sound tracks and subtitles in one pop-up.
from GullionTV.tv import soundsubs  # noqa: E402
assert soundsubs.track_label("NAR", "MPEG") == "Audio description"
assert soundsubs.track_label("Dolby Audio", "AC3") == "Main sound  ·  Dolby"
assert soundsubs.track_label("eng", "MPEG") == "English"
assert soundsubs.track_label("gle", "AAC") == "Irish"
assert soundsubs.subtitle_label((0, 1234, 0, 0, "eng")) == "English"
assert soundsubs.subtitle_label((1, 0, 888, 8, "eng")) == "English  ·  Teletext"


class Track(object):
	def __init__(self, language, codec):
		self.language, self.codec = language, codec

	def getLanguage(self):
		return self.language

	def getDescription(self):
		return self.codec


class Tracks(object):
	def __init__(self):
		self.current = 1
		self.list = [Track("NAR", "MPEG"), Track("Dolby Audio", "AC3")]

	def getNumberOfTracks(self):
		return len(self.list)

	def getTrackInfo(self, i):
		return self.list[i]

	def getCurrentTrack(self):
		return self.current

	def selectTrack(self, i):
		self.current = i


tracks = Tracks()
live_service = types.SimpleNamespace(audioTracks=lambda: tracks)
sound_session = types.SimpleNamespace(nav=types.SimpleNamespace(getCurrentService=lambda: live_service))
subtitle_list = [(0, 1234, 0, 0, "eng")]
watching = types.SimpleNamespace(selected_subtitle=None,
	getCurrentServiceSubtitle=lambda: types.SimpleNamespace(getSubtitleList=lambda: subtitle_list))
watching.enableSubtitle = lambda subtitle: setattr(watching, "selected_subtitle", subtitle)
popup = soundsubs.SoundAndSubtitles(sound_session, watching)
for widget in ET.fromstring(soundsubs.SoundAndSubtitles.skin).iter("widget"):
	assert widget.get("name") in popup, widget.get("name")
popup.layout()


def column(screen, c):
	return [screen["col%d_row%d" % (c, i)].text for i in range(len(screen.columns[c]))]


def ticked(screen, c):
	return [i for i in range(len(screen.columns[c])) if screen["col%d_row%d_tick" % (c, i)].visible]


assert column(popup, soundsubs.SOUND) == ["Audio description", "Main sound  ·  Dolby"]
assert column(popup, soundsubs.SUBTITLES) == ["Off", "English"]
assert popup.column == soundsubs.SOUND and popup.row[0] == 1 and ticked(popup, 0) == [1], "opens on the track that's playing"
assert ticked(popup, 1) == [0], "subtitles are off"
assert popup["col0_row0_icon"].instance.pixmap.endswith("audio_description_40.png")
assert popup["col0_row1_tick"].instance.pixmap.endswith("check_on_light_40.png"), "a dark tick on the highlighted row"
popup.move(-1)
popup.choose()
assert tracks.current == 0 and ticked(popup, 0) == [0], "OK switches to audio description"
popup.switch(soundsubs.SUBTITLES)
popup.move(1)
popup.choose()
assert watching.selected_subtitle == (0, 1234, 0, 0, "eng") and ticked(popup, 1) == [1]
popup.move(-1)
popup.choose()
assert watching.selected_subtitle is None and ticked(popup, 1) == [0], "Off turns them off"
assert not popup["col1_row2_bg"].visible, "unused rows are hidden"
subs_first = soundsubs.SoundAndSubtitles(sound_session, watching, "subtitles")
subs_first.layout()
assert subs_first.column == soundsubs.SUBTITLES, "SUBTITLE opens on the subtitles"
subtitle_list[:] = []
tracks.list = tracks.list[:1]
none = soundsubs.SoundAndSubtitles(sound_session, watching)
none.layout()
assert column(none, 0) == ["Only one sound track"] and column(none, 1) == ["None for this programme"]
assert not none["col0_row0_bg"].visible, "a note isn't drawn as a choice"
none.choose()
print("sound and subtitles ok")

# Channel banner: plain-language service facts.
assert serviceinfo.delivery("1:0:19:1:1:1:EEEE0000:0:0:0:") == "Terrestrial"
assert serviceinfo.delivery("1:0:19:1B58:802:2:11A0000:0:0:0:") == "Satellite  ·  28.2°E"
assert serviceinfo.delivery("1:0:1:1:1:1:E080000:0:0:0:") == "Satellite  ·  0.8°W"
assert serviceinfo.delivery("4097:0:1:0:0:0:0:0:0:0:https%3a//example.ie/live.m3u8:Church") == "Internet stream"
assert serviceinfo.delivery("") == ""
assert serviceinfo.is_hd("1:0:19:1:1:1:EEEE0000:0:0:0:")
assert not serviceinfo.is_hd("1:0:1:1:1:1:EEEE0000:0:0:0:")
assert not serviceinfo.is_hd("1:0:19:1:1:1:EEEE0000:0:0:0:", 576), "decoded height wins over service type"
assert serviceinfo.is_hd("1:0:1:1:1:1:EEEE0000:0:0:0:", 1080)
assert serviceinfo.remaining(65 * 60) == "1 hr 5 min left"
assert serviceinfo.split_codes("Homeowners compete for the title. (HD, S, R)") == ("Homeowners compete for the title.", ["HD", "S", "R"])
assert serviceinfo.split_codes("A trip across the USA (USA)") == ("A trip across the USA (USA)", []), "other brackets stay"
assert serviceinfo.split_codes("No codes here") == ("No codes here", [])
assert serviceinfo.split_codes("Contains strong language. [S,AD] [HD]") == ("Contains strong language.", ["S", "AD", "HD"]), "Freesat's form"
assert serviceinfo.badges("Kay gives Dom an ultimatum. (HD, S, AD, SL)") == ["S", "AD", "SL"], "HD comes from the channel"
assert serviceinfo.delivery_kind("1:0:19:1:1:1:EEEE0000:0:0:0:") == "terrestrial"
assert serviceinfo.delivery_kind("1:0:19:1B58:802:2:11A0000:0:0:0:") == "satellite"
assert serviceinfo.delivery_kind("4097:0:1:0:0:0:0:0:0:0:https%3a//example.ie/live.m3u8:Church") == "internet"
details = serviceinfo.signal_details(
	{"tuner_signal_quality": 55705, "tuner_signal_quality_db": 1234, "tuner_signal_power": 39321, "tuner_bit_error_rate": 0, "tuner_number": 0},
	{"tuner_type": "DVB-S", "frequency": 11428000, "polarization": 0, "symbol_rate": 27500000})
assert details == [("Quality", "85%"), ("SNR", "12.3 dB"), ("Power", "60%"), ("Errors", "0"), ("Tuner", "A"), ("Frequency", "11428 H"), ("Symbol rate", "27500")], details
assert serviceinfo.signal_details({}, {"tuner_type": "DVB-T", "frequency": 690000000}) == [("Frequency", "690 MHz")]
assert serviceinfo.signal_details(None, None) == [], "a stream has no tuner"
print("service info ok")

saorview_hd = "1:0:19:1:1:1:EEEE0000:0:0:0:"
for kind, expected in (("Number", "1"), ("Name", "RTÉ One")):
	c = converter.GullionServiceInfo(kind)
	c.source = e2stubs.fake_service(saorview_hd, name="\xc2\x86RTÉ One\xc2\x87")
	assert c.text == expected, (kind, c.text)
c = converter.GullionServiceInfo("Remaining")
c.source = types.SimpleNamespace(event=types.SimpleNamespace(getBeginTime=lambda: sample_epg.NOW - 42 * 60, getDuration=lambda: 3600))
assert c.text == "18 min left" and c.poll_enabled
c.changed((c.CHANGED_SPECIFIC, 6))
assert not c.notified, "unrelated service events are ignored"
c.changed((c.CHANGED_SPECIFIC, 0))
assert c.notified and not converter._numbers, "a channel change re-reads channel numbers"
event_now = types.SimpleNamespace(event=types.SimpleNamespace(getShortDescription=lambda: "",
	getExtendedDescription=lambda: "Kay gives Dom an ultimatum. (HD, S, AD)"))
playing = {"ref": saorview_hd, "height": 1080}
converter._playing = lambda: (playing["ref"], playing["height"])
row = []
for slot in range(1, 6):
	c = converter.GullionServiceInfo("Icon:%d" % slot)
	c.source = event_now
	row.append(c.text)
assert row == ["terrestrial", "hd", "audio_description", "subtitles", ""], row
playing["height"] = 576
c = converter.GullionServiceInfo("Icon:2")
c.source = event_now
assert c.text == "audio_description", "no icon for SD"
playing["height"] = 2160
assert converter.GullionServiceInfo("Icon:2").__class__ and serviceinfo.icon_row(saorview_hd, 2160, "")[0] == "uhd"
assert serviceinfo.icon_row("1:0:1:1:1:1:EEEE0000:0:0:0:", -1, "Old film. (R)") == ["repeat", "terrestrial"]
for name in ("hd", "uhd", "subtitles", "audio_description", "sign_language", "repeat", "satellite", "terrestrial", "cable", "internet"):
	assert os.path.isfile(ui_icons.icon_path(name)), ui_icons.icon_path(name)
print("converter ok")

import skin  # noqa: E402  the stub
skin.domScreens = {"InfoBar": ("stock InfoBar element", "/usr/share/enigma2/skin")}  # OpenATV 6.4's name
config.plugins.gulliontv.infobar.value = True
plugin.sessionstart(0, session=FakeSession())
element, path = skin.domScreens["InfoBar"]
assert skin.dom_screens["InfoBar"][0] == "stock InfoBar element", "OpenATV 6.4's table is used when it's there"
del skin.domScreens
banner.install()
assert skin.dom_screens["InfoBar"][0].get("name") == "InfoBar", "newer images' table otherwise"
assert element.get("name") == "InfoBar" and path.endswith("GullionTV")
assert sys.modules["Components.Converter.GullionServiceInfo"] is converter
assert sys.modules["Components.Renderer.GullionIcon"] is renderer
known = {"ServiceName", "FrontendInfo", "GullionServiceInfo", "ClockToText", "ConditionalShowHide", "EventTime", "EventName"}
for widget in element.iter("widget"):
	assert widget.get("source"), "banner widgets must come from sources, not screen code"
	x, y = [int(v) for v in widget.get("position").split(",")]
	w, h = [int(v) for v in widget.get("size").split(",")]
	assert 0 <= x and x + w <= 1920 and banner.PANEL_Y <= y and y + h <= banner.PANEL_Y + banner.PANEL_H, widget.attrib
	for convert in widget.iter("convert"):
		assert convert.get("type") in known, convert.get("type")
		if convert.get("type") == "GullionServiceInfo":
			assert convert.text in ("Number", "Name", "Remaining") or convert.text.startswith("Icon:"), convert.text
assert len([w for w in element.iter("widget") if w.get("render") == "GullionIcon"]) == banner.ICON_SLOTS
for name in ("NumberZap", "Volume"):
	popup, path = skin.dom_screens[name]
	assert popup.get("name") == name and path.endswith("GullionTV")
print("infobar ok")

# Webcams: the config file.
entries, problems = webcamconfig.parse(sample_webcams.CONFIG)
assert [entry.kind for entry in entries] == ["mcn", "churchservices", "playlist", "stream", "stream"], [e.kind for e in entries]
assert entries[0].name == "St Malachy's Parish" and entries[0].group == "Church"
assert problems == ["Line 17: add a url"], problems
entries2, problems2 = webcamconfig.parse("""webcams:
  - name: "Harbour # 2"   # a comment
    url: https://example.com/live.m3u8
    player: 5002
  - name: Odd
    url: http://x
    type: telly
""")
assert entries2[0].name == "Harbour # 2" and entries2[0].player == 5002
assert problems2 == ["Line 5: type should be one of mcn, churchservices, stream, playlist"], problems2
assert webcamconfig.parse("cameras:\n  - name: x\n")[1] == ["Line 1: the file should start with 'webcams:'"]
assert webcamconfig.load("/nonexistent/webcams.yaml") == ([], [])
print("webcam config ok")

# Webcams: finding streams, pictures and status.
fetch = sample_webcams.fake_fetch
cams = sources.expand(entries, fetch)
assert [cam.name for cam in cams] == ["St Malachy's Parish", "Armagh Cathedral", "Main Street", "Harbour", "Bridge", "Front door"]
assert cams[2].image == "http://cams.example/main-street.jpg" and cams[3].url == "http://cams.example/harbour.m3u8"
assert cams[3].group == "Local"
for cam in cams:
	sources.check(cam, fetch, now=sample_webcams.NOW)
assert [cam.status for cam in cams] == ["live", "live", "live", "live", "offline", "ready"], [cam.status for cam in cams]
assert cams[0].stream == "https://cdn.example/live/stmalachys.stream/playlist.m3u8"
assert cams[0].image.endswith("ProfileImages/stmalachys.jpeg")
assert cams[1].detail == "Daily Mass tomorrow 10:00", "private services are left out: %s" % cams[1].detail
assert sources.status_line(cams[1]) == "Live now  ·  Daily Mass tomorrow 10:00"
assert sources.status_line(cams[4]) == "Not live right now"
assert sources.describe_schedule([(100, 200, "Mass")], 150) == "Mass on now"
assert cams[0].service_ref() == "4097:0:1:0:0:0:0:0:0:0:https%3a//cdn.example/live/stmalachys.stream/playlist.m3u8:St Malachy's Parish"
assert cams[0].source_label == "mcn.live" and cams[2].source_label == "Internet stream"
unreachable = sources.Webcam(webcamconfig.Entry("Gone", "https://mcn.live/Camera/gone"))
assert sources.check(unreachable, fetch).status == "broken"
bad_list = sources.expand([webcamconfig.Entry("Empty", "http://nowhere.example/x.m3u")], fetch)
assert len(bad_list) == 1 and bad_list[0].status == "broken"

thumbs = tempfile.mkdtemp()
sample_webcams.PICTURES["https://cdn.example/live/Uploads/ProfileImages/stmalachys.jpeg"] = b"jpeg bytes"
path = sources.download_thumbnail(cams[0], fetch, thumbs)
assert path and open(path, "rb").read() == b"jpeg bytes" and path.endswith(".jpg")
assert sources.download_thumbnail(cams[4], fetch, thumbs) is None
print("webcam sources ok")

# Webcams: the screens.
sources.fetch = sample_webcams.fake_fetch
sources.THUMB_DIR = thumbs
config_file = os.path.join(thumbs, "webcams.yaml")
with open(config_file, "w") as handle:
	handle.write(sample_webcams.CONFIG)
session = e2stubs.fake_session()
grid = webcams.WebcamList(session, config_file)
for widget in ET.fromstring(webcams.WebcamList.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in grid, "skin widget %s missing from webcams" % name
assert grid["tile0_status"].text == "", "nothing drawn before layout"
grid.layout()
grid.worker.join(5)
grid.repaint_if_changed()
assert grid["tile0_name"].text == "St Malachy's Parish" and grid["tile0_status"].text == "Live now"
assert grid["tile0_image"].instance.pixmap == path, "the downloaded picture is shown"
assert grid["tile4_status"].text == "Not live right now" and grid["tile5_status"].text == "Ready to watch"
assert grid["note"].text.startswith("1 webcam couldn't be read") and grid["page"].text == ""
assert grid["tile0_band"].instance.background == theme_rgb("CARD_SELECTED")
grid.move(1)
assert grid.selected == 1 and grid["tile1_band"].instance.background == theme_rgb("CARD_SELECTED")
grid.move(webcams.COLS)
assert grid.selected == 4
grid.move(webcams.COLS)
assert grid.selected == 4, "no row below"
grid.ok()
assert session.opened[-1][0] == "GullionChoice" and session.opened[-1][2][0] == ("Try anyway", "play")
grid.move(-4)
grid.ok()
assert session.opened[-1] == ("WebcamPlayer", grid.webcams[0])
grid.leave()
assert grid.closing and grid.closed == ()

empty = webcams.WebcamList(session, "/nonexistent/webcams.yaml")
empty.layout()
assert empty["empty_title"].text == "No webcams yet" and not empty["tile0_name"].visible
print("webcam list ok")

player = webcams.WebcamPlayer(session, grid.webcams[0])
player.layout()
assert session.nav.played[-1].ref == grid.webcams[0].service_ref()
assert player["source"].text == "Church · mcn.live" and player["badge"].text == "Live"
player.check_picture()
assert player["message"].text == "Connecting..."
for _ in range(player.GIVE_UP_SECONDS):
	player.check_picture()
assert "isn't sending a picture" in player["message"].text
player.toggle_banner()
assert not player["panel"].visible
player.toggle_banner()
assert player["panel"].visible
player.leave()
assert session.nav.played[-1].name == "RTÉ One", "the channel from before is put back"

player = webcams.WebcamPlayer(session, grid.webcams[1])
player.layout()
session.picture["height"] = 1080
player.check_picture()
assert not player["message"].visible, "the Connecting message goes once there's a picture"
session.picture["height"] = -1
print("webcam player ok")

# Recordings on disk.
e2stubs.SERVICE_NAMES.update({"1:0:19:1:1:1:EEEE0000:0:0:0:": "RTÉ One", "1:0:19:5:1:1:11A0000:0:0:0:": "BBC One NI",
	"1:0:19:4:1:1:EEEE0000:0:0:0:": "TG4", "1:0:19:8:1:1:11A0000:0:0:0:": "Channel 4", "1:0:19:6:1:1:11A0000:0:0:0:": "BBC Two NI"})
folder = sample_plex.make_recordings(os.path.join(tempfile.mkdtemp(), "movie"))
recordings.DEFAULT_FOLDER = folder
found = recordings.list_recordings(folder, watchagain._channel_name)
assert [r.title for r in found] == ["Fair City", "MasterChef", "Nationwide", "Ros na Rún", "Grand Designs", "Gardeners' World"]
fair_city = found[0]
assert fair_city.channel == "RTÉ One" and fair_city.duration == 30 * 60 and fair_city.position == 12 * 60
assert fair_city.in_progress and abs(fair_city.progress - 0.4) < 0.01
assert not found[2].in_progress, "watched to the end"
assert found[1].progress is None and found[1].when(sample_plex.NOW) == "Yesterday 21:00", found[1].when(sample_plex.NOW)
assert fair_city.service_ref == "1:0:0:0:0:0:0:0:0:0:" + fair_city.path
assert recordings.list_recordings("/nonexistent") == []
print("recordings ok")

# Plex client.
settings_file = os.path.join(tempfile.mkdtemp(), "gulliontv", "plex.json")
settings = plex.load_settings(settings_file)
assert settings["client_id"] and settings["remote_kbps"] == 8000 and not plex.is_configured(settings)
plex.save_settings(dict(settings, account_token="secret"), settings_file)
assert oct(os.stat(settings_file).st_mode & 0o777) == oct(0o600), "the token file is private"
assert plex.load_settings(settings_file)["client_id"] == settings["client_id"]

fake = sample_plex.FakePlex("home")
client = plex.Client(sample_plex.configured_settings(), fake)
assert client.create_pin() == (111, "GT4K")
assert client.check_pin(111) is None and client.check_pin(111) == "account-token"
users = client.home_users("account-token")
assert [u["title"] for u in users] == ["Alex", "Sam"] and users[1]["protected"]
assert client.switch_user("account-token", users[1], "1234") == "sam-token"
try:
	client.switch_user("account-token", users[1], "9999")
	raise AssertionError("a wrong Plex PIN should fail")
except plex.PlexError:
	pass
servers = client.servers("sam-token")
assert [s["name"] for s in servers] == ["Gullion Plex"], "players and phones are left out"
client.settings.pop("last_uri")
assert client.connect(servers[0])["uri"] == sample_plex.LOCAL and plex.Client.describe(client.connect(servers[0])) == "local"
assert not client.is_remote()
away = plex.Client(dict(sample_plex.configured_settings(), last_uri=sample_plex.LOCAL), sample_plex.FakePlex("away"))
connection = away.connect()
assert connection["uri"] == sample_plex.REMOTE and plex.Client.describe(connection) == "remote (direct)", "relay is the last resort"
assert away.is_remote() and away.settings["last_uri"] == sample_plex.REMOTE
headers = client.headers("t")
assert headers["X-Plex-Token"] == "t" and headers["X-Plex-Client-Identifier"] == "test-client" and headers["Accept"] == "application/json"

assert [s["title"] for s in client.sections()] == ["Films", "TV Programmes"], "only film and TV libraries"
watching = client.continue_watching()
assert [i.heading for i in watching] == ["Line of Duty", "The Commitments"], "items from other libraries are left out"
assert watching[0].subheading == "S6 E3  ·  Episode 3" and abs(watching[0].progress - 22 / 60.0) < 0.01
assert watching[1].subheading == "1991"
recent = client.recently_added()
assert [i.heading for i in recent] == ["The Banshees of Inisherin", "Derry Girls", "Brooklyn", "Normal People"]
url = client.image_url("/library/metadata/601/thumb", 328, 184)
assert url.startswith(sample_plex.LOCAL + "/photo/:/transcode?") and "X-Plex-Token=server-token" in url and "width=328" in url
print("plex client ok")

# Tech Support setup, start to finish.
session = e2stubs.fake_session()
setup_screen = plexsetup.PlexSetup(session, settings_file, sample_plex.FakePlex("home"))
setup_screen.settings.pop("account_token", None)
setup_screen.layout()
assert [row[1] for row in setup_screen.rows()] == ["link"]
setup_screen.ok()
assert session.opened[-1][0] == "PlexLink"
setup_screen.linked("account-token")
setup_screen.background.wait()
assert session.opened[-1][0] == "OptionList" and [o[0] for o in session.opened[-1][2]] == ["Alex", "Sam"]
setup_screen.user_picked(1, True)
assert session.opened[-1][0] == "PinEntry", "Sam's Plex profile has a PIN"
setup_screen.user_chosen(setup_screen.users[1], "1234", True)
setup_screen.background.wait()
assert setup_screen.settings["user_token"] == "sam-token"
setup_screen.background.wait()
assert session.opened[-1][0] == "OptionList" and session.opened[-1][1] == "Choose the server"
setup_screen.server_picked(0, True)
setup_screen.background.wait()
assert setup_screen.settings["server"]["name"] == "Gullion Plex" and setup_screen.settings["last_uri"] == sample_plex.LOCAL
setup_screen.background.wait()
assert session.opened[-1][0] == "OptionList" and session.opened[-1][4] == {"toggles": ["1", "2"]}, "every library ticked to start"
setup_screen.libraries_chosen({"1", "2"})
saved = plex.load_settings(settings_file)
assert plex.is_configured(saved) and saved["user"]["title"] == "Sam" and saved["section_names"] == ["Films", "TV Programmes"]
assert setup_screen["fact_server"].text == "Gullion Plex  ·  local" and setup_screen["fact_user"].text == "Sam"
setup_screen.step_quality()
assert setup_screen.settings["remote_kbps"] == 12000
setup_screen.step_subtitles()
assert setup_screen.settings["subtitles"] is True
setup_screen.unlink_chosen("unlink")
assert not plex.is_configured(plex.load_settings(settings_file))
print("plex setup ok")

link = plexsetup.PlexLink(session, plex.Client(plex.load_settings(settings_file), sample_plex.FakePlex()))
link.layout()
link.background.wait()
assert link["code"].text == "GT4K"
link.check()
link.background.wait()
assert link.closed is None
link.check()
link.background.wait()
assert link.closed == ("account-token",)
print("plex link ok")

picker = plexsetup.OptionList(session, "Libraries", [("Films", "1"), ("TV Programmes", "2")], toggles=["1"])
picker.layout()
assert picker["row0_value"].text == "On" and picker["row1_value"].text == "Off" and picker["row2"].text == "Done"
picker.move(1)
picker.ok()
assert picker["row1_value"].text == "On"
picker.move(1)
picker.ok()
assert picker.closed == ({"1", "2"},)

# Watch again with recorded TV and Plex.
plex.http_request = sample_plex.FakePlex("home")
sources.fetch = lambda url, binary=False, timeout=8: b"picture"
watchagain.PLEX_THUMBS = tempfile.mkdtemp()
session = e2stubs.fake_session()
screen = watchagain.WatchAgain(session, sample_plex.configured_settings())
for widget in ET.fromstring(watchagain.WatchAgain.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in screen, "skin widget %s missing from Watch again" % name
del session.nav.played[:]
screen.layout()
assert session.nav.played == [None], "live TV stops while Watch again is open"
screen.background.wait()
assert [section["title"] for section in screen.sections] == ["Continue watching", "Recently added to Plex", "Recorded TV"]
assert [tile.title for tile in screen.sections[0]["tiles"]] == ["Fair City", "Line of Duty", "The Commitments"], "most recently watched first"
assert screen.sections[0]["tiles"][0].subtitle == "RTÉ One  ·  18 min left"
assert screen.sections[0]["tiles"][2].subtitle == "44 min left"
assert screen.sections[0]["tiles"][1].image and os.path.isfile(screen.sections[0]["tiles"][1].image)
assert screen["slot0_title"].text == "Continue watching" and screen["slot1_title"].text == "Recently added to Plex"
assert screen["slot0_tile0_band"].instance.background == theme_rgb("CARD_SELECTED")
assert [b[0] for b in screen.buttons] == ["Films", "TV programmes", "All recordings"]
screen.move_down(1)
screen.move_down(1)
assert screen.top == 1 and screen["slot1_title"].text == "Recorded TV", "rows scroll up as you go down"
screen.move_down(1)
assert screen.browsing and screen["button0"].instance.background == theme_rgb("CARD_SELECTED")
screen.move_across(2)
screen.ok()
assert session.opened[-1] == ("AllRecordings",)
screen.plex_ready(([], []), None)
assert screen.browsing, "stays on Browse when rows change"
screen.move_down(-1)
screen.ok()
assert session.opened[-1][0] == "RecordingPlayer" and session.opened[-1][1].ref == fair_city.service_ref
screen.plex_ready(None, plex.PlexError("down"))
assert screen["note"].text == "Plex isn't reachable right now"

plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert [section["title"] for section in plain.sections] == ["Continue watching", "Recorded TV"] and [b[0] for b in plain.buttons] == ["All recordings"]
print("watch again ok")

grid = watchagain.AllRecordings(session)
grid.layout()
grid.background.wait()
assert grid["tile0_name"].text == "Fair City" and grid["tile5_name"].text == "Gardeners' World" and not grid["tile6_name"].visible
grid.move(1)
grid.delete()
assert session.opened[-1][0] == "GullionChoice" and session.opened[-1][1] == "Delete MasterChef?"
grid.delete_chosen("delete")
grid.background.wait()
assert [r.title for r in grid.recordings][:2] == ["Fair City", "Nationwide"]
trash = os.path.join(folder, ".Trash")
assert sorted(os.listdir(trash)) == ["20261026 2100 - BBC One NI - MasterChef.ts", "20261026 2100 - BBC One NI - MasterChef.ts.meta"]
print("all recordings ok")

# Recording drive check.
assert recordings.storage("/nonexistent/movie") == (recordings.MISSING, 0)
for free, state in ((500, recordings.READY), (5, recordings.LOW), (1, recordings.FULL)):
	recordings.free_space = lambda path, free=free: free * recordings.GB
	assert recordings.storage(folder)[0] == state, (free, state)
recordings.mount_point = lambda path: "/"
assert recordings.storage(folder)[0] == recordings.MISSING, "the box's own flash doesn't count"
recordings.mount_point = lambda path: "/media"
recordings.mount_type = lambda mount: "tmpfs"
assert recordings.storage(folder)[0] == recordings.MISSING, "an empty folder in memory, waiting for a drive, doesn't count"
recordings.mount_type = lambda mount: "ext4"
recordings.mount_point = lambda path: "/"
assert recordings.can_record(recordings.LOW) and not recordings.can_record(recordings.FULL)

session = e2stubs.fake_session()
g = guide.Guide(session)
g.layout()
assert g.storage == recordings.MISSING
assert g["hints"].text == "OK  Watch          INFO  More details", "no REC hint when the box can't record"
assert g["footer"].text.endswith("OK to watch   ·   BACK for home") and g["storage_note"].text == "Recording isn't available"
g.record_key()
assert session.opened[-1][:2] == ("GullionChoice", "This box can't record right now")
g.choice_made("record")
assert session.opened[-1][:2] == ("GullionChoice", "This box can't record right now")
g.next_event()
assert g.selected_event().title == "Fair City" and g["hints"].text == "INFO  More details"
g.ok()
assert session.opened[-1][2][0] == ("Don't record", "remove"), "a recording already set can still be cancelled"
g.next_event()
g.ok()
assert session.opened[-1][:2] == ("GullionChoice", "This box can't record right now")

recordings.mount_point = lambda path: "/media/hdd"
recordings.free_space = lambda path: 1 * recordings.GB
g = guide.Guide(session)
g.layout()
g.record_key()
assert session.opened[-1][:2] == ("GullionChoice", "The recording drive is full") and g["storage_note"].text == "The recording drive is full"
recordings.free_space = lambda path: 5 * recordings.GB
g = guide.Guide(session)
g.layout()
assert "REC  Record" in g["hints"].text and g["storage_note"].text == "Recording space is low"

recordings.mount_point = lambda path: "/"
recordings.DEFAULT_FOLDER = tempfile.mkdtemp()
plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert plain["slot0_empty"].text == "Recording isn't set up on this box. Ask Tech Support to check the recording drive."
recordings.mount_point = lambda path: "/media/hdd"
plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert plain["slot0_empty"].text.startswith("No recordings yet. Press REC")
print("recording drive ok")

# Plex pictures: landscape for the Watch again rows, posters as a fallback.
recordings.DEFAULT_FOLDER = folder
recordings.mount_point = lambda path: "/media/hdd"
recordings.free_space = lambda path: 500 * recordings.GB
items = dict((item.title, item) for item in plex.Client(sample_plex.configured_settings(), sample_plex.FakePlex()).recently_added())
assert items["The Night Before"].landscape == "/library/metadata/502/still", "an episode uses its own still"
assert items["The Banshees of Inisherin"].landscape == "/library/metadata/602/art" and items["The Banshees of Inisherin"].poster.endswith("/thumb")
assert items["Brooklyn"].landscape is None and items["Brooklyn"].poster
session = e2stubs.fake_session()
screen = watchagain.WatchAgain(session, sample_plex.configured_settings())
screen.layout()
screen.background.wait()
recent = dict((tile.title, tile) for tile in screen.sections[1]["tiles"])
assert recent["Brooklyn"].image is None and recent["Brooklyn"].poster, "only a poster, so it sits at the left"
assert all(tile.badge == "Plex" for tile in screen.sections[1]["tiles"])
continuing = screen.sections[0]["tiles"]
assert [tile.badge for tile in continuing] == ["", "Plex", "Plex"], "recordings and Plex told apart"
screen.paint()
assert screen["slot0_tile1_badge"].text == "Plex" and screen["slot0_tile1_badge"].visible and not screen["slot0_tile0_badge"].visible
brooklyn = [i for i, tile in enumerate(screen.sections[1]["tiles"]) if tile.title == "Brooklyn"][0]
assert screen["slot1_tile%d_poster" % brooklyn].visible and not screen["slot1_tile%d_image" % brooklyn].visible
print("plex pictures ok")

# Recording pictures.
sample = recordings.list_recordings(folder)[0]
assert sample.image is None
calls = []


def fake_ffmpeg(arguments, sizes=[200, 9000]):
	calls.append(arguments)
	with open(arguments[-1], "wb") as handle:
		handle.write(b"x" * sizes[min(len(calls) - 1, len(sizes) - 1)])
	return 0


made = thumbnails.make(sample, "/usr/bin/ffmpeg", fake_ffmpeg)
assert made == sample.path + ".jpg" and os.path.getsize(made) == 9000, "a nearly blank first try is taken again further in"
assert calls[0][calls[0].index("-ss") + 1] == str(int(sample.duration * 0.10)) and calls[1][calls[1].index("-ss") + 1] == str(int(sample.duration * 0.25))
assert "scale=328:184" in calls[0] and not os.path.exists(made + ".part")
assert recordings.read(sample.path).image == made
tile = watchagain.recording_tile(recordings.read(sample.path))
assert tile.image == made and tile.logo == picon.picon_path(sample.channel_ref), "the frame, with the channel's logo in the corner"
assert thumbnails.make(sample, None, fake_ffmpeg) is None or thumbnails.find_ffmpeg(), "no ffmpeg, no picture"
assert thumbnails.make_missing(recordings.list_recordings(folder), 12, "/usr/bin/ffmpeg", lambda arguments: 1) == 0
os.remove(made)

ended = []
thumbnails.make = lambda recording, *args: ended.append(recording.title)
timer_list = types.SimpleNamespace(on_state_change=[])
thumbnails.watch_recordings(types.SimpleNamespace(nav=types.SimpleNamespace(RecordTimer=timer_list)))
assert len(timer_list.on_state_change) == 1
on_change = timer_list.on_state_change[0]
on_change(types.SimpleNamespace(state=2, Filename=os.path.splitext(sample.path)[0]))
on_change(types.SimpleNamespace(state=3, Filename=os.path.splitext(sample.path)[0]))
for _ in range(50):
	if ended:
		break
	time.sleep(0.02)
assert ended == ["Fair City"], "a picture is made when a recording finishes, not while it runs"
print("recording pictures ok")

# Films and TV programmes.
plexlibrary.POSTERS = tempfile.mkdtemp()
session = e2stubs.fake_session()
films = plexlibrary.PlexLibrary(session, sample_plex.configured_settings(), plex.MOVIE, sample_plex.FakePlex())
for widget in ET.fromstring(plexlibrary.PlexLibrary.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in films, "skin widget %s missing from the library" % name
films.layout()
assert films["empty"].text == "Loading..."
films.background.wait()
assert films.total == 36 and films["summary"].text == "36 films  ·  A to Z" and films["page"].text == "Page 1 of 3"
assert [films["tile%d_name" % i].text for i in range(3)] == ["Adam and Paul", "An Cailin Ciuin", "The Banshees of Inisherin"]
assert sorted(films.pages) == [0, 1], "the next page is fetched ahead"
assert films["tile0_image"].instance.pixmap and films["key_green"].text == "Newest first" and not films["key_blue_dot"].visible
belfast = [i for i in range(16) if films["tile%d_name" % i].text == "Belfast"][0]
assert films["tile%d_progress" % belfast].value > 0, "part-watched films show how far through"
films.move(plexlibrary.PER_PAGE)
films.background.wait()
assert films.selected == 16 and films["page"].text == "Page 2 of 3" and films["tile0_band"].instance.background == theme_rgb("CARD_SELECTED")
films.move(100)
assert films.selected == 35
films.toggle_order()
films.background.wait()
assert films["tile0_name"].text == "The Banshees of Inisherin" and films["summary"].text == "36 films  ·  Newest first" and films.selected == 0
films.toggle_unwatched()
films.background.wait()
assert films.total == 27 and films["summary"].text == "27 unwatched films  ·  Newest first" and films["key_yellow"].text == "Everything"
films.ok()
assert session.opened[-1][:2] == ("GullionChoice", films.selected_item().title)

shows = plexlibrary.PlexLibrary(session, sample_plex.configured_settings(), plex.SHOW, sample_plex.FakePlex())
shows.layout()
shows.background.wait()
names = [shows["tile%d_name" % i].text for i in range(16)]
assert names[:3] == ["Bad Sisters", "Ballykissangel", "Blue Lights"] and shows["heading"].text == "TV programmes"
badge = dict((shows["tile%d_name" % i].text, shows["tile%d_badge" % i].text) for i in range(16))
assert badge["Bad Sisters"] == "8 to watch" and badge["Derry Girls"] == "Watched" and badge["Holding"] == ""
assert shows["tile0_sub"].text == "2 series" and shows["summary"].text == "20 programmes  ·  A to Z"

mixed = sample_plex.configured_settings()
mixed["sections"] = ["2"]
nothing = plexlibrary.PlexLibrary(session, mixed, plex.MOVIE, sample_plex.FakePlex())
nothing.layout()
nothing.background.wait()
assert nothing["empty"].text == "Tech Support hasn't chosen a film library"
print("plex library ok")

# Choosing the Tech Support PIN the first time.
assert config.plugins.gulliontv.pin.args[0] == 0, "there's no default PIN"
assert [p for p in ("0000", "1111", "1234", "4321", "6789", "4821", "1357") if pin.weak(p)] == ["0000", "1111", "1234", "4321", "6789"]
config.plugins.gulliontv.pin_set.value = False
config.plugins.gulliontv.pin.value = 0
session = e2stubs.fake_session()
results = []
chooser = pin.PinChooser(session, results.append)
chooser.start()
assert session.opened[-1][1:3] == ("Choose a Tech Support PIN", "This is the first time Settings has been opened. Choose a 4-digit PIN for Tech Support.")
chooser.chosen("1234")
assert session.opened[-1][2] == "That PIN is too easy to guess. Choose another."
chooser.chosen("4821")
assert session.opened[-1][1] == "Enter the PIN again"
chooser.confirmed("4821", "4812")
assert session.opened[-1][2] == "Those didn't match. Choose a PIN again." and not config.plugins.gulliontv.pin_set.value
chooser.confirmed("4821", "4821")
assert results == [True] and config.plugins.gulliontv.pin.value == 4821 and config.plugins.gulliontv.pin_set.value
assert not config.plugins.gulliontv.pin.isChanged(), "the PIN is saved"
chooser.chosen(None)
assert results == [True, False], "BACK abandons it"
prompt = pin.TechSupportPin(session)
for digit in (4, 8, 2, 1):
	prompt.digit(digit)
assert prompt.closed == (True,), "the chosen PIN then opens Settings"

settings_screen = setup.GullionTVSetup(session)
settings_screen.keySave = lambda: results.append("saved")
config.plugins.gulliontv.pin.value = 1111
settings_screen.save()
assert session.opened[-1][1] == "That PIN is too easy to guess" and results[-1] is False
config.plugins.gulliontv.pin.value = 2580
settings_screen.save()
assert results[-1] == "saved"
print("first-use pin ok")

# Weather.
noon = time.mktime(time.localtime(sample_weather.NOW)[:3] + (12, 0, 0, 0, 0, -1)) + 86400
evening = forecast.read_met_eireann(sample_weather.met_eireann(), sample_weather.NOW)
assert evening.line == "11°  Light rain  ·  Tomorrow 14°" and evening.source == "Met Éireann", evening.line
midday = forecast.read_met_eireann(sample_weather.met_eireann(noon), noon)
assert midday.line == "12°  Light rain  ·  High 14°", midday.line
sunny_night = forecast.read_met_eireann(sample_weather.met_eireann(symbol="Sun"), sample_weather.NOW)
assert sunny_night.summary == "Clear", "no sunlight reaching the ground means it's dark"
assert forecast.read_met_eireann(sample_weather.met_eireann(noon, symbol="Sun"), noon).summary == "Sunny"
assert [forecast.symbol_words(name) for name in ("LightRainSun", "Rain", "HeavySnowThunder", "PartlyCloud", "Dark_Sun", "Fog")] == \
	["Light rain showers", "Rain", "Thunder", "Partly cloudy", "Sunny", "Fog"]

backup = forecast.report(54.083, -6.45, sample_weather.fetcher(met_up=False), sample_weather.NOW)
assert backup.source == "Open-Meteo" and backup.line == "8°  Light rain  ·  Tomorrow 14°", backup.line
assert forecast.report(54.083, -6.45, sample_weather.fetcher(), sample_weather.NOW).source == "Met Éireann"
assert forecast.wmo_words(0, daytime=False) == "Clear" and forecast.wmo_words(81) == "Showers"

icon = lambda path: os.path.basename(path) if path else None
assert icon(evening.icon) == "lightrain.png" and icon(backup.icon) == "lightrain.png"
assert icon(sunny_night.icon) == "clearsky_night.png", "a moon after dark"
assert [icon(forecast.symbol_icon(name, day)) for name, day in (("LightRainSun", True), ("LightCloud", False), ("HeavySnowThunderSun", True),
	("LightSnowThunderSun", True), ("Drizzle", True), ("Dark_Sun", True), ("Fog", False))] == ["lightrainshowers_day.png", "fair_night.png",
	"heavysnowshowersandthunder_day.png", "lightssnowshowersandthunder_day.png", "lightrain.png", "clearsky_day.png", "fog.png"]
assert forecast.symbol_icon("Something new") is None and forecast.wmo_icon(42) is None, "unknown weather: words only, no blank icon"
for code in (0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99):
	assert forecast.wmo_icon(code, True) and forecast.wmo_icon(code, False), "Open-Meteo code %d has no icon" % code
assert os.path.isfile(os.path.join(forecast.ICONS, "LICENSE")), "the icons' MIT notice ships with them"
assert forecast.parse_location("54.0830, -6.4500") == (54.083, -6.45) and forecast.parse_location("54.08 -6.45") == (54.08, -6.45)
assert forecast.parse_location("Forkhill") is None and forecast.parse_location("120, 5") is None and forecast.parse_location("") is None
here = (54.083, -6.45)
assert forecast.latest(here) is None and forecast.due(here)
forecast.remember(here, forecast.Report(7, "Cloudy", 10, "today", "Met Éireann", fetched_at=sample_weather.NOW - 2 * 3600))
assert forecast.latest(here).line == "7°  Cloudy  ·  High 10°" and forecast.due(here), "two hours old: shown, but due a refresh"
forecast.remember(here, forecast.Report(7, "Cloudy", 10, "today", "Met Éireann", fetched_at=sample_weather.NOW - 7 * 3600))
assert forecast.latest(here) is None, "too old to show"
assert forecast.latest((53.0, -7.0)) is None, "a different place"

sources.fetch = sample_weather.fetcher()
config.plugins.gulliontv.weather_location.value = ""
screen = home.GullionHome(e2stubs.fake_session(now=(0, 3600, "Nationwide")))
screen.layout()
screen.refresh()
assert screen["weather"].text == "" and not screen.background.jobs, "no location, no weather and nothing fetched"
assert not getattr(screen["weather_icon"], "visible", True)
config.plugins.gulliontv.weather_location.value = "54.0830, -6.4500"
forecast.remember(None, None)
screen.refresh()
screen.background.wait()
assert screen["weather"].text == "11°  Light rain  ·  Tomorrow 14°", screen["weather"].text
assert screen["weather_icon"].visible and screen["weather_icon"].instance.pixmap.endswith("weather/lightrain.png")
assert "Met" not in screen["weather"].text, "the credit is on the settings screen, not Home"

settings_screen = setup.GullionTVSetup(e2stubs.fake_session())
assert all(name in settings_screen["credit"].text for name in ("Met Éireann", "Open-Meteo", "Yr"))
saved = []
settings_screen.keySave = lambda: saved.append(True)
config.plugins.gulliontv.weather_location.value = "Forkhill"
settings_screen.save()
assert settings_screen.session.opened[-1][1] == "That weather location isn't right" and not saved
config.plugins.gulliontv.weather_location.value = "54.0830, -6.4500"
settings_screen.save()
assert saved == [True]
print("weather ok")

# Python 2 on the box needs a coding line in any file with non-ASCII text.
import glob  # noqa: E402
for path in glob.glob(os.path.join(e2stubs.PLUGIN_PARENT, "GullionTV", "**", "*.py"), recursive=True):
	with open(path, "rb") as handle:
		data = handle.read()
	if any(byte > 127 for byte in bytearray(data)):
		assert b"coding: utf-8" in data.split(b"\n", 2)[0] + data.split(b"\n", 2)[1], "%s needs a coding line" % path
print("python 2 encoding ok")

# enigma2 exec()s anything in onLayoutFinish that isn't a bound method, so a lambda there
# crashes the box when the screen opens.
for folder, _, files in os.walk(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "GullionTV")):
	for name in files:
		if name.endswith(".py"):
			assert "onLayoutFinish.append(lambda" not in open(os.path.join(folder, name)).read(), name

# Fitting other skin sizes: every screen designed at 1920x1080 must fit the
# skin's own size once scaled (MetrixHD and the default skin are 1280x720).
screens = [home.GullionHome, guide.Guide, watchagain.WatchAgain, watchagain.AllRecordings, webcams.WebcamList,
	webcams.WebcamPlayer, plexlibrary.PlexLibrary, plexsetup.PlexSetup, plexsetup.OptionList, plexsetup.PlexLink,
	popups.GullionChoice, popups.EventDetails, pin.PinEntry, placeholder.ComingSoon, setup.GullionTVSetup]
assert scale.factor() == 1.0 and scale.skin(home.GullionHome.skin) == home.GullionHome.skin, "full HD is drawn exactly as designed"
for width, height in ((1280, 720), (720, 576), (3840, 2160)):
	scale.set_factor(width / 1920.0)
	for cls in screens + [types.SimpleNamespace(skin=banner.SKIN, __name__="InfoBar")]:
		root = ET.fromstring(scale.skin(cls.skin))
		w, h = [int(v) for v in root.get("size").split(",")]
		assert w <= width and h <= height, "%s is %dx%d on a %dx%d skin" % (cls.__name__, w, h, width, height)
		for element in root:
			if element.get("position") and element.get("size") and "center" not in element.get("position"):
				x, y = [int(v) for v in element.get("position").split(",")]
				ew, eh = [int(v) for v in element.get("size").split(",")]
				assert x + ew <= w + 1 and y + eh <= h + 1, "%s: %s runs off a %dx%d skin" % (cls.__name__, element.attrib, width, height)
scale.set_factor(1280 / 1920.0)
scaled = scale.skin('<screen position="center,center" size="900,460"><widget name="a" position="90,62" size="1740,1" font="Regular;30" itemHeight="75" /></screen>')
assert scaled == '<screen position="center,center" size="600,307"><widget name="a" position="60,41" size="1160,1" font="Regular;20" itemHeight="50" /></screen>', scaled
cell = guide._text(390, 0, 1350, 72, "Nationwide", 0, guide.theme.TEXT, guide.theme.CARD)
assert cell["pos"] == (260, 0) and cell["size"] == (900, 48), "guide cells shrink with the skin"
assert guide.rec_icon_path().endswith("rec_clock_17.png") and os.path.isfile(guide.rec_icon_path())
scale.set_factor(720 / 1920.0)
assert guide.rec_icon_path().endswith("rec_clock_10.png")
scale.set_factor(1.0)
print("skin sizes ok")
