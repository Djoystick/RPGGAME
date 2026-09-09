from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import QIODevice, QSaveFile

import config as C
from engine.state import (
    FarmProfile,
    GameData,
    GameState,
    HeroState,
    ItemDrop,
    require_number,
)
from models.hero import build_from_dict
from models.item import item_from_dict


class SaveError(RuntimeError):
    pass


class SaveManager:
    def __init__(self, path: Path = C.SAVE_PATH) -> None:
        self.path = Path(path)

    def load(self) -> GameData:
        if not self.path.exists():
            return GameData()

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            version = payload["schema_version"]

            if type(version) is not int:
                raise ValueError("Некорректная версия сохранения")
            if version not in (1, 2, 3, 4, 5, C.SAVE_SCHEMA_VERSION):
                raise ValueError(f"Неподдерживаемая версия: {version}")

            raw = dict(payload["state"])

            raw["party"] = tuple(
                HeroState(**hero) for hero in raw["party"]
            )
            raw["stash"] = tuple(
                item_from_dict(item) for item in raw["stash"]
            )
            raw["backpack"] = tuple(
                item_from_dict(item)
                for item in raw.get("backpack", ())
            )
            raw["farm"] = FarmProfile(**raw["farm"])

            raw["hero_builds"] = tuple(
                build_from_dict(build)
                for build in raw.get("hero_builds", ())
            )
            raw["unlocked_runes"] = tuple(
                raw.get("unlocked_runes", ())
            )

            raw["reward_claims"] = tuple(raw.get("reward_claims", ()))
            data = GameData(**raw)

            # Импорт внутри метода: runes_tree использует SaveManager.
            from engine.runes_tree import RunesTree
            RunesTree().validate_unlocked(data.unlocked_runes)

            return data

        except (
            OSError,
            UnicodeError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
        ) as exc:
            raise SaveError(
                f"Не удалось загрузить {self.path}: {exc}"
            ) from exc

    def write(self, data: GameData) -> None:
        payload = {
            "schema_version": C.SAVE_SCHEMA_VERSION,
            "state": asdict(data),
        }

        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError, TypeError) as exc:
            raise SaveError(f"Ошибка подготовки сохранения: {exc}") from exc

        file = QSaveFile(str(self.path))
        file.setDirectWriteFallback(False)

        if not file.open(QIODevice.OpenModeFlag.WriteOnly):
            raise SaveError(file.errorString())

        if file.write(encoded) != len(encoded):
            message = file.errorString()
            file.cancelWriting()
            raise SaveError(f"Ошибка записи: {message}")

        if not file.commit():
            raise SaveError(f"Ошибка фиксации сохранения: {file.errorString()}")

    def checkpoint(
        self,
        state: GameState,
        now: float | None = None,
    ) -> None:
        """Сохранить активную сессию без начисления оффлайн-наград."""
        state.assert_owner_thread()

        timestamp = time.time() if now is None else now
        require_number("now", timestamp)

        before = state.data
        after = replace(
            before,
            # Не отматываем уже обработанное время назад.
            last_active_timestamp=max(
                timestamp,
                before.last_active_timestamp,
            ),
        )

        self.write(after)
        state.commit(before, after)
