"""Route the remote's MENU key to the Gullion TV screen.

The stock main menu stays reachable through the Tech Support PIN gate, which calls
the original InfoBarMenu method saved here.
"""
from Components.config import config
from Screens import InfoBarGenerics

from . import settings  # noqa: F401  registers config.plugins.gulliontv

# OpenATV 6.4 calls the method mainMenu and its action mainMenu; 7.x calls them
# showMainMenu and showMenu.
if hasattr(InfoBarGenerics.InfoBarMenu, "mainMenu"):
	_METHOD, _ACTION = "mainMenu", "mainMenu"
else:
	_METHOD, _ACTION = "showMainMenu", "showMenu"
_original_main_menu = getattr(InfoBarGenerics.InfoBarMenu, _METHOD)
_original_info = getattr(getattr(InfoBarGenerics, "InfoBarEPG", None), "InfoPressed", None)
_original_toggle = getattr(getattr(InfoBarGenerics, "InfoBarShowHide", None), "toggleShow", None)
_original_audio = getattr(getattr(InfoBarGenerics, "InfoBarAudioSelection", None), "audioSelection", None)
_original_subtitles = getattr(getattr(InfoBarGenerics, "InfoBarSubtitleSupport", None), "subtitleSelection", None)
# REC on live TV. OpenATV 7.x asks its questions in keyInstantRecord (instantRecord hands over to
# it); 6.4 asks them in instantRecord itself.
_RECORD_METHOD = "keyInstantRecord" if hasattr(getattr(InfoBarGenerics, "InfoBarInstantRecord", None), "keyInstantRecord") else "instantRecord"
_original_record = getattr(getattr(InfoBarGenerics, "InfoBarInstantRecord", None), _RECORD_METHOD, None)


def _gullion_main_menu(self):
	if config.plugins.gulliontv.enabled.value:
		open_home(self.session)
	else:
		_original_main_menu(self)


def _gullion_info(self):
	"""INFO on live TV: Gullion TV's what's-on panel instead of the stock one."""
	if config.plugins.gulliontv.enabled.value:
		from .tv.nowinfo import ChannelInfo
		self.session.open(ChannelInfo)
	else:
		_original_info(self)


def _gullion_toggle(self):
	"""OK shows the banner; OK again, while it's up, opens the same panel as INFO."""
	shown = getattr(self, "_InfoBarShowHide__state", None) == getattr(self, "STATE_SHOWN", object())
	if config.plugins.gulliontv.enabled.value and shown and self is _infobar():
		self.hide()
		from .tv.nowinfo import ChannelInfo
		self.session.open(ChannelInfo)
	else:
		_original_toggle(self)


def _sound_and_subtitles(focus, original):
	def opener(self):
		"""YELLOW or AUDIO, and SUBTITLE: one Gullion TV pop-up for both, not the stock lists."""
		if config.plugins.gulliontv.enabled.value:
			from .tv.soundsubs import SoundAndSubtitles
			self.session.open(SoundAndSubtitles, self, focus)
		else:
			original(self)
	return opener


# The keys that open the stock guide or channel list on live TV: GUIDE (EPGPressed), the
# arrows (switchChannelUp/Down), TV and FAV (showTv, openBouquetList) and anything else that
# opens the channel list. Each opens Gullion TV's guide instead.
_GUIDE_KEYS = (
	("InfoBarEPG", "EPGPressed"), ("InfoBarChannelSelection", "switchChannelUp"),
	("InfoBarChannelSelection", "switchChannelDown"), ("InfoBarChannelSelection", "openServiceList"),
	("InfoBarChannelSelection", "showTvChannelList"), ("InfoBar", "showTv"), ("InfoBar", "openBouquetList"),
)


def open_guide(session):
	from .tv.guide import Guide
	session.open(Guide)


def _guide_instead(original):
	def opener(self, *args, **kwargs):
		if config.plugins.gulliontv.enabled.value and self is _infobar():
			# The stock TV key also switches the channel list back from radio to TV, which
			# number entry uses; keep doing that.
			tv_mode(self)
			open_guide(self.session)
		else:
			return original(self, *args, **kwargs)
	opener.gullion_original = original
	return opener


def tv_mode(infobar):
	servicelist = getattr(infobar, "servicelist", None)
	if servicelist is not None and hasattr(servicelist, "setModeTv"):
		servicelist.setModeTv()


def _install_guide_keys():
	from Screens import InfoBar as InfoBarModule
	for owner_name, method in _GUIDE_KEYS:
		owner = getattr(InfoBarModule, owner_name, None) if owner_name == "InfoBar" else getattr(InfoBarGenerics, owner_name, None)
		original = owner is not None and owner.__dict__.get(method)
		if not original or hasattr(original, "gullion_original"):
			continue
		setattr(owner, method, _guide_instead(original))
		rebind(original, method)


def _gullion_record(self, *args, **kwargs):
	"""REC records the programme on now until it ends, with no questions. Pressed again on a
	channel that's recording, it asks whether to stop."""
	if not config.plugins.gulliontv.enabled.value or self is not _infobar():
		return _original_record(self, *args, **kwargs)
	from .recordings import store as recordings
	from .ui.popups import GullionChoice
	state, free = recordings.storage()
	if not recordings.can_record(state):
		if state == recordings.FULL:
			heading, detail = "The recording drive is full", "Delete some old recordings to make room."
		else:
			heading, detail = "This box can't record right now", "Ask Tech Support to check the recording drive."
		self.session.open(GullionChoice, heading, [("OK", None)], detail)
		return
	index = _recording_here(self)
	if index is not None:
		def chosen(choice=None):
			if choice == "stop":
				_stop_recording(self, index)
		self.session.openWithCallback(chosen, GullionChoice, "This channel is recording",
			[("Stop recording", "stop"), ("Keep recording", None)])
		return
	if hasattr(self, "selectedInstantServiceRef"):
		self.selectedInstantServiceRef = args[0] if args else None
	self.startInstantRecording(limitEvent=True)
	# The banner comes up with its REC pill once the recording is under way.
	_show_banner_soon(self, 1500)


def _stop_key(infobar):
	"""STOP on live TV: stop this channel's recording straight away. With nothing recording
	here, the key goes on to the box's own STOP (timeshift)."""
	if not config.plugins.gulliontv.enabled.value:
		return 0
	index = _recording_here(infobar)
	if index is None:
		return 0
	_stop_recording(infobar, index)


def _stop_recording(infobar, index):
	infobar.stopCurrentRecording(index)
	_show_banner_soon(infobar, 300)


def _show_banner_soon(infobar, milliseconds):
	"""Show the banner, after re-reading the channel's details so the REC pill is up to date."""
	from enigma import eTimer
	timer = eTimer()

	def show():
		source = getattr(infobar.session, "CurrentService", None)
		if source is not None and hasattr(source, "changed"):
			source.changed((source.CHANGED_ALL,))
		(getattr(infobar, "doShow", None) or infobar.show)()
	timer.callback.append(show)
	timer.start(milliseconds, True)
	_timers[:] = [timer]  # kept so it isn't garbage collected before it fires


_timers = []


def _install_stop_key():
	"""Load keymap.xml and give each live TV InfoBar a GullionLiveActions map for STOP."""
	import os
	from Components.ActionMap import ActionMap
	from Screens import InfoBar as InfoBarModule
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keymap.xml")
	try:
		from Components.ActionMap import loadKeymap
		loadKeymap(path)
	except ImportError:
		from keymapparser import readKeymap
		readKeymap(path)
	original = InfoBarModule.InfoBar.__dict__.get("__init__")
	if original is None or hasattr(original, "gullion_original"):
		return

	def init(self, *args, **kwargs):
		original(self, *args, **kwargs)
		# Before the box's own maps (-1), and passed on when there's nothing to stop.
		self["GullionLiveActions"] = ActionMap(["GullionLiveActions"], {"stop": lambda: _stop_key(self)}, -2)
	init.gullion_original = original
	InfoBarModule.InfoBar.__init__ = init


def _recording_here(infobar):
	"""Which of the InfoBar's instant recordings is of the channel on now, if any."""
	playing = infobar.session.nav.getCurrentlyPlayingServiceReference()
	if playing is None:
		return None
	wanted = playing.toCompareString()
	for index, timer in enumerate(getattr(infobar, "recording", [])):
		if timer.service_ref.ref.toCompareString() == wanted and timer.isRunning():
			return index
	return None


def _quiet_record_start():
	"""No "A recording has been started" pop-up: the banner's REC pill says so instead. The
	box's own setting is turned off only for that moment, never changed or saved."""
	try:
		import RecordTimer
		from enigma import iRecordableService
	except Exception:
		return
	original = RecordTimer.RecordTimerEntry.__dict__.get("gotRecordEvent")
	if original is None or hasattr(original, "gullion_original"):
		return

	def got_record_event(self, record, event, *args, **kwargs):
		setting = getattr(config.usage, "show_message_when_recording_starts", None)
		if not config.plugins.gulliontv.enabled.value or setting is None or event != iRecordableService.evStart:
			return original(self, record, event, *args, **kwargs)
		shown = setting.value
		setting.value = False
		try:
			return original(self, record, event, *args, **kwargs)
		finally:
			setting.value = shown
	got_record_event.gullion_original = original
	RecordTimer.RecordTimerEntry.gotRecordEvent = got_record_event


def install():
	setattr(InfoBarGenerics.InfoBarMenu, _METHOD, _gullion_main_menu)
	if _original_info is not None:
		InfoBarGenerics.InfoBarEPG.InfoPressed = _gullion_info
		rebind(_original_info, "InfoPressed")
	if _original_toggle is not None:
		InfoBarGenerics.InfoBarShowHide.toggleShow = _gullion_toggle
		rebind(_original_toggle, "toggleShow")
	if _original_audio is not None:
		InfoBarGenerics.InfoBarAudioSelection.audioSelection = _sound_and_subtitles("audio", _original_audio)
		rebind(_original_audio, "audioSelection")
	_install_guide_keys()
	_quiet_record_start()
	try:
		_install_stop_key()
	except Exception as error:
		print("[GullionTV] STOP key not set up: %s" % error)
	if _original_record is not None:
		setattr(InfoBarGenerics.InfoBarInstantRecord, _RECORD_METHOD, _gullion_record)
		rebind(_original_record, _RECORD_METHOD)
	if _original_subtitles is not None:
		InfoBarGenerics.InfoBarSubtitleSupport.subtitleSelection = _sound_and_subtitles("subtitles", _original_subtitles)
		rebind(_original_subtitles, "subtitleSelection")
	# If InfoBar already exists, its ActionMap holds a bound copy of the old
	# method, so point the action at the patched one.
	infobar = _infobar()
	if infobar is not None and "MenuActions" in infobar:
		infobar["MenuActions"].actions[_ACTION] = getattr(infobar, _METHOD)


def open_home(session):
	from .home import GullionHome
	session.openWithCallback(_home_closed, GullionHome)


def open_techsupport_menu():
	infobar = _infobar()
	if infobar is not None:
		from . import lock
		lock.grant()  # Home has just had the PIN
		_original_main_menu(infobar)


def _home_closed(action=None, service=None):
	infobar = _infobar()
	if infobar is None:
		return
	if action == "tv":
		back_to(infobar.session, service)
	elif action == "techsupport":
		open_techsupport_menu()


def back_to(session, service):
	"""Live TV: the channel that was on when Home opened, if something else is playing now."""
	if service is None:
		return
	playing = session.nav.getCurrentlyPlayingServiceReference()
	if playing is None or playing.toString() != service.toString():
		session.nav.playService(service)


def rebind(original, name):
	"""An InfoBar that already exists holds bound copies of the old method in its action maps."""
	infobar = _infobar()
	if infobar is None:
		return
	for key in list(infobar.keys()):
		actions = getattr(infobar[key], "actions", None)
		if not isinstance(actions, dict):
			continue
		for action, fnc in list(actions.items()):
			if getattr(fnc, "__func__", None) is original:
				actions[action] = getattr(infobar, name)


def _infobar():
	from Screens.InfoBar import InfoBar
	return InfoBar.instance
