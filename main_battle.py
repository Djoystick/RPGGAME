from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication

import config as C
from engine.combat_manager import CombatManager
from engine.offline_manager import OfflineManager
from engine.save_manager import SaveError, SaveManager
from engine.state import GameState
from ui.battle_stage import BattleStage


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setOrganizationName(C.ORGANIZATION_NAME)

    try:
        C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Ошибка каталога данных: {exc}", file=sys.stderr)
        return 1

    lock = QLockFile(str(C.LOCK_PATH))
    lock.setStaleLockTime(0)

    if not lock.tryLock(0):
        print(
            "Не удалось получить блокировку. "
            "Закройте другой экземпляр Desktop Abyss.",
            file=sys.stderr,
        )
        return 1

    try:
        state = GameState.instance()
        saves = SaveManager()

        try:
            state.load(saves.load())
            offline = OfflineManager().claim(state, saves)
        except (SaveError, ValueError) as exc:
            print(f"Ошибка загрузки: {exc}", file=sys.stderr)
            return 1

        print(
            f"Оффлайн: {offline.waves_cleared} волн, "
            f"+{offline.total_gold} золота, +{offline.total_exp} XP"
        )

        combat = CombatManager(state, saves=saves)

        try:
            combat.start()
        except ValueError as exc:
            print(f"Ошибка состава отряда: {exc}", file=sys.stderr)
            return 1

        stage = BattleStage(combat)
        stage.setWindowTitle(f"{C.APP_NAME} — Battle Stage")
        stage.show()

        exit_status = 0

        def checkpoint() -> None:
            nonlocal exit_status
            try:
                combat.flush()
                saves.checkpoint(state)
            except (SaveError, ValueError) as exc:
                exit_status = 1
                print(f"Ошибка сохранения: {exc}", file=sys.stderr)

        autosave = QTimer(app)
        autosave.setInterval(C.AUTOSAVE_INTERVAL_MS)
        autosave.timeout.connect(checkpoint)
        autosave.start()

        interrupt_timer = QTimer(app)
        interrupt_timer.setInterval(200)
        interrupt_timer.timeout.connect(lambda: None)
        interrupt_timer.start()

        signal.signal(signal.SIGINT, lambda *_: app.quit())
        signal.signal(signal.SIGTERM, lambda *_: app.quit())

        app.aboutToQuit.connect(checkpoint)

        qt_status = app.exec()
        return qt_status or exit_status

    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
