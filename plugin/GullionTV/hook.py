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
