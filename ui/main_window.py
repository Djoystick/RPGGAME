from __future__ import annotations

import sys

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import config as C
from engine.combat_manager import CombatManager
from engine.save_manager import SaveError, SaveManager
from engine.state import GameState
from ui.actions import UiActions
from ui.battle_stage import BattleStage
from ui.common import APP_STYLESHEET
from ui.gothic_frame import GothicFrame
from ui.panels.cube_panel import CubePanel
from ui.panels.hero_panel import HeroPanel
from ui.panels.runes_panel import RunesPanel
from ui.panels.shop_panel import ShopPanel
from ui.panels.stash_panel import StashPanel


class CompactBattleStage(BattleStage):
    def __init__(self, combat, parent=None) -> None:
        super().__init__(combat, parent)
        self.setFixedSize(520, 108)


class PanelDrawer(GothicFrame):
    closed = Signal()

    def __init__(self, owner: QWidget) -> None:
        super().__init__("ПАНЕЛЬ БЕЗДНЫ", owner, top_level=True)

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # Внутри находится уже оформленная GothicFrame-панель.
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack)

        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.setFixedSize(25, 22)
        self.close_button.setToolTip("Закрыть панель — бой продолжится")
        self.close_button.clicked.connect(self.close)

        self._pages = {}

    def add_panel(
        self,
        page: str,
        panel: QWidget,
        minimum_height: int,
    ) -> None:
        panel.setMinimumHeight(minimum_height)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel)

        self.stack.addWidget(scroll)
        self._pages[page] = scroll

    def select(self, page: str) -> None:
        self.stack.setCurrentWidget(self._pages[page])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.close_button.move(self.width() - 39, 17)
        self.close_button.raise_()

    def closeEvent(self, event) -> None:
        self.hide()
        self.closed.emit()
        event.ignore()


class MainWindow(QWidget):
    WIDTH = 540
    HEIGHT = 168

    PANEL_SIZES = {
        "hero": (430, 720),
        "stash": (420, 550),
        "cube": (390, 640),
        "runes": (790, 650),
        "shop": (440, 720),
    }

    PANEL_TITLES = {
        "hero": "ГЕРОЙ",
        "stash": "СУНДУК",
        "cube": "КУБ СИНТЕЗА",
        "runes": "ДРЕВО РУН",
        "shop": "ЛАВКА БЕЗДНЫ",
    }

    def __init__(
        self,
        state: GameState,
        saves: SaveManager,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(C.APP_NAME)
        self.setStyleSheet(APP_STYLESHEET)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self.state = state
        self.saves = saves
        self.settings = QSettings()
        self.combat = CombatManager(state, saves=saves, parent=self)
        self.actions = UiActions(state, saves, self.combat, self)

        self._closed = False
        self._active_panel = None
        self._drag_offset = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 8)
        layout.setSpacing(2)

        self.header = QWidget()
        self.header.setFixedHeight(20)
        self.header.installEventFilter(self)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title = QLabel("ᚨ DESKTOP ABYSS")
        title.setStyleSheet("color: #ad895f; font-size: 9px;")
        title.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        header_layout.addWidget(title)

        self.gold = QLabel()
        self.gold.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.gold.setStyleSheet(
            "color: #edc579; font-weight: bold; font-size: 11px;"
        )
        self.gold.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        header_layout.addWidget(self.gold, 1)

        self.pin = QToolButton()
        self.pin.setText("◆")
        self.pin.setCheckable(True)
        self.pin.setChecked(True)
        self.pin.setFixedSize(22, 18)
        self.pin.setToolTip("Закрепить поверх других окон")
        self.pin.toggled.connect(self._pin)

        minimize = QToolButton()
        minimize.setText("—")
        minimize.setFixedSize(22, 18)
        minimize.setToolTip("Свернуть игру")
        minimize.clicked.connect(self.showMinimized)

        close = QToolButton()
        close.setText("×")
        close.setFixedSize(22, 18)
        close.setToolTip("Сохранить и закрыть игру")
        close.clicked.connect(self.close)

        header_layout.addWidget(self.pin)
        header_layout.addWidget(minimize)
        header_layout.addWidget(close)
        layout.addWidget(self.header)

        self.battle = CompactBattleStage(self.combat)
        layout.addWidget(self.battle)

        dock = QHBoxLayout()
        dock.setContentsMargins(0, 0, 0, 0)
        dock.setSpacing(4)

        self.dock_buttons = {}

        for caption, page in (
            ("ГЕРОЙ", "hero"),
            ("СУНДУК", "stash"),
            ("КУБ", "cube"),
            ("ЛАВКА", "shop"),
            ("РУНЫ", "runes"),
        ):
            button = QPushButton(caption)
            button.setCheckable(True)
            button.setFixedHeight(24)
            button.clicked.connect(
                lambda checked=False, target=page:
                self.toggle_panel(target)
            )
            dock.addWidget(button, 1)
            self.dock_buttons[page] = button

        layout.addLayout(dock)

        # Один drawer, один QStackedWidget, одна видимая панель.
        self.drawer = PanelDrawer(self)
        self.drawer.closed.connect(self._drawer_closed)

        self.hero_panel = HeroPanel(self.actions)
        self.stash_panel = StashPanel(self.actions)
        self.cube_panel = CubePanel(self.actions)
        self.shop_panel = ShopPanel(self.actions)
        self.runes_panel = RunesPanel(self.actions)

        self.drawer.add_panel("hero", self.hero_panel, 840)
        self.drawer.add_panel("stash", self.stash_panel, 470)
        self.drawer.add_panel("cube", self.cube_panel, 550)
        self.drawer.add_panel("shop", self.shop_panel, 700)
        self.drawer.add_panel("runes", self.runes_panel, 460)

        self.hero_panel.navigate.connect(self.navigate)

        self.actions.error.connect(self._show_error)
        self.actions.notice.connect(self._show_notice)
        self.state.state_changed.connect(self._refresh_header)
        self.combat.party_defeated.connect(self._show_notice)
        self.combat.combat_error.connect(self._show_notice)

        self.autosave = QTimer(self)
        self.autosave.setInterval(C.AUTOSAVE_INTERVAL_MS)
        self.autosave.timeout.connect(self._autosave)
        self.autosave.start()

        self._refresh_header()
        self._restore_position()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        path = QPainterPath()
        path.moveTo(1, 12)
        path.lineTo(9, 3)
        path.lineTo(25, 3)
        path.lineTo(29, 0)
        path.lineTo(w - 29, 0)
        path.lineTo(w - 25, 3)
        path.lineTo(w - 9, 3)
        path.lineTo(w - 1, 12)
        path.lineTo(w - 1, h - 10)
        path.lineTo(w - 11, h - 1)
        path.lineTo(11, h - 1)
        path.lineTo(1, h - 10)
        path.closeSubpath()

        painter.setBrush(QColor(22, 15, 27, 247))
        painter.setPen(QPen(QColor("#a27949"), 1.2))
        painter.drawPath(path)

        painter.setPen(QPen(QColor("#6b3045"), 2))
        painter.drawLine(9, h - 4, w - 9, h - 4)

        for x, direction in ((5, 1), (w - 5, -1)):
            painter.setPen(QPen(QColor("#d0a469"), 1))
            painter.drawLine(x, 15, x, 35)
            painter.drawLine(x, 15, x + direction * 7, 8)
            painter.drawLine(x, h - 14, x + direction * 8, h - 6)

        painter.end()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.header:
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.pos()
                )
                return True

            if (
                event.type() == QEvent.Type.MouseMove
                and self._drag_offset is not None
            ):
                self.move(
                    event.globalPosition().toPoint() - self._drag_offset
                )
                return True

            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                self.settings.setValue("widget/position", self.pos())
                return True

        return super().eventFilter(watched, event)

    def _restore_position(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        saved = self.settings.value("widget/position")

        if isinstance(saved, QPoint):
            candidate = QApplication.screenAt(
                saved + QPoint(self.width() // 2, self.height() // 2)
            )
            if candidate is not None:
                area = candidate.availableGeometry()
                screen = candidate

            x, y = saved.x(), saved.y()
        else:
            x = area.right() - self.width() - 12
            y = area.bottom() - self.height() - 8

        x = max(area.left(), min(x, area.right() - self.width() + 1))
        y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)

    def _position_drawer(self) -> None:
        if self._active_panel is None:
            return

        screen = QApplication.screenAt(self.frameGeometry().center())
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry().adjusted(6, 6, -6, -6)
        preferred_w, preferred_h = self.PANEL_SIZES[self._active_panel]

        width = min(preferred_w, area.width())
        above = self.y() - area.top() - 7

        if above >= 280:
            height = min(preferred_h, above)
            y = self.y() - height - 7
        else:
            height = min(preferred_h, area.height())
            y = area.top()

        self.drawer.resize(width, height)

        x = self.x() + self.width() // 2 - width // 2
        x = max(area.left(), min(x, area.right() - width + 1))
        y = max(area.top(), min(y, area.bottom() - height + 1))

        self.drawer.move(x, y)

    def toggle_panel(self, page: str) -> None:
        if self._active_panel == page and self.drawer.isVisible():
            self.drawer.close()
        else:
            self.navigate(page)

    def navigate(self, page: str) -> None:
        if page not in self.PANEL_SIZES:
            return

        self._active_panel = page
        self.drawer.title = self.PANEL_TITLES[page]
        self.drawer.select(page)
        self._position_drawer()

        for key, button in self.dock_buttons.items():
            button.setChecked(key == page)

        self.drawer.show()
        self.drawer.raise_()
        self.drawer.update()

        if page == "hero":
            self.hero_panel.refresh()
        elif page == "shop":
            self.shop_panel.refresh()
        elif page == "runes":
            QTimer.singleShot(0, self.runes_panel.view.fit_tree)

    def _drawer_closed(self) -> None:
        self._active_panel = None
        for button in self.dock_buttons.values():
            button.setChecked(False)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if hasattr(self, "drawer") and self.drawer.isVisible():
            self._position_drawer()

    def hideEvent(self, event) -> None:
        if hasattr(self, "drawer"):
            self.drawer.hide()
            self._drawer_closed()
        super().hideEvent(event)

    def _pin(self, enabled: bool) -> None:
        position = self.pos()
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint, enabled
        )
        self.drawer.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint, enabled
        )
        self.show()
        self.move(position)

    def _refresh_header(self, *_args) -> None:
        data = self.state.data
        from engine.biomes import biome_for_wave
        location = biome_for_wave(data.current_wave)
        self.gold.setText(f"✦ {data.gold:,}")
        self.header.setToolTip(
            f"Золото: {data.gold:,}\n"
            f"Волна: {data.current_wave:,}\n"
            f"Локация: {location.name}\n"
            "Перетащите заголовок, чтобы переместить виджет"
        )

    def _show_notice(self, message: str) -> None:
        # Сообщения не увеличивают размер базового виджета.
        self.header.setToolTip(message)
        self.gold.setToolTip(message)

    def _show_error(self, message: str) -> None:
        parent = self.drawer if self.drawer.isVisible() else self
        QMessageBox.warning(parent, "Предупреждение Бездны", message)

    def start_combat(self) -> None:
        self.combat.start()

    def save_now(self) -> None:
        self.combat.flush()
        self.saves.checkpoint(self.state)
        self.settings.setValue("widget/position", self.pos())

    def _autosave(self) -> None:
        try:
            self.save_now()
        except (SaveError, ValueError, RuntimeError) as exc:
            self._show_notice(f"Ошибка сохранения: {exc}")
            print(f"Ошибка автосохранения: {exc}", file=sys.stderr)

    def show_offline_report(self, result) -> None:
        if result.elapsed_seconds < 1:
            return

        hours, remainder = divmod(int(result.elapsed_seconds), 3600)
        minutes = remainder // 60

        text = (
            f"Вы отсутствовали: {hours} ч {minutes} мин\n"
            f"Отражено волн: {result.waves_cleared:,}\n\n"
            f"Золото: +{result.total_gold:,}\n"
            f"Опыт отряду: +{result.total_exp:,}\n"
            f"Предметов в сундук: {result.items_stored}\n"
            f"Автопродано: {result.items_sold}"
        )

        if result.clock_rollback:
            text += "\n\nОбнаружен перевод часов назад."

        QMessageBox.information(self, "Приветствие Бездны", text)

    def closeEvent(self, event) -> None:
        if self._closed:
            event.accept()
            return

        try:
            self.save_now()
        except (SaveError, ValueError, RuntimeError) as exc:
            answer = QMessageBox.warning(
                self,
                "Не удалось сохранить игру",
                f"{exc}\n\nВыйти без нового сохранения?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        self._closed = True
        self.autosave.stop()
        self.drawer.hide()
        self.combat.stop()
        event.accept()

    def final_checkpoint(self) -> None:
        if self._closed:
            return

        try:
            self.save_now()
        except (SaveError, ValueError, RuntimeError) as exc:
            print(f"Ошибка финального сохранения: {exc}", file=sys.stderr)

        self._closed = True
        self.autosave.stop()
        self.drawer.hide()
        self.combat.stop()
