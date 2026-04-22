# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Logosforge — Mac Intel (x86_64), macOS 12 Monterey."""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT = os.path.abspath(os.path.dirname(SPECPATH))

# Collect PySide6 — PyInstaller's hook handles most of it,
# but we exclude unused Qt modules to shrink the bundle.
EXCLUDE_QT = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTest",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtDBus",
    "PySide6.QtSql",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtHttpServer",
]

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "assets"), "assets"),
        (os.path.join(ROOT, "plugins"), "plugins"),
        (os.path.join(ROOT, "docs"), "docs"),
    ],
    hiddenimports=[
        "storyplanner",
        "storyplanner.app",
        "storyplanner.db",
        "storyplanner.db.database",
        "storyplanner.models",
        "storyplanner.models.models",
        "storyplanner.plugins",
        "storyplanner.plugins.dialogue_tension",
        "storyplanner.plugins.character_presence",
        "sqlmodel",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDE_QT,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Logosforge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    target_arch="x86_64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name="Logosforge",
)

def _find_icon():
    for name in ("icon.icns", "icon.png"):
        p = os.path.join(ROOT, "assets", name)
        if os.path.exists(p):
            return p
    return None

app = BUNDLE(
    coll,
    name="Logosforge.app",
    icon=_find_icon(),
    bundle_identifier="com.logosforge.app",
    info_plist={
        "CFBundleName": "Logosforge",
        "CFBundleDisplayName": "Logosforge",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSRequiresAquaSystemAppearance": False,
    },
)
