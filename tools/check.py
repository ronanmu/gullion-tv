"""Offline check: import GullionTV against stub enigma2 modules, parse every
skin as XML, and drive the MENU hook, home navigation and PIN logic.

	python3 tools/check.py
"""
import io
import os
import struct
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
# REC on live TV: records the programme on now straight away; again asks whether to stop.
recorder = e2stubs.InfoBarInstantRecord()
asked = []
here = types.SimpleNamespace(toCompareString=lambda: "1:0:19:1:1:1:EEEE0000:0:0:0:")
recorder.session = types.SimpleNamespace(nav=types.SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: here),
	open=lambda cls, *a: asked.append((cls.__name__,) + a), openWithCallback=lambda cb, cls, *a: asked.append((cls.__name__, cb) + a))
recorder.recording = []
Screens.InfoBar.InfoBar.instance = recorder
e2stubs.InfoBarInstantRecord.keyInstantRecord(recorder)
assert recorder.started is True and not asked and not hasattr(recorder, "opened"), "until the programme ends, no questions"
running = types.SimpleNamespace(service_ref=types.SimpleNamespace(ref=here), isRunning=lambda: True)
recorder.recording = [running]
e2stubs.InfoBarInstantRecord.keyInstantRecord(recorder)
assert asked[-1][0] == "GullionChoice" and asked[-1][2] == "This channel is recording", asked
assert len(hook._timers) == 1, "the banner is shown again once the recording is under way"
shown = []
recorder.doShow = lambda: shown.append(True)
recorder.session.CurrentService = types.SimpleNamespace(CHANGED_ALL=1, changed=lambda what: shown.append(what))
for fnc in hook._timers[0].callback:
	fnc()
assert shown == [(1,), True], "re-read for the REC pill, then shown"
asked[-1][1]("stop")
assert recorder.stopped == 0
# STOP on live TV stops this channel's recording; with nothing recording it goes on to the box.
recorder.stopped = None
assert hook._stop_key(recorder) is None and recorder.stopped == 0
recorder.recording = []
recorder.stopped = None
assert hook._stop_key(recorder) == 0 and recorder.stopped is None
from GullionTV.recordings import store as record_store  # noqa: E402
real_storage = record_store.storage
record_store.storage = lambda folder=None: (record_store.MISSING, 0)
recorder.recording = []
recorder.started = None
e2stubs.InfoBarInstantRecord.keyInstantRecord(recorder)
assert recorder.started is None and asked[-1][1] == "This box can't record right now", "no drive, no recording"
record_store.storage = real_storage
# No "A recording has been started" pop-up, and the box's own setting is left as it was.
import RecordTimer  # noqa: E402  the stub
entry = RecordTimer.RecordTimerEntry()
entry.gotRecordEvent(None, 1)
assert entry.popup is False and config.usage.show_message_when_recording_starts.value is True
config.plugins.gulliontv.enabled.value = False
entry.gotRecordEvent(None, 1)
assert entry.popup is True, "the stock pop-up while Gullion TV is off"
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
assert screen["live_text"].text == "LIVE" and screen["live_tag"].visible, "the preview says LIVE, without the channel name"
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
assert session.opened[-1] == ("Recordings",), "the YELLOW card opens the full recorded TV list"
screen.open_item(0)
assert screen.closed[0] == "tv" and screen.closed[1] is screen.opened_on
assert [card[2] for card in home.CARDS] == ["red", "green", "yellow", "blue"], "cards follow the remote's colour order"
keys = screen["actions"].args[1]
keys["green"]()
assert session.opened[-1] == ("Guide",)
keys["red"]()
assert screen.closed[0] == "tv"
from GullionTV.tv import epg as guide_epg  # noqa: E402
# Live TV goes back to the channel Home was opened on.
played = []
ref = lambda text: types.SimpleNamespace(toString=lambda: text)
nav = types.SimpleNamespace(playService=played.append, getCurrentlyPlayingServiceReference=lambda: ref("bbc"))
hook.back_to(types.SimpleNamespace(nav=nav), ref("bbc"))
assert played == [], "nothing to do when it's still on"
hook.back_to(types.SimpleNamespace(nav=nav), ref("rte"))
assert [p.toString() for p in played] == ["rte"], "back to it after Recordings or a webcam played something else"

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
for title, subtitle, colour, icon in home.CARDS:
	for name in (icon, icon + "_on_light"):
		assert os.path.isfile(ui_icons.card_icon(name)), name
assert [card[0] for card in home.CARDS] == ["Live TV", "TV Guide", "Recordings", "Webcams"]
for el in ET.fromstring(home.GullionHome.skin).iter("ePixmap"):
	assert os.path.isfile(el.get("pixmap")), el.get("pixmap")
screen.paint_selection()
assert screen["card0_icon"].instance.pixmap.endswith("live_tv_on_light_72.png") or screen.selected != 0
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
assert "REC: record" in g["footer"].text and "INFO: details" in g["footer"].text
assert g["footer"].text.endswith("BACK: home") and g["storage_note"].text == ""
assert time.strftime("%H:%M", time.localtime(g.window_start)) == "19:30"
assert len(g["grid"].list) == guide.ROWS

g.next_event()
assert g.selected_event().title == "Fair City" and g["rec_pill"].visible
assert g["rec_pill"].instance.pixmap.endswith("rec_pill_96x40.png")
icons = [entry for entry in g["grid"].list[0][1:] if "png" in entry]
assert len(icons) == 1 and icons[0]["png"] == guide.rec_icon_path() and guide.rec_icon_path().endswith("icons/record_26.png") and os.path.isfile(guide.rec_icon_path()), "Fair City gets the red record mark"
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
g["actions"].args[1]["yellow"]()
assert session.opened[-1][0] == "ChannelLists", "YELLOW must open a selector instead of cycling"
g.list_chosen(1)
assert g["list_name"].text == "Saorview" and g.row == len(g.lists[0][2])
g.list_chosen(0)
guide.Guide.last_list = 0

# Picon in the guide: the logo when there is one, otherwise a name card.
picon._found.clear()
picon_dir = tempfile.mkdtemp()
open(os.path.join(picon_dir, "1_0_19_1_1_1_EEEE0000_0_0_0.png"), "wb").close()
picon._system_lookup = lambda channel: os.path.join(picon_dir, "%s.png" % channel.replace(":", "_").strip("_")) if "EEEE" in channel else None
g = guide.Guide(session)
g.layout()
assert g["picon"].instance.pixmap.endswith("1_0_19_1_1_1_EEEE0000_0_0_0.png") and g["picon"].visible
assert not g["picon_fallback"].visible and g["chan_num"].text == "1", "just the number under the picon"
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
# A programme that has finished: OK and REC do nothing, and no hints offer them.
g = guide.Guide(session)
g.layout()
finished = guide.epg.Event(2, sample_epg.NOW - 1800, 1200, "Earlier", "", "")
g.selected_event = lambda: finished
g.draw_details()
before = len(session.opened)
g.ok()
g.record_key()
assert len(session.opened) == before and not getattr(g, "closed", None), "nothing to watch or record"
assert not any(el.get("name", "").startswith("hint") for el in ET.fromstring(g.skin)), "outlined action hints must be removed"

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
assert details and details[-1][2:] == (coded.description, g.channels[g.row].ref), "details must receive raw codes and the selected channel"
detail_panel = popups.EventDetails(session, *details[-1])
detail_panel.layout()
assert detail_panel["description"].text == "Sandra enlists help."
assert detail_panel.icon_names == ["subtitles", "audio_description", "hd", "terrestrial"], "details must use the same icons as What's on"
assert detail_panel["icon0"].instance.pixmap.endswith("terrestrial_40.png")
alias_panel = popups.EventDetails(session, "Programme", "20:00", "A story. (HD, A, R)", "1:0:19:5:1:1:11A0000:0:0:0:")
alias_panel.layout()
assert alias_panel["description"].text == "A story." and alias_panel.icon_names == ["audio_description", "repeat", "hd", "satellite"], "A must be parsed as audio description"
unknown_panel = popups.EventDetails(session, "Programme", "20:00", "A film (USA)")
unknown_panel.layout()
assert unknown_panel["description"].text == "A film (USA)" and not unknown_panel["icon0"].visible, "ordinary bracketed text must remain"

# A continuous grid crosses bouquets in either direction, retaining box numbers.
original_lists = guide.epg.channel_lists
try:
	first = [guide.epg.Channel("saor%d" % n, "Saorview %d" % n, n) for n in range(1, 21)]
	second = [guide.epg.Channel("free%d" % n, "Freesat %d" % n, n) for n in range(101, 111)]
	guide.epg.channel_lists = lambda: [("saor", "Saorview", first), ("empty", "Empty", []), ("free", "Freesat", second)]
	continuous = guide.Guide(session)
	continuous.layout()
	continuous.show_channel(lambda channel: channel.number == 20)
	continuous.redraw()
	assert len(continuous["grid"].list) == guide.ROWS, "visible rows must continue into the next bouquet"
	continuous.move_row(1)
	assert continuous.channels[continuous.row].number == 101 and continuous["list_name"].text == "Freesat", "20 must lead straight to 101"
	original_zap = guide.epg.zap
	zaps = []
	try:
		guide.epg.zap = lambda session, ref, bouquet: zaps.append((ref, bouquet))
		continuous.selected_event = lambda: coded
		continuous.ok()
		assert zaps == [("free101", "free")], "watching across a boundary must use that channel's bouquet"
		del continuous.selected_event
	finally:
		guide.epg.zap = original_zap
	continuous.move_row(-1)
	assert continuous.channels[continuous.row].number == 20 and continuous["list_name"].text == "Saorview", "101 must lead back to 20"
	continuous.move_row(guide.ROWS)
	assert continuous.channels[continuous.row].number == 106, "page movement must cross bouquet boundaries"
	continuous.move_row(-guide.ROWS)
	assert continuous.channels[continuous.row].number == 20
	continuous.list_chosen(1)
	assert continuous.channels[continuous.row].number == 101 and len(continuous.lists) == 2, "selector must skip empty lists and jump to the first channel"
	row_before = continuous.row
	continuous.list_chosen(None)
	assert continuous.row == row_before, "cancelling the selector must retain the channel"
	continuous.move_row(1000)
	assert continuous.channels[continuous.row].number == 110, "end of all lists must clamp safely"
	continuous.move_row(-1000)
	assert continuous.channels[continuous.row].number == 1
	guide.epg.channel_lists = lambda: []
	empty_guide = guide.Guide(session)
	empty_guide.layout()
	empty_guide.move_row(1)
	empty_guide.choose_list()
	assert empty_guide["list_name"].text == "No channel lists yet"
finally:
	guide.epg.channel_lists = original_lists
	guide.Guide.last_list = 0

selector = guide.ChannelLists(session, [("List %d" % n, n) for n in range(7)], 2)
selector.layout()
assert selector.selected == 2 and len(selector.options) == 3
selector.move(1)
assert selector.options[selector.selected][1] == 3 and selector["option0"].text == "List 3", "selector must page beyond three lists"
selector.move(3)
assert len(selector.options) == 1 and selector.options[selector.selected][1] == 6
selector.move(-1)
assert selector.options[selector.selected][1] == 5, "selector must page backwards"
selector["actions"].args[1]["ok"]()
assert selector.closed == (5,), "selector must return the actual bouquet index"
for panel in (selector, detail_panel):
	for widget in ET.fromstring(panel.skin).iter("widget"):
		assert widget.get("name") in panel, "every selector and details widget must exist"
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
for kind, expected in (("Number", "1"), ("Name", "RTÉ One"), ("NumberAndName", "1   RTÉ One")):
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
# The REC pill: only while this channel is being recorded, not any channel.
timer = lambda ref, state: types.SimpleNamespace(state=state, service_ref=types.SimpleNamespace(ref=e2stubs.eServiceReference(ref)))
assert converter.recording_now(saorview_hd, [timer(saorview_hd, 2)])
assert not converter.recording_now(saorview_hd, [timer("1:0:19:5:1:1:11A0000:0:0:0:", 2)]), "another channel recording"
assert not converter.recording_now(saorview_hd, [timer(saorview_hd, 0)]), "set to record later"
assert not converter.recording_now(saorview_hd), "no box, no recordings"
assert converter.GullionServiceInfo("IsRecording").poll_enabled
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
	assert 0 <= x and x + w <= 1920 and banner.TITLE_Y <= y and y + h <= banner.PANEL_Y + banner.PANEL_H, widget.attrib
	for convert in widget.iter("convert"):
		assert convert.get("type") in known, convert.get("type")
		if convert.get("type") == "GullionServiceInfo":
			assert convert.text in ("Number", "Name", "NumberAndName", "Remaining", "IsRecording") or convert.text.startswith("Icon:"), convert.text
for widget in element.iter("widget"):
	if widget.get("render") == "Pixmap":
		assert os.path.isfile(widget.get("pixmap")), widget.get("pixmap")
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

# A picture for any kind of webcam: a link, or a file on the box, full path or next to webcams.yaml.
folder = tempfile.mkdtemp()
os.makedirs(os.path.join(folder, "images"))
open(os.path.join(folder, "images", "armagh.png"), "wb").close()
assert webcamconfig.image_location("https://example.com/a.jpg", folder) == "https://example.com/a.jpg"
assert webcamconfig.image_location("images/armagh.png", folder) == os.path.join(folder, "images", "armagh.png")
assert webcamconfig.image_location("file:///media/hdd/cam.jpg", folder) == "/media/hdd/cam.jpg"
assert webcamconfig.image_location("/media/hdd/cam.jpg", folder) == "/media/hdd/cam.jpg"
with open(os.path.join(folder, "webcams.yaml"), "w") as handle:
	handle.write("""webcams:
  - name: Armagh Cathedral
    url: https://www.churchservices.tv/armaghcathedral
    image: images/armagh.png
  - name: Missing
    url: https://mcn.live/Camera/somewhere
    image: images/nothing.png
""")
pictured, picture_problems = webcamconfig.load(os.path.join(folder, "webcams.yaml"))
assert pictured[0].image == os.path.join(folder, "images", "armagh.png")
assert pictured[1].image is None and picture_problems == [], "a missing file falls back to the page's own picture"
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
sample_webcams.PICTURES["https://cdn.example/live/Uploads/ProfileImages/stmalachys.jpeg"] = e2stubs.TINY_JPEG
path = sources.download_thumbnail(cams[0], fetch, thumbs)
assert path and open(path, "rb").read() == e2stubs.TINY_JPEG and path.endswith(".jpg")
assert sources.download_thumbnail(cams[4], fetch, thumbs) is None
# A picture from webcams.yaml wins over the one on the church's or camera's page.
for page in ("https://www.churchservices.tv/armaghcathedral", "https://mcn.live/Camera/st-malachys-parish-belfast"):
	own = sources.Webcam(webcamconfig.Entry("Own picture", page, image=pictured[0].image))
	sources.check(own, fetch, now=sample_webcams.NOW)
	assert own.image == pictured[0].image, own.image
	assert sources.download_thumbnail(own, fetch, thumbs) == pictured[0].image, "a local file is used where it is"
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
assert player["source"].text == "Church · mcn.live" and player.live and player["live_text"].text == "LIVE"
assert player["live_dot"].visible and player["live_dot"].instance.pixmap.endswith("key_red_24.png")
player.check_picture()
assert player["message"].text == "Connecting..."
for _ in range(player.GIVE_UP_SECONDS):
	player.check_picture()
assert "isn't sending a picture" in player["message"].text
player.toggle_banner()
assert not player["panel"].visible and not player["live_tag"].visible, "LIVE hides with the banner"
player.toggle_banner()
assert player["panel"].visible and player["live_tag"].visible
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
sources.fetch = lambda url, binary=False, timeout=8: e2stubs.TINY_JPEG
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
assert screen.title == "Media" and watchagain.FILTERS == ("All", "Recorded TV", "Movies on Plex", "TV Shows on Plex")
assert [section["title"] for section in screen.sections] == ["Continue watching", "Recently added"]
assert [tile.title for tile in screen.sections[0]["tiles"]] == ["Fair City", "The Commitments", "Line of Duty"], "All has up to three recordings, one movie and one TV item"
assert [tile.title for tile in screen.sections[1]["tiles"]] == ["Fair City", "MasterChef", "Nationwide", "The Banshees of Inisherin", "Derry Girls"]
assert screen.sections[0]["tiles"][0].subtitle == "RTÉ One  ·  18 min left"
assert screen.sections[0]["tiles"][1].subtitle == "44 min left"
assert screen.sections[0]["tiles"][2].image and os.path.isfile(screen.sections[0]["tiles"][2].image)
assert screen["slot0_title"].text == "Continue watching" and screen["slot1_title"].text == "Recently added"
assert screen["slot0_tile0_band"].instance.background == theme_rgb("CARD_SELECTED")
assert screen["tab0_bg"].instance.background == theme_rgb("CARD_SELECTED")
assert watchagain.VISIBLE == (4, 5) and watchagain.ROW_LIMIT == (8, 10), "Media shelves must show four and five cards and cap at eight and ten"
assert screen.sections[1]["tiles"][3].image == screen.plex_rows[1][0].poster_picture, "recent Plex cards must use portrait poster art"
screen.recordings = screen.recordings * 10
screen["actions"].args[1]["green"]()
assert screen.filter == 1 and [tile.title for tile in screen.sections[0]["tiles"]][:1] == ["Fair City"]
assert [tile.title for tile in screen.sections[1]["tiles"]][:3] == ["Fair City", "MasterChef", "Nationwide"]
assert len(screen.sections[0]["tiles"]) == 8 and len(screen.sections[1]["tiles"]) == 10, "filtered shelves must stop at their separate limits"
assert screen.sections[1]["tiles"][0].image, "recent recordings must use their channel picon"
screen.move_down(1)
for _ in range(9):
	screen.move_across(1)
assert screen.columns["Recently added"] == 9 and screen.offsets["Recently added"] == 5, "five-wide rows must scroll to the tenth panel"
screen.choose_filter(0)
screen.move_down(-1)
assert screen.row == -1, "UP from Continue watching must focus the filters"
screen.move_across(1)
assert screen.filter == 1 and screen.row == -1, "LEFT and RIGHT must change a focused filter"
screen.move_down(1)
assert screen.row == 0, "DOWN from the filters must return to Continue watching"
screen["actions"].args[1]["yellow"]()
assert [tile.title for tile in screen.sections[0]["tiles"]] == ["The Commitments"]
assert [tile.title for tile in screen.sections[1]["tiles"]] == ["The Banshees of Inisherin", "Brooklyn"]
screen["actions"].args[1]["blue"]()
assert [tile.title for tile in screen.sections[0]["tiles"]] == ["Line of Duty"]
assert [tile.title for tile in screen.sections[1]["tiles"]] == ["Derry Girls", "Normal People"]
screen["actions"].args[1]["red"]()
screen.ok()
assert session.opened[-1][0] == "RecordingPlayer" and session.opened[-1][1].ref == fair_city.service_ref
screen["actions"].args[1]["green"]()
screen.open_recordings()
assert session.opened[-1] == ("Recordings", False), "MENU keeps the full Recorded TV list available"
screen.plex_ready(None, plex.PlexError("down"))
assert screen["note"].text == "Plex isn't reachable right now"

plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert [section["title"] for section in plain.sections] == ["Continue watching", "Recently added"]
assert [tile.title for tile in plain.sections[1]["tiles"]][:3] == ["Fair City", "MasterChef", "Nationwide"]
plain.choose_filter(2)
assert plain["slot0_empty"].text == "Plex isn't set up" or plain["slot1_empty"].text == "Plex isn't set up"
print("watch again ok")

# Recordings: the list with the chosen recording's details beside it.
from GullionTV.recordings import screen as recscreen  # noqa: E402
for widget in ET.fromstring(recscreen.Recordings.skin).iter("widget"):
	name = widget.get("name")
	assert name is None or name in recscreen.Recordings(session), "skin widget %s missing from Recordings" % name
session = e2stubs.fake_session()
listing = recscreen.Recordings(session)
del session.nav.played[:]
listing.layout()
assert session.nav.played == [None], "live TV stops while Recordings is open"
assert listing["count"].text == "Looking for recordings..."
listing.background.wait()
assert listing["count"].text == "6 programmes  ·  Newest first"
assert [listing["row%d_title" % i].text for i in range(5)] == ["Fair City", "MasterChef", "Nationwide", "Ros na Rún", "Grand Designs"]
assert listing["row0_edge"].visible and not listing["row1_edge"].visible, "the chosen row is outlined"
assert listing["row0_status"].text == "Part watched" and listing["row1_status"].text == "New" and listing["row2_status"].text == "Watched"
assert listing["row0_progress"].visible and not listing["row1_progress"].visible
assert listing["row0_when"].text == recscreen.short_when(listing.recordings[0]) and listing["row0_when"].text.endswith("·  30 min")
assert listing["title"].text == "Fair City" and listing["channel"].text == "RTÉ One"
assert listing["length"].text == "30 min  ·  1.2 GB", listing["length"].text
assert listing["description"].text == "Paul worries about the cafe, and Katy has news for Dean.", "the access codes are icons, not text"
assert listing["code0"].visible and listing["code0"].instance.pixmap.endswith("subtitles_40.png") and not listing["code1"].visible
assert listing["watched"].text == "12 min watched  ·  18 min left" and listing["progress"].value == 40
assert listing["page"].text == "1 of 6"
assert not listing["row5_title"].visible if "row5_title" in listing else True
listing.move(1)
assert listing["title"].text == "MasterChef" and listing["length"].text == "1 hr  ·  2.8 GB"
assert [listing["code%d" % i].instance.pixmap.rsplit("/", 1)[1] for i in range(2)] == ["audio_description_40.png", "subtitles_40.png"], "packed from the right"
assert not listing["progress"].visible and listing["watched"].text == ""
listing.move(10)
assert listing.selected == 5 and listing.top == 1 and listing["row4_title"].text == "Gardeners' World", "the list scrolls"
assert listing["length"].text == "30 min  ·  640 MB"
assert listing["description"].text == "No description for this recording."
assert listing["picture_icon"].visible or listing["picture_logo"].visible, "no frame yet: the logo or a record mark"
listing.move(-10)
assert listing.selected == 0 and listing.top == 0
assert recordings.file_size(0) == "0 MB" and recordings.file_size(300 * recordings.MB) == "300 MB"
assert recordings.file_size(int(14.4 * recordings.GB)) == "14 GB" and recordings.file_size(int(1.25 * recordings.GB)) in ("1.2 GB", "1.3 GB")
older = recordings.Recording("/older.ts", "Older", "", "", int(time.mktime((2025, 10, 27, 20, 0, 0, 0, 0, -1))), 1800, 0)
assert "2025" in recscreen.short_when(older) and "2025" in recscreen.long_when(older), "older recordings must include their year"
assert str(time.localtime().tm_year) not in recscreen.short_when(listing.recordings[0]), "this year's recordings must stay compact"

# BLUE changes the order and shows the start of each newly sorted list.
listing.move(1)
listing["actions"].args[1]["blue"]()
assert listing["count"].text.endswith("Oldest first") and listing.selected == 0 and listing.top == 0
assert listing.recordings[0].title == "Gardeners' World"
listing.change_order()
assert [r.title for r in listing.recordings] == ["Fair City", "Gardeners' World", "Grand Designs", "MasterChef", "Nationwide", "Ros na Rún"]
listing.change_order()
assert [r.channel for r in listing.recordings][:3] == ["BBC One NI", "BBC Two NI", "Channel 4"]
listing.change_order()
assert listing.order == recordings.NEWEST and listing.chosen().title == "Fair City"

# A recording still being made has REC on its picture and says so.
session.nav.RecordTimer = types.SimpleNamespace(timer_list=[types.SimpleNamespace(state=2, Filename=listing.recordings[1].path[:-3])])
listing.select(1)
listing.paint()
assert listing["row1_status"].text == "Recording now" and listing["rec_pill"].visible
listing.options()
assert "Delete" not in [o[0] for o in session.opened[-1][2]], "active recordings must not offer Delete"
listing.option_chosen("delete")
assert session.opened[-1][1] == "Still recording", "active recordings must also reject direct deletion"
del session.nav.RecordTimer
listing.paint()
assert not listing["rec_pill"].visible

# RED goes directly to the safe delete confirmation.
listing["actions"].args[1]["red"]()
assert session.opened[-1][1].startswith("Delete ") and listing.pending_delete is listing.chosen()
listing.delete_chosen(None)

# OK plays it; MENU offers more.
listing.move(-1)
listing.ok()
assert session.opened[-1][0] == "RecordingPlayer" and session.opened[-1][1].ref == listing.recordings[0].service_ref
listing.options()
assert session.opened[-1][0] == "GullionChoice" and [o[0] for o in session.opened[-1][2]] == ["Watch from the start", "Delete", "Cancel"]
cuts = open(listing.recordings[0].path + ".cuts", "rb").read()
listing.option_chosen("start")
assert session.opened[-1][0] == "RecordingPlayer" and recordings.read(listing.recordings[0].path).position == 0, "from the start forgets the stop"
assert len(open(listing.recordings[0].path + ".cuts", "rb").read()) == 12, "other cue marks are kept"
with open(listing.recordings[0].path + ".cuts", "wb") as handle:
	handle.write(cuts)
listing.background.wait()
listing.move(1)
listing.options()
assert [o[0] for o in session.opened[-1][2]] == ["Delete", "Cancel"], "nothing to start again when it hasn't been watched"
listing.option_chosen("delete")
assert session.opened[-1][0] == "GullionChoice" and session.opened[-1][1] == "Delete MasterChef?"
# The confirmation keeps its original target even if a refresh changes selection.
listing.move(1)
listing.delete_chosen("delete")
listing.background.wait()
assert [r.title for r in listing.recordings][:2] == ["Fair City", "Nationwide"] and listing["count"].text.startswith("5 programmes")
trash = os.path.join(folder, ".Trash")
trash_group = os.path.join(trash, os.listdir(trash)[0])
assert sorted(os.listdir(trash_group)) == ["20261026 2100 - BBC One NI - MasterChef.ts", "20261026 2100 - BBC One NI - MasterChef.ts.meta"], "the confirmed recording and companions stay together"

# Cancelling must leave the files and queue untouched.
listing.option_chosen("delete")
cancelled = listing.pending_delete
listing.delete_chosen(None)
assert listing.pending_delete is None and not listing.deleting and os.path.exists(cancelled.path), "Keep it must leave the recording intact"

# A timer starting during confirmation must prevent deletion.
listing.option_chosen("delete")
pending = listing.pending_delete
session.nav.RecordTimer = types.SimpleNamespace(timer_list=[types.SimpleNamespace(state=2, Filename=pending.path[:-3])])
listing.delete_chosen("delete")
assert session.opened[-1][1] == "Still recording" and os.path.exists(pending.path), "confirmation must recheck active timers"
del session.nav.RecordTimer

# Queue the work without running it: disk work must not run on the UI thread.
real_run = listing.background.run
queued_deletes = []
listing.background.run = lambda work, done: queued_deletes.append((work, done))
listing.option_chosen("delete")
listing.delete_chosen("delete")
assert listing.deleting and len(queued_deletes) == 1 and os.path.exists(pending.path), "deletion must be queued in Background"
opened_before = len(session.opened)
listing.options()
listing.ok()
assert len(session.opened) == opened_before, "playback and repeat deletion must wait for the move"
listing.background.run = real_run
listing.deleted(None, OSError("drive unavailable"))
assert not listing.deleting and session.opened[-1][1] == "Could not delete recording", "disk failures must show a recoverable message"
listing.background.wait()
listing.deleted(None, recordings.TrashError(trash_group, True))
assert "restore" in session.opened[-1][3], "failed rollback must direct Tech Support to restore files"
listing.background.wait()
listing.leave()
assert session.nav.played[-1] is not None, "live TV comes back"
from_watch_again = recscreen.Recordings(session, False)
del session.nav.played[:]
from_watch_again.layout()
from_watch_again.background.wait()
from_watch_again.leave()
assert session.nav.played == [], "Watch again looks after live TV itself"
# Recycle-bin collisions and partial moves, using real temporary files.
with tempfile.TemporaryDirectory() as trash_test:
	path = os.path.join(trash_test, "programme.ts")
	def write_recording_files(payload):
		for suffix in ("", ".meta", ".cuts"):
			with open(path + suffix, "wb") as handle:
				handle.write(payload)
	write_recording_files(b"first recording")
	recording = recordings.read(path)
	first_trash = recordings.move_to_trash(recording)
	write_recording_files(b"second recording")
	second_trash = recordings.move_to_trash(recording)
	assert first_trash != second_trash, "identical names must get separate recycle-bin folders"
	assert open(os.path.join(first_trash, "programme.ts"), "rb").read() == b"first recording", "existing recycled recordings must remain intact"
	assert open(os.path.join(second_trash, "programme.ts"), "rb").read() == b"second recording"
	write_recording_files(b"restore me")
	real_rename = recordings.os.rename
	def fail_programme_move(source, destination):
		if source == path:
			raise OSError("simulated drive error")
		real_rename(source, destination)
	recordings.os.rename = fail_programme_move
	try:
		try:
			recordings.move_to_trash(recording)
			assert False, "a failed move must be reported"
		except recordings.TrashError as error:
			assert not error.recovery_needed, "successful rollback must restore all files"
	finally:
		recordings.os.rename = real_rename
	assert all(open(path + suffix, "rb").read() == b"restore me" for suffix in ("", ".meta", ".cuts")), "rollback must preserve programme and companions"
	assert len(os.listdir(os.path.join(trash_test, ".Trash"))) == 2, "successful rollback must remove its empty folder"
	def fail_move_and_rollback(source, destination):
		if source == path or destination == path + ".meta":
			raise OSError("simulated persistent drive error")
		real_rename(source, destination)
	recordings.os.rename = fail_move_and_rollback
	try:
		try:
			recordings.move_to_trash(recording)
			assert False, "rollback failure must be reported"
		except recordings.TrashError as error:
			assert error.recovery_needed, "incomplete rollback must request recovery"
	finally:
		recordings.os.rename = real_rename
	assert os.path.exists(path) and os.path.exists(path + ".cuts"), "files that can be restored must be restored"
	remaining = [os.path.join(trash_test, ".Trash", name, "programme.ts.meta") for name in os.listdir(os.path.join(trash_test, ".Trash"))]
	assert any(os.path.exists(name) and open(name, "rb").read() == b"restore me" for name in remaining), "failed rollback must keep the remaining companion recoverable"
print("recordings screen ok")

# Recording playback: transport, overlay lifecycle, missing metadata and subtitles.
from GullionTV.recordings import player as recplayer  # noqa: E402
player_session = e2stubs.fake_session()
playing = e2stubs.PlaybackService()
player_session.nav.getCurrentService = lambda: playing
recording = recordings.Recording("/sample.ts", "Fair City", "", "Paul worries about the cafe. (HD, S)", 0, 1800, 720)
player = recplayer.RecordingPlayer(player_session, e2stubs.eServiceReference(recording.service_ref), recording)
for widget in ET.fromstring(player.skin).iter("widget"):
	assert widget.get("name") in player, "recording player skin widgets must exist"
player.layout()
assert player.shown and player.skinName == "GullionRecordingPlayer", "playback must start with the Gullion overlay visible"
assert player["programme"].text == "Fair City" and player["description"].text == "Paul worries about the cafe."
assert player["recorded"].text.startswith("Recorded ") and " 1970 at " in player["recorded"].text
assert player["progress"].value == 40 and player["elapsed"].text == "12:00 / 30:00" and player["remaining"].text == "18:00 left"
assert player["control1_icon"].instance.pixmap.endswith("pause_40.png") and player["control3_icon"].visible, "pause must be central and subtitles offered when present"
assert not player["progress_focus"].visible and "control1" not in player, "playback controls must use icons without text labels"
assert player.controls_timer.active and player.progress_timer.active
assert not player.hideTimer.active and not player.DimmingTimer.active, "stock hiding must not compete with the new overlay"
del playing.seeker.moves[:]
player.triggerResumeLogic()
assert player.cuesheet_downloaded and player.hidden_after_resume, "silent resume must retain the stock cue-sheet lifecycle"
assert playing.seeker.moves == [("absolute", 720 * 90000)] and not player_session.opened, "silent resume must seek without opening the stock question"
player.activate_control()
assert player.paused() and player["control1_icon"].instance.pixmap.endswith("play_40.png") and not player.controls_timer.active, "paused controls must remain visible"
player.activate_control()
assert not player.paused() and player.controls_timer.active
player.skip(30)
assert playing.seeker.moves[-1] == (1, 30 * 90000) and player["elapsed"].text.startswith("12:30"), "forward must seek exactly 30 seconds"
player.skip(-30)
assert playing.seeker.moves[-1] == (-1, 30 * 90000)
playing.seeker.position = 10 * 90000
player.skip(-30)
assert playing.seeker.position == 0, "backward skip must stop at the beginning"
playing.seeker.position = 1790 * 90000
player.skip(30)
assert playing.seeker.position == 1799 * 90000, "forward skip must stay inside the recording"
player.toggle_pause()
player.skip(-30)
assert player.paused(), "skipping while paused must keep playback paused"
player.play()
player.hide_controls()
player.activate_control()
assert player.shown and not player.paused(), "OK with controls hidden must show them without pausing"
playing.seeker.position = 720 * 90000
player["GullionPlaybackActions"].args[1]["up"]()
assert player.progress_selected and player["progress_focus"].visible, "UP must select the progress bar"
player["GullionPlaybackActions"].args[1]["right"]()
assert playing.seeker.moves[-1] == ("absolute", 738 * 90000), "RIGHT must scrub one percent while the bar is selected"
player["GullionPlaybackActions"].args[1]["left"]()
assert playing.seeker.moves[-1] == ("absolute", 720 * 90000)
player["GullionPlaybackActions"].args[1]["down"]()
assert not player.progress_selected and not player["progress_focus"].visible, "DOWN must return focus to the controls"
player["GullionPlaybackActions"].args[1]["down"]()
assert not player.shown, "DOWN from the transport row must hide the overlay"
player.show_controls()
player["GullionPlaybackActions"].args[1]["up"]()
player["GullionPlaybackActions"].args[1]["up"]()
assert not player.shown, "UP from the selected progress bar must hide the overlay"
player.show_controls()
player.move_control(-1)
assert player.control == 0
player.activate_control()
assert playing.seeker.moves[-1] == (-1, 30 * 90000), "the left on-screen button must skip backward"
player.move_control(2)
player.activate_control()
assert playing.seeker.moves[-1][0] == 1, "the right on-screen button must skip forward"
player.move_control(1)
player.activate_control()
assert player_session.opened[-1][0] == "SoundAndSubtitles" and player_session.opened[-1][-1] == {"focus": "subtitles"}
assert player.subtitle_dialog_open and not player.shown and not player.controls_timer.active
subtitle_panel = soundsubs.SoundAndSubtitles(player_session, player, focus="subtitles")
subtitle_panel.layout()
subtitle_panel.move(1)
subtitle_panel.choose()
assert player.selected_subtitle == playing.tracks[0], "subtitle selection must reach the recording player's subtitle API"
subtitle_panel.move(-1)
subtitle_panel.choose()
assert player.selected_subtitle is None, "subtitles must be switchable off"
player.subtitles_closed()
assert player.shown and player.controls_timer.active
playing.tracks = []
player.refresh_playback()
assert not player["control3_icon"].visible and player.control == 1, "missing subtitle streams must hide the button and reset its focus"
opened_before = len(player_session.opened)
player.open_subtitles()
assert len(player_session.opened) == opened_before
playing.seeker.error = 1
player.refresh_playback()
assert player["progress"].value == 0 and player["elapsed"].text == "--:-- / 30:00", "invalid seek data must not invent progress"
playing.seeker.error = 0
playing.seeker.seekable = False
moves_before = len(playing.seeker.moves)
player.skip(30)
assert len(playing.seeker.moves) == moves_before and "isn't available" in player["notice"].text
playing.seeker.seekable = True
playing.seeker.length = 0
player.skip(30)
assert len(playing.seeker.moves) == moves_before, "skip must wait for a reliable length"
recording.duration = 0
player.refresh_playback()
assert player["elapsed"].text.endswith("/ --:--"), "unknown duration must have a clear fallback"
player_session.nav.getCurrentService = lambda: None
player.refresh_playback()
assert not player["control3_icon"].visible and player["elapsed"].text == "--:-- / --:--", "service transitions must be safe"
player.pauseService = None
player.toggle_pause()
assert "isn't available" in player["notice"].text, "missing image-specific controls must fail safely"
player.back()
assert not player.shown and player.closed is None, "BACK first hides the overlay"
player.back()
assert player.left == "quit" and player.saved_resume, "BACK while hidden must use the stock resume-saving exit"
assert not player.progress_timer.active and not player.controls_timer.active and not player.onPlayStateChanged, "close must clean up timers and callbacks"
assert recplayer.clock(3661) == "1:01:01"
playback_map = ET.parse(os.path.join(e2stubs.PLUGIN_PARENT, "GullionTV", "keymap.xml")).find("map[@context='GullionPlaybackActions']")
assert playback_map is not None
assert all(key.get("mapto") in player["GullionPlaybackActions"].args[1] for key in playback_map), "every playback key must have a handler"
assert player["GullionPlaybackActions"].args[2] < -1, "playback controls must take priority over stock key maps"
for size in ui_icons.SIZES:
	for name in ("pause", "play", "replay_30", "forward_30"):
		for suffix in ("", "_on_light"):
			assert os.path.isfile(os.path.join(ui_icons.FOLDER, "%s%s_%d.png" % (name, suffix, size))), "transport icons must cover each skin scale"
print("recording player ok")

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
assert "REC: record" not in g["footer"].text, "no REC hint when the box cannot record"
assert g["footer"].text.endswith("BACK: home") and g["storage_note"].text == "Recording isn't available"
g.record_key()
assert session.opened[-1][:2] == ("GullionChoice", "This box can't record right now")
g.choice_made("record")
assert session.opened[-1][:2] == ("GullionChoice", "This box can't record right now")
g.next_event()
assert g.selected_event().title == "Fair City" and "INFO: details" in g["footer"].text
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
assert "REC: record" in g["footer"].text and g["storage_note"].text == "Recording space is low"

recordings.mount_point = lambda path: "/"
recordings.DEFAULT_FOLDER = tempfile.mkdtemp()
plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert plain["slot1_empty"].text == "Recording isn't set up on this box. Ask Tech Support to check the recording drive."
recordings.mount_point = lambda path: "/media/hdd"
plain = watchagain.WatchAgain(session, {})
plain.layout()
plain.background.wait()
assert plain["slot1_empty"].text.startswith("No recordings yet. Press REC")
print("recording drive ok")

# Plex pictures: landscape for Continue watching and posters for Recently added.
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
screen.choose_filter(2)
recent = dict((tile.title, tile) for tile in screen.sections[1]["tiles"])
assert recent["Brooklyn"].image == recent["Brooklyn"].poster, "a recent item must fill its portrait card with its poster"
assert all(tile.badge == "Movie" for tile in screen.sections[1]["tiles"])
screen.choose_filter(0)
continuing = screen.sections[0]["tiles"]
assert [tile.badge for tile in continuing] == ["Recorded TV", "Movie", "TV Show"], "each media type must be clear"
screen.paint()
assert screen["slot0_tile1_badge"].text == "Movie" and screen["slot0_tile1_badge"].visible and screen["slot0_tile0_badge"].text == "Recorded TV"
screen.choose_filter(2)
brooklyn = [i for i, tile in enumerate(screen.sections[1]["tiles"]) if tile.title == "Brooklyn"][0]
assert screen["slot1_tile%d_image" % brooklyn].visible and not screen["slot1_tile%d_poster" % brooklyn].visible
print("plex pictures ok")

# Recording pictures.
sample = recordings.list_recordings(folder)[0]
assert sample.image is None
calls = []


def fake_ffmpeg(arguments, sizes=[200, 19000]):
	calls.append(arguments)
	with open(arguments[-1], "wb") as handle:
		handle.write(b"x" * sizes[min(len(calls) - 1, len(sizes) - 1)])
	return 0


# The stand-in ffmpeg writes filler, so it's saved under a name that isn't a picture.
original_path_for = thumbnails.path_for
thumbnails.path_for = lambda path: path + ".frame-test"
made = thumbnails.make(sample, "/usr/bin/ffmpeg", fake_ffmpeg)
assert made == sample.path + ".frame-test" and os.path.getsize(made) == 19000, "a nearly blank first try is taken again further in"
assert calls[0][calls[0].index("-ss") + 1] == str(int(sample.duration * 0.10)) and calls[1][calls[1].index("-ss") + 1] == str(int(sample.duration * 0.25))
assert "scale=768:432" in calls[0] and not os.path.exists(made + ".part")
assert thumbnails.make(sample, None, fake_ffmpeg) is None or thumbnails.find_ffmpeg(), "no ffmpeg, no picture"
assert thumbnails.make_missing(recordings.list_recordings(folder), 12, "/usr/bin/ffmpeg", lambda arguments: 1) == 0
os.remove(made)
thumbnails.path_for = original_path_for

# Small pictures from earlier versions are made again at the size the large picture needs.
# Read from memory: header-only .jpg files on disk upset virus scanners.
def jpeg_header(width, height, frame=b"\xc0"):
	"""The start of a JPEG: a JFIF segment, a table, then the frame size."""
	jfif = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
	table = b"\xff\xc4" + struct.pack(">H", 5) + b"\x00\x00\x00"
	return b"\xff\xd8" + jfif + table + b"\xff" + frame + struct.pack(">HBHHB", 11, 8, height, width, 3) + b"\x00" * 6


assert thumbnails.read_jpeg_size(io.BytesIO(jpeg_header(328, 184))) == (328, 184)
assert thumbnails.read_jpeg_size(io.BytesIO(jpeg_header(768, 432, b"\xc2"))) == (768, 432), "progressive too"
assert thumbnails.read_jpeg_size(io.BytesIO(b"not a picture")) is None
fake = types.SimpleNamespace(image="frame")
original_size = thumbnails.jpeg_size
for size, needed in (((328, 184), True), ((768, 432), False), (None, False)):
	thumbnails.jpeg_size = lambda path, size=size: size
	assert thumbnails.needs_frame(fake) == needed, size
thumbnails.jpeg_size = original_size
assert thumbnails.needs_frame(types.SimpleNamespace(image=None))

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
screens = [recplayer.RecordingPlayer, home.GullionHome, guide.Guide, guide.ChannelLists, watchagain.WatchAgain, watchagain.Recordings, webcams.WebcamList,
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
assert guide.rec_icon_path().endswith("record_17.png") and os.path.isfile(guide.rec_icon_path())
scale.set_factor(720 / 1920.0)
assert guide.rec_icon_path().endswith("record_10.png")
scale.set_factor(1.0)
print("skin sizes ok")

# The documentation: every link and picture points at something that exists, every
# rendered screenshot is shown on a page, and every page is in the index.
import re  # noqa: E402

REPO = os.path.abspath(os.path.join(e2stubs.PLUGIN_PARENT, ".."))
DOCS = os.path.join(REPO, "docs")
LINK = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)\)")


def heading_anchors(path):
	"""The #anchors GitHub makes for a page's headings."""
	anchors = set()
	in_code = False
	for line in open(path, encoding="utf-8"):
		if line.startswith("```"):
			in_code = not in_code
		elif not in_code and line.startswith("#"):
			title = line.lstrip("#").strip().lower()
			anchors.add(re.sub(r"[^\w\- ]", "", title).replace(" ", "-"))
	return anchors


pages = [os.path.join(REPO, "README.md")] + sorted(glob.glob(os.path.join(DOCS, "**", "*.md"), recursive=True))
shown, linked = set(), {}
for page in pages:
	text = re.sub(r"```.*?```", "", open(page, encoding="utf-8").read(), flags=re.S)
	for picture, target in LINK.findall(text):
		if re.match(r"[a-z]+:", target):
			continue
		path, _, anchor = target.partition("#")
		resolved = os.path.normpath(os.path.join(os.path.dirname(page), path)) if path else page
		where = "%s links to %s" % (os.path.relpath(page, REPO), target)
		assert os.path.exists(resolved), where + ", which doesn't exist"
		if anchor and resolved.endswith(".md"):
			assert anchor in heading_anchors(resolved), where + ", which has no such heading"
		if picture:
			shown.add(resolved)
		else:
			linked.setdefault(page, set()).add(resolved)
renders = set(glob.glob(os.path.join(DOCS, "images", "*.png")))
assert renders, "no rendered screenshots in docs/images"
unused = sorted(os.path.basename(path) for path in renders - shown)
assert not unused, "screenshots not shown on any page: %s" % ", ".join(unused)
index = os.path.join(DOCS, "README.md")
missing = sorted(os.path.relpath(page, DOCS) for page in pages[1:] if page != index and page not in linked.get(index, set()))
assert not missing, "pages not linked from docs/README.md: %s" % ", ".join(missing)
print("docs ok")
