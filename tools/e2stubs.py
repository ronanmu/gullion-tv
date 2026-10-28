"""Minimal stand-ins for the enigma2 modules GullionTV imports.

Lets the plugin be imported and driven on a dev machine (Python 3) by
tools/check.py and tools/preview.py. Install before importing the plugin.
"""
import os
import sys
import types

PLUGIN_PARENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin")


class Obj(object):
	def __init__(self, *args, **kwargs):
		self.args = args
		self.kwargs = kwargs
		self.value = kwargs.get("default")
		self.saved = self.value

	def save(self):
		self.saved = self.value

	def isChanged(self):
		return self.value != self.saved


class Timer(object):
	def __init__(self):
		self.callback = []

	def start(self, *args):
		pass

	def stop(self):
		pass


class Instance(object):
	"""Records the colours a screen sets on a widget at runtime."""

	def __init__(self):
		self.background = None
		self.foreground = None

	def setBackgroundColor(self, colour):
		self.background = colour

	def setForegroundColor(self, colour):
		self.foreground = colour

	def invalidate(self):
		pass

	def move(self, point):
		self.position = point

	def setSelectionEnable(self, enabled):
		pass

	def setPixmap(self, pixmap):
		self.pixmap = pixmap


class Widget(object):
	def __init__(self, text=""):
		self.text = text
		self.value = 0
		self.instance = None

	def setText(self, text):
		self.text = text

	def setValue(self, value):
		self.value = value

	def show(self):
		self.visible = True

	def hide(self):
		self.visible = False


class Pixmap(Widget):
	pass


class PicLoad(object):
	"""ePicLoad: 'decodes' a picture to its own path, which tools/preview.py draws."""

	def setPara(self, parameters):
		self.parameters = parameters

	def startDecode(self, path, *args):
		import os
		self.path = path
		return 0 if os.path.isfile(path) else 1

	def getData(self):
		return self.path


class ListContent(object):
	def __init__(self):
		self.fonts = {}
		self.item_height = 30

	def setItemHeight(self, height):
		self.item_height = height

	def setFont(self, index, font):
		self.fonts[index] = font

	def setSelectionClip(self, *args):
		pass


class MenuList(Widget):
	def __init__(self, items, enableWrapAround=True, content=None):
		Widget.__init__(self)
		self.l = ListContent()
		self.list = items

	def setList(self, items):
		self.list = items


class eServiceReference(object):
	isDirectory = 1
	isMarker = 64

	def __init__(self, ref=""):
		self.ref = ref

	def toString(self):
		return self.ref

	def toCompareString(self):
		return self.ref


class Screen(dict):
	def __init__(self, session):
		self.session = session
		self.onLayoutFinish = []
		self.onShow = []
		self.onHide = []
		self.onClose = []
		self.closed = None

	def setTitle(self, title):
		self.title = title

	def close(self, *retval):
		self.closed = retval

	def layout(self):
		"""What enigma2 does once the skin is applied: widgets get instances."""
		for widget in self.values():
			if isinstance(widget, Widget):
				widget.instance = Instance()
		for fnc in self.onLayoutFinish:
			fnc()


class Config(object):
	pass


class RecordTimerEntry(object):
	"""Notes whether the "recording has been started" pop-up would show."""

	def gotRecordEvent(self, record, event):
		self.popup = config.usage.show_message_when_recording_starts.value


class Converter(object):
	CHANGED_DEFAULT, CHANGED_ALL, CHANGED_CLEAR, CHANGED_SPECIFIC, CHANGED_POLL = range(5)

	def __init__(self, type):
		self.converter_arguments = type
		self.source = None
		self.notified = []

	def changed(self, what):
		self.notified.append(what)


class Poll(object):
	def __init__(self):
		self.poll_interval = 1000
		self.poll_enabled = False


class InfoBarMenu(object):
	def mainMenu(self):
		self.opened = "stock"


class InfoBarExtensions(object):
	def showExtensionSelection(self):
		self.opened = "extensions"


class InfoBarEPG(object):
	def InfoPressed(self):
		self.opened = "stock info"

	def EPGPressed(self):
		self.opened = "stock guide"


class InfoBarShowHide(object):
	STATE_HIDDEN, STATE_SHOWN = 0, 2

	def toggleShow(self):
		self.toggled = True

	def hide(self):
		self._InfoBarShowHide__state = self.STATE_HIDDEN


class InfoBarChannelSelection(object):
	def switchChannelUp(self):
		self.opened = "stock channel list"

	def showTvChannelList(self, zap=False):
		self.opened = "stock channel list"


class InfoBarInstantRecord(object):
	def keyInstantRecord(self, serviceRef=None):
		self.opened = "stock record options"

	def startInstantRecording(self, limitEvent=False):
		self.started = limitEvent

	def stopCurrentRecording(self, entry=-1):
		self.stopped = entry


class InfoBarAudioSelection(object):
	def audioSelection(self):
		self.opened = "stock audio"


class InfoBarSubtitleSupport(object):
	def subtitleSelection(self):
		self.opened = "stock subtitles"


class MoviePlayer(Screen):
	def __init__(self, session, service, *args):
		Screen.__init__(self, session)
		self.service = service

	def handleLeave(self, how, *args):
		self.left = how


SERVICE_NAMES = {}  # channel reference -> name, for ServiceReference(ref string)

config = Config()
config.plugins = Config()


def _module(name, **attrs):
	module = types.ModuleType(name)
	module.__dict__.update(attrs)
	sys.modules[name] = module
	if "." in name:
		parent, child = name.rsplit(".", 1)
		setattr(sys.modules[parent], child, module)
	return module


def install():
	for package in ("Components", "Components.Sources", "Components.Converter", "Components.Renderer", "Screens", "Plugins", "Tools"):
		_module(package)
	_module("enigma", eTimer=Timer, gRGB=lambda value: value, gFont=lambda name, size: size,
		ePoint=lambda x, y: (x, y), eRect=lambda *args: args, eListboxPythonMultiContent=object,
		eEPGCache=object, eServiceCenter=object, eServiceReference=eServiceReference, ePicLoad=PicLoad, ePixmap=object,
		iPlayableService=types.SimpleNamespace(evStart=0, evEnd=1, evUpdatedInfo=4, evVideoSizeChanged=10, evSeekableStatusChanged=6),
		iServiceInformation=types.SimpleNamespace(sVideoHeight=0, sServiceref=143),
		iRecordableService=types.SimpleNamespace(evStart=1, evEnd=2),
		RT_HALIGN_LEFT=0, RT_HALIGN_RIGHT=1, RT_HALIGN_CENTER=2, RT_VALIGN_TOP=0, RT_VALIGN_CENTER=4, RT_VALIGN_BOTTOM=8)
	_module("Components.MenuList", MenuList=MenuList)
	_module("RecordTimer", RecordTimerEntry=RecordTimerEntry)
	config.usage = Config()
	config.usage.show_message_when_recording_starts = Obj(default=True)
	_module("Components.Renderer.Renderer", Renderer=type("Renderer", (object,), {}))
	_module("Components.Pixmap", Pixmap=Pixmap)
	_module("Tools.LoadPixmap", LoadPixmap=lambda path, desktop=None, cached=False: path)
	_module("timer", TimerEntry=types.SimpleNamespace(StateWaiting=0, StatePrepared=1, StateRunning=2, StateEnded=3))
	_module("Components.Converter.Converter", Converter=Converter)
	_module("Components.Converter.Poll", Poll=Poll)
	_module("Components.Element", cached=lambda fnc: fnc)
	_module("skin", dom_screens={"InfoBar": ("stock InfoBar element", "/usr/share/enigma2/skin")})
	_module("Components.MultiContent", MultiContentEntryText=lambda **kwargs: kwargs,
		MultiContentEntryPixmapAlphaBlend=lambda **kwargs: kwargs)
	_module("Components.ActionMap", ActionMap=Obj)
	_module("Components.Label", Label=Widget)
	_module("Components.ProgressBar", ProgressBar=Widget)
	_module("Components.Sources.StaticText", StaticText=Widget)
	_module("Components.ConfigList", ConfigListScreen=type("ConfigListScreen", (), {
		"__init__": lambda self, *a, **k: None, "keySave": lambda self: self.close(), "keyCancel": lambda self: self.close()}))
	_module("Components.config", config=config, configfile=types.SimpleNamespace(save=lambda: None),
		ConfigSubsection=Config, ConfigYesNo=Obj, ConfigPIN=Obj, ConfigText=Obj,
		getConfigListEntry=lambda *args: args)
	_module("ServiceReference", ServiceReference=lambda ref: types.SimpleNamespace(
		getServiceName=lambda: getattr(ref, "name", None) or SERVICE_NAMES.get(ref, "")))
	_module("Screens.Screen", Screen=Screen)
	_module("Screens.InfoBarGenerics", InfoBarMenu=InfoBarMenu, InfoBarExtensions=InfoBarExtensions, InfoBarEPG=InfoBarEPG, InfoBarShowHide=InfoBarShowHide,
		InfoBarAudioSelection=InfoBarAudioSelection, InfoBarSubtitleSupport=InfoBarSubtitleSupport,
		InfoBarChannelSelection=InfoBarChannelSelection, InfoBarInstantRecord=InfoBarInstantRecord)
	_module("Screens.InfoBar", InfoBar=type("InfoBar", (), {"instance": None}), MoviePlayer=MoviePlayer)
	_module("Plugins.Plugin", PluginDescriptor=type("PluginDescriptor", (Obj,), {"WHERE_SESSIONSTART": 1, "WHERE_PLUGINMENU": 2}))
	sys.path.insert(0, os.path.abspath(PLUGIN_PARENT))


def fake_session(channel="RTÉ One", now=None, upcoming=None):
	"""A session whose current service has the given now and next events."""
	def event(details):
		if details is None:
			return None
		begin, duration, name = details
		return types.SimpleNamespace(getBeginTime=lambda: begin, getDuration=lambda: duration, getEventName=lambda: name)

	events = [event(now), event(upcoming)]
	picture = {"height": -1}
	info = types.SimpleNamespace(getEvent=lambda i: events[i], getInfo=lambda what: picture["height"])
	service = types.SimpleNamespace(info=lambda: info)
	nav = types.SimpleNamespace(
		getCurrentService=lambda: service,
		getCurrentlyPlayingServiceReference=lambda: types.SimpleNamespace(name=channel),
		played=[],
	)
	nav.playService = nav.played.append
	nav.stopService = lambda: nav.played.append(None)
	session = types.SimpleNamespace(nav=nav, opened=[], zapped=[], picture=picture)
	session.open = lambda cls, *args, **kwargs: session.opened.append((cls.__name__,) + args + ((kwargs,) if kwargs else ()))
	session.openWithCallback = lambda callback, cls, *args, **kwargs: session.opened.append((cls.__name__,) + args + ((kwargs,) if kwargs else ()))
	return session


def fake_service(ref, video_height=-1, name=""):
	"""A playing service as session.CurrentService exposes it."""
	info = types.SimpleNamespace(
		getInfoString=lambda what: ref,
		getInfo=lambda what: video_height,
		getName=lambda: name,
	)
	return types.SimpleNamespace(service=types.SimpleNamespace(info=lambda: info))
