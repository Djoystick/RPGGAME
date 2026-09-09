from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gfx.sprite_loader import SpriteLoader
from models.hero import Hero, SecondaryStats
from models.stats import StatBlock
from ui.gothic_frame import GothicFrame


class StatsBackground(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sprite = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121018"))

        if self.sprite is not None:
            painter.setOpacity(0.08)
            width = min(260, self.width() - 20)
            rect = QRectF(
                (self.width() - width) / 2,
                max(100, (self.height() - width) / 2),
                width,
                width,
            )
            painter.drawPixmap(
                rect,
                self.sprite,
                QRectF(self.sprite.rect()),
            )
        painter.end()


class DetailedStatsWindow(GothicFrame):
    def __init__(self, parent=None) -> None:
        super().__init__("", parent, top_level=True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(380, 560)
        self.setMinimumSize(350, 320)

        self.loader = SpriteLoader()
        self._sprite_key = None
        self._rows: dict[str, QLabel] = {}

        self.title_label = QLabel("Detailed Stats", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color:#e2ba70; font-size:14px; font-weight:bold;"
        )
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.setFixedSize(23, 22)
        self.close_button.clicked.connect(self.close)

        self.hero_label = QLabel()
        self.hero_label.setWordWrap(True)
        self.body.addWidget(self.hero_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body.addWidget(self.scroll, 1)

        self.content = StatsBackground()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(7)
        self.scroll.setWidget(self.content)

        from models.hero import DETAILED_REGISTRY

        for section, rows in DETAILED_REGISTRY.items():
            label = QLabel(section)
            label.setStyleSheet(
                "color:#d5a360; font-size:14px; font-weight:bold;"
            )
            self.content_layout.addWidget(label)

            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background:#745038;")
            self.content_layout.addWidget(line)

            for name, _, _ in rows:
                row = QHBoxLayout()
                title = QLabel(name)
                title.setWordWrap(True)
                title.setStyleSheet("color:#cfc5b8; font-size:10px;")

                value = QLabel()
                value.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                value.setMinimumWidth(67)
                value.setStyleSheet("color:#e9d5ab; font-size:11px;")

                row.addWidget(title, 1)
                row.addWidget(value)
                self.content_layout.addLayout(row)
                self._rows[name] = value

        self.content_layout.addStretch()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.title_label.setGeometry(45, 24, self.width() - 90, 18)
        self.close_button.move(self.width() - 37, 19)
        self.close_button.raise_()

    def refresh(
        self,
        hero: Hero,
        bonuses: StatBlock = StatBlock(),
        *,
        secondary: SecondaryStats | None = None,
    ) -> None:
        self.hero_label.setText(
            f"{hero.name} · {hero.definition.name} Lv.{hero.level}"
        )

        sections = hero.detailed_stats(bonuses, secondary=secondary)
        for rows in sections.values():
            for name, value in rows:
                if self._rows[name].text() != value:
                    self._rows[name].setText(value)

        key = hero.hero_class.value
        if key != self._sprite_key:
            self._sprite_key = key
            self.content.sprite = self.loader.frames(
                key, "idle", size=256, dpr=self.devicePixelRatioF()
            )[0]
            self.content.update()

    def closeEvent(self, event) -> None:
        self.hide()
        event.ignore()
