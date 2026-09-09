from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabBar,
)

from ui.actions import UiActions
from ui.common import ItemGrid
from ui.gothic_frame import GothicFrame


PAGE_SIZE = 40


class StashPanel(GothicFrame):
    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("STASH · СУНДУК БЕЗДНЫ", parent)
        self.actions = actions

        self.counter = QLabel()
        self.body.addWidget(self.counter)

        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._show_page)
        self.body.addWidget(self.tabs)

        self.grid = ItemGrid()
        self.grid.setMinimumHeight(250)
        self.grid.itemDoubleClicked.connect(self._take_one)
        self.body.addWidget(self.grid, 1)

        hint = QLabel(
            "Наведение / клик — карточка предмета.\n"
            "Двойной клик — забрать в рюкзак. Ctrl/Shift — выбор."
        )
        hint.setWordWrap(True)
        self.body.addWidget(hint)

        selected = QPushButton("Забрать выбранное")
        selected.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.move_items(
                    self.grid.selected_ids(), True
                )
            )
        )
        self.body.addWidget(selected)

        row = QHBoxLayout()
        take_all = QPushButton("Забрать всё")
        store_all = QPushButton("Сохранить всё")

        take_all.setToolTip(
            "Перенести предметы из всех вкладок в рюкзак, пока есть место"
        )
        store_all.setToolTip(
            "Перенести рюкзак в сундук, пока есть место"
        )

        take_all.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.move_all(True)
            )
        )
        store_all.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.move_all(False)
            )
        )

        row.addWidget(take_all)
        row.addWidget(store_all)
        self.body.addLayout(row)

        sort = QPushButton("Сортировка · редкость / уровень")
        sort.clicked.connect(
            lambda: self.actions.run(self.actions.sort_stash)
        )
        self.body.addWidget(sort)

        self.actions.state.state_changed.connect(self.refresh)
        self.refresh()

    def _take_one(self, entry) -> None:
        item_id = entry.data(Qt.ItemDataRole.UserRole)
        self.actions.run(
            lambda: self.actions.move_items((item_id,), True)
        )

    def refresh(self, *_args) -> None:
        data = self.actions.state.data
        self.counter.setText(
            f"Сундук: {len(data.stash)}/{data.stash_capacity}"
            f" · Рюкзак: {len(data.backpack)}"
        )

        pages = max(1, math.ceil(data.stash_capacity / PAGE_SIZE))
        current = max(0, self.tabs.currentIndex())

        self.tabs.blockSignals(True)
        while self.tabs.count() > pages:
            self.tabs.removeTab(self.tabs.count() - 1)
        while self.tabs.count() < pages:
            self.tabs.addTab(str(self.tabs.count() + 1))
        self.tabs.setCurrentIndex(min(current, pages - 1))
        self.tabs.blockSignals(False)

        self._show_page(self.tabs.currentIndex())

    def _show_page(self, index: int) -> None:
        index = max(0, index)
        start = index * PAGE_SIZE
        self.grid.set_items(
            self.actions.state.data.stash[start:start + PAGE_SIZE]
        )
