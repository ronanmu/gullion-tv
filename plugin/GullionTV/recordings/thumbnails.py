# -*- coding: utf-8 -*-
"""Pictures for recordings: one frame from each recording, saved beside it.

Uses ffmpeg (opkg install ffmpeg) at the lowest priority, so playback and the
guide aren't slowed. Without ffmpeg, recordings keep showing their channel's
picon. A frame is taken about 10% in, past the opening titles; one that comes
out nearly blank (a fade, a black screen) is tried again further in.
"""
import os
import subprocess
import threading

from . import store as recordings

WIDTH, HEIGHT = 328, 184
TRIES = (0.10, 0.25, 0.40)
BLANK_BYTES = 3500  # a black or flat 328x184 JPEG is smaller than this
SEARCH_PATH = ("/usr/bin", "/usr/local/bin", "/bin")
_lock = threading.Lock()


def path_for(recording_path):
	return recording_path + ".jpg"


def find_program(name):
	for folder in os.environ.get("PATH", "").split(os.pathsep) + list(SEARCH_PATH):
		candidate = os.path.join(folder, name)
		if folder and os.access(candidate, os.X_OK):
			return candidate
	return None


def find_ffmpeg():
	return find_program("ffmpeg")


def command(ffmpeg, source, target, seconds):
	nice = ["nice", "-n", "19"] if find_program("nice") else []
	return nice + [ffmpeg, "-nostdin", "-loglevel", "error", "-ss", str(int(seconds)), "-i", source,
		"-frames:v", "1", "-vf", "scale=%d:%d" % (WIDTH, HEIGHT), "-q:v", "4", "-y", target]


def make(recording, ffmpeg=None, run=None):
	"""Save a frame for one recording. Returns the picture's path, or None."""
	ffmpeg = ffmpeg or find_ffmpeg()
	if not ffmpeg or not recording.duration:
		return None
	run = run or _run
	target = path_for(recording.path)
	working = target + ".part"
	with _lock:  # one ffmpeg at a time
		for share in TRIES:
			if run(command(ffmpeg, recording.path, working, recording.duration * share)) != 0:
				break
			try:
				size = os.path.getsize(working)
			except OSError:
				break
			if size >= BLANK_BYTES:
				os.rename(working, target)
				return target
		if os.path.exists(working):
			os.remove(working)
	return None


def make_missing(found, limit=12, ffmpeg=None, run=None):
	"""Frames for the newest recordings that don't have one yet. Returns how many were made."""
	ffmpeg = ffmpeg or find_ffmpeg()
	if not ffmpeg:
		return 0
	made = 0
	for recording in found[:limit]:
		if recording.image is None and make(recording, ffmpeg, run):
			made += 1
	return made


def watch_recordings(session):
	"""Make a frame as soon as each recording finishes. Called once, at start-up."""
	try:
		from timer import TimerEntry
		timers = session.nav.RecordTimer
	except Exception:
		return

	def changed(timer):
		if timer.state == TimerEntry.StateEnded and getattr(timer, "Filename", None):
			path = timer.Filename + ".ts"
			worker = threading.Thread(target=lambda: os.path.isfile(path) and make(recordings.read(path)))
			worker.daemon = True
			worker.start()

	timers.on_state_change.append(changed)


def _run(arguments):
	try:
		with open(os.devnull, "wb") as quiet:
			return subprocess.call(arguments, stdout=quiet, stderr=quiet)
	except OSError:
		return 1
