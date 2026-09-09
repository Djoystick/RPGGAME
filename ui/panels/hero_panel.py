from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

import config as C
from gfx.sprite_loader import SpriteLoader
from models.hero import PRIMARY_STAT_KEYS, total_exp_for_level
from models.item import EquipmentSlot
from ui.actions import UiActions
from ui.common import (
    ItemGrid, RARITY_COLORS, SLOT_LABELS,
    item_icon, item_tooltip, show_item_card,
)
from ui.detailed_stats_window import DetailedStatsWindow
from ui.gothic_frame import GothicFrame


ATTRIBUTE_LABELS = {
    "strength": "СИЛА · STR",
    "agility": "ЛОВКОСТЬ · AGI",
    "intelligence": "ИНТЕЛЛЕКТ · INT",
    "vitality": "ЖИВУЧЕСТЬ · VIT",
    "luck": "УДАЧА · LUK",
}


class HeroPanel(GothicFrame):
    navigate = Signal(str)

    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("HERO · ГЕРОЙ И ОТРЯД", parent)
        self.actions = actions
        self.active_id = actions.state.data.party[0].hero_id
        self.loader = SpriteLoader()
        self._selector_signature = None
        self._last_frame_time = -1.0
        self._equipment = {}
        self._member = None

        self.details_window = DetailedStatsWindow(self)

        self.selector = QHBoxLayout()
        self.body.addLayout(self.selector)

        top = QHBoxLayout()
        self.portrait = QLabel()
        self.portrait.setFixedSize(72, 80)
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.portrait)

        summary = QVBoxLayout()
        self.name = QLabel()
        self.name.setWordWrap(True)
        summary.addWidget(self.name)

        self.hp = QProgressBar()
        self.mp = QProgressBar()
        self.xp = QProgressBar()
        for bar in (self.hp, self.mp, self.xp):
            bar.setRange(0, 1000)
            summary.addWidget(bar)

        self.mp.setStyleSheet("QProgressBar::chunk { background:#4b70ad; }")
        self.xp.setStyleSheet("QProgressBar::chunk { background:#a58242; }")

        top.addLayout(summary, 1)
        self.body.addLayout(top)

        self.points = QLabel()
        self.body.addWidget(self.points)

        attributes = QGridLayout()
        self.attribute_values = {}
        self.attribute_buttons = {}

        for row, key in enumerate(PRIMARY_STAT_KEYS):
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignRight)

            plus = QPushButton("+")
            plus.setFixedSize(26, 24)
            plus.clicked.connect(
                lambda checked=False, stat=key:
                self.actions.run(
                    lambda: self.actions.allocate_stat(self.active_id, stat)
                )
            )

            attributes.addWidget(QLabel(ATTRIBUTE_LABELS[key]), row, 0)
            attributes.addWidget(value, row, 1)
            attributes.addWidget(plus, row, 2)
            self.attribute_values[key] = value
            self.attribute_buttons[key] = plus

        self.body.addLayout(attributes)

        detailed_button = QPushButton(
            "ПОДРОБНАЯ СТАТИСТИКА / DETAILED STATS"
        )
        detailed_button.setMinimumHeight(32)
        detailed_button.clicked.connect(self._open_details)
        self.body.addWidget(detailed_button)

        self.secondary = QLabel()
        self.secondary.setWordWrap(True)
        self.body.addWidget(self.secondary)

        self.body.addWidget(QLabel("ЭКИПИРОВКА · ПКМ: снять предмет"))
        equipment = QGridLayout()
        equipment.setSpacing(4)
        self.slots = {}

        order = (
            EquipmentSlot.HEAD, EquipmentSlot.AMULET,
            EquipmentSlot.WEAPON, EquipmentSlot.OFFHAND,
            EquipmentSlot.CHEST, EquipmentSlot.GLOVES,
            EquipmentSlot.BELT, EquipmentSlot.BOOTS,
            EquipmentSlot.RING_1, EquipmentSlot.RING_2,
        )

        for index, slot in enumerate(order):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setIconSize(QSize(30, 30))
            button.setMinimumHeight(37)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

            button.clicked.connect(
                lambda checked=False, selected=slot: self._inspect_slot(selected)
            )
            button.customContextMenuRequested.connect(
                lambda point, selected=slot:
                self.actions.run(
                    lambda: self.actions.unequip(self.active_id, selected)
                )
            )
            equipment.addWidget(button, index // 2, index % 2)
            self.slots[slot] = button

        self.body.addLayout(equipment)

        self.skills = QLabel()
        self.skills.setWordWrap(True)
        self.body.addWidget(self.skills)

        self.bag_title = QLabel()
        self.body.addWidget(self.bag_title)

        self.bag = ItemGrid()
        self.bag.setMinimumHeight(140)
        self.bag.itemDoubleClicked.connect(self._equip)
        self.body.addWidget(self.bag, 1)

        controls = QHBoxLayout()
        equip = QPushButton("Надеть выбранное")
        store = QPushButton("В сундук")

        equip.clicked.connect(lambda: self._equip())
        store.clicked.connect(
            lambda: self.actions.run(
                lambda: self.actions.move_items(self.bag.selected_ids(), False)
            )
        )

        controls.addWidget(equip)
        controls.addWidget(store)
        self.body.addLayout(controls)

        dock = QHBoxLayout()
        for caption, page in (
            ("Сундук", "stash"), ("Куб", "cube"), ("Руны", "runes")
        ):
            button = QPushButton(caption)
            button.clicked.connect(
                lambda checked=False, target=page: self.navigate.emit(target)
            )
            dock.addWidget(button)
        self.body.addLayout(dock)

        self.actions.state.state_changed.connect(self.refresh)
        self.actions.combat.frame_changed.connect(self._combat_frame)
        self.refresh()

    def _select(self, hero_id: str) -> None:
        self.active_id = hero_id
        self.refresh()

    def _inspect_slot(self, slot: EquipmentSlot) -> None:
        item = self._equipment.get(slot)
        if item is not None:
            show_item_card(item, self.slots[slot])

    def _equip(self, entry=None) -> None:
        ids = self.bag.selected_ids()
        if entry is not None:
            ids = (entry.data(Qt.ItemDataRole.UserRole),)
        if len(ids) != 1:
            self.actions.error.emit("Выберите один предмет в рюкзаке")
            return
        self.actions.run(lambda: self.actions.equip(self.active_id, ids[0]))

    @staticmethod
    def _set_bar(bar, value: float, maximum: float, title: str) -> None:
        ratio = value / maximum if maximum > 0 else 0.0
        bar.setValue(round(max(0.0, min(1.0, ratio)) * 1000))
        bar.setFormat(f"{title} {value:,.0f}/{maximum:,.0f}")

    def _refresh_selector(self, members) -> None:
        signature = tuple(
            (m.hero.hero_id, m.hero.hero_class, m.hero.level, m.hero.name)
            for m in members
        )

        if signature != self._selector_signature:
            self._selector_signature = signature
            while self.selector.count():
                widget = self.selector.takeAt(0).widget()
                if widget:
                    widget.deleteLater()

            for member in members:
                hero = member.hero
                button = QToolButton()
                button.setProperty("hero_id", hero.hero_id)
                button.setCheckable(True)
                button.setIcon(QIcon(self.loader.frames(
                    hero.hero_class.value, "idle",
                    size=32, dpr=self.devicePixelRatioF(),
                )[0]))
                button.setIconSize(QSize(32, 32))
                button.setToolTip(
                    f"{hero.name} · {hero.definition.name} Lv.{hero.level}"
                )
                button.clicked.connect(
                    lambda checked=False, hero_id=hero.hero_id:
                    self._select(hero_id)
                )
                self.selector.addWidget(button)

        for index in range(self.selector.count()):
            button = self.selector.itemAt(index).widget()
            button.setChecked(button.property("hero_id") == self.active_id)

    def refresh(self, *_args) -> None:
        data = self.actions.state.data
        members = self.actions.runes.squad(data)

        if self.active_id not in {m.hero.hero_id for m in members}:
            self.active_id = members[0].hero.hero_id

        self._refresh_selector(members)
        self._member = next(
            m for m in members if m.hero.hero_id == self.active_id
        )
        hero = self._member.hero
        secondary = self._member.stats
        bonuses = self.actions.runes.effects(data.unlocked_runes).stats
        primary = hero.primary_stats(bonuses)

        self.name.setText(
            f"<b>{hero.definition.name} Lv.{hero.level}</b><br>{hero.name}"
        )
        self.portrait.setPixmap(self.loader.frames(
            hero.hero_class.value, "idle",
            size=70, dpr=self.devicePixelRatioF(),
        )[0])

        start = total_exp_for_level(hero.level)
        end = total_exp_for_level(hero.level + 1)
        self.xp.setValue(round((hero.total_exp - start) / (end - start) * 1000))
        self.xp.setFormat(f"XP · до уровня {hero.exp_to_next_level:,}")

        self.points.setText(
            f"<b>Свободные очки: {hero.free_stat_points}</b>"
            f" · распределено {sum(hero.allocated_stats)}"
        )

        for index, key in enumerate(PRIMARY_STAT_KEYS):
            self.attribute_values[key].setText(f"{getattr(primary, key):,.1f}")
            self.attribute_values[key].setToolTip(
                f"Вложено очков: {hero.allocated_stats[index]}"
            )
            self.attribute_buttons[key].setEnabled(hero.free_stat_points > 0)

        self.secondary.setText(
            f"Урон: {secondary.physical_damage:,.1f} физ. / "
            f"{secondary.magical_damage:,.1f} маг.<br>"
            f"Броня: {secondary.armor:,.1f} · Блок: {secondary.block_chance:.1%}<br>"
            f"Крит: {secondary.crit_chance:.1%} ×{secondary.crit_multiplier:.2f}"
            f" · Вампиризм: {secondary.lifesteal:.1%}"
        )

        self._equipment = {item.slot: item for item in hero.equipment}
        for slot, button in self.slots.items():
            item = self._equipment.get(slot)
            button.setText(SLOT_LABELS[slot])
            button.setEnabled(item is not None)
            if item is None:
                button.setIcon(QIcon())
                button.setToolTip("Пустой слот")
                button.setStyleSheet("")
            else:
                button.setIcon(item_icon(item, 30))
                button.setToolTip(item_tooltip(item))
                button.setStyleSheet(
                    f"QToolButton {{ border-color:{RARITY_COLORS[item.rarity]}; }}"
                )

        self.skills.setText(
            "<b>Навыки:</b> " + " · ".join(skill.name for skill in hero.skills)
        )
        self.bag_title.setText(
            f"РЮКЗАК · {len(data.backpack)}/{C.DEFAULT_BACKPACK_CAPACITY}"
        )
        self.bag.set_items(data.backpack)

        snapshot = next(h for h in data.party if h.hero_id == self.active_id)
        self._set_bar(
            self.hp,
            secondary.max_hp * snapshot.hp / snapshot.max_hp,
            secondary.max_hp, "HP",
        )
        self._set_bar(self.mp, secondary.max_mana, secondary.max_mana, "MP")
        self._combat_frame(self.actions.combat.frame(), force=True)
        self._refresh_details()

    def _open_details(self) -> None:
        self._refresh_details()
        window = self.details_window

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = self.window().geometry().right() + 6
            y = self.window().y()
            x = max(area.left(), min(x, area.right() - window.width() + 1))
            y = max(area.top(), min(y, area.bottom() - window.height() + 1))
            window.move(x, y)

        window.show()
        window.raise_()

    def _refresh_details(self) -> None:
        if self._member is None:
            return

        secondary = self._member.stats
        runtime = next(
            (
                h for h in self.actions.combat.heroes
                if h.hero.hero_id == self.active_id
            ),
            None,
        )

        # Базовые значения берём из актуальной модели, а не из устаревшего
        # runtime-снимка между покупкой предмета и следующим combat tick.
        if runtime is not None:
            now = self.actions.combat.time
            damage_bonus = runtime.buff("damage", now)
            if (
                "berserker" in self.actions.runes.effects(
                    self.actions.state.data.unlocked_runes
                ).keystones
                and runtime.hp < runtime.stats.max_hp * 0.40
            ):
                damage_bonus = (1 + damage_bonus) * 1.8 - 1

            secondary = replace(
                secondary,
                physical_damage=secondary.physical_damage * (1 + damage_bonus),
                magical_damage=secondary.magical_damage * (1 + damage_bonus),
                evasion=min(
                    0.95, secondary.evasion + runtime.buff("evasion", now)
                ),
                damage_absorption=(
                    secondary.damage_absorption
                    + (runtime.shield if runtime.shield_until > now else 0.0)
                ),
            )

        self.details_window.refresh(
            self._member.hero,
            secondary=secondary,
        )

    def _combat_frame(self, frame, force: bool = False) -> None:
        if not force and not self.isVisible() and not self.details_window.isVisible():
            return
        if not force and frame.time - self._last_frame_time < 0.10:
            return

        self._last_frame_time = frame.time
        actor = next(
            (
                actor for actor in frame.actors
                if not actor.enemy and actor.actor_id == self.active_id
            ),
            None,
        )
        if actor:
            self._set_bar(self.hp, actor.hp, actor.max_hp, "HP")
            self._set_bar(self.mp, actor.mana, actor.max_mana, "MP")

        if self.details_window.isVisible():
            self._refresh_details()

    def hideEvent(self, event) -> None:
        self.details_window.hide()
        super().hideEvent(event)
