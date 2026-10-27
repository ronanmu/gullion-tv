from Components.config import config
from Plugins.Plugin import PluginDescriptor

from . import settings  # noqa: F401  registers config.plugins.gulliontv


def sessionstart(reason, session=None, **kwargs):
	if reason == 0 and session is not None:
		from .hook import install
		install()
		try:
			from . import lock
			lock.install(session)
		except Exception as error:
			print("[GullionTV] stock screens not locked: %s" % error)
		try:
			from .recordings import thumbnails
			thumbnails.watch_recordings(session)
		except Exception as error:
			print("[GullionTV] recording pictures not set up: %s" % error)
		if config.plugins.gulliontv.infobar.value:
			try:
				from .tv import infobar
				infobar.install()
			except Exception as error:
				# Fall back to the skin's own banner rather than stop the box starting.
				print("[GullionTV] channel banner not installed: %s" % error)


def open_setup(session, **kwargs):
	from .setup import GullionTVSetup
	session.open(GullionTVSetup)


def Plugins(**kwargs):
	return [
		PluginDescriptor(
			name="Gullion TV",
			where=PluginDescriptor.WHERE_SESSIONSTART,
			fnc=sessionstart,
		),
		PluginDescriptor(
			name="Gullion TV",
			description="Settings for the simplified home screen",
			where=PluginDescriptor.WHERE_PLUGINMENU,
			fnc=open_setup,
		),
	]
