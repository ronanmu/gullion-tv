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


def install():
	setattr(InfoBarGenerics.InfoBarMenu, _METHOD, _gullion_main_menu)
	if _original_info is not None:
		InfoBarGenerics.InfoBarEPG.InfoPressed = _gullion_info
		rebind(_original_info, "InfoPressed")
	if _original_toggle is not None:
		InfoBarGenerics.InfoBarShowHide.toggleShow = _gullion_toggle
		rebind(_original_toggle, "toggleShow")
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


def _home_closed(action=None):
	infobar = _infobar()
	if infobar is None:
		return
	if action == "tv":
		watch_first_channel(infobar.session)
	elif action == "techsupport":
		open_techsupport_menu()


def watch_first_channel(session):
	"""Watch TV goes straight to channel 1, the first channel in the first list."""
	from .tv import epg
	lists = epg.channel_lists()
	if lists:
		bouquet, name, channels = lists[0]
		epg.zap(session, channels[0].ref, bouquet)


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
