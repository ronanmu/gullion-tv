# -*- coding: utf-8 -*-
"""The box's recordings, read straight from the recording folder.

Each recording is a .ts file with a .ts.meta file beside it:
	line 1  service reference      line 4  time recorded (epoch)
	line 2  title                  line 6  length (90 kHz ticks)
	line 3  description
A .ts.cuts file holds cue marks; type 3 is where playback last stopped.
"""
import os
import struct
import time

DEFAULT_FOLDER = "/media/hdd/movie"
GB = 1024 ** 3
MIN_FREE = 2 * GB   # below this a recording would soon fill the drive
LOW_FREE = 10 * GB  # below this, warn
READY, LOW, FULL, MISSING = "ready", "low", "full", "missing"
TICKS = 90000
LAST_POSITION = 3
COMPANIONS = (".meta", ".ap", ".sc", ".cuts", ".sc.cuts")


class Recording(object):
	def __init__(self, path, title, channel_ref, description, begin, duration, position):
		self.path = path
		self.title = title
		self.channel_ref = channel_ref
		self.description = description
		self.begin = begin
		self.duration = duration
		self.position = position
		self.channel = ""

	@property
	def service_ref(self):
		return "1:0:0:0:0:0:0:0:0:0:" + self.path

	@property
	def progress(self):
		"""How far through it was left, 0-1, or None if never started."""
		if not self.position or not self.duration:
			return None
		return min(1.0, float(self.position) / self.duration)

	@property
	def in_progress(self):
		"""Started, more than a minute in, and not finished."""
		return self.progress is not None and self.position > 60 and self.progress < 0.95

	@property
	def viewed_at(self):
		"""When it was last watched: the cue file is rewritten each time playback stops."""
		try:
			return int(os.path.getmtime(self.path + ".cuts"))
		except OSError:
			return 0

	@property
	def image(self):
		"""A picture saved beside the recording by a thumbnail tool, if there is one."""
		for candidate in (self.path + ".jpg", os.path.splitext(self.path)[0] + ".jpg"):
			if os.path.isfile(candidate):
				return candidate
		return None

	def when(self, now=None):
		now = time.time() if now is None else now
		day = time.localtime(self.begin)
		days = (_midnight(now) - _midnight(self.begin)) // 86400
		clock = time.strftime("%H:%M", day)
		if days == 0:
			return "Today %s" % clock
		if days == 1:
			return "Yesterday %s" % clock
		if days < 7:
			return "%s %s" % (time.strftime("%A", day), clock)
		return "%d %s" % (day.tm_mday, time.strftime("%b", day))


def storage(folder=None):
	"""(state, free bytes) for the recording folder.

	MISSING: no folder, not on a plugged-in drive (the box's own flash is far too
	small), or it can't be written to. FULL: under MIN_FREE left. LOW: under
	LOW_FREE. READY: fine.
	"""
	folder = folder or default_folder()
	if not os.path.isdir(folder) or mount_point(folder) == "/" or not os.access(folder, os.W_OK):
		return MISSING, 0
	free = free_space(folder)
	if free < MIN_FREE:
		return FULL, free
	if free < LOW_FREE:
		return LOW, free
	return READY, free


def can_record(state):
	return state in (READY, LOW)


def mount_point(path):
	path = os.path.realpath(path)
	while not os.path.ismount(path):
		path = os.path.dirname(path)
	return path


def free_space(path):
	stats = os.statvfs(path)
	return stats.f_bavail * stats.f_frsize


def default_folder():
	try:
		from Components.config import config
		return config.usage.default_path.value or DEFAULT_FOLDER
	except Exception:
		return DEFAULT_FOLDER


def list_recordings(folder=None, channel_name=None):
	"""Recordings in the folder, newest first. channel_name(ref) names the channel."""
	folder = folder or default_folder()
	found = []
	try:
		names = os.listdir(folder)
	except OSError:
		return found
	for name in names:
		if not name.endswith(".ts") or name.startswith("."):
			continue
		recording = read(os.path.join(folder, name))
		if recording is not None:
			if channel_name is not None:
				try:
					recording.channel = channel_name(recording.channel_ref)
				except Exception:
					recording.channel = ""
			found.append(recording)
	found.sort(key=lambda recording: recording.begin, reverse=True)
	return found


def read(path):
	lines = []
	try:
		with open(path + ".meta", "rb") as handle:
			lines = handle.read().decode("utf-8", "replace").splitlines()
	except (IOError, OSError):
		pass
	lines += [""] * (7 - len(lines))
	title = lines[1].strip() or os.path.splitext(os.path.basename(path))[0]
	begin = _number(lines[3]) or _mtime(path)
	duration = _number(lines[5]) // TICKS
	return Recording(path, _native(title), lines[0].strip(), _native(lines[2].strip()), begin, duration, last_position(path))


def last_position(path):
	"""Seconds into the recording where it was last stopped, or 0."""
	try:
		with open(path + ".cuts", "rb") as handle:
			data = handle.read()
	except (IOError, OSError):
		return 0
	position = 0
	for offset in range(0, len(data) - 11, 12):
		ticks, kind = struct.unpack(">QI", data[offset:offset + 12])
		if kind == LAST_POSITION:
			position = ticks // TICKS
	return position


def move_to_trash(recording):
	"""Move the recording and its companion files to the recycle bin folder."""
	folder = os.path.dirname(recording.path)
	trash = _trash_folder(folder)
	base = os.path.splitext(recording.path)[0]
	paths = [recording.path] + [recording.path + suffix for suffix in COMPANIONS] + [base + ".eit", base + ".jpg", recording.path + ".jpg"]
	for path in paths:
		if os.path.exists(path):
			os.rename(path, os.path.join(trash, os.path.basename(path)))
	return trash


def _trash_folder(folder):
	try:
		from Tools.Trashcan import createTrashFolder
		trash = createTrashFolder(folder)
		if trash:
			return trash
	except Exception:
		pass
	trash = os.path.join(folder, ".Trash")
	if not os.path.isdir(trash):
		os.makedirs(trash)
	return trash


def _number(text):
	try:
		return int(text.strip())
	except (ValueError, AttributeError):
		return 0


def _mtime(path):
	try:
		return int(os.path.getmtime(path))
	except OSError:
		return 0


def _native(text):
	if str is bytes and isinstance(text, type(u"")):
		return text.encode("utf-8")
	return text


def _midnight(timestamp):
	day = time.localtime(timestamp)
	return int(time.mktime((day.tm_year, day.tm_mon, day.tm_mday, 0, 0, 0, 0, 0, -1)))
