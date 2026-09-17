#!/usr/bin/env bash
# Docker's /tmp is not the desktop session /tmp, so Chromium in the API
# container cannot see /tmp/.X11-unix/X0. Forward the real X socket into $HOME.
set -euo pipefail
dir="${HOME}/.n3xus-x11"
mkdir -p "$dir"
sock="$dir/X0"
# Replace a stale listener.
if ss -xl 2>/dev/null | grep -q "$sock"; then
  pkill -f "socat UNIX-LISTEN:${sock}" 2>/dev/null || true
fi
rm -f "$sock"
exec socat "UNIX-LISTEN:${sock},fork,unlink-close=0,mode=777" "UNIX-CONNECT:/tmp/.X11-unix/X0"
