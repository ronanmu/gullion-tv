#!/bin/sh
# Copy the GullionTV plugin to the box, restart enigma2 and grab a screenshot.
#
#   BOX=192.168.1.50 scripts/deploy.sh
#
# Needs SSH access as root on the box and OpenWebif running (for the screenshot).
set -eu

BOX="${BOX:?Set BOX to the box IP address or hostname}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/usr/lib/enigma2/python/Plugins/Extensions/GullionTV
SHOT="$ROOT/screenshots/$(date +%Y%m%d-%H%M%S).png"

echo "Copying plugin to $BOX:$DEST"
COPYFILE_DISABLE=1 tar -C "$ROOT/plugin/GullionTV" --exclude '*.pyc' --exclude '__pycache__' -cf - . \
	| ssh "root@$BOX" "rm -rf $DEST && mkdir -p $DEST && tar -xf - -C $DEST"

CONFIG_DIR=/etc/enigma2/gulliontv
FORCE="${FORCE_CONFIG:-0}"
echo "Installing webcams.yaml (an existing one on the box is kept unless FORCE_CONFIG=1)"
ssh "root@$BOX" "mkdir -p $CONFIG_DIR && if [ $FORCE = 1 ] || [ ! -f $CONFIG_DIR/webcams.yaml ]; then cat > $CONFIG_DIR/webcams.yaml; else cat > /dev/null; fi" \
	< "$ROOT/config/webcams.yaml"

echo "Restarting enigma2"
ssh "root@$BOX" "init 4; sleep 3; init 3"

echo "Waiting for the box to come back"
for _ in $(seq 1 30); do
	if curl -fs -m 3 "http://$BOX/api/statusinfo" >/dev/null 2>&1; then
		mkdir -p "$ROOT/screenshots"
		sleep 5
		curl -fs -m 15 "http://$BOX/grab?format=png&mode=all" -o "$SHOT" && echo "Screenshot: $SHOT"
		exit 0
	fi
	sleep 2
done
echo "Box didn't answer on OpenWebif within 60 seconds. Check /home/root/logs or the crash log." >&2
exit 1
