# -*- coding: utf-8 -*-
"""Read /etc/enigma2/gulliontv/webcams.yaml.

Uses PyYAML when the box has it, otherwise a small reader for the simple
layout the file uses: a `webcams:` list of `- key: value` entries.
"""
import io
import os

CONFIG_PATH = "/etc/enigma2/gulliontv/webcams.yaml"
KINDS = ("mcn", "churchservices", "stream", "playlist")
FIELDS = ("name", "url", "type", "image", "group", "player")


class Entry(object):
	def __init__(self, name, url, kind=None, image=None, group=None, player=4097, line=0):
		self.name = name
		self.url = url
		self.kind = kind or detect_kind(url)
		self.image = image
		self.group = group
		self.player = player
		self.line = line


def detect_kind(url):
	lowered = (url or "").lower()
	if "mcn.live/" in lowered:
		return "mcn"
	if "churchservices.tv/" in lowered:
		return "churchservices"
	if lowered.split("?")[0].endswith(".m3u"):
		return "playlist"
	return "stream"


def load(path=CONFIG_PATH):
	"""(entries, problems). problems are short sentences for Tech Support."""
	if not os.path.isfile(path):
		return [], []
	with io.open(path, encoding="utf-8") as handle:
		text = handle.read()
	return parse(text)


def parse(text):
	try:
		raw, lines = _parse_yaml(text)
	except ValueError as error:
		return [], [str(error)]
	entries, problems = [], []
	for item, line in zip(raw, lines):
		if not isinstance(item, dict):
			problems.append("Line %d: each webcam needs name and url" % line)
			continue
		name = _text(item.get("name"))
		url = _text(item.get("url"))
		if not name or not url:
			problems.append("Line %d: add a %s" % (line, "name" if not name else "url"))
			continue
		kind = _text(item.get("type")).lower() or None
		if kind and kind not in KINDS:
			problems.append("Line %d: type should be one of %s" % (line, ", ".join(KINDS)))
			continue
		try:
			player = int(item.get("player") or 4097)
		except (TypeError, ValueError):
			problems.append("Line %d: player should be 4097 or 5002" % line)
			continue
		entries.append(Entry(name, url, kind, _text(item.get("image")) or None, _text(item.get("group")) or None, player, line))
	return entries, problems


def _text(value):
	"""A stripped native string: UTF-8 bytes on the box's Python 2, as enigma2 expects."""
	if value is None:
		return ""
	if str is bytes and isinstance(value, type(u"")):
		value = value.encode("utf-8")
	elif not isinstance(value, str):
		value = str(value)
	return value.strip()


def _parse_yaml(text):
	"""[(dict per webcam)], [line number of each]."""
	try:
		import yaml
	except ImportError:
		return _parse_simple(text)
	try:
		data = yaml.safe_load(text) or {}
	except yaml.YAMLError as error:
		mark = getattr(error, "problem_mark", None)
		raise ValueError("Line %d: the file couldn't be read" % (mark.line + 1 if mark else 0))
	items = (data.get("webcams") or []) if isinstance(data, dict) else []
	return items, _item_lines(text, len(items))


def _item_lines(text, count):
	lines = [number for number, line in enumerate(text.splitlines(), 1) if line.strip().startswith("- ")]
	return (lines + [0] * count)[:count]


def _parse_simple(text):
	items, lines = [], []
	in_list = False
	current = None
	for number, raw in enumerate(text.splitlines(), 1):
		line = _strip_comment(raw).rstrip()
		if not line.strip():
			continue
		indent = len(line) - len(line.lstrip())
		body = line.strip()
		if indent == 0:
			in_list = body == "webcams:"
			if not in_list:
				raise ValueError("Line %d: the file should start with 'webcams:'" % number)
			continue
		if not in_list:
			continue
		if body.startswith("- "):
			current = {}
			items.append(current)
			lines.append(number)
			body = body[2:].strip()
			if not body:
				continue
		if current is None or ":" not in body:
			raise ValueError("Line %d: expected 'key: value'" % number)
		key, value = body.split(":", 1)
		current[key.strip().lower()] = _unquote(value.strip())
	return items, lines


def _strip_comment(line):
	"""Drop a trailing ' # comment'. A quoted value keeps everything inside its quotes,
	and an apostrophe in plain text (St Malachy's) isn't treated as a quote."""
	if line.lstrip().startswith("#"):
		return ""
	head, sep, value = line.partition(": ")
	value = value.lstrip()
	if sep and value[:1] in ("'", '"'):
		end = value.find(value[0], 1)
		if end > 0:
			return head + sep + value[:end + 1]
	index = line.find(" #")
	return line if index < 0 else line[:index]


def _unquote(value):
	if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
		return value[1:-1]
	return value
