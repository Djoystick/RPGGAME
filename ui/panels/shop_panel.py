from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from engine.shop import merchant_price
from ui.actions import UiActions
from ui.common import ItemGrid, item_tooltip
from ui.gothic_frame import GothicFrame


class ShopPanel(GothicFrame):
    """ЛАВКА БЕЗДНЫ — продажа лута и покупка снаряжения торговца."""

    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("SHOP · ЛАВКА БЕЗДНЫ", parent)
        self.actions = actions
        self._stock: tuple = ()
        self._stock_by_id: dict = {}
        self._container = "backpack"

        # Заголовок-визитка торговца.
        self.greeting = QLabel()
        self.greeting.setWordWrap(True)
        self.greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(self.greeting)

        self.wallet = QLabel()
        self.wallet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wallet.setStyleSheet("color:#edc579; font-weight:bold; font-size:12px;")
        self.body.addWidget(self.wallet)

        # ---- Продажа вашего лута -----------------------------------------
        self.body.addWidget(QLabel("⚔ ПРОДАЖА ЛУТА"))
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Показывать:"))
        self.source = QComboBox()
        self.source.addItem("Рюкзак", "backpack")
        self.source.addItem("Тайник", "stash")
        self.source.currentIndexChanged.connect(self._source_changed)
        source_row.addWidget(self.source)
        source_row.addStretch(1)
        self.body.addLayout(source_row)

        self.sell_grid = ItemGrid()
        self.sell_grid.setMinimumHeight(150)
        self.body.addWidget(self.sell_grid, 1)

        sell_row = QHBoxLayout()
        sell_selected = QPushButton("Продать выбранное")
        sell_selected.clicked.connect(self._sell_selected)
        sell_junk = QPushButton("Распродать хлам")
        sell_junk.setToolTip(
            "Мгновенно продать все обычные и необычные предметы"
        )
        sell_junk.clicked.connect(
            lambda: self.actions.run(self.actions.sell_junk)
        )
        sell_row.addWidget(sell_selected)
        sell_row.addWidget(sell_junk)
        self.body.addLayout(sell_row)

        # ---- Покупка у торговца ------------------------------------------
        self.body.addWidget(QLabel("✦ ТОВАРЫ ТОРГОВЦА"))
        self.stock_grid = ItemGrid()
        self.stock_grid.setMinimumHeight(160)
        self.stock_grid.itemDoubleClicked.connect(self._buy_double)
        self.stock_grid.itemSelectionChanged.connect(self._stock_selection)
        self.body.addWidget(self.stock_grid, 1)

        self.stock_detail = QLabel("Двойной клик по товару — купить.")
        self.stock_detail.setWordWrap(True)
        self.body.addWidget(self.stock_detail)

        buy_row = QHBoxLayout()
        self.buy_button = QPushButton("Купить выбранный товар")
        self.buy_button.clicked.connect(self._buy_selected)
        reroll = QPushButton("Обновить прилавок")
        reroll.setToolTip("Торговец достаёт новую партию товаров")
        reroll.clicked.connect(self._reroll)
        buy_row.addWidget(self.buy_button)
        buy_row.addWidget(reroll)
        self.body.addLayout(buy_row)

        self.actions.state.state_changed.connect(self.refresh)
        self._reroll()
        self.refresh()

    # ---- Interaction helpers -------------------------------------------

    def _source_changed(self) -> None:
        self._container = self.source.currentData()
        self.refresh()

    def _sell_selected(self) -> None:
        ids = self.sell_grid.selected_ids()
        self.actions.run(lambda: self.actions.sell_items(ids))

    def _stock_selection(self) -> None:
        self._update_buy_button()

    def _update_buy_button(self) -> None:
        ids = self.stock_grid.selected_ids()
        item = self._stock_by_id.get(ids[0]) if len(ids) == 1 else None
        if item is None:
            self.buy_button.setEnabled(False)
            self.buy_button.setText("Купить выбранный товар")
            self.stock_detail.setText("Двойной клик по товару — купить.")
            return

        price = merchant_price(item)
        affordable = self.actions.state.data.gold >= price
        self.buy_button.setEnabled(affordable)
        self.buy_button.setText(
            f"Купить {item.display_name} · {price:,} ✦"
        )
        self.stock_detail.setText(
            f"Цена: <b>{price:,}</b> золота · {item.rarity.value} · "
            f"Lv.{item.level}<br>{item_tooltip(item)}"
        )

    def _buy_item(self, item) -> None:
        if self.actions.run(lambda: self.actions.buy_offer(item)):
            self.refresh()

    def _buy_selected(self) -> None:
        ids = self.stock_grid.selected_ids()
        if len(ids) != 1:
            self.actions.error.emit("Выберите один товар для покупки")
            return
        self._buy_item(self._stock_by_id[ids[0]])

    def _buy_double(self, entry) -> None:
        item_id = entry.data(Qt.ItemDataRole.UserRole)
        item = self._stock_by_id.get(item_id)
        if item is not None:
            self._buy_item(item)

    def _reroll(self) -> None:
        self._stock = self.actions.roll_stock(count=6)
        self._stock_by_id = {item.item_id: item for item in self._stock}
        self.refresh()

    # ---- Reactive refresh ----------------------------------------------

    def refresh(self, *_args) -> None:
        data = self.actions.state.data

        self.wallet.setText(f"Казна отряда: ✦ {data.gold:,}")

        self.greeting.setText(
            "Торговец Бездны выкупает любой трофей и ссужает снаряжение.\n"
            f"Наценка сбыта от рун: +{data.farm.sale_bonus:.0%}"
        )

        source_items = (
            data.backpack if self._container == "backpack" else data.stash
        )
        self.sell_grid.set_items(source_items)
        self.source.setCurrentIndex(self.source.findData(self._container))

        # Полка лавки: убираем товары, которые игрок уже приобрёл.
        container_ids = {item.item_id for item in (*data.stash, *data.backpack)}
        self._stock = tuple(
            item for item in self._stock if item.item_id not in container_ids
        )
        self._stock_by_id = {item.item_id: item for item in self._stock}
        self.stock_grid.set_items(self._stock)

        # После снятия предметов/золота пересчитываем кнопку покупки.
        self._update_buy_button()
