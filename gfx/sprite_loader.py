from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QPolygon

import config as C
from gfx.animations import AnimationState


class SpriteLoader:
    def __init__(self, root: Path = C.SPRITES_DIR) -> None:
        self.root = Path(root)
        self._cache: dict[tuple, tuple[QPixmap, ...]] = {}

    def clear(self) -> None:
        self._cache.clear()

    def frames(
        self,
        key: str,
        state: AnimationState | str,
        *,
        size: int = 36,
        dpr: float = 1.0,
        frame_count: int = 4,
    ) -> tuple[QPixmap, ...]:
        state = AnimationState(state)

        if type(size) is not int or size < 1:
            raise ValueError("Некорректный размер спрайта")
        if type(frame_count) is not int or frame_count < 1:
            raise ValueError("Некорректное количество кадров")
        if not math.isfinite(dpr) or dpr <= 0:
            raise ValueError("Некорректный DPR")

        dpr = round(dpr, 3)
        cache_key = (key, state.value, size, dpr, frame_count)

        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.root / key / f"{state.value}.png"
        sheet = QImage(str(path)) if path.is_file() else QImage()

        valid_sheet = (
            not sheet.isNull()
            and sheet.width() >= frame_count
            and sheet.width() % frame_count == 0
        )

        physical_size = max(1, math.ceil(size * dpr))
        frames = []

        for index in range(frame_count):
            if valid_sheet:
                width = sheet.width() // frame_count
                image = sheet.copy(
                    index * width, 0, width, sheet.height()
                )
            else:
                image = self._pixel_frame(
                    key,
                    state,
                    index,
                    frame_count,
                    boss=size >= 48,
                )

            image = image.scaled(
                physical_size,
                physical_size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            pixmap = QPixmap.fromImage(image)
            pixmap.setDevicePixelRatio(dpr)
            frames.append(pixmap)

        result = tuple(frames)
        self._cache[cache_key] = result
        return result

    @staticmethod
    def _pixel_frame(
        key: str,
        state: AnimationState,
        frame: int,
        count: int,
        *,
        boss: bool,
    ) -> QImage:
        image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(Qt.PenStyle.NoPen)

        aliases = {
            "warlock": "pyromancer",
            "priest": "paladin",
            "fire_imp": "imp",
            # Расширенный бестиарий v1.4.0 опирается на уже прорисованные
            # силуэты, сохраняя узнаваемость и читаемость на малом экране.
            "bone_archer": "skeleton",
            "grave_horror": "imp",
            "ash_reaver": "skeleton",
            "plague_ghoul": "spider",
            "bog_witch": "dryad",
            "mangrove_brute": "golem",
            "cinder_spawn": "imp",
            "magma_giant": "golem",
            "rift_herald": "inquisitor",
        }
        key = aliases.get(key, key)

        hero_keys = {
            "knight", "assassin", "pyromancer",
            "ranger", "necromancer", "paladin",
        }
        is_hero = key in hero_keys
        boss = boss and not is_hero

        phase = frame % 4
        progress = frame / max(1, count - 1)
        walking = state == AnimationState.RUN
        attacking = state == AnimationState.ATTACK
        casting = state == AnimationState.CAST

        bob = (0, -1, 0, 1)[phase] if walking else (0, 0, -1, 0)[phase]
        stride = (-2, 0, 2, 0)[phase] if walking else 0

        if state == AnimationState.DIE:
            p.setOpacity(max(0.15, 1.0 - progress * 0.80))
            p.translate(0, int(progress * 20))
            p.scale(1.0, max(0.25, 1.0 - progress * 0.75))
        else:
            p.translate(0, bob)

        def rect(x, y, w, h, color):
            p.fillRect(int(x), int(y), int(w), int(h), QColor(color))

        def poly(points, color):
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygon([QPoint(x, y) for x, y in points]))

        def line(x1, y1, x2, y2, color, width=1):
            from PySide6.QtGui import QPen
            p.setPen(QPen(QColor(color), width))
            p.drawLine(x1, y1, x2, y2)
            p.setPen(Qt.PenStyle.NoPen)

        outline = "#15121e"
        skin = "#d8ae85"
        bone = "#d6cfb3"
        steel = "#8796ad"
        shine = "#d2dde3"
        gold = "#d2a65d"

        # Все персонажи ориентированы вправо.
        # BattleStage зеркалит врагов при рисовании.
        if is_hero:
            cloth = {
                "knight": "#5b3452",
                "assassin": "#443450",
                "pyromancer": "#713b99",
                "ranger": "#3d654c",
                "necromancer": "#355d59",
                "paladin": "#ddd2ad",
            }[key]

            poly([(9, 14), (20, 14), (24, 29), (6, 29)], outline)
            poly([(10, 14), (19, 14), (22, 27), (8, 27)], cloth)
            rect(10, 16, 3, 10, QColor(cloth).lighter(135).name())
            rect(17, 16, 3, 11, QColor(cloth).darker(145).name())

            rect(10 + stride, 27, 5, 4, outline)
            rect(18 - stride, 27, 5, 4, outline)
            rect(10 + stride, 27, 4, 2, "#655663")
            rect(18 - stride, 27, 4, 2, "#655663")

            if key in ("knight", "paladin"):
                rect(10, 7, 11, 9, outline)
                rect(11, 6, 9, 9, steel if key == "knight" else gold)
                rect(12, 6, 3, 7, shine)
                rect(11, 11, 9, 2, "#202332")
                rect(18, 11, 2, 1, "#e2b756")
                rect(15, 5, 3, 3, "#a74655")

                rect(9, 16, 14, 10, outline)
                rect(10, 16, 12, 8, steel)
                rect(11, 17, 4, 6, shine)
                rect(16, 17, 4, 6, "#58677e")
                rect(9, 16, 4, 4, "#b4c0cd")
                rect(20, 16, 4, 4, "#aeb9c5")
                rect(10, 24, 12, 2, gold)

                if key == "knight":
                    poly(
                        [(4, 17), (10, 15), (14, 18), (12, 25), (8, 29), (4, 25)],
                        outline,
                    )
                    poly(
                        [(5, 18), (10, 17), (12, 19), (10, 25), (8, 27), (5, 24)],
                        "#536b96",
                    )
                    rect(8, 18, 2, 8, gold)
                    rect(6, 20, 5, 2, gold)

                    if attacking:
                        rect(23, 17, 7, 2, shine)
                        rect(22, 15, 2, 6, gold)
                        rect(19, 17, 3, 2, "#715044")
                        rect(29, 16, 2, 1, "#eff4df")
                    else:
                        rect(25, 6, 2, 16, shine)
                        rect(24, 7, 1, 13, "#748eac")
                        rect(22, 21, 7, 2, gold)
                        rect(25, 23, 2, 5, "#604433")
                else:
                    rect(26, 8, 2, 22, "#93603a")
                    rect(25, 8, 1, 21, gold)
                    rect(24, 5, 6, 5, "#eadbad")
                    rect(26, 3, 2, 9, "#fff0c2")
                    rect(23, 7, 8, 2, "#fff0c2")
                    rect(14, 18, 2, 6, gold)
                    rect(12, 20, 6, 2, gold)

            elif key in ("assassin", "ranger"):
                hood = "#342943" if key == "assassin" else "#2a4b36"
                poly([(9, 12), (10, 6), (15, 3), (21, 7), (23, 15)], outline)
                poly([(10, 12), (12, 7), (16, 5), (20, 8), (21, 14)], hood)
                rect(13, 10, 7, 4, "#11131b")
                rect(17, 10, 2, 1, "#dfbd71")
                rect(20, 13, 3, 7, hood)
                rect(10, 22, 11, 2, "#8a6540")
                rect(14, 21, 3, 3, gold)

                if key == "assassin":
                    reach = (2, 5, 7, 3)[phase] if attacking else 0
                    rect(21, 18, 4, 3, skin)
                    poly(
                        [(24, 18), (29 + min(2, reach), 15), (27, 21), (24, 21)],
                        shine,
                    )
                    rect(23, 18, 1, 4, gold)
                    rect(6, 21, 5, 2, skin)
                    poly([(4, 17), (7, 20), (7, 25)], "#b6c7d9")
                else:
                    line(26, 10, 29, 18, "#bb8956", 2)
                    line(29, 18, 26, 27, "#bb8956", 2)
                    line(26, 10, 26, 27, "#d3c4a6")
                    line(21, 18, 31, 18, "#d9d7bf")
                    rect(21, 17, 3, 3, skin)
                    rect(7, 12, 3, 10, "#664531")
                    line(7, 10, 10, 6, "#c1b797")

            else:
                # Колдун/пиромант: широкополая остроконечная шляпа.
                # Некромант: тёмная корона-капюшон и посох с черепом.
                hat = cloth if key == "pyromancer" else "#24453f"

                rect(12, 10, 8, 7, skin)
                rect(17, 12, 2, 1, "#241e2d")
                rect(11, 15, 8, 3, "#c2b8ba")
                rect(12, 17, 5, 4, "#d8ccd0")

                poly([(6, 11), (13, 8), (17, 1), (20, 9), (25, 12)], outline)
                poly([(8, 10), (14, 8), (17, 3), (19, 10), (23, 11)], hat)
                rect(11, 9, 11, 2, gold)
                rect(16, 5, 2, 2, "#ab7acc")

                rect(24, 8, 2, 22, "#75513d")
                rect(25, 9, 1, 20, "#b38c59")

                if key == "necromancer":
                    rect(22, 5, 7, 6, bone)
                    rect(23, 7, 2, 2, outline)
                    rect(26, 7, 2, 2, outline)
                    rect(24, 10, 3, 2, bone)
                    rect(15, 22, 3, 4, "#70bf91")
                else:
                    poly([(21, 7), (25, 2), (29, 7), (25, 11)], "#431f68")
                    poly([(23, 6), (25, 3), (27, 7), (25, 9)], "#d098fa")
                    rect(25, 4, 1, 3, "#f1d2ff")

            if casting:
                colors = ("#7250b8", "#a774e0", "#e1b2ff", "#b781ed")
                radius = (2, 3, 4, 3)[phase]
                poly(
                    [(27, 12 - radius), (27 + radius, 12),
                     (27, 12 + radius), (27 - radius, 12)],
                    colors[phase],
                )
                rect(26, 11, 2, 2, "#f7ddff")
                rect(22, 4 + phase, 1, 2, "#c698ef")

        elif boss:
            # Рогатый бронированный демон с крыльями.
            poly([(11, 13), (3, 7), (1, 21), (9, 19)], "#442639")
            poly([(21, 13), (29, 7), (31, 21), (23, 19)], "#442639")
            line(4, 11, 8, 17, "#875063")
            line(28, 11, 24, 17, "#875063")

            poly([(8, 15), (24, 15), (26, 27), (6, 27)], outline)
            rect(9, 15, 14, 11, "#70414c")
            rect(11, 16, 4, 8, "#a16a69")
            rect(17, 16, 4, 8, "#462c3e")
            rect(13, 7, 9, 10, "#994751")
            poly([(13, 9), (7, 3), (10, 11)], "#c3a785")
            poly([(21, 9), (26, 2), (24, 12)], "#c3a785")
            rect(15, 10, 2, 2, "#ffd55a")
            rect(20, 10, 2, 2, "#ffd55a")
            rect(17, 14, 5, 1, "#e8cfb0")
            rect(8 + stride, 26, 6, 5, "#392536")
            rect(20 - stride, 26, 6, 5, "#392536")
            rect(28, 12, 2, 18, "#b4a385")
            poly([(26, 10), (31, 7), (31, 18), (27, 16)], "#c75f50")

        elif key == "bat":
            wing = (5, 10, 16, 10)[phase]
            poly(
                [(14, 16), (5, wing), (0, wing + 3),
                 (4, 20), (8, 17), (11, 21)],
                "#33233f",
            )
            poly(
                [(18, 16), (27, wing), (31, wing + 3),
                 (28, 20), (24, 17), (21, 21)],
                "#33233f",
            )
            line(3, wing + 3, 13, 17, "#8d5479")
            line(29, wing + 3, 19, 17, "#8d5479")
            rect(13, 12, 7, 12, "#68415f")
            poly([(13, 14), (13, 7), (16, 12)], "#8e577b")
            poly([(17, 12), (20, 7), (20, 15)], "#8e577b")
            rect(16, 14, 2, 1, "#ffb365")
            rect(19, 14, 1, 1, "#ffb365")

        elif key == "spider":
            for side in (-1, 1):
                for leg in range(4):
                    sy = 15 + leg * 3
                    ex = 16 + side * (12 + (leg % 2))
                    ey = sy - 4 + ((phase + leg) % 2) * 3
                    line(16 + side * 4, sy, ex, ey, "#312a40", 2)
                    line(ex, ey, ex + side, ey + 6, "#66546e")
            poly([(8, 16), (11, 10), (20, 10), (24, 17), (20, 25), (11, 25)],
                 "#3c2d48")
            rect(12, 12, 7, 3, "#6a4768")
            rect(19, 17, 8, 7, "#201c2e")
            rect(23, 18, 2, 1, "#ed695b")
            rect(26, 18, 1, 1, "#ed695b")
            line(25, 22, 28, 25, "#c0a28c")
            line(22, 23, 24, 26, "#c0a28c")

        elif key in ("skeleton", "sentinel"):
            armor = key == "sentinel"

            rect(12, 5, 10, 9, outline)
            rect(13, 5, 8, 8, bone if not armor else steel)
            rect(14, 8, 2, 2, "#241c28")
            rect(19, 8, 2, 2, "#241c28")
            rect(16, 12, 4, 2, "#b1a58d")

            rect(16, 14, 2, 11, bone)
            for y in (16, 19, 22):
                rect(11, y, 12, 1, bone)
                rect(11, y, 1, 2, bone)
                rect(22, y, 1, 2, bone)

            if armor:
                rect(10, 15, 14, 9, "#66718c")
                rect(12, 16, 4, 6, "#a0aec1")
                rect(18, 16, 3, 6, "#3f465e")

            line(12, 24, 10 + stride, 30, bone, 2)
            line(21, 24, 23 - stride, 30, bone, 2)
            line(22, 16, 26, 21, bone, 2)
            rect(26, 9 if not attacking else 17, 2, 13, "#b7bec5")
            rect(24, 22, 6, 2, "#856744")

        elif key == "imp":
            tail = (0, 1, 0, -1)[phase]
            poly([(8, 24), (3, 23), (1, 17 + tail), (4, 20), (10, 20)], "#a54432")
            poly([(10, 14), (22, 14), (24, 25), (8, 25)], "#982f30")
            rect(12, 15, 5, 8, "#de653e")
            rect(13, 6, 10, 9, "#c34834")
            poly([(13, 8), (10, 3), (16, 7)], "#e0b477")
            poly([(20, 7), (24, 2), (23, 11)], "#e0b477")
            rect(19, 9, 3, 2, "#ffe069")
            rect(18, 13, 5, 1, "#25171e")
            rect(10 + stride, 25, 5, 5, "#6b2831")
            rect(20 - stride, 25, 5, 5, "#6b2831")

            flame_height = (5, 8, 6, 9)[phase]
            poly([(25, 19), (27, 19 - flame_height), (31, 19), (28, 23)], "#ed742e")
            poly([(27, 19), (28, 15), (30, 20)], "#ffe376")

        elif key == "wolf":
            poly([(4, 17), (10, 13), (22, 15), (27, 20), (20, 25), (7, 24)], "#454153")
            rect(8, 16, 12, 5, "#777181")
            poly([(21, 15), (24, 9), (27, 15), (31, 18), (29, 22), (22, 22)], "#595364")
            rect(27, 16, 2, 1, "#dcbb6b")
            poly([(4, 18), (1, 12), (7, 17)], "#646074")
            rect(8 + stride, 23, 3, 7, "#292635")
            rect(20 - stride, 23, 3, 7, "#292635")

        elif key == "golem":
            poly([(7, 13), (13, 10), (23, 13), (27, 26), (6, 26)], "#242432")
            rect(10, 14, 13, 11, "#48424f")
            rect(12, 6, 11, 10, "#514953")
            rect(13, 6, 4, 7, "#74606b")
            rect(18, 10, 4, 2, "#f6984d")
            line(15, 16, 18, 20, "#d57840")
            line(18, 20, 16, 24, "#d57840")
            rect(4, 16, 6, 11, "#5b505b")
            rect(23, 16, 6, 11, "#3b3543")
            rect(9 + stride, 25, 6, 6, "#302c3b")
            rect(20 - stride, 25, 6, 6, "#302c3b")

        else:
            # Призраки, дриады и инквизиторы — отдельные палитры.
            palettes = {
                "wraith": ("#365d77", "#78afc2", "#d9f2eb"),
                "dryad": ("#395b42", "#72a26b", "#dac37a"),
                "inquisitor": ("#593c62", "#98618f", "#efad88"),
                "funeral_wraith": ("#5a4a7d", "#a88ac2", "#ecd2ff"),
                "void_reaper": ("#24304d", "#6b7fb0", "#cf9aff"),
                "distortion_eye": ("#6a2f52", "#c25a8f", "#ffd0ff"),
            }
            base, light, eyes = palettes.get(
                key, ("#584262", "#a27093", "#e6be78")
            )

            poly([(10, 11), (15, 5), (22, 10), (25, 27),
                  (20, 25), (16, 30), (12, 26), (6, 29)], outline)
            poly([(11, 12), (16, 7), (21, 11), (23, 25),
                  (18, 24), (15, 28), (12, 24), (8, 26)], base)
            rect(13, 14, 3, 10, light)
            rect(15, 11, 7, 4, "#1b202b")
            rect(18, 12, 3, 1, eyes)
            line(24, 15, 28, 23, light, 2)

            if key == "dryad":
                line(14, 8, 10, 2, "#8c754f", 2)
                line(20, 9, 24, 2, "#8c754f", 2)
                rect(8, 3, 4, 2, "#83ab62")
                rect(23, 4, 4, 2, "#83ab62")

        if state == AnimationState.HURT:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
            p.fillRect(0, 0, 32, 32, QColor(255, 231, 210, 70))

        p.end()
        return image
