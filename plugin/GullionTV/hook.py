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


def _gullion_main_menu(self):
	if config.plugins.gulliontv.enabled.value:
		open_home(self.session)
	else:
		_original_main_menu(self)


def install():
	setattr(InfoBarGenerics.InfoBarMenu, _METHOD, _gullion_main_menu)
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
		_original_main_menu(infobar)


def _home_closed(action=None):
	infobar = _infobar()
	if infobar is None:
		return
	if action == "tv":
		for name in ("showTv", "showTvChannelList", "openServiceList"):
			fnc = getattr(infobar, name, None)
			if fnc is not None:
				fnc()
				break
	elif action == "techsupport":
		open_techsupport_menu()


def _infobar():
	from Screens.InfoBar import InfoBar
	return InfoBar.instance
