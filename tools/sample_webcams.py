# -*- coding: utf-8 -*-
"""Made-up webcam pages, streams and pictures for offline checks and renders.

The pages copy only the structure of mcn.live and churchservices.tv pages (the
bits GullionTV reads), not their content.
"""
import time

import sample_epg

NOW = sample_epg.NOW
TOMORROW_10AM = time.mktime(time.localtime(NOW)[:3] + (10, 0, 0, 0, 0, -1)) + 86400

MCN_PAGE = """<html><body>
<video id='CameraLiveStream-0'><source id="LiveStreamSrc-0" src="https://cdn.example/live/stmalachys.stream/playlist.m3u8" type="application/x-mpegURL"></video>
<img src="https://cdn.example/live/Uploads/ProfileImages/stmalachys.jpeg" class="profile">
</body></html>"""

CHURCHSERVICES_PAGE = """<html><body>
<img src="https://www.churchservices.tv/wp-content/uploads/cathedral-225x300.jpg" class="img-responsive church-image">
<div class="default-stream" data-src="https://cdn3.wowza.com/5/abc/CSTV-HTTP/cathedral.stream/playlist.m3u8"></div>
<div data-show="1" class="playlist-row schedule-type schedule-11 "><div class="playlist-content">
<div class="playlist-title"><span class="playlist-time" data-src="10:00"></span> - Daily Mass</div></div></div>
<div data-show="2" class="playlist-row schedule-type schedule-12 hidden"><div class="playlist-content">
<div class="playlist-title"><span class="playlist-time" data-src="19:30"></span> - Private Vigil</div></div></div>
<script>var todays_schedules = '[{"id":11,"start_time":%d,"end_time":%d,"password":"","length":2400},{"id":12,"start_time":%d,"end_time":%d,"password":"secret","length":3600}]';</script>
</body></html>""" % (TOMORROW_10AM, TOMORROW_10AM + 2400, NOW + 3600, NOW + 7200)

CAMERA_LIST = """#EXTM3U
#EXTINF:-1 tvg-logo="http://cams.example/main-street.jpg" group-title="Local",Main Street
http://cams.example/main-street.m3u8
#EXTINF:-1 group-title="Local",Harbour
harbour.m3u8
"""

LIVE_HLS = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720\nchunklist.m3u8\n"

CONFIG = """webcams:
  - name: St Malachy's Parish
    url: https://mcn.live/Camera/st-malachys-parish-belfast
    group: Church
  - name: Armagh Cathedral
    url: https://www.churchservices.tv/armaghcathedral
    group: Church
  - name: Town cameras
    type: playlist
    url: http://cams.example/cameras.m3u
  - name: Bridge
    url: https://quiet.example/bridge/live.m3u8
    group: Local
  - name: Front door
    url: rtsp://192.168.1.40:554/stream1
    group: Home
  - name: Missing link
"""

PAGES = {
	"https://mcn.live/Camera/st-malachys-parish-belfast": MCN_PAGE,
	"https://www.churchservices.tv/armaghcathedral": CHURCHSERVICES_PAGE,
	"http://cams.example/cameras.m3u": CAMERA_LIST,
	"https://cdn.example/live/stmalachys.stream/playlist.m3u8": LIVE_HLS,
	"https://cdn3.wowza.com/5/abc/CSTV-HTTP/cathedral.stream/playlist.m3u8": LIVE_HLS,
	"http://cams.example/main-street.m3u8": LIVE_HLS,
	"http://cams.example/harbour.m3u8": LIVE_HLS,
	# The bridge camera's stream answers, but with nothing playing.
	"https://quiet.example/bridge/live.m3u8": "",
}
PICTURES = {}  # url -> image bytes; filled in by tools/preview.py


def fake_fetch(url, binary=False, timeout=8):
	if binary:
		if url in PICTURES:
			return PICTURES[url]
		raise IOError("no picture at %s" % url)
	if url in PAGES:
		return PAGES[url]
	raise IOError("can't reach %s" % url)
