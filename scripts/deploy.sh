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

# macOS tar adds its own file attributes, which the box's tar doesn't understand.
TAR_FLAGS=""
if tar --version 2>/dev/null | grep -q bsdtar; then
	TAR_FLAGS="--no-xattrs --no-mac-metadata"
fi

echo "Copying plugin to $BOX:$DEST.new"
# shellcheck disable=SC2086
COPYFILE_DISABLE=1 tar $TAR_FLAGS -C "$ROOT/plugin/GullionTV" --exclude '*.pyc' --exclude '__pycache__' -cf - . \
	| ssh "root@$BOX" "rm -rf $DEST.new && mkdir -p $DEST.new && tar -xof - -C $DEST.new"

# Compile every file with the box's own Python 2.7 before swapping it in, so a
# Python 2 mistake stops the deploy instead of breaking enigma2's next start.
echo "Checking it compiles on the box"
ssh "root@$BOX" "sh -s" <<SCRIPT
set -e
cd $DEST.new
python -c "
import os, py_compile, sys
failed = 0
for root, dirs, files in os.walk('.'):
    for name in files:
        if name.endswith('.py'):
            try:
                py_compile.compile(os.path.join(root, name), doraise=True)
            except Exception as error:
                failed += 1
                print(error)
sys.exit(1 if failed else 0)
"
rm -rf $DEST
mv $DEST.new $DEST
SCRIPT

CONFIG_DIR=/etc/enigma2/gulliontv
FORCE="${FORCE_CONFIG:-0}"
echo "Installing webcams.yaml (an existing one on the box is kept unless FORCE_CONFIG=1)"
ssh "root@$BOX" "mkdir -p $CONFIG_DIR && if [ $FORCE = 1 ] || [ ! -f $CONFIG_DIR/webcams.yaml ]; then cat > $CONFIG_DIR/webcams.yaml; else cat > /dev/null; fi" \
	< "$ROOT/config/webcams.yaml"
if [ -d "$ROOT/config/images" ]; then
	echo "Copying webcam pictures to $CONFIG_DIR/images"
	COPYFILE_DISABLE=1 tar -C "$ROOT/config" $TAR_FLAGS -cf - images | ssh "root@$BOX" "tar -xof - -C $CONFIG_DIR"
fi

echo "Restarting enigma2"
ssh "root@$BOX" "/sbin/init 4; sleep 3; /sbin/init 3"

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
