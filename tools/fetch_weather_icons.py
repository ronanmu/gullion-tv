"""Fetch Yr's weather icons (met.no, MIT licence) and scale them for the weather line.

	pip install pillow
	python3 tools/fetch_weather_icons.py     # writes plugin/GullionTV/images/weather/

Pinned to one commit of github.com/metno/weathericons, so the same icons come
back every time. The polar twilight versions aren't needed this far south.
"""
import io
import json
import os
import urllib.request

from PIL import Image

COMMIT = "89e3173756248b4696b9b10677b66c4ef435db53"
REPO = "https://raw.githubusercontent.com/metno/weathericons/%s/" % COMMIT
LISTING = "https://api.github.com/repos/metno/weathericons/contents/weather/png?ref=%s" % COMMIT
SIZE = 48
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "GullionTV", "images", "weather")


def get(url):
	with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gullion-tv"}), timeout=30) as response:
		return response.read()


def main():
	if not os.path.isdir(OUT):
		os.makedirs(OUT)
	names = sorted(entry["name"] for entry in json.loads(get(LISTING)) if "polartwilight" not in entry["name"])
	for name in names:
		icon = Image.open(io.BytesIO(get(REPO + "weather/png/" + name))).convert("RGBA")
		icon.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name), optimize=True)
	licence = get(REPO + "LICENSE").decode("utf-8")
	with open(os.path.join(OUT, "LICENSE"), "w") as handle:
		handle.write("Weather icons from Yr (https://github.com/metno/weathericons, commit %s),\n"
			"scaled to %dx%d by tools/fetch_weather_icons.py.\n\n%s" % (COMMIT, SIZE, SIZE, licence))
	print("%d icons in %s" % (len(names), os.path.normpath(OUT)))


if __name__ == "__main__":
	main()
