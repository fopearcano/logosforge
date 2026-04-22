#!/usr/bin/env bash
# Build Logosforge.app for macOS Intel (x86_64), targeting Monterey (12.0+).
#
# Usage:
#   chmod +x build_mac.sh
#   ./build_mac.sh
#
# Prerequisites:
#   - macOS 12+ on Intel (or Rosetta on Apple Silicon)
#   - Python 3.10+
#   - pip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Logosforge Mac Build ==="
echo "Target: macOS 12 Monterey, Intel x86_64"
echo ""

# --- 1. Create or reuse virtual environment ---
VENV_DIR="$PROJECT_ROOT/build_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/5] Creating build virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/5] Reusing existing build virtual environment..."
fi

source "$VENV_DIR/bin/activate"

# --- 2. Install dependencies ---
echo "[2/5] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller>=6.0 -q

# --- 3. Convert PNG icon to ICNS (if not already done) ---
ICON_PNG="$PROJECT_ROOT/assets/icon.png"
ICON_SVG="$PROJECT_ROOT/assets/icon.svg"
ICON_ICNS="$PROJECT_ROOT/assets/icon.icns"
if [ ! -f "$ICON_ICNS" ]; then
    # Prefer PNG source; fall back to SVG
    if [ -f "$ICON_PNG" ]; then
        ICON_SRC="$ICON_PNG"
    elif [ -f "$ICON_SVG" ]; then
        ICON_SRC="$ICON_SVG"
    else
        ICON_SRC=""
    fi

    if [ -n "$ICON_SRC" ]; then
        echo "[3/5] Converting icon to ICNS..."
        ICONSET_DIR="$PROJECT_ROOT/assets/icon.iconset"
        mkdir -p "$ICONSET_DIR"

        if command -v sips &>/dev/null; then
            for SIZE in 16 32 64 128 256 512; do
                sips -s format png -z $SIZE $SIZE "$ICON_SRC" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" 2>/dev/null || true
                DOUBLE=$((SIZE * 2))
                sips -s format png -z $DOUBLE $DOUBLE "$ICON_SRC" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}@2x.png" 2>/dev/null || true
            done
            if command -v iconutil &>/dev/null; then
                iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS" 2>/dev/null || echo "  Warning: iconutil failed, building without custom icon"
            fi
        else
            echo "  Warning: sips not available, building without custom icon"
        fi
        rm -rf "$ICONSET_DIR"
    else
        echo "[3/5] No icon source found, building without custom icon."
    fi
else
    echo "[3/5] Icon ICNS already exists."
fi

# --- 4. Run PyInstaller ---
echo "[4/5] Building with PyInstaller..."
pyinstaller "$SCRIPT_DIR/logosforge.spec" \
    --noconfirm \
    --clean \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build"

# --- 5. Verify ---
APP_PATH="$PROJECT_ROOT/dist/Logosforge.app"
if [ -d "$APP_PATH" ]; then
    echo ""
    echo "[5/5] Build successful!"
    echo ""
    echo "  App:  $APP_PATH"
    SIZE=$(du -sh "$APP_PATH" | cut -f1)
    echo "  Size: $SIZE"
    echo ""
    echo "To run:  open dist/Logosforge.app"
    echo "To distribute: zip or create a DMG from dist/Logosforge.app"
    echo ""
    echo "=== Create DMG (optional) ==="
    echo "  hdiutil create -volname Logosforge -srcfolder dist/Logosforge.app -ov dist/Logosforge.dmg"
else
    echo ""
    echo "[5/5] Build failed — dist/Logosforge.app not found."
    exit 1
fi

deactivate 2>/dev/null || true
