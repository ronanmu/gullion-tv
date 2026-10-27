"""Route the remote's MENU key to the Gullion TV screen.

The stock main menu stays reachable through the Tech Support PIN gate, which calls
the original InfoBarMenu.mainMenu saved here.
"""
from Components.config import config
from Screens import InfoBarGenerics

from . import settings  # noqa: F401  registers config.plugins.gulliontv

_original_main_menu = InfoBarGenerics.InfoBarMenu.mainMenu


def _gullion_main_menu(self):
	if config.plugins.gulliontv.enabled.value:
		open_home(self.session)
	else:
		_original_main_menu(self)


def install():
	InfoBarGenerics.InfoBarMenu.mainMenu = _gullion_main_menu
	# If InfoBar already exists, its ActionMap holds a bound copy of the old
	# method, so point the action at the patched one.
	infobar = _infobar()
	if infobar is not None and "MenuActions" in infobar:
		infobar["MenuActions"].actions["mainMenu"] = infobar.mainMenu


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
