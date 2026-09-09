from __future__ import annotations

import hashlib
from dataclasses import fields
from html import escape

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import (
    QColor, QCursor, QIcon, QImage, QPainter, QPen, QPixmap, QPolygon,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QListWidget, QListWidgetItem, QToolTip,
)

from models.item import (
    ACT_LORE, ACT_NAMES, EquipmentSlot, Item,
    PREFIX_BY_ID, Rarity, SUFFIX_BY_ID,
)
from models.stats import StatBlock


RARITY_COLORS = {
    Rarity.COMMON: "#bdc1cf",
    Rarity.UNCOMMON: "#78d99b",
    Rarity.RARE: "#71b8ff",
    Rarity.LEGENDARY: "#ffd17b",
    Rarity.IMMORTAL: "#d29aff",
    Rarity.MYTHIC: "#ff7faf",
}

RARITY_NAMES = {
    Rarity.COMMON: "Обычный",
    Rarity.UNCOMMON: "Необычный",
    Rarity.RARE: "Редкий",
    Rarity.LEGENDARY: "Легендарный",
    Rarity.IMMORTAL: "Бессмертный",
    Rarity.MYTHIC: "Мифический",
}

SLOT_LABELS = {
    EquipmentSlot.WEAPON: "Оружие",
    EquipmentSlot.OFFHAND: "Левая рука",
    EquipmentSlot.HEAD: "Шлем",
    EquipmentSlot.CHEST: "Нагрудник",
    EquipmentSlot.GLOVES: "Перчатки",
    EquipmentSlot.BOOTS: "Сапоги",
    EquipmentSlot.BELT: "Пояс",
    EquipmentSlot.AMULET: "Амулет",
    EquipmentSlot.RING_1: "Перстень I",
    EquipmentSlot.RING_2: "Перстень II",
}

STAT_NAMES = {
    "strength": "Сила",
    "agility": "Ловкость",
    "intelligence": "Интеллект",
    "vitality": "Живучесть",
    "luck": "Удача",
    "damage": "Урон",
    "armor": "Броня",
    "max_hp": "Здоровье",
    "mana": "Мана",
    "physical_bonus": "Физический урон",
    "magical_bonus": "Магический урон",
    "hp_bonus": "Максимальное HP",
    "crit_chance": "Шанс крита",
    "crit_damage": "Сила крита",
    "evasion": "Уклонение",
    "attack_speed": "Скорость атаки",
    "basic_requirement_reduction": "Снижение затрат атаки",
    "cooldown_reduction": "Сокращение перезарядки",
    "skill_range": "Дальность навыков",
    "basic_attack_range": "Дальность атаки",
    "cast_speed": "Скорость сотворения",
    "fire_bonus": "Огненный урон",
    "cold_bonus": "Урон холодом",
    "lightning_bonus": "Урон молнией",
    "chaos_bonus": "Урон хаосом",
    "multistrike": "Повторные атаки",
    "projectile_count": "Дополнительные снаряды",
    "melee_bonus": "Урон ближнего боя",
    "projectile_bonus": "Урон снарядов",
    "aoe_damage": "Урон по площади",
    "projectile_speed": "Скорость снарядов",
    "summon_damage": "Урон призыва",
    "fire_res": "Сопротивление огню",
    "cold_res": "Сопротивление холоду",
    "lightning_res": "Сопротивление молнии",
    "chaos_res": "Сопротивление хаосу",
    "block_chance": "Шанс блока",
    "elemental_dodge": "Стихийное уклонение",
    "elemental_block": "Стихийный блок",
    "hp_regen": "HP в секунду",
    "damage_absorption": "Поглощение урона",
    "movement_speed": "Скорость передвижения",
    "aoe_enhancement": "Радиус области",
    "skill_duration": "Длительность навыков",
    "hp_per_hit": "HP за попадание",
    "hp_per_kill": "HP за убийство",
    "life_leech": "Вампиризм",
    "skill_heal": "Сила лечения",
    "all_skill_level": "Уровни навыков",
    "exp_gain": "Получаемый опыт",
    "additional_exp": "Дополнительный опыт",
}

PERCENT_STATS = {
    "physical_bonus", "magical_bonus", "hp_bonus",
    "crit_chance", "crit_damage", "evasion",
    "cooldown_reduction", "skill_range",
    "fire_bonus", "cold_bonus", "lightning_bonus", "chaos_bonus",
    "melee_bonus", "projectile_bonus", "aoe_damage",
    "projectile_speed", "summon_damage",
    "fire_res", "cold_res", "lightning_res", "chaos_res",
    "block_chance", "elemental_dodge", "elemental_block",
    "aoe_enhancement", "skill_duration", "life_leech",
    "skill_heal", "exp_gain",
}


def stats_text(stats: StatBlock) -> str:
    result = []
    for definition in fields(stats):
        value = getattr(stats, definition.name)
        if value == 0:
            continue

        formatted = (
            f"{value * 100:+.1f}%"
            if definition.name in PERCENT_STATS
            else f"{value:+.2f}".rstrip("0").rstrip(".")
        )
        result.append(
            f"{STAT_NAMES.get(definition.name, definition.name)}: {formatted}"
        )

    return "\n".join(result) or "Без дополнительных характеристик"


def item_tooltip(item: Item) -> str:
    color = RARITY_COLORS[item.rarity]
    lore = item.lore or ACT_LORE["crypts"][0]
    origin = ACT_NAMES.get(item.origin_act, "Неизвестное происхождение")

    affixes = []
    if item.prefix_id:
        affixes.append("Префикс: " + PREFIX_BY_ID[item.prefix_id].name)
    if item.suffix_id:
        affixes.append("Суффикс: " + SUFFIX_BY_ID[item.suffix_id].name)

    affix_html = "<br>".join(escape(line) for line in affixes)
    stats_html = escape(stats_text(item.stats)).replace("\n", "<br>")

    return f"""
    <table width="300" cellpadding="5" cellspacing="0">
      <tr><td align="center">
        <span style="color:#a98654;">◆ ─── ᚨ ᛟ ᚱ ─── ◆</span>
      </td></tr>
      <tr><td>
        <b style="color:{color};font-size:15px;">
          {escape(item.display_name)}
        </b><br>
        <span style="color:#b8a8bf;">
          {RARITY_NAMES[item.rarity]} · {SLOT_LABELS[item.slot]}
          · Ур. {item.level}
        </span><br>
        <span style="color:#988899;">{escape(origin)}</span>
      </td></tr>
      <tr><td><hr>
        <span style="color:#c6aad8;">{affix_html}</span><br>
        <span style="color:#e9e0d2;">{stats_html}</span>
      </td></tr>
      <tr><td>
        <i style="color:#ac9caf;">«{escape(lore)}»</i>
      </td></tr>
      <tr><td><hr>
        <span style="color:#f0c77e;">✦ Продажа: {item.sell_value:,} золота</span>
      </td></tr>
    </table>
    """


def show_item_card(item: Item, widget=None) -> None:
    QToolTip.showText(
        QCursor.pos(), item_tooltip(item),
        widget, msecShowTime=12000,
    )


_ICON_CACHE: dict[tuple, QIcon] = {}


def item_icon(item: Item, size: int = 40) -> QIcon:
    digest = hashlib.blake2b(
        item.item_id.encode("utf-8"), digest_size=8
    ).digest()
    visual = item.visual_key
    key = (visual, item.rarity, digest[:3], size)

    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    def rect(x, y, w, h, color):
        p.fillRect(int(x), int(y), int(w), int(h), QColor(color))

    def poly(points, color):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygon([QPoint(x, y) for x, y in points]))

    def line(x1, y1, x2, y2, color, width=1):
        p.setPen(QPen(QColor(color), width))
        p.drawLine(x1, y1, x2, y2)

    metal, shine = (
        ("#76869e", "#d9e6ee"),
        ("#8e8192", "#e5cce9"),
        ("#9b876e", "#eed5ae"),
    )[digest[0] % 3]
    gem = ("#71c9ff", "#ce88ff", "#ff7e9d", "#86efb2")[digest[1] % 4]
    gold = "#d5ab67"
    dark = "#211b30"
    wood = "#8f624c"
    rarity = QColor(RARITY_COLORS[item.rarity])

    rect(1, 1, 30, 30, "#100c17")
    for inset, alpha in ((2, 70), (4, 35), (7, 22)):
        color = QColor(rarity)
        color.setAlpha(alpha)
        rect(inset, inset, 32 - inset * 2, 32 - inset * 2, color)

    for x, y in ((2, 2), (27, 2), (2, 27), (27, 27)):
        rect(x, y, 3, 1, rarity)
        rect(x, y, 1, 3, rarity)

    if visual in ("sword", "greatsword", "sabre", "dagger", "dual"):
        offsets = (-3, 5) if visual == "dual" else (0,)
        for offset in offsets:
            tip_y = 9 if visual == "dagger" else 4
            width = 5 if visual == "greatsword" else 3
            if visual == "sabre":
                poly([(10, 23), (19, 14), (25, 4), (25, 13), (14, 26)], metal)
                line(12, 22, 24, 7, shine)
            else:
                poly([
                    (9 + offset, 23), (23 + offset, tip_y),
                    (25 + offset, tip_y),
                    (12 + width + offset, 25),
                ], metal)
                line(11 + offset, 22, 24 + offset, tip_y + 1, shine)
            line(7 + offset, 20, 16 + offset, 27, gold, 2)
            line(9 + offset, 25, 5 + offset, 29, wood, 3)

    elif visual in ("staff", "wand", "scythe"):
        line(9, 29, 22, 5, wood, 3)
        line(10, 27, 22, 6, gold)
        if visual == "scythe":
            poly([(18, 6), (28, 5), (30, 10), (25, 8),
                  (17, 9), (7, 16), (10, 10)], shine)
        else:
            radius = 5 if visual == "staff" else 3
            poly([(22, 3), (22 + radius, 8), (22, 13),
                  (22 - radius, 8)], metal)
            poly([(22, 5), (25, 8), (22, 11), (19, 8)], gem)
            rect(21, 6, 2, 2, "#fff1f6")

    elif visual in ("bow", "crossbow"):
        line(10, 5, 21, 10, wood, 3)
        line(21, 10, 24, 17, wood, 3)
        line(24, 17, 20, 24, wood, 3)
        line(20, 24, 10, 28, wood, 3)
        line(10, 5, 10, 28, "#d0c4ac")
        line(5, 17, 29, 17, shine)
        poly([(29, 17), (25, 14), (25, 20)], metal)
        if visual == "crossbow":
            line(8, 25, 24, 9, wood, 4)
            rect(10, 20, 4, 3, gold)

    elif visual in ("hammer", "mace", "flail"):
        line(8, 29, 21, 9, wood, 3)
        if visual == "hammer":
            poly([(12, 7), (19, 3), (28, 9), (23, 17)], metal)
            line(14, 7, 22, 13, shine, 2)
        elif visual == "mace":
            poly([(17, 5), (23, 4), (28, 9), (24, 16), (17, 14)], metal)
            rect(20, 6, 3, 7, shine)
        else:
            line(20, 10, 26, 14, gold)
            line(26, 14, 23, 20, gold)
            poly([(22, 17), (27, 18), (29, 23), (24, 27), (19, 23)], metal)
            rect(23, 20, 2, 2, shine)

    elif visual in ("shield", "tower", "buckler"):
        if visual == "buckler":
            poly([(10, 7), (22, 7), (27, 13), (27, 21),
                  (21, 27), (11, 27), (5, 20), (5, 13)], metal)
        else:
            bottom = 29
            poly([(6, 7), (16, 3), (26, 7), (24, 23),
                  (16, bottom), (8, 23)], metal)
            poly([(8, 8), (16, 5), (23, 8), (21, 21),
                  (16, 26), (10, 21)], "#43547b")
        line(16, 8, 16, 24, gold, 2)
        line(10, 14, 22, 14, gold, 2)
        rect(14, 12, 4, 4, gem)

    elif visual == "book":
        rect(6, 6, 20, 23, dark)
        rect(8, 7, 17, 20, "#633e69")
        rect(6, 7, 3, 21, gold)
        rect(24, 8, 2, 19, "#d8cbaa")
        rect(11, 10, 11, 1, gold)
        poly([(16, 13), (21, 18), (16, 23), (11, 18)], gem)

    elif visual == "skull":
        poly([(10, 5), (22, 5), (27, 11), (25, 21),
              (21, 23), (21, 28), (11, 28), (11, 23),
              (6, 20), (5, 11)], "#c8c2a7")
        rect(9, 12, 6, 6, dark)
        rect(19, 12, 6, 6, dark)
        rect(11, 14, 2, 2, gem)
        rect(21, 14, 2, 2, gem)
        poly([(17, 17), (14, 22), (19, 22)], dark)
        for x in (12, 15, 18):
            rect(x, 25, 1, 3, dark)

    elif visual == "orb":
        poly([(11, 5), (21, 5), (27, 11), (27, 21),
              (21, 27), (11, 27), (5, 21), (5, 11)], metal)
        poly([(12, 8), (20, 8), (24, 12), (24, 20),
              (20, 24), (12, 24), (8, 20), (8, 12)], gem)
        rect(10, 10, 6, 3, "#eef4ff")
        rect(9, 13, 2, 5, "#cce7ff")
        rect(12, 28, 10, 2, gold)

    elif visual in ("quiver", "arrows"):
        for x in (10, 15, 20):
            line(x, 5, x - 3, 25, shine)
            poly([(x, 3), (x - 3, 8), (x + 2, 7)], "#a9bfd8")
        if visual == "quiver":
            poly([(7, 13), (22, 16), (19, 29), (5, 26)], wood)
            line(7, 14, 21, 17, gold, 2)
            line(8, 18, 17, 27, "#bc9067")

    elif visual in ("plate", "leather", "robe"):
        color = {
            "plate": metal,
            "leather": "#826044",
            "robe": "#70518a",
        }[visual]
        poly([(7, 7), (12, 5), (16, 9), (21, 5),
              (26, 8), (29, 16), (23, 18),
              (25 if visual == "robe" else 22, 29),
              (7 if visual == "robe" else 10, 29),
              (9, 18), (3, 16)], dark)
        poly([(8, 9), (12, 7), (16, 11), (21, 7),
              (24, 10), (26, 15), (21, 16),
              (22, 27), (10, 27), (11, 16), (6, 15)], color)
        rect(12, 13, 3, 11, shine if visual == "plate" else gold)
        rect(10, 24, 12, 2, gold)
        rect(16, 14, 3, 3, gem)

    elif visual in ("helm", "hood", "crown"):
        if visual == "hood":
            poly([(6, 25), (8, 10), (16, 3), (24, 10), (27, 25)], "#493758")
            rect(11, 12, 11, 9, dark)
            rect(17, 14, 3, 1, gem)
        elif visual == "crown":
            poly([(6, 24), (4, 8), (11, 14), (16, 4),
                  (21, 14), (28, 8), (25, 24)], gold)
            rect(8, 23, 16, 4, metal)
            rect(14, 15, 4, 5, gem)
        else:
            poly([(10, 10), (5, 5), (5, 12), (10, 17)], gold)
            poly([(22, 10), (27, 5), (27, 12), (22, 17)], gold)
            rect(10, 8, 13, 18, metal)
            rect(12, 9, 4, 13, shine)
            rect(10, 16, 13, 3, dark)
            rect(16, 14, 2, 13, gold)

    elif visual == "gloves":
        for x, y in ((5, 9), (18, 5)):
            rect(x, y + 7, 9, 13, metal)
            for finger in range(3):
                rect(x + finger * 3, y + finger % 2, 2, 10, shine)
            rect(x, y + 17, 9, 3, gold)

    elif visual == "boots":
        for x, y in ((5, 8), (18, 5)):
            rect(x, y, 8, 18, wood)
            rect(x, y + 15, 11, 6, metal)
            rect(x, y, 8, 3, gold)
            rect(x + 1, y + 4, 2, 9, shine)

    elif visual == "belt":
        rect(4, 11, 25, 11, wood)
        rect(4, 11, 25, 2, "#bb9667")
        rect(12, 9, 11, 15, gold)
        rect(14, 11, 7, 11, dark)
        rect(14, 16, 9, 2, shine)

    elif visual == "amulet":
        line(7, 4, 16, 15, gold)
        line(25, 4, 16, 15, gold)
        poly([(16, 12), (25, 20), (16, 29), (7, 20)], gold)
        poly([(16, 15), (21, 20), (16, 26), (11, 20)], gem)
        rect(15, 16, 2, 3, "#fff2ff")

    else:
        for x, y, w, h in (
            (10, 9, 12, 3), (7, 12, 3, 11),
            (22, 12, 3, 11), (10, 23, 12, 3),
        ):
            rect(x, y, w, h, gold)

        if visual == "signet":
            rect(10, 5, 12, 11, metal)
            rect(15, 7, 2, 7, gem)
            rect(12, 9, 7, 2, gem)
        else:
            poly([(16, 4), (23, 10), (16, 17), (9, 10)], metal)
            poly([(16, 6), (20, 10), (16, 14), (12, 10)], gem)
        rect(11, 24, 2, 1, dark)
        rect(17, 24, 2, 1, dark)

    p.end()

    image = image.scaled(
        size * 2, size * 2,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(2.0)
    icon = QIcon(pixmap)

    if len(_ICON_CACHE) >= 1024:
        _ICON_CACHE.clear()
    _ICON_CACHE[key] = icon
    return icon


class ItemGrid(QListWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items_by_id: dict[str, Item] = {}
        self._signature = None

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(44, 44))
        self.setGridSize(QSize(62, 68))
        self.setSpacing(3)
        self.setUniformItemSizes(True)
        self.setMinimumHeight(110)

        self.itemClicked.connect(self._show_card)

    def selected_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.data(Qt.ItemDataRole.UserRole)
            for entry in self.selectedItems()
        )

    def _show_card(self, entry: QListWidgetItem) -> None:
        item = self._items_by_id.get(entry.data(Qt.ItemDataRole.UserRole))
        if item is not None:
            show_item_card(item, self)

    def set_items(self, items: tuple[Item, ...]) -> None:
        if self._signature == items:
            return

        selected = set(self.selected_ids())
        scroll = self.verticalScrollBar().value()

        self._signature = items
        self._items_by_id = {item.item_id: item for item in items}
        self.clear()

        for item in items:
            entry = QListWidgetItem(item_icon(item, 44), str(item.level))
            entry.setData(Qt.ItemDataRole.UserRole, item.item_id)
            entry.setToolTip(item_tooltip(item))
            entry.setForeground(QColor(RARITY_COLORS[item.rarity]))
            entry.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addItem(entry)
            entry.setSelected(item.item_id in selected)

        self.verticalScrollBar().setValue(scroll)


APP_STYLESHEET = """
QWidget {
    color:#e6dcc9;
    font-family:"Segoe UI","DejaVu Sans",sans-serif;
    font-size:11px;
}
QLabel { background:transparent; }
QPushButton, QToolButton {
    background:#261c2c;
    color:#dec8a5;
    border:1px solid #735039;
    border-radius:3px;
    padding:4px 6px;
}
QPushButton:hover, QToolButton:hover {
    background:#3b253b;
    border-color:#d8ab62;
}
QPushButton:checked, QToolButton:checked {
    background:#532e46;
    border-color:#edc77d;
}
QPushButton:disabled, QToolButton:disabled {
    background:#201a25;
    color:#706674;
    border-color:#403343;
}
QListWidget, QGraphicsView {
    background:#100e18;
    border:1px solid #543b52;
    border-radius:3px;
}
QListWidget::item:selected {
    background:#49304e;
    border:1px solid #deb373;
}
QProgressBar {
    background:#19141f;
    border:1px solid #56424c;
    border-radius:2px;
    text-align:center;
    min-height:13px;
    max-height:16px;
    font-size:10px;
}
QProgressBar::chunk { background:#963f53; }
QTabBar::tab {
    background:#241a2b;
    color:#bba488;
    border:1px solid #51394d;
    padding:5px 12px;
}
QTabBar::tab:selected {
    background:#493044;
    color:#edc784;
}
QToolTip {
    background:#170f20;
    color:#eee2cc;
    border:2px solid #987246;
    padding:7px;
}
QDialog, QMessageBox { background:#1c1523; }
QScrollArea { background:transparent; border:none; }
QScrollBar:vertical { background:#18121e; width:9px; }
QScrollBar::handle:vertical {
    background:#705063;
    min-height:24px;
}
"""
