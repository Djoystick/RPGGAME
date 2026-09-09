from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTabBar,
)

from models.item import Rarity, RARITY_ORDER
from ui.actions import UiActions
from ui.common import ItemGrid, show_item_card
from ui.gothic_frame import GothicFrame


PAGE_SIZE = 40

_RARITY_FILTER_LABELS = {
    None: "Все редкости",
    Rarity.COMMON: "Обычные",
    Rarity.UNCOMMON: "Необычные",
    Rarity.RARE: "Редкие",
    Rarity.LEGENDARY: "Легендарные",
    Rarity.IMMORTAL: "Бессмертные",
    Rarity.MYTHIC: "Мифические",
}


class StashPanel(GothicFrame):
    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("STASH · СУНДУК БЕЗДНЫ", parent)
        self.actions = actions
        self._rarity_filter = None

        self.counter = QLabel()
        self.body.addWidget(self.counter)

        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._show_page)
        self.body.addWidget(self.tabs)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Фильтр редкости:"))
        self.filter = QComboBox()
        for rarity in (None, *RARITY_ORDER):
            self.filter.addItem(_RARITY_FILTER_LABELS[rarity], rarity)
        self.filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.filter, 1)

        self.worth = QLabel()
        self.worth.setAlignment(Qt.AlignmentFlag.AlignRight)
        filter_row.addWidget(self.worth)
        self.body.addLayout(filter_row)

        self.grid = ItemGrid()
        self.grid.setMinimumHeight(250)
        self.grid.itemDoubleClicked.connect(self._take_one)
        self.grid.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.body.addWidget(self.grid, 1)

        hint = QLabel(
            "ЛКМ/наведение — карточка предмета · ПКМ — действия\n"
            "Двойной клик — забрать в рюкзак. Ctrl/Shift — выбор."
        )
        hint.setWordWrap(True)
        self.body.addWidget(hint)

        row = QHBoxLayout()
        take_selected = QPushButton("Забрать выбранное")
        sell_selected = QPushButton("Продать выбранное")
        take_selected.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.move_items(
                    self.grid.selected_ids(), True
                )
            )
        )
        sell_selected.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.sell_items(self.grid.selected_ids())
            )
        )
        row.addWidget(take_selected)
        row.addWidget(sell_selected)
        self.body.addLayout(row)

        bulk = QHBoxLayout()
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

        bulk.addWidget(take_all)
        bulk.addWidget(store_all)
        self.body.addLayout(bulk)

        sort = QPushButton("Сортировка · редкость / уровень")
        sort.clicked.connect(
            lambda: self.actions.run(self.actions.sort_stash)
        )
        self.body.addWidget(sort)

        self.actions.state.state_changed.connect(self.refresh)
        self.refresh()

    # ---- Вспомогательные геттеры ---------------------------------------

    def _filtered_stash(self) -> tuple:
        data = self.actions.state.data
        if self._rarity_filter is None:
            return data.stash
        return tuple(
            item for item in data.stash
            if item.rarity == self._rarity_filter
        )

    def _page_items(self) -> tuple:
        index = max(0, self.tabs.currentIndex())
        items = self._filtered_stash()
        start = index * PAGE_SIZE
        return items[start:start + PAGE_SIZE]

    # ---- Действия -------------------------------------------------------

    def _take_one(self, entry) -> None:
        item_id = entry.data(Qt.ItemDataRole.UserRole)
        self.actions.run(
            lambda: self.actions.move_items((item_id,), True)
        )

    def _sell_one(self, entry) -> None:
        item_id = entry.data(Qt.ItemDataRole.UserRole)
        self.actions.run(
            lambda: self.actions.sell_items((item_id,))
        )

    def _context_menu(self, pos) -> None:
        entry = self.grid.itemAt(pos)
        if entry is None:
            return
        item_id = entry.data(Qt.ItemDataRole.UserRole)
        item = self.grid.item_for_id(item_id)
        name = item.display_name if item is not None else "Предмет"

        menu = QMenu(self)
        take = QAction(f"Забрать в рюкзак — {name}", menu)
        sell = QAction(f"Продать — {name}", menu)
        card = QAction("Показать карточку", menu)

        take.triggered.connect(lambda: self._take_one(entry))
        sell.triggered.connect(lambda: self._sell_one(entry))
        card.triggered.connect(lambda: show_item_card(item, self.grid))

        menu.addAction(take)
        menu.addAction(sell)
        menu.addSeparator()
        menu.addAction(card)
        menu.exec(self.grid.mapToGlobal(pos))

    # ---- Отрисовка ------------------------------------------------------

    def refresh(self, *_args) -> None:
        data = self.actions.state.data

        self._rarity_filter = self.filter.currentData()
        filtered = self._filtered_stash()

        # После смены фильтра — актуальное число страниц.
        pages = max(1, math.ceil(len(filtered) / PAGE_SIZE))
        current = max(0, self.tabs.currentIndex())

        self.counter.setText(
            f"Сундук: {len(data.stash)}/{data.stash_capacity}"
            f" · Показано: {len(filtered)}"
            f" · Рюкзак: {len(data.backpack)}"
        )
        self.worth.setText(
            f"Ценность: {sum(i.sell_value for i in filtered):,} ✦"
        )

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
        self.grid.set_items(self._page_items())
