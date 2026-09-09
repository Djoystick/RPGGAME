from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from models.item import Rarity
from ui.actions import UiActions
from ui.common import ItemGrid, RARITY_NAMES, item_icon, item_tooltip
from ui.gothic_frame import GothicFrame


class TransmutationCircle(QWidget):
    """Анимированный круг трансмутации: вращение гексаграммы и пульс.

    Таймер перерисовки запускается всегда — виджет лёгкий, а дорогой
    repaint у скрытого окна Qt не выполняет.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(102)
        self._phase = 0.0

        self._pulse = QTimer(self)
        self._pulse.setInterval(33)
        self._pulse.timeout.connect(self._spin)
        self._pulse.start()

    def _spin(self) -> None:
        self._phase += 0.035
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        phase = self._phase

        painter.setBrush(QColor(42, 21, 50, 170))
        painter.setPen(QPen(QColor("#9b4dca"), 1.3))

        for radius in (28, 40, 47):
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Вращающееся пунктирное кольцо между гексаграммой и внешним кругом.
        ring_pen = QPen(QColor("#7c5aa0"), 1.4)
        ring_pen.setDashPattern([1.0, 2.6])
        ring_pen.setDashOffset(-phase * 22)
        painter.setPen(ring_pen)
        painter.drawEllipse(QPointF(cx, cy), 43.5, 43.5)

        # Вращающаяся гексаграмма.
        painter.setPen(QPen(QColor("#c8963e"), 1))
        points = [
            QPointF(
                cx + math.cos(phase + index * math.tau / 6) * 40,
                cy + math.sin(phase + index * math.tau / 6) * 40,
            )
            for index in range(6)
        ]
        for index in range(6):
            painter.drawLine(points[index], points[(index + 2) % 6])

        # Мерцающие руны на орбите (рассеиваются при росте фазы).
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(8):
            angle = phase * 1.4 + index * math.tau / 8
            px = cx + math.cos(angle) * 33
            py = cy + math.sin(angle) * 33
            glow = QColor("#b98bff")
            glow.setAlpha(int(120 + 90 * math.sin(phase * 3 + index)))
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(px, py), 2.1, 2.1)

        painter.setPen(QColor("#d2afd9"))
        painter.drawText(
            QRectF(cx - 25, cy - 14, 50, 28),
            Qt.AlignmentFlag.AlignCenter,
            "ᚨ ᛟ ᚱ",
        )
        painter.end()


class CubePanel(GothicFrame):
    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("CUBE · КУБ БЕЗДНЫ", parent)
        self.actions = actions
        self.selected_ids: tuple[str, ...] = ()

        self.body.addWidget(TransmutationCircle())

        self.summary = QLabel("Поместите 4–12 предметов одного ранга")
        self.summary.setWordWrap(True)
        self.body.addWidget(self.summary)

        layout = QGridLayout()
        self.slots = []

        for index in range(12):
            button = QToolButton()
            button.setText("+")
            button.setMinimumSize(42, 42)
            button.clicked.connect(
                lambda checked=False, slot_index=index:
                self._slot_clicked(slot_index)
            )
            layout.addWidget(button, index // 4, index % 4)
            self.slots.append(button)

        self.body.addLayout(layout)

        self.odds = QLabel()
        self.odds.setWordWrap(True)
        self.odds.setMinimumHeight(80)
        self.body.addWidget(self.odds)

        choose = QPushButton("Выбрать ингредиенты из тайника")
        choose.clicked.connect(self._choose)
        self.body.addWidget(choose)

        row = QHBoxLayout()
        auto = QPushButton("Автозаполнение")
        clear = QPushButton("Очистить")

        auto.clicked.connect(self._autofill)
        clear.clicked.connect(self._clear)

        row.addWidget(auto)
        row.addWidget(clear)
        self.body.addLayout(row)

        self.synthesize = QPushButton("✦ СИНТЕЗ ✦")
        self.synthesize.setMinimumHeight(38)
        self.synthesize.clicked.connect(self._synthesize)
        self.body.addWidget(self.synthesize)

        explanation = QLabel(
            "Ингредиенты остаются в тайнике до подтверждения.\n"
            "Синтез необратимо расходует выбранные предметы."
        )
        explanation.setWordWrap(True)
        self.body.addWidget(explanation)
        self.body.addStretch()

        self.actions.state.state_changed.connect(self.refresh)
        self.refresh()

    def _slot_clicked(self, index: int) -> None:
        if index < len(self.selected_ids):
            self.selected_ids = tuple(
                item_id for position, item_id in enumerate(self.selected_ids)
                if position != index
            )
            self.refresh()
        else:
            self._choose()

    def _choose(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Ингредиенты Куба")
        dialog.resize(540, 430)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "Выберите 4–12 предметов. Ctrl/Shift — множественный выбор."
        ))

        grid = ItemGrid()
        grid.set_items(self.actions.state.data.stash)

        selected = set(self.selected_ids)
        for index in range(grid.count()):
            entry = grid.item(index)
            entry.setSelected(
                entry.data(Qt.ItemDataRole.UserRole) in selected
            )

        layout.addWidget(grid, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            ids = grid.selected_ids()
            if len(ids) > 12:
                self.actions.error.emit("В Куб помещается не более 12 предметов")
                return
            self.selected_ids = ids
            self.refresh()

    def _autofill(self) -> None:
        self.selected_ids = self.actions.cube.autofill(
            self.actions.state.data.stash
        )
        self.refresh()
        if not self.selected_ids:
            self.actions.notice.emit("Подходящая группа ингредиентов не найдена")

    def _clear(self) -> None:
        self.selected_ids = ()
        self.refresh()

    def _synthesize(self) -> None:
        ids = self.selected_ids
        if self.actions.run(lambda: self.actions.synthesize(ids)):
            self.selected_ids = ()
            self.refresh()

    def refresh(self, *_args) -> None:
        from PySide6.QtGui import QIcon

        data = self.actions.state.data
        by_id = {item.item_id: item for item in data.stash}

        self.selected_ids = tuple(
            item_id for item_id in self.selected_ids if item_id in by_id
        )
        ingredients = tuple(by_id[item_id] for item_id in self.selected_ids)

        for index, button in enumerate(self.slots):
            if index < len(ingredients):
                item = ingredients[index]
                button.setIcon(item_icon(item))
                button.setText("")
                button.setToolTip(item_tooltip(item) + "<br>Нажать: убрать из Куба")
            else:
                button.setIcon(QIcon())
                button.setText("+")
                button.setToolTip("Выбрать ингредиенты")

        self.summary.setText(f"Ингредиенты: {len(ingredients)}/12")

        try:
            bonus = self.actions.runes.effects(
                data.unlocked_runes
            ).synthesis_bonus
            odds = self.actions.cube.probabilities(ingredients, bonus)
        except ValueError as exc:
            self.odds.setText(str(exc))
            self.synthesize.setEnabled(False)
            return

        lines = [
            f"{RARITY_NAMES[rarity]}: {chance:.1%}"
            for rarity, chance in odds.items()
        ]

        for rarity in (Rarity.LEGENDARY, Rarity.IMMORTAL):
            if rarity not in odds:
                lines.append(f"{RARITY_NAMES[rarity]}: 0.0%")

        self.odds.setText("\n".join(lines))
        self.synthesize.setEnabled(True)
