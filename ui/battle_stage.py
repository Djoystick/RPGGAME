from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import (
    QElapsedTimer, QPointF, QRectF, Qt, QTimer,
)
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QPolygonF, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from engine.combat_manager import (
    CombatFrame, CombatManager, DamageEvent, LootEvent, VfxEvent,
)
from gfx.animations import AnimationController
from gfx.sprite_loader import SpriteLoader
from models.enemy import Act
from ui.common import RARITY_COLORS, RARITY_NAMES


ACT_TITLES = {
    Act.CRYPTS: "Катакомбы Падших",
    Act.FOREST: "Осквернённая Чаща",
    Act.CALDERA: "Пепельная Кальдера",
    Act.CITADEL: "Цитадель Бездны",
}

ELEMENT_COLORS = {
    "physical": "#e5e8ee",
    "fire": "#ff9b49",
    "cold": "#9edfff",
    "lightning": "#ffe4a0",
    "chaos": "#94efb5",
    "magic": "#c991ed",
}

TEXT_COLORS = {
    "physical": "#f0ece4",
    "magical": "#c789f3",
    "heal": "#88e9a4",
    "dodge": "#a9a3b2",
    "barrier": "#98d9fb",
    "block": "#a9d7ff",
}


@dataclass
class FloatingText:
    x: float
    y: float
    text: str
    color: QColor
    age: float = 0.0
    lifetime: float = 0.85


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: QColor
    size: float
    age: float = 0.0
    lifetime: float = 0.45
    gravity: float = 65.0


@dataclass
class Effect:
    kind: str
    x: float
    y: float
    color: QColor
    age: float = 0.0
    lifetime: float = 0.25


@dataclass
class LootOrb:
    event: LootEvent
    offset: float
    age: float = 0.0
    landed: bool = False
    lifetime: float = 1.45


@dataclass
class LootNotice:
    event: LootEvent
    age: float = 0.0
    lifetime: float = 2.5


class BattleStage(QWidget):
    def __init__(
        self,
        combat: CombatManager,
        parent: QWidget | None = None,
        *,
        drive_combat: bool = True,
    ) -> None:
        super().__init__(parent)

        self.combat = combat
        self.drive_combat = drive_combat
        self.loader = SpriteLoader()

        self._frame = combat.frame()
        self._animations: dict[str, AnimationController] = {}
        self._texts: list[FloatingText] = []
        self._particles: list[Particle] = []
        self._effects: list[Effect] = []
        self._loot: list[LootOrb] = []
        self._notices: deque[LootNotice] = deque(maxlen=24)

        self._last_simulation_time = self._frame.time
        self._visual_time = 0.0
        self._barrier_flash = 0.0
        self._event_serial = 0

        self.setFixedSize(520, 144)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        combat.frame_changed.connect(self._receive_frame)
        combat.damage_event.connect(self._receive_damage)
        combat.vfx_event.connect(self._receive_vfx)
        combat.loot_event.connect(self._receive_loot)

        self._clock = QElapsedTimer()
        self._clock.start()

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _receive_frame(self, frame: CombatFrame) -> None:
        self._frame = frame
        ids = {actor.actor_id for actor in frame.actors}

        for actor_id in tuple(self._animations):
            if actor_id not in ids:
                del self._animations[actor_id]

        for actor in frame.actors:
            animator = self._animations.setdefault(
                actor.actor_id, AnimationController()
            )
            animator.set_state(actor.animation)

    def _receive_damage(self, event: DamageEvent) -> None:
        labels = {
            "dodge": "УВОРОТ",
            "barrier": "БАРЬЕР",
            "block": "БЛОК",
        }

        if event.kind in labels:
            text = labels[event.kind]
        elif event.kind == "heal":
            text = f"+{max(1, round(event.amount))}"
        else:
            text = str(max(1, round(event.amount)))

        color = QColor(
            "#ffe09a" if event.critical
            else TEXT_COLORS.get(event.kind, "#ffffff")
        )

        self._texts.append(FloatingText(
            event.x + (len(self._texts) % 5 - 2) * 3,
            event.y,
            text,
            color,
        ))
        if len(self._texts) > 100:
            del self._texts[:-100]

        if event.critical:
            self._burst(event.x, event.y + 8, QColor("#ffda7f"), 14)
        elif event.kind == "block":
            self._burst(event.x, event.y + 8, QColor("#91d9ff"), 9)
            self._effects.append(Effect(
                "shield", event.x, event.y + 7,
                QColor("#9bdfff"), lifetime=0.30,
            ))

    def _receive_vfx(self, event: VfxEvent) -> None:
        color = QColor(ELEMENT_COLORS.get(event.element, "#c6b6df"))

        if event.kind == "barrier":
            self._barrier_flash = 0.35
            self._effects.append(Effect(
                "ripple", event.x, event.y,
                QColor("#bcefff"), lifetime=0.35,
            ))
        elif event.kind == "slash":
            self._effects.append(Effect(
                "slash", event.x, event.y,
                color, lifetime=0.15,
            ))
        elif event.kind == "holy":
            self._effects.append(Effect(
                "holy", event.x, event.y,
                QColor("#ffe5a0"), lifetime=0.32,
            ))
        elif event.kind == "impact":
            self._burst(event.x, event.y, color, 5)

        if len(self._effects) > 100:
            del self._effects[:-100]

    def _receive_loot(self, event: LootEvent) -> None:
        self._event_serial += 1
        offset = ((self._event_serial % 5) - 2) * 13
        self._loot.append(LootOrb(event, offset))
        self._notices.append(LootNotice(event))

        if len(self._loot) > 32:
            del self._loot[:-32]

    def _burst(
        self,
        x: float,
        y: float,
        color: QColor,
        count: int,
    ) -> None:
        self._event_serial += 1
        phase = self._event_serial * 0.71

        for index in range(count):
            angle = phase + index * math.tau / count
            speed = 25 + (index % 4) * 15
            self._particles.append(Particle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed - 16,
                QColor(color),
                1.0 + index % 2,
                lifetime=0.30 + (index % 4) * 0.08,
            ))

        if len(self._particles) > 320:
            del self._particles[:-320]

    def _tick(self) -> None:
        dt = min(max(0.0, self._clock.restart() / 1000.0), 0.25)

        if self.drive_combat:
            self.combat.advance(dt)

        simulation_dt = max(
            0.0, self._frame.time - self._last_simulation_time
        )
        self._last_simulation_time = self._frame.time
        self._visual_time += dt

        for animation in self._animations.values():
            animation.advance(simulation_dt)

        for text in self._texts:
            text.age += dt
        self._texts = [
            text for text in self._texts if text.age < text.lifetime
        ]

        for particle in self._particles:
            particle.age += dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += particle.gravity * dt
        self._particles = [
            particle for particle in self._particles
            if particle.age < particle.lifetime
        ]

        for effect in self._effects:
            effect.age += dt
        self._effects = [
            effect for effect in self._effects
            if effect.age < effect.lifetime
        ]

        for orb in self._loot:
            orb.age += dt
            if orb.age >= 0.80 and not orb.landed:
                orb.landed = True
                self._burst(
                    orb.event.x + orb.offset,
                    orb.event.y - 2,
                    QColor(RARITY_COLORS[orb.event.item.rarity]),
                    10,
                )
        self._loot = [orb for orb in self._loot if orb.age < orb.lifetime]

        if self._notices:
            self._notices[0].age += dt
            if self._notices[0].age >= self._notices[0].lifetime:
                self._notices.popleft()

        self._barrier_flash = max(0.0, self._barrier_flash - dt)
        self.update()

    @staticmethod
    def _polygon(painter: QPainter, points, color) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF([
            QPointF(float(x), float(y)) for x, y in points
        ]))

    @staticmethod
    def _line(
        painter: QPainter,
        x1: float, y1: float, x2: float, y2: float,
        color, width: float = 1,
    ) -> None:
        painter.setPen(QPen(QColor(color), width))
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    @staticmethod
    def _arch(x: float, y: float, width: float, height: float) -> QPainterPath:
        path = QPainterPath(QPointF(x, y + height))
        path.lineTo(x, y + height * 0.42)
        path.quadTo(x, y + height * 0.15, x + width / 2, y)
        path.quadTo(
            x + width, y + height * 0.15,
            x + width, y + height * 0.42,
        )
        path.lineTo(x + width, y + height)
        path.closeSubpath()
        return path

    def _flame(
        self, painter: QPainter,
        x: float, y: float, color: str, seed: float,
    ) -> None:
        t = self._visual_time
        h = 10 + 3 * math.sin(t * 6 + seed)
        self._polygon(painter, [
            (x - 6, y), (x - 4, y - 8),
            (x - 1, y - h - 5), (x + 2, y - 6),
            (x + 5, y - h), (x + 6, y),
        ], color)
        self._polygon(painter, [
            (x - 3, y), (x, y - h),
            (x + 3, y - 3), (x + 2, y),
        ], "#d1f7b7" if color == "#58a68b" else "#ffe3a1")

    def _draw_background(self, painter: QPainter) -> None:
        t = self._visual_time
        act = self._frame.act

        colors = {
            Act.CRYPTS: ("#15121e", "#252330"),
            Act.FOREST: ("#0b1919", "#213832"),
            Act.CALDERA: ("#3d1520", "#160f1a"),
            Act.CITADEL: ("#201334", "#100d1c"),
        }

        sky = QLinearGradient(0, 0, 0, 144)
        sky.setColorAt(0, QColor(colors[act][0]))
        sky.setColorAt(1, QColor(colors[act][1]))
        painter.fillRect(QRectF(0, 0, 520, 144), sky)

        if act == Act.CRYPTS:
            offset = (t * 2.2) % 126

            for index in range(-1, 6):
                x = index * 126 - offset

                painter.setBrush(QColor("#100f19"))
                painter.setPen(QPen(QColor("#454052"), 4))
                painter.drawPath(self._arch(x + 13, 24, 78, 92))

                painter.setPen(QPen(QColor("#625563"), 1))
                painter.drawPath(self._arch(x + 20, 31, 64, 82))

                painter.fillRect(QRectF(x + 1, 38, 10, 87), QColor("#393342"))
                painter.fillRect(QRectF(x - 2, 35, 16, 5), QColor("#514552"))
                painter.fillRect(QRectF(x - 2, 119, 16, 5), QColor("#514552"))

                for crack in range(3):
                    cx = x + 100 + crack * 6
                    cy = 35 + crack * 23
                    self._line(painter, cx, cy, cx - 5, cy + 9, "#17131f")
                    self._line(painter, cx - 5, cy + 9, cx + 1, cy + 17, "#17131f")

            near = (t * 5) % 156
            for index in range(-1, 5):
                x = index * 156 - near

                painter.save()
                painter.translate(x + 33, 123)
                painter.rotate(-8 if index % 2 else 7)
                painter.setPen(QPen(QColor("#73666f"), 1))
                painter.setBrush(QColor("#48404b"))
                painter.drawRoundedRect(QRectF(-10, -30, 21, 32), 6, 6)
                self._line(painter, 0, -24, 0, -8, "#b2a387")
                self._line(painter, -5, -19, 5, -19, "#b2a387")
                self._line(painter, -4, -8, 4, -11, "#28212e")
                painter.restore()

                for link in range(8):
                    painter.setPen(QPen(QColor("#645665"), 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(QRectF(x + 101, 17 + link * 5, 3, 7))

                self._polygon(painter, [
                    (x + 91, 84), (x + 110, 84),
                    (x + 105, 91), (x + 96, 91),
                ], "#65515d")
                self._flame(painter, x + 101, 83, "#58a68b", index)

        elif act == Act.FOREST:
            offset = (t * 2.7) % 118
            for index in range(-1, 7):
                x = index * 118 - offset
                trunk = QPainterPath(QPointF(x + 28, 128))
                trunk.cubicTo(x + 50, 90, x + 18, 69, x + 38, 18)
                painter.setPen(QPen(QColor("#142724"), 15))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(trunk)

                for branch in range(4):
                    by = 42 + branch * 17
                    direction = -1 if branch % 2 else 1
                    self._line(
                        painter, x + 34, by,
                        x + 34 + direction * 30, by - 20,
                        "#19352d", 5,
                    )
                    self._line(
                        painter, x + 34 + direction * 23, by - 15,
                        x + 34 + direction * 37, by - 38,
                        "#19352d", 2,
                    )

            near = (t * 5.5) % 142
            for index in range(-1, 6):
                x = index * 142 - near

                self._polygon(painter, [
                    (x + 4, 132), (x + 13, 113),
                    (x + 39, 110), (x + 54, 129),
                ], "#334b42")
                self._line(painter, x + 15, 116, x + 39, 113, "#6f8b55", 3)

                for mushroom in range(3):
                    mx = x + 73 + mushroom * 10
                    my = 127 - mushroom % 2 * 6
                    self._line(painter, mx, my, mx, my - 9, "#70969b", 2)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#4faeaa"))
                    painter.drawEllipse(QRectF(mx - 6, my - 14, 13, 7))
                    painter.setBrush(QColor("#b3f2d7"))
                    painter.drawEllipse(QRectF(mx - 2, my - 13, 3, 2))

                vine = QPainterPath(QPointF(x + 98, 14))
                vine.cubicTo(x + 78, 30, x + 119, 39, x + 94, 66)
                painter.setPen(QPen(QColor("#3c6650"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(vine)

        elif act == Act.CALDERA:
            glow = QRadialGradient(QPointF(390, 46), 160)
            glow.setColorAt(0, QColor(216, 65, 35, 100))
            glow.setColorAt(1, QColor(216, 65, 35, 0))
            painter.fillRect(QRectF(0, 0, 520, 144), glow)

            offset = (t * 2.4) % 110
            for index in range(-1, 7):
                x = index * 110 - offset
                self._polygon(painter, [
                    (x - 12, 130), (x + 13, 62), (x + 20, 77),
                    (x + 43, 22), (x + 51, 76), (x + 67, 52),
                    (x + 101, 130),
                ], "#211b2b")
                self._line(painter, x + 43, 25, x + 35, 92, "#55323d", 2)

            near = (t * 5.0) % 174
            pulse = 0.65 + 0.35 * math.sin(t * 2.2)

            for index in range(-1, 5):
                x = index * 174 - near

                self._polygon(painter, [
                    (x + 26, 125), (x + 26, 75), (x + 34, 70),
                    (x + 39, 79), (x + 45, 71), (x + 57, 84),
                    (x + 60, 126),
                ], "#3b2935")
                self._line(painter, x + 31, 90, x + 53, 89, "#5c3b42")
                self._line(painter, x + 30, 108, x + 58, 106, "#5c3b42")

                magma = QColor("#f47c3b")
                magma.setAlphaF(pulse)
                points = [
                    (x + 75, 125), (x + 93, 115),
                    (x + 108, 123), (x + 123, 110),
                    (x + 147, 126),
                ]
                for a, b in zip(points, points[1:]):
                    self._line(painter, *a, *b, "#6e302c", 6)
                    self._line(painter, *a, *b, magma, 2)

        else:
            offset = (t * 1.8) % 136

            for index in range(-1, 6):
                x = index * 136 - offset
                arch = self._arch(x + 15, 24, 78, 95)

                painter.setPen(QPen(QColor("#655072"), 3))
                painter.setBrush(QColor("#312143"))
                painter.drawPath(arch)

                painter.save()
                painter.setClipPath(arch)

                for pane in range(5):
                    color = QColor(105 + pane * 15, 57, 160 + pane * 12)
                    color.setAlpha(120 + int(35 * math.sin(t * 2 + pane + index)))
                    self._polygon(painter, [
                        (x + 12 + pane * 17, 27),
                        (x + 55, 67),
                        (x + 13 + pane * 17, 121),
                    ], color)
                painter.restore()

                self._line(painter, x + 54, 30, x + 54, 119, "#b18b99", 1)
                self._line(painter, x + 17, 73, x + 91, 73, "#b18b99", 1)

                oy = 64 + math.sin(t * 1.2 + index) * 5
                self._polygon(painter, [
                    (x + 111, oy - 23), (x + 121, oy - 7),
                    (x + 120, oy + 23), (x + 110, oy + 31),
                    (x + 104, oy + 16), (x + 104, oy - 10),
                ], "#100d19")
                self._line(painter, x + 111, oy - 15, x + 111, oy + 20, "#7c5eae")

            near = (t * 4.5) % 192
            for index in range(-1, 4):
                x = index * 192 - near
                painter.fillRect(QRectF(x + 8, 61, 17, 74), QColor("#423149"))
                painter.fillRect(QRectF(x + 5, 59, 23, 7), QColor("#6c5165"))
                for notch in range(5):
                    self._line(
                        painter, x + 12, 72 + notch * 11,
                        x + 21, 76 + notch * 11,
                        "#a77b94",
                    )

                painter.setPen(QPen(QColor("#9864c2"), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(x + 72, 116, 73, 14))
                painter.drawEllipse(QRectF(x + 83, 119, 51, 8))
                painter.setPen(QColor("#c9a1e8"))
                painter.drawText(QPointF(x + 89, 125), "ᚨ ᚱ ᛟ")

        ground = QLinearGradient(0, 109, 0, 144)
        ground.setColorAt(0, QColor(10, 9, 16, 0))
        ground.setColorAt(1, QColor(9, 7, 14, 225))
        painter.fillRect(QRectF(0, 105, 520, 39), ground)

        self._draw_atmosphere(painter)

    def _draw_atmosphere(self, painter: QPainter) -> None:
        t = self._visual_time
        act = self._frame.act

        if act == Act.CRYPTS:
            for layer in range(3):
                x = ((t * (6 + layer * 2)) + layer * 180) % 750 - 220
                fog = QRadialGradient(QPointF(x + 160, 126), 175)
                fog.setColorAt(0, QColor(161, 159, 170, 22))
                fog.setColorAt(1, QColor(161, 159, 170, 0))
                painter.fillRect(QRectF(x, 107, 370, 35), fog)
            return

        for index in range(23):
            x = (index * 73.7 + math.sin(t * 0.3 + index) * 15) % 520

            if act == Act.CALDERA:
                y = 143 - ((index * 19 + t * (9 + index % 7)) % 125)
                color = QColor("#ffae68" if index % 3 else "#82767d")
                radius = 0.8 + index % 2 * 0.5
            else:
                y = 35 + (index * 37 % 100) + math.sin(t * 0.6 + index) * 7
                color = QColor("#82dec5" if act == Act.FOREST else "#c193fa")
                radius = 0.7 + index % 3 * 0.3

            color.setAlpha(60 + int(60 * (0.5 + 0.5 * math.sin(t + index))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def _draw_barrier(self, painter: QPainter) -> None:
        if self._frame.barrier_max <= 0:
            return

        ratio = max(0.0, min(
            1.0, self._frame.barrier / self._frame.barrier_max
        ))
        if ratio <= 0 and self._barrier_flash <= 0:
            return

        t = self._visual_time
        pulse = 0.8 + 0.2 * math.sin(t * 3)
        flash = min(1.0, self._barrier_flash / 0.35)
        strength = min(1.0, ratio * pulse + flash * 0.7)

        rect = QRectF(36, 39, 173, 95)

        glow = QRadialGradient(QPointF(123, 104), 98)
        glow.setColorAt(0.0, QColor(112, 152, 225, 5))
        glow.setColorAt(0.65, QColor(111, 142, 232, int(13 * strength)))
        glow.setColorAt(1.0, QColor(121, 196, 244, int(85 * strength)))

        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        for width, alpha in ((6, 16), (3, 35), (1, 150)):
            color = QColor("#a3d7ff")
            color.setAlpha(int(alpha * strength))
            painter.setPen(QPen(color, width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

        for index in range(17):
            angle = math.pi + index * math.pi / 16
            x = 122.5 + math.cos(angle) * 86.5
            y = 86.5 + math.sin(angle) * 47.5

            color = QColor("#e3c58b" if index % 3 == 0 else "#98dbf0")
            color.setAlpha(int(160 * strength))
            painter.save()
            painter.translate(x, y)
            painter.rotate(math.degrees(angle) + 90)
            self._line(painter, 0, -3, 0, 3, color, 1)
            self._line(painter, -2, -1, 2, 1, color, 1)
            if index % 2:
                self._line(painter, -2, 2, 0, 0, color, 1)
            painter.restore()

        if flash > 0:
            color = QColor("#e9fbff")
            color.setAlpha(int(180 * flash))
            painter.setPen(QPen(color, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = (1 - flash) * 10
            painter.drawEllipse(rect.adjusted(inset, inset / 2, -inset, -inset / 2))

    def _draw_actors(self, painter: QPainter) -> None:
        dpr = self.devicePixelRatioF()

        for actor in sorted(self._frame.actors, key=lambda entry: entry.y):
            size = 48 if actor.boss else 36
            animator = self._animations.setdefault(
                actor.actor_id, AnimationController()
            )
            animator.set_state(actor.animation)

            frames = self.loader.frames(
                actor.sprite_key, actor.animation,
                size=size, dpr=dpr,
            )
            pixmap = frames[animator.frame_index % len(frames)]

            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 75))
            painter.drawEllipse(QRectF(actor.x - 12, actor.y - 3, 24, 5))

            painter.translate(actor.x, actor.y)
            if actor.enemy:
                painter.scale(-1, 1)

            painter.drawPixmap(QPointF(-size / 2, -size), pixmap)
            painter.restore()

            if actor.hp <= 0:
                continue

            width = 45 if actor.boss else 24
            left = actor.x - width / 2
            top = actor.y - size - 5
            ratio = max(0.0, min(1.0, actor.hp / actor.max_hp))

            painter.fillRect(QRectF(left, top, width, 3), QColor("#211727"))
            painter.fillRect(
                QRectF(left, top, width * ratio, 3),
                QColor("#c45e62" if actor.enemy else "#79c19b"),
            )

            if actor.elite:
                painter.setPen(QColor("#efc776"))
                painter.drawText(QPointF(actor.x - 4, top - 2), "◆")

            if actor.boss:
                painter.fillRect(
                    QRectF(left, top + 5, width, 2), QColor("#3c2531")
                )
                painter.fillRect(
                    QRectF(left, top + 5, width * actor.rage, 2),
                    QColor("#ef9653"),
                )

    def _draw_projectiles(self, painter: QPainter) -> None:
        for projectile in self._frame.projectiles:
            painter.save()
            painter.translate(projectile.x, projectile.y)
            painter.rotate(math.degrees(projectile.angle))

            if projectile.kind == "arrow":
                self._line(painter, -19, 0, -4, 0, QColor(225, 238, 255, 80), 2)
                self._line(painter, -10, 0, 8, 0, "#d7d3bc", 1.5)
                self._polygon(painter, [(10, 0), (5, -3), (5, 3)], "#e2edf2")
                self._line(painter, -10, 0, -14, -3, "#95b5cb")
                self._line(painter, -10, 0, -14, 3, "#95b5cb")

            else:
                fire = projectile.kind == "fireball"
                color = QColor("#ff9347" if fire else "#84e7ad")
                tail = QColor(color)
                tail.setAlpha(85)

                self._polygon(painter, [
                    (-22, 0), (-3, -5), (2, 0), (-3, 5),
                ], tail)

                gradient = QRadialGradient(QPointF(0, 0), 9)
                gradient.setColorAt(0, QColor("#fff1c1" if fire else "#e9ffe8"))
                gradient.setColorAt(0.35, color)
                gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradient)
                painter.drawEllipse(QRectF(-9, -9, 18, 18))

                if projectile.kind == "necrotic":
                    painter.fillRect(QRectF(-3, -3, 6, 5), QColor("#d7efd2"))
                    painter.fillRect(QRectF(0, -2, 2, 2), QColor("#31554c"))
                    painter.fillRect(QRectF(-2, 2, 4, 2), QColor("#a8d6b7"))

            painter.restore()

    def _draw_effects(self, painter: QPainter) -> None:
        for effect in self._effects:
            progress = effect.age / effect.lifetime
            color = QColor(effect.color)
            color.setAlphaF(max(0.0, 1 - progress))

            painter.save()
            painter.translate(effect.x, effect.y)

            if effect.kind == "slash":
                painter.rotate(-25 + progress * 65)
                path = QPainterPath()
                path.moveTo(-18, 15)
                path.cubicTo(-6, -20, 20, -24, 31, -1)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(color, 5 * (1 - progress) + 1))
                painter.drawPath(path)

                bright = QColor("#ffffff")
                bright.setAlphaF(max(0.0, 1 - progress))
                painter.setPen(QPen(bright, 1))
                painter.drawPath(path)

            elif effect.kind == "holy":
                gradient = QLinearGradient(0, -100, 0, 20)
                gradient.setColorAt(0, QColor(255, 230, 154, 0))
                gradient.setColorAt(0.55, color)
                gradient.setColorAt(1, QColor(255, 235, 181, 0))
                painter.fillRect(QRectF(-9, -100, 18, 120), gradient)
                self._line(painter, 0, -85, 0, 10, color, 3)
                self._line(painter, -15, -14, 15, -14, color, 2)

            elif effect.kind == "shield":
                painter.setPen(QPen(color, 1.5))
                painter.setBrush(QColor(110, 184, 243, int(55 * (1 - progress))))
                painter.drawPolygon(QPolygonF([
                    QPointF(-10, -9), QPointF(0, -13), QPointF(10, -9),
                    QPointF(8, 5), QPointF(0, 12), QPointF(-8, 5),
                ]))
                self._line(painter, 0, -7, 0, 6, color)
                self._line(painter, -5, -2, 5, -2, color)

            elif effect.kind == "ripple":
                radius = 5 + progress * 25
                painter.setPen(QPen(color, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(
                    QRectF(-radius, -radius * 0.7, radius * 2, radius * 1.4)
                )

            painter.restore()

        for particle in self._particles:
            color = QColor(particle.color)
            color.setAlphaF(max(0.0, 1 - particle.age / particle.lifetime))
            painter.fillRect(
                QRectF(particle.x, particle.y, particle.size, particle.size),
                color,
            )

    def _draw_loot(self, painter: QPainter) -> None:
        for orb in self._loot:
            t = min(1.0, orb.age / 0.80)
            x = orb.event.x + orb.offset * t
            y = orb.event.y - 9 - 39 * math.sin(math.pi * t)

            fade = (
                1.0 if orb.age < 0.9
                else max(0.0, (orb.lifetime - orb.age) / (orb.lifetime - 0.9))
            )
            color = QColor(RARITY_COLORS[orb.event.item.rarity])

            painter.save()
            painter.setOpacity(fade)

            glow = QRadialGradient(QPointF(x, y), 14)
            glow.setColorAt(0, color)
            glow.setColorAt(0.4, QColor(color.red(), color.green(), color.blue(), 100))
            glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QRectF(x - 14, y - 14, 28, 28))

            self._polygon(painter, [
                (x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y),
            ], color)
            painter.fillRect(QRectF(x - 1, y - 3, 2, 3), QColor("#fff5dc"))
            painter.restore()

    def _draw_texts(self, painter: QPainter) -> None:
        painter.setFont(QFont("Sans Serif", 8, QFont.Weight.Bold))

        for text in self._texts:
            alpha = max(0.0, 1 - text.age / text.lifetime)
            color = QColor(text.color)
            color.setAlphaF(alpha)

            y = text.y - text.age * 27
            rect = QRectF(text.x - 48, y - 10, 96, 20)

            painter.setPen(QColor(0, 0, 0, int(180 * alpha)))
            painter.drawText(
                rect.translated(1, 1),
                Qt.AlignmentFlag.AlignCenter, text.text,
            )
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text.text)

    def _draw_notice(self, painter: QPainter) -> None:
        if not self._notices:
            return

        notice = self._notices[0]
        event = notice.event
        color = QColor(RARITY_COLORS[event.item.rarity])

        age = notice.age
        alpha = min(1.0, age / 0.15, (notice.lifetime - age) / 0.30)
        alpha = max(0.0, alpha)

        painter.save()
        painter.setOpacity(alpha)
        rect = QRectF(230, 25, 281, 31)

        path = QPainterPath(QPointF(rect.left() + 7, rect.top()))
        path.lineTo(rect.right() - 7, rect.top())
        path.lineTo(rect.right(), rect.top() + 7)
        path.lineTo(rect.right(), rect.bottom() - 7)
        path.lineTo(rect.right() - 7, rect.bottom())
        path.lineTo(rect.left() + 7, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - 7)
        path.lineTo(rect.left(), rect.top() + 7)
        path.closeSubpath()

        painter.setBrush(QColor(23, 14, 31, 235))
        painter.setPen(QPen(color.darker(135), 1))
        painter.drawPath(path)

        painter.setFont(QFont("Sans Serif", 8, QFont.Weight.Bold))
        title = (
            f"✦ {RARITY_NAMES[event.item.rarity]}: "
            f"{event.item.display_name}"
        )
        title = painter.fontMetrics().elidedText(
            title, Qt.TextElideMode.ElideRight, 265
        )

        painter.setPen(color)
        painter.drawText(QPointF(238, 37), title)

        painter.setFont(QFont("Sans Serif", 7))
        painter.setPen(QColor("#c2b3c7"))
        message = (
            "Отправлено в сундук"
            if event.stored
            else f"Сундук полон · продано за {event.sale_gold:,}"
        )
        painter.drawText(QPointF(238, 49), message)
        painter.restore()

    def _draw_hud(self, painter: QPainter) -> None:
        painter.fillRect(QRectF(0, 0, 520, 23), QColor(11, 8, 17, 215))
        painter.setFont(QFont("Sans Serif", 8))
        painter.setPen(QColor("#ded0bd"))

        title = f"{ACT_TITLES[self._frame.act]} · {self._frame.wave}"
        painter.drawText(QPointF(8, 15), title)

        if self._frame.boss_remaining is not None:
            painter.setPen(QColor("#efc675"))
            painter.drawText(
                QRectF(350, 2, 160, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"БОСС · {self._frame.boss_remaining:04.1f} с",
            )
        elif self._frame.phase == "defeat":
            painter.setPen(QColor("#e88e98"))
            painter.drawText(QPointF(380, 15), "Отступление")
        elif self._frame.phase == "between":
            painter.drawText(QPointF(379, 15), "Волна отражена")

        painter.fillRect(QRectF(8, 138, 504, 3), QColor("#342437"))
        painter.fillRect(
            QRectF(8, 138, 504 * self._frame.progress, 3),
            QColor("#bd9258"),
        )

        painter.setPen(QPen(QColor("#765143"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0.5, 0.5, 519, 143))

    def paint_scene(self, painter: QPainter) -> None:
        self._draw_background(painter)
        self._draw_barrier(painter)
        self._draw_actors(painter)
        self._draw_projectiles(painter)
        self._draw_loot(painter)
        self._draw_effects(painter)
        self._draw_texts(painter)
        self._draw_hud(painter)
        self._draw_notice(painter)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121018"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, False
        )
        painter.scale(self.width() / 520.0, self.height() / 144.0)
        painter.setClipRect(QRectF(0, 0, 520, 144))

        self.paint_scene(painter)
        painter.end()
