#!/usr/bin/env bash
# Starts a virtual desktop (Xvfb + openbox) served over VNC on port 5900.
# Connect from macOS: Finder > Go > Connect to Server > vnc://localhost:5900  (password: ros)

Xvfb :1 -screen 0 1024x700x24 +extension GLX +render -noreset > /tmp/xvfb.log 2>&1 &
sleep 1
DISPLAY=:1 openbox > /tmp/openbox.log 2>&1 &
x11vnc -display :1 -forever -shared -passwd ros -quiet -bg -o /tmp/x11vnc.log

echo "Desktop ready. On your Mac: Finder > Go > Connect to Server > vnc://localhost:5900 (password: ros)"
echo "Then in this shell:  export DISPLAY=:1"
websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/neptune-novnc.log 2>&1 &
