#!/bin/bash
# ═══════════════════════════════════════════════════════════
#   A Whale's Heart — Launcher v0.12
# ═══════════════════════════════════════════════════════════
cd "$(dirname "$0")"
clear

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │      A Whale's Heart            │"
echo "  └─────────────────────────────────┘"
echo ""

# ── FIND SCLANG ─────────────────────────────────────────────
SCLANG="/Applications/SuperCollider.app/Contents/MacOS/sclang"

if [ ! -f "$SCLANG" ]; then
    echo "  ✗  SuperCollider not found at:"
    echo "     $SCLANG"
    echo "  Download: https://supercollider.github.io"
    read -p "  Press Enter to exit..."
    exit 1
fi

# ── KILL OLD INSTANCES ───────────────────────────────────────
pkill -f "python3 bridge.py" 2>/dev/null
pkill -f "sclang"            2>/dev/null
sleep 0.4

# ── START BRIDGE ─────────────────────────────────────────────
echo "  Starting bridge (HTTP + OSC)..."
python3 bridge.py &
BRIDGE_PID=$!
sleep 1.0

if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "  ✗  Bridge failed. Is port 8080 already in use?"
    echo "     Run: lsof -i :8080   to check"
    read -p "  Press Enter to exit..."
    exit 1
fi
echo "  ✓  Bridge on http://localhost:8080  (pid $BRIDGE_PID)"

# ── OPEN BROWSER ─────────────────────────────────────────────
echo "  Opening browser..."
open "http://localhost:8080"
sleep 0.4

# ── START SCLANG (headless — no IDE needed) ──────────────────
echo "  Starting SuperCollider (sclang)..."
"$SCLANG" supercollider/whaleheart.scd &
SC_PID=$!

echo ""
echo "  ┌──────────────────────────────────────────┐"
echo "  │  SuperCollider output appears below.     │"
echo "  │                                          │"
echo "  │  When you see 'SC ready' →               │"
echo "  │  browser dot turns green → press Play.   │"
echo "  │                                          │"
echo "  │  Ctrl+C stops everything.                │"
echo "  └──────────────────────────────────────────┘"
echo ""

# Stop everything cleanly on exit
trap "echo ''; echo '  Stopping...'; kill $BRIDGE_PID $SC_PID 2>/dev/null; exit 0" INT TERM

# Wait — sclang output streams here
wait $SC_PID
kill $BRIDGE_PID 2>/dev/null
