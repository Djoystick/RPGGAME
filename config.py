from __future__ import annotations

APP_VERSION = "1.2.0"

import os
import sys
from pathlib import Path
from types import MappingProxyType


APP_NAME = "Desktop Abyss: Taskbar Chronicle"
APP_SLUG = "desktop-abyss"
ORGANIZATION_NAME = "DesktopAbyss"
SAVE_SCHEMA_VERSION = 6

PROJECT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
SPRITES_DIR = ASSETS_DIR / "sprites"
ORNAMENTS_DIR = ASSETS_DIR / "ornaments"
SOUNDS_DIR = ASSETS_DIR / "sounds"


def _user_data_dir() -> Path:
    override = os.environ.get("DESKTOP_ABYSS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        root = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        )
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(
            os.environ.get(
                "XDG_DATA_HOME",
                str(Path.home() / ".local" / "share"),
            )
        )

    return root / APP_SLUG


DATA_DIR = _user_data_dir()
SAVE_PATH = DATA_DIR / "save.json"
LOCK_PATH = DATA_DIR / "application.lock"

AUTOSAVE_INTERVAL_MS = 30_000
MAX_PARTY_SIZE = 4
DEFAULT_STASH_CAPACITY = 120
DEFAULT_BACKPACK_CAPACITY = 48

# Индекс ступени хранится в сохранении.
OFFLINE_CAP_HOURS = (2, 3, 4, 6, 8, 12)
OFFLINE_CAP_SECONDS = tuple(hours * 3600 for hours in OFFLINE_CAP_HOURS)
OFFLINE_EFFICIENCIES = (0.60, 0.75, 0.90, 1.00)

# Начальный баланс. Эти значения не зафиксированы в GDD.
DEFAULT_WAVE_CLEAR_SECONDS = 12.0
MIN_WAVE_CLEAR_SECONDS = 1.0
DEFAULT_GOLD_PER_WAVE = 100
DEFAULT_EXP_PER_WAVE = 30
DEFAULT_DROP_CHANCE = 0.02

# Минимальный предметный DTO Модуля 1:
# редкость, относительный вес, базовая цена продажи.
LOOT_TABLE = (
    ("common", 75, 10),
    ("rare", 20, 50),
    ("legendary", 5, 250),
)
ITEM_RARITIES = frozenset({
    "common",
    "uncommon",
    "rare",
    "legendary",
    "immortal",
    "mythic",
})

PALETTE = MappingProxyType({
    "basalt": "#121118",
    "steel": "#23212b",
    "ruby": "#8b1818",
    "gold": "#c8963e",
    "amethyst": "#9b4dca",
    "text": "#e4dccb",
    "muted_text": "#9a919f",
    "border": "#514032",
    "health": "#a32b36",
    "mana": "#477cb8",
})

BATTLE_STAGE_WIDTH = 520
BATTLE_STAGE_HEIGHT = 144
