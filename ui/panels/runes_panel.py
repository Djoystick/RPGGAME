from __future__ import annotations

from html import escape

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from engine.runes_tree import RuneNode, Sector
from ui.actions import UiActions
from ui.common import stats_text
from ui.gothic_frame import GothicFrame


SECTOR_COLORS = {
    Sector.WAR: "#d86b55",
    Sector.ETHER: "#639cd9",
    Sector.VITALITY: "#70b780",
    Sector.GREED: "#d3af56",
    Sector.CHRONOMANCY: "#ac79db",
    None: "#ead8a5",
}


def effect_description(node: RuneNode) -> str:
    effect = node.effects
    lines = []

    stat_lines = stats_text(effect.stats)
    if stat_lines != "Без дополнительных характеристик":
        lines.append(stat_lines)

    for value, caption in (
        (effect.gold_bonus, "Золото"),
        (effect.sale_bonus, "Цена продажи"),
        (effect.drop_bonus, "Шанс предмета"),
        (effect.synthesis_bonus, "Критический синтез"),
        (effect.active_speed_bonus, "Активная скорость"),
    ):
        if value:
            lines.append(f"{caption}: +{value:.1%}")

    if effect.cap_steps:
        lines.append("Следующая ступень потолка оффлайна")
    if effect.efficiency_steps:
        lines.append("Следующая ступень эффективности оффлайна")
    if effect.keystones:
        lines.append("Великая руна: " + ", ".join(effect.keystones))

    return "\n".join(lines) or "Центр созвездия"


class RuneView(QGraphicsView):
    node_selected = Signal(str)
    node_activated = Signal(str)

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#100e19"))
        self._press_position = None

    def wheelEvent(self, event) -> None:
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        current = self.transform().m11()
        target = max(0.22, min(2.8, current * factor))
        self.scale(target / current, target / current)
        event.accept()

    def mousePressEvent(self, event) -> None:
        self._press_position = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (
            self._press_position is not None
            and (event.position() - self._press_position).manhattanLength() < 5
        ):
            item = self.itemAt(event.position().toPoint())
            if item is not None and isinstance(item.data(0), str):
                self.node_selected.emit(item.data(0))

        self._press_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is not None and isinstance(item.data(0), str):
            self.node_activated.emit(item.data(0))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def fit_tree(self) -> None:
        self.resetTransform()
        self.fitInView(
            self.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )


class RunesPanel(GothicFrame):
    def __init__(self, actions: UiActions, parent=None) -> None:
        super().__init__("RUNES · СОЗВЕЗДИЯ БЕЗДНЫ", parent)
        self.actions = actions
        self.selected_id = "nexus"

        self.header = QLabel()
        self.body.addWidget(self.header)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-760, -760, 1520, 1520)
        self.view = RuneView(self.scene)
        self.view.setMinimumHeight(290)
        self.body.addWidget(self.view, 1)

        self._nodes: dict[str, QGraphicsEllipseItem] = {}
        self._edges = []

        tree = self.actions.runes

        for parent_id, child_id in tree.edges:
            parent = tree.nodes[parent_id]
            child = tree.nodes[child_id]

            line = self.scene.addLine(
                *parent.position,
                *child.position,
                QPen(QColor("#3f334c"), 2),
            )
            line.setZValue(-1)
            self._edges.append((parent_id, child_id, line))

        for node in tree.nodes.values():
            radius = 14 if node.keystone or node.node_id == "nexus" else 9

            item = QGraphicsEllipseItem(
                -radius, -radius, radius * 2, radius * 2
            )
            item.setPos(QPointF(*node.position))
            item.setData(0, node.node_id)
            item.setAcceptHoverEvents(True)
            item.setZValue(1)

            description = escape(effect_description(node)).replace("\n", "<br>")
            item.setToolTip(
                f"<b>{escape(node.name)}</b><br>"
                f"{description}<hr>Цена: {node.cost:,} золота"
            )

            self.scene.addItem(item)
            self._nodes[node.node_id] = item

        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setMinimumHeight(65)
        self.body.addWidget(self.details)

        row = QHBoxLayout()
        self.buy = QPushButton("Купить руну")
        self.buy.clicked.connect(self._buy)

        fit = QPushButton("Показать всё")
        fit.clicked.connect(self.view.fit_tree)

        row.addWidget(self.buy)
        row.addWidget(fit)
        row.addWidget(QLabel("Колесо: зум · ЛКМ: перемещение"))
        self.body.addLayout(row)

        self.view.node_selected.connect(self._select)
        self.view.node_activated.connect(self._activate)
        self.actions.state.state_changed.connect(self.refresh)

        self.refresh()

    def _select(self, node_id: str) -> None:
        self.selected_id = node_id
        self.refresh()

    def _activate(self, node_id: str) -> None:
        # Двойной щелчок выбирает узел; покупка остаётся явной кнопкой.
        self._select(node_id)
        self.buy.setFocus()

    def _buy(self) -> None:
        self.actions.run(
            lambda: self.actions.buy_rune(self.selected_id)
        )

    def refresh(self, *_args) -> None:
        data = self.actions.state.data
        tree = self.actions.runes
        owned = set(data.unlocked_runes) | {"nexus"}

        self.header.setText(
            f"Открыто {len(data.unlocked_runes)}/150  ·  "
            f"Оффлайн {data.offline_cap_seconds // 3600} ч  ·  "
            f"Эффективность {data.offline_efficiency:.0%}"
        )

        for node_id, item in self._nodes.items():
            node = tree.nodes[node_id]
            unlocked = node_id in owned
            connected = set(node.prerequisites) <= owned
            affordable = data.gold >= node.cost
            color = QColor(SECTOR_COLORS[node.sector])

            if unlocked:
                item.setBrush(QBrush(color))
                item.setPen(QPen(color.lighter(155), 2.5))
            elif connected:
                item.setBrush(QBrush(color.darker(280)))
                item.setPen(QPen(
                    color if affordable else QColor("#8b776c"),
                    2,
                ))
            else:
                item.setBrush(QBrush(QColor("#201b2b")))
                item.setPen(QPen(QColor("#494050"), 1))

            if node_id == self.selected_id:
                item.setPen(QPen(QColor("#fff1c4"), 3.5))

        for parent_id, child_id, line in self._edges:
            if parent_id in owned and child_id in owned:
                color = QColor("#ae8c58")
            elif parent_id in owned:
                color = QColor("#735675")
            else:
                color = QColor("#342c40")
            line.setPen(QPen(color, 2))

        node = tree.nodes[self.selected_id]
        connected = set(node.prerequisites) <= owned
        purchased = self.selected_id in owned

        status = (
            "Открыта"
            if purchased else
            "Сначала откройте предыдущую руну"
            if not connected else
            "Недостаточно золота"
            if data.gold < node.cost else
            "Доступна для покупки"
        )

        self.details.setText(
            f"{node.name} · {node.cost:,} золота · {status}\n"
            f"{effect_description(node)}"
        )
        self.buy.setEnabled(
            not purchased and connected and data.gold >= node.cost
        )
        self.buy.setText(
            "Открыта" if purchased else f"Купить · {node.cost:,}"
        )
