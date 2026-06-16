#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# 1. Start a virtual framebuffer (headless X11 display inside the container)
# ---------------------------------------------------------------------------
Xvfb :0 -screen 0 1280x800x24 -ac &

# Wait until the display is ready (avoids races with x11vnc/app startup)
until xdpyinfo -display :0 >/dev/null 2>&1; do
    sleep 0.1
done

# ---------------------------------------------------------------------------
# 2. Start VNC server connected to the virtual display
#    -nopw   : no password (local development only, not exposed externally)
#    -listen : only accept connections from localhost (noVNC proxy)
#    -forever: keep running after the first client disconnects
#    -shared : allow more than one VNC viewer at once
# ---------------------------------------------------------------------------
x11vnc -display :0 -nopw -listen localhost -forever -shared -quiet &

# ---------------------------------------------------------------------------
# 3. Start noVNC — serves the browser-based VNC client on port 6080
#    Open http://localhost:6080/vnc.html in Safari or Chrome on your Mac
#    Add ?autoconnect=true&resize=scale for an auto-connecting scaled view
# ---------------------------------------------------------------------------
websockify --web /usr/share/novnc 6080 localhost:5900 &

# ---------------------------------------------------------------------------
# 4. Launch the application (replaces this shell as PID 1)
# ---------------------------------------------------------------------------
exec python -m src.main
