# -*- coding: utf-8 -*-
"""The LIVE marker on Home's preview and the webcam player: a red dot and LIVE in white,
on a small dark tag so it reads over any picture."""
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap

from .. import theme
from . import icons

WIDTH, HEIGHT = 140, 44


def skin(prefix, x, y, z=3):
	return (
		'<widget name="%(p)s_tag" position="%(x)d,%(y)d" size="%(w)d,%(h)d" backgroundColor="%(bg)s" zPosition="%(z)d" />'
		'<widget name="%(p)s_dot" position="%(dx)d,%(dy)d" size="24,24" alphatest="blend" zPosition="%(z1)d" />'
		'<widget name="%(p)s_text" position="%(tx)d,%(y)d" size="%(tw)d,%(h)d" font="Regular;28" valign="center" '
		'foregroundColor="#00ffffff" transparent="1" zPosition="%(z1)d" />'
	) % {"p": prefix, "x": x, "y": y, "w": WIDTH, "h": HEIGHT, "bg": theme.BACKGROUND, "z": z, "z1": z + 1,
		"dx": x + 16, "dy": y + (HEIGHT - 24) // 2, "tx": x + 52, "tw": WIDTH - 60}


def add_widgets(screen, prefix):
	screen[prefix + "_tag"] = Label()
	screen[prefix + "_dot"] = Pixmap()
	screen[prefix + "_text"] = Label("LIVE")


def show(screen, prefix, visible=True):
	dot = screen[prefix + "_dot"]
	if visible and dot.instance is not None:
		dot.instance.setPixmap(LoadPixmap(icons.key_icon("red"), cached=True))
	for part in ("_tag", "_dot", "_text"):
		if visible:
			screen[prefix + part].show()
		else:
			screen[prefix + part].hide()
