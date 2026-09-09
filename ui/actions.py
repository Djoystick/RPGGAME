from __future__ import annotations

import time
from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QObject, Signal

import config as C
from engine.combat_manager import CombatManager
from engine.cube_synth import CubeSynth
from engine.runes_tree import RunesTree
from engine.save_manager import SaveError, SaveManager
from engine.state import GameData, GameState
from models.hero import Hero, HeroBuild, PRIMARY_STAT_KEYS, default_build
from models.item import EquipmentSlot, RARITY_ORDER


class UiActions(QObject):
    error = Signal(str)
    notice = Signal(str)

    def __init__(
        self,
        state: GameState,
        saves: SaveManager,
        combat: CombatManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.saves = saves
        self.combat = combat
        self.runes = RunesTree()
        self.cube = CubeSynth(self.runes)

    def run(self, operation: Callable) -> bool:
        """Граница обработки пользовательских ошибок."""
        try:
            operation()
            return True
        except (ValueError, SaveError, RuntimeError) as exc:
            self.error.emit(str(exc))
            return False

    def _transaction(self, transform: Callable[[GameData], GameData]) -> GameData:
        self.state.assert_owner_thread()

        if self.combat.running:
            self.combat.flush()

        before = self.state.data
        after = transform(before)
        after = replace(
            after,
            last_active_timestamp=max(
                time.time(),
                before.last_active_timestamp,
            ),
        )

        self.saves.write(after)
        self.state.commit(before, after)
        return after

    def move_items(self, ids: tuple[str, ...], to_backpack: bool) -> None:
        selected = set(ids)
        if not selected:
            raise ValueError("Сначала выберите предметы")

        def transform(data: GameData) -> GameData:
            source = data.stash if to_backpack else data.backpack
            target = data.backpack if to_backpack else data.stash
            capacity = (
                C.DEFAULT_BACKPACK_CAPACITY
                if to_backpack else data.stash_capacity
            )

            available = {item.item_id for item in source}
            if not selected <= available:
                raise ValueError("Часть выбранных предметов уже перемещена")

            moving = tuple(item for item in source if item.item_id in selected)
            if len(target) + len(moving) > capacity:
                raise ValueError("В целевом контейнере недостаточно места")

            remaining = tuple(
                item for item in source if item.item_id not in selected
            )

            if to_backpack:
                return replace(data, stash=remaining, backpack=target + moving)
            return replace(data, backpack=remaining, stash=target + moving)

        self._transaction(transform)
        self.notice.emit(f"Перемещено предметов: {len(selected)}")

    def move_all(self, to_backpack: bool) -> None:
        data = self.state.data
        source = data.stash if to_backpack else data.backpack
        target = data.backpack if to_backpack else data.stash
        capacity = (
            C.DEFAULT_BACKPACK_CAPACITY
            if to_backpack else data.stash_capacity
        )
        free = max(0, capacity - len(target))

        ids = tuple(item.item_id for item in source[:free])
        if not ids:
            raise ValueError("Нет предметов для переноса или контейнер заполнен")

        self.move_items(ids, to_backpack)

    def sort_stash(self) -> None:
        self._transaction(lambda data: replace(
            data,
            stash=tuple(sorted(
                data.stash,
                key=lambda item: (
                    -RARITY_ORDER.index(item.rarity),
                    -item.level,
                    item.slot.value,
                    item.item_id,
                ),
            )),
        ))
        self.notice.emit("Тайник отсортирован по редкости и уровню")

    @staticmethod
    def _build(data: GameData, hero_id: str) -> HeroBuild:
        if hero_id not in {hero.hero_id for hero in data.party}:
            raise ValueError("Герой больше не входит в активный отряд")

        return next(
            (build for build in data.hero_builds if build.hero_id == hero_id),
            default_build(hero_id),
        )

    @staticmethod
    def _replace_build(data: GameData, build: HeroBuild):
        return tuple(
            entry for entry in data.hero_builds
            if entry.hero_id != build.hero_id
        ) + (build,)

    def equip(self, hero_id: str, item_id: str) -> None:
        def transform(data: GameData) -> GameData:
            item = next(
                (entry for entry in data.backpack if entry.item_id == item_id),
                None,
            )
            if item is None:
                raise ValueError("Предмет отсутствует в рюкзаке")

            build = self._build(data, hero_id)
            updated, previous = build.equip(item)

            backpack = tuple(
                entry for entry in data.backpack if entry.item_id != item_id
            )
            if previous is not None:
                backpack += (previous,)

            return replace(
                data,
                backpack=backpack,
                hero_builds=self._replace_build(data, updated),
            )

        self._transaction(transform)
        self.notice.emit("Экипировка обновлена")

    def unequip(self, hero_id: str, slot: EquipmentSlot) -> None:
        def transform(data: GameData) -> GameData:
            build = self._build(data, hero_id)
            item = next(
                (entry for entry in build.equipment if entry.slot == slot),
                None,
            )
            if item is None:
                raise ValueError("Слот пуст")
            if len(data.backpack) >= C.DEFAULT_BACKPACK_CAPACITY:
                raise ValueError("Рюкзак заполнен")

            updated = replace(
                build,
                equipment=tuple(
                    entry for entry in build.equipment if entry.slot != slot
                ),
            )

            return replace(
                data,
                backpack=data.backpack + (item,),
                hero_builds=self._replace_build(data, updated),
            )

        self._transaction(transform)
        self.notice.emit("Предмет снят в рюкзак")

    def buy_rune(self, node_id: str) -> None:
        self._transaction(
            lambda data: self.runes.calculate_purchase(data, node_id)
        )
        self.notice.emit(f"Открыта руна: {self.runes.nodes[node_id].name}")

    def synthesize(self, ids: tuple[str, ...]) -> None:
        result_holder = []

        def transform(data: GameData) -> GameData:
            result = self.cube.calculate(data, ids)
            result_holder.append(result)
            return result.after

        self._transaction(transform)
        item = result_holder[0].item
        self.notice.emit(
            f"Синтез: {item.display_name} · {item.rarity.value} · Lv.{item.level}"
        )

    def allocate_stat(self, hero_id: str, stat_key: str) -> None:
        if stat_key not in PRIMARY_STAT_KEYS:
            raise ValueError("Неизвестная характеристика")

        def transform(data: GameData) -> GameData:
            build = self._build(data, hero_id)
            snapshot = next(
                hero for hero in data.party
                if hero.hero_id == hero_id
            )
            hero = Hero.from_state(snapshot, build)

            if hero.free_stat_points <= 0:
                raise ValueError("Нет свободных очков характеристик")

            allocation = list(build.allocated_stats)
            allocation[PRIMARY_STAT_KEYS.index(stat_key)] += 1

            updated = replace(
                build,
                allocated_stats=tuple(allocation),
            )
            return replace(
                data,
                hero_builds=self._replace_build(data, updated),
            )

        self._transaction(transform)
        self.notice.emit("Очко характеристики распределено")
