from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget


class GothicFrame(QWidget):
    """
    Прозрачный QWidget с фигурной областью рисования.

    top_level=True включает перетаскивание окна за заголовок.
    """

    drag_finished = Signal()

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        top_level: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.top_level = top_level
        self._drag_offset = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(13, 46, 13, 13)
        self.body.setSpacing(8)

    def _shape(self) -> QPainterPath:
        w = float(self.width())
        h = float(self.height())
        c = w / 2

        path = QPainterPath(QPointF(1, 35))
        path.lineTo(9, 27)
        path.lineTo(9, 15)
        path.lineTo(19, 24)
        path.lineTo(c - 43, 24)
        path.lineTo(c - 31, 13)
        path.lineTo(c - 19, 20)
        path.lineTo(c - 10, 4)
        path.lineTo(c, 11)
        path.lineTo(c + 10, 4)
        path.lineTo(c + 19, 20)
        path.lineTo(c + 31, 13)
        path.lineTo(c + 43, 24)
        path.lineTo(w - 19, 24)
        path.lineTo(w - 9, 15)
        path.lineTo(w - 9, 27)
        path.lineTo(w - 1, 35)
        path.lineTo(w - 1, h - 15)
        path.lineTo(w - 15, h - 1)
        path.lineTo(15, h - 1)
        path.lineTo(1, h - 15)
        path.closeSubpath()
        return path

    def _draw_demon(self, painter: QPainter) -> None:
        c = self.width() / 2

        painter.save()
        painter.translate(c, 21)

        # Крылья/рога барельефа.
        painter.setPen(QPen(QColor("#c19550"), 1))
        painter.setBrush(QColor("#51333c"))

        for direction in (-1, 1):
            painter.drawPolygon(QPolygonF([
                QPointF(direction * 5, 1),
                QPointF(direction * 25, -8),
                QPointF(direction * 18, 4),
                QPointF(direction * 31, 8),
                QPointF(direction * 10, 9),
            ]))

        face = QPainterPath(QPointF(-9, -1))
        face.lineTo(-5, -8)
        face.lineTo(0, -4)
        face.lineTo(5, -8)
        face.lineTo(9, -1)
        face.lineTo(6, 10)
        face.lineTo(0, 14)
        face.lineTo(-6, 10)
        face.closeSubpath()

        gradient = QLinearGradient(-8, -7, 8, 14)
        gradient.setColorAt(0, QColor("#a87f49"))
        gradient.setColorAt(0.5, QColor("#584149"))
        gradient.setColorAt(1, QColor("#221923"))

        painter.setBrush(gradient)
        painter.drawPath(face)

        painter.setPen(QPen(QColor("#d95b69"), 1.8))
        painter.drawLine(QPointF(-5, 2), QPointF(-2, 4))
        painter.drawLine(QPointF(5, 2), QPointF(2, 4))
        painter.setPen(QPen(QColor("#c7a679"), 1))
        painter.drawLine(QPointF(-2, 9), QPointF(0, 11))
        painter.drawLine(QPointF(2, 9), QPointF(0, 11))

        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(43, 27, 40, 248))
        gradient.setColorAt(0.4, QColor(18, 17, 24, 240))
        gradient.setColorAt(1, QColor(25, 18, 29, 248))

        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#976d43"), 1.4))
        painter.drawPath(self._shape())

        painter.setPen(QPen(QColor("#572633"), 3))
        painter.drawLine(16, 41, self.width() - 16, 41)

        painter.setPen(QPen(QColor("#bc9454"), 0.8))
        painter.drawLine(18, 43, self.width() - 18, 43)

        # Кованые нижние уголки.
        painter.setPen(QPen(QColor("#9e7949"), 2))
        for x, direction in ((13, 1), (self.width() - 13, -1)):
            y = self.height() - 13
            painter.drawLine(x, y, x + direction * 22, y)
            painter.drawLine(x, y, x, y - 23)
            painter.drawLine(x, y - 9, x + direction * 10, y - 9)

        self._draw_demon(painter)

        painter.setPen(QColor("#d3b47c"))
        painter.drawText(
            QRectF(25, 24, self.width() - 50, 17),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )

        painter.setPen(QColor("#8c6654"))
        painter.drawText(
            QRectF(self.width() - 110, 25, 84, 15),
            Qt.AlignmentFlag.AlignRight,
            "ᚱ ᚨ ᚾ ᛟ",
        )
        painter.end()

    def mousePressEvent(self, event) -> None:
        if (
            self.top_level
            and event.button() == Qt.MouseButton.LeftButton
            and event.position().y() < 44
        ):
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().pos()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.window().move(
                event.globalPosition().toPoint() - self._drag_offset
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.drag_finished.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
