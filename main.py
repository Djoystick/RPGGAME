from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import config as C
from engine.offline_manager import OfflineManager
from engine.save_manager import SaveError, SaveManager
from engine.state import GameState
from ui.common import APP_STYLESHEET
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setOrganizationName(C.ORGANIZATION_NAME)
    app.setStyleSheet(APP_STYLESHEET)

    try:
        C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось создать каталог данных:\n{exc}",
        )
        return 1

    lock = QLockFile(str(C.LOCK_PATH))
    lock.setStaleLockTime(0)

    if not lock.tryLock(0):
        QMessageBox.warning(
            None,
            C.APP_NAME,
            "Не удалось получить блокировку сохранения.\n"
            "Возможно, игра уже запущена.",
        )
        return 1

    try:
        state = GameState.instance()
        saves = SaveManager()

        try:
            state.load(saves.load())

            # Проверяем новые данные героев до выдачи и записи наград.
            from engine.runes_tree import RunesTree
            RunesTree().squad(state.data)

            if not 3 <= len(state.data.party) <= 4:
                raise ValueError("Для боя необходим отряд из 3–4 героев")

            offline = OfflineManager().claim(state, saves)

        except (SaveError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(
                None,
                "Не удалось загрузить игру",
                f"{exc}\n\nСохранение не сброшено.",
            )
            return 1

        window = MainWindow(state, saves)
        window.show()

        # Никакая панель автоматически не открывается.
        # CombatManager ещё остановлен, пока читается оффлайн-отчёт.
        window.show_offline_report(offline)
        window.start_combat()

        signal_timer = QTimer(app)
        signal_timer.setInterval(200)
        signal_timer.timeout.connect(lambda: None)
        signal_timer.start()

        signal.signal(signal.SIGINT, lambda *_: window.close())
        signal.signal(signal.SIGTERM, lambda *_: window.close())

        app.aboutToQuit.connect(window.final_checkpoint)

        return app.exec()

    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
