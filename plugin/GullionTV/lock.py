"""Keep the stock settings and plugin screens behind the Tech Support PIN.

MENU is routed to Gullion TV by hook.py, but other keys open stock screens too:
GREEN opens the plugin browser, BLUE the extensions list, MENU in the channel
list its edit menu, and any key can be given a stock screen in Button setup. So
instead of chasing keys, session.open asks for the PIN before any screen in
LOCKED opens. Once it's given, everything opened from that screen is allowed
until it closes.
"""
import time

from Components.config import config
from Screens import InfoBarGenerics

from . import settings  # noqa: F401  registers config.plugins.gulliontv

# Class names, matched against each class a screen is built from, so a skin or
# image's subclass of Menu or Setup is caught too.
LOCKED = frozenset((
	"Menu", "MainMenu", "Setup", "PluginBrowser", "PluginDownloadBrowser", "PluginFilter",
	"ChannelContextMenu", "ButtonSetup", "ButtonSetupSelect", "QuickMenu",
))

_open_unlocked = [0]  # how many screens opened with the PIN are still open
_granted = []  # when Home last had the PIN: the next locked screen opens without asking
GRANT_SECONDS = 5
_original_extensions = getattr(InfoBarGenerics.InfoBarExtensions, "showExtensionSelection", None)


def is_locked(screen):
	return any(cls.__name__ in LOCKED for cls in getattr(screen, "__mro__", ()))


def needs_pin(screen):
	return bool(config.plugins.gulliontv.enabled.value) and not _open_unlocked[0] and is_locked(screen)


def grant():
	"""Let the next locked screen open without asking, as the PIN has just been given."""
	_granted[:] = [time.time()]


def _take_grant():
	granted = _granted and time.time() - _granted[0] < GRANT_SECONDS
	del _granted[:]
	return granted


def install(session):
	open_screen = session.open
	open_with_callback = session.openWithCallback

	def track(open_it):
		"""Open a locked screen, and allow what it opens until it closes."""
		_open_unlocked[0] += 1  # also lets openWithCallback's own call to session.open through
		try:
			dialog = open_it()
		except Exception:
			_open_unlocked[0] -= 1
			raise
		closed = []

		def on_close():
			if not closed:
				closed.append(True)
				_open_unlocked[0] = max(0, _open_unlocked[0] - 1)
		onClose = getattr(dialog, "onClose", None)
		if onClose is not None:
			onClose.append(on_close)
		else:
			on_close()
		return dialog

	def guarded(open_it, screen):
		if not needs_pin(screen):
			return open_it()
		if _take_grant():
			return track(open_it)
		ask_pin(session, lambda: track(open_it))

	def guarded_open(screen, *args, **kwargs):
		return guarded(lambda: open_screen(screen, *args, **kwargs), screen)

	def guarded_open_with_callback(callback, screen, *args, **kwargs):
		return guarded(lambda: open_with_callback(callback, screen, *args, **kwargs), screen)

	session.open = guarded_open
	session.openWithCallback = guarded_open_with_callback

	# BLUE's extensions list is a plain choice list, so the InfoBar method is locked instead.
	if _original_extensions is not None:
		InfoBarGenerics.InfoBarExtensions.showExtensionSelection = _locked_extensions
		from .hook import rebind
		rebind(_original_extensions, "showExtensionSelection")


def ask_pin(session, then):
	"""The Tech Support PIN, or choosing one if it's never been set; then() once it's right."""
	from .ui.pin import PinChooser, TechSupportPin

	def entered(ok=False):
		if ok:
			then()
	if config.plugins.gulliontv.pin_set.value:
		# Opened directly: the PIN screen isn't locked, and this must not recurse.
		session.openWithCallback(entered, TechSupportPin)
	else:
		PinChooser(session, entered).start()


def _locked_extensions(self):
	if not config.plugins.gulliontv.enabled.value or _open_unlocked[0]:
		return _original_extensions(self)

	def unlocked():
		_open_unlocked[0] += 1
		try:
			_original_extensions(self)
		finally:
			_open_unlocked[0] -= 1
	ask_pin(self.session, unlocked)
