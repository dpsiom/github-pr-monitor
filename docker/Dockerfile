FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Virtual display used by Xvfb and the app
ENV DISPLAY=:0

# Install system-level X11, VNC, noVNC web client, and Tcl/Tk for the GUI
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        x11-utils \
        novnc \
        python3-tk \
    && rm -rf /var/lib/apt/lists/*

# websockify is the WebSocket-to-VNC bridge used by noVNC
RUN pip install --no-cache-dir websockify

RUN addgroup --system app && adduser --system --ingroup app app

# Writable home directory (default /nonexistent causes font/config errors)
ENV HOME=/app

# Pre-create the X11 socket directory with sticky bit so non-root Xvfb can use it
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    chmod +x /entrypoint.sh

USER app

# noVNC is served on this port; open http://localhost:6080/vnc.html in a browser
EXPOSE 6080

ENTRYPOINT ["/entrypoint.sh"]
