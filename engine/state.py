from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import ClassVar

from PySide6.QtCore import QObject, QThread, Signal

import config as C
from models.hero import HeroBuild
from models.item import Item as ItemDrop


def require_int(name: str, value: int, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name}: ожидается целое число >= {minimum}")


def require_number(
    name: str,
    value: float,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> None:
    if type(value) not in (int, float):
        raise ValueError(f"{name}: ожидается число")

    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name}: недопустимое значение {value}")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name}: значение больше {maximum}")


@dataclass(frozen=True)
class HeroState:
    hero_id: str
    name: str
    max_hp: int = 100
    hp: int = 100
    attack: int = 10
    defense: int = 0
    total_exp: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.hero_id, str) or not self.hero_id:
            raise ValueError("У героя должен быть непустой hero_id")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("У героя должно быть имя")

        require_int("max_hp", self.max_hp, 1)
        require_int("hp", self.hp)
        require_int("attack", self.attack)
        require_int("defense", self.defense)
        require_int("total_exp", self.total_exp)

        if self.hp > self.max_hp:
            raise ValueError("hp не может превышать max_hp")


@dataclass(frozen=True)
class FarmProfile:
    average_wave_clear_seconds: float = C.DEFAULT_WAVE_CLEAR_SECONDS
    gold_per_wave: int = C.DEFAULT_GOLD_PER_WAVE
    exp_per_wave: int = C.DEFAULT_EXP_PER_WAVE

    # 0.25 означает +25%, а не итоговый множитель x0.25.
    gold_bonus: float = 0.0
    sale_bonus: float = 0.0
    drop_chance: float = C.DEFAULT_DROP_CHANCE

    def __post_init__(self) -> None:
        require_number(
            "average_wave_clear_seconds",
            self.average_wave_clear_seconds,
            C.MIN_WAVE_CLEAR_SECONDS,
        )
        require_int("gold_per_wave", self.gold_per_wave)
        require_int("exp_per_wave", self.exp_per_wave)
        require_number("gold_bonus", self.gold_bonus)
        require_number("sale_bonus", self.sale_bonus)
        require_number("drop_chance", self.drop_chance, 0.0, 1.0)


def default_party() -> tuple[HeroState, ...]:
    return (
        HeroState("knight", "Рыцарь", 250, 250, 14, 20),
        HeroState("assassin", "Ассасин", 130, 130, 28, 5),
        HeroState("warlock", "Колдун", 110, 110, 32, 3),
        HeroState("priest", "Жрец", 150, 150, 12, 7),
    )


@dataclass(frozen=True)
class GameData:
    gold: int = 0
    cleared_waves: int = 0

    # Рациональная доля незавершённой волны: "0", "1/2", ...
    # Строка нужна для точного JSON round-trip.
    wave_fraction: str = "0"

    party: tuple[HeroState, ...] = field(default_factory=default_party)
    stash: tuple[ItemDrop, ...] = ()
    stash_capacity: int = C.DEFAULT_STASH_CAPACITY

    farm: FarmProfile = field(default_factory=FarmProfile)
    offline_cap_level: int = 0
    offline_efficiency_level: int = 0

    # Следующий герой, которому достанется остаточная единица XP.
    exp_cursor: int = 0
    last_active_timestamp: float = field(default_factory=time.time)

    hero_builds: tuple[HeroBuild, ...] = ()
    unlocked_runes: tuple[str, ...] = ()
    backpack: tuple[ItemDrop, ...] = ()
    reward_claims: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_int("gold", self.gold)
        require_int("cleared_waves", self.cleared_waves)
        require_int("stash_capacity", self.stash_capacity)
        require_int("offline_cap_level", self.offline_cap_level)
        require_int("offline_efficiency_level", self.offline_efficiency_level)
        require_int("exp_cursor", self.exp_cursor)
        require_number("last_active_timestamp", self.last_active_timestamp)

        if self.offline_cap_level >= len(C.OFFLINE_CAP_SECONDS):
            raise ValueError("Неизвестная ступень потолка оффлайна")
        if self.offline_efficiency_level >= len(C.OFFLINE_EFFICIENCIES):
            raise ValueError("Неизвестная ступень эффективности")

        if not isinstance(self.wave_fraction, str):
            raise ValueError("wave_fraction должна быть строкой")
        try:
            fraction = Fraction(self.wave_fraction)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("Некорректная доля волны") from exc
        if not 0 <= fraction < 1:
            raise ValueError("Доля волны должна находиться в [0, 1)")

        if type(self.party) is not tuple:
            raise ValueError("party должна быть tuple")
        if not 1 <= len(self.party) <= C.MAX_PARTY_SIZE:
            raise ValueError("Отряд должен содержать от 1 до 4 героев")
        if not all(isinstance(hero, HeroState) for hero in self.party):
            raise ValueError("Некорректные данные героев")
        if len({hero.hero_id for hero in self.party}) != len(self.party):
            raise ValueError("Повторяющиеся hero_id")
        if self.exp_cursor >= len(self.party):
            raise ValueError("exp_cursor вне состава отряда")

        if type(self.stash) is not tuple:
            raise ValueError("stash должна быть tuple")
        if not all(isinstance(item, ItemDrop) for item in self.stash):
            raise ValueError("Некорректные предметы")
        if len(self.stash) > self.stash_capacity:
            raise ValueError("Тайник переполнен")
        if len({item.item_id for item in self.stash}) != len(self.stash):
            raise ValueError("Повторяющиеся item_id")

        if not isinstance(self.farm, FarmProfile):
            raise ValueError("Некорректный профиль фарма")

        if type(self.hero_builds) is not tuple:
            raise ValueError("hero_builds должна быть tuple")
        if not all(isinstance(build, HeroBuild) for build in self.hero_builds):
            raise ValueError("Некорректные сборки героев")

        build_ids = [build.hero_id for build in self.hero_builds]
        if len(build_ids) != len(set(build_ids)):
            raise ValueError("Повторяющиеся сборки героев")

        if type(self.backpack) is not tuple:
            raise ValueError("backpack должна быть tuple")

        if not all(isinstance(item, ItemDrop) for item in self.backpack):
            raise ValueError("Некорректные предметы рюкзака")

        if len(self.backpack) > C.DEFAULT_BACKPACK_CAPACITY:
            raise ValueError("Рюкзак переполнен")

        all_item_ids = [
            item.item_id
            for item in (*self.stash, *self.backpack)
        ]
        all_item_ids.extend(
            item.item_id
            for build in self.hero_builds
            for item in build.equipment
        )
        if len(all_item_ids) != len(set(all_item_ids)):
            raise ValueError(
                "Предмет одновременно находится в нескольких контейнерах"
            )

        if type(self.unlocked_runes) is not tuple:
            raise ValueError("unlocked_runes должна быть tuple")
        if not all(
            isinstance(node_id, str) and node_id
            for node_id in self.unlocked_runes
        ):
            raise ValueError("Некорректные идентификаторы рун")
        if len(self.unlocked_runes) != len(set(self.unlocked_runes)):
            raise ValueError("Повторяющиеся руны")

    @property
    def current_wave(self) -> int:
        return self.cleared_waves + 1

    @property
    def offline_cap_seconds(self) -> int:
        return C.OFFLINE_CAP_SECONDS[self.offline_cap_level]

    @property
    def offline_efficiency(self) -> float:
        return C.OFFLINE_EFFICIENCIES[self.offline_efficiency_level]

    @property
    def computed_squad(self):
        # Локальный импорт исключает циклический импорт модулей.
        from engine.runes_tree import RunesTree
        return RunesTree().squad(self)

    @property
    def squad_attack(self) -> int:
        return int(sum(
            member.stats.magical_damage
            if member.hero.definition.magical
            else member.stats.physical_damage
            for member in self.computed_squad
        ))

    @property
    def squad_max_hp(self) -> int:
        return sum(
            member.stats.max_hp
            for member in self.computed_squad
        )

    @property
    def squad_hp(self) -> int:
        return sum(
            snapshot.hp * member.stats.max_hp // snapshot.max_hp
            for snapshot, member in zip(self.party, self.computed_squad)
        )


class _SingletonQObject(type(QObject)):
    _instances: ClassVar[dict[type, QObject]] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class GameState(QObject, metaclass=_SingletonQObject):
    gold_changed = Signal(object)            # Новый баланс: Python int.
    exp_gained = Signal(str, object)         # hero_id, начисленный XP.
    item_dropped = Signal(object)           # ItemDrop, помещённый в тайник.

    # Пакетный контракт: первая пройденная волна, количество волн.
    # Для активного боя количество будет равно 1.
    wave_cleared = Signal(object, object)

    party_changed = Signal(object)
    stash_changed = Signal(object)
    backpack_changed = Signal(object)
    runes_changed = Signal(object)
    builds_changed = Signal(object)
    state_changed = Signal(object)          # Полный GameData.
    offline_completed = Signal(object)      # OfflineResult.
    state_loaded = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._data = GameData()

    @classmethod
    def instance(cls) -> GameState:
        return cls()

    def assert_owner_thread(self) -> None:
        if QThread.currentThread() != self.thread():
            raise RuntimeError(
                "GameState разрешено изменять только в его Qt-потоке"
            )

    @property
    def data(self) -> GameData:
        return self._data

    def load(self, data: GameData) -> None:
        """Вызывается при загрузке, а не для выдачи игровых наград."""
        self.assert_owner_thread()
        if not isinstance(data, GameData):
            raise TypeError("Ожидается GameData")

        self._data = data
        self.state_loaded.emit(data)
        self.state_changed.emit(data)

    def commit(
        self,
        expected: GameData,
        updated: GameData,
        offline_result: object | None = None,
    ) -> None:
        """Применить снимок, только если исходное состояние ещё актуально."""
        self.assert_owner_thread()

        if self._data is not expected:
            raise RuntimeError("Попытка применить устаревший снимок")
        if not isinstance(updated, GameData):
            raise TypeError("Ожидается GameData")

        previous = self._data

        # Сначала заменяем все данные, только затем рассылаем события.
        self._data = updated

        if previous.gold != updated.gold:
            self.gold_changed.emit(updated.gold)

        old_exp = {hero.hero_id: hero.total_exp for hero in previous.party}
        for hero in updated.party:
            gained = hero.total_exp - old_exp.get(hero.hero_id, hero.total_exp)
            if gained > 0:
                self.exp_gained.emit(hero.hero_id, gained)

        if previous.party != updated.party:
            self.party_changed.emit(updated.party)

        if previous.stash != updated.stash:
            old_ids = {item.item_id for item in previous.stash}
            for item in updated.stash:
                if item.item_id not in old_ids:
                    self.item_dropped.emit(item)
            self.stash_changed.emit(updated.stash)

        if previous.backpack != updated.backpack:
            self.backpack_changed.emit(updated.backpack)

        waves = updated.cleared_waves - previous.cleared_waves
        if waves > 0:
            self.wave_cleared.emit(previous.current_wave, waves)

        if previous.unlocked_runes != updated.unlocked_runes:
            self.runes_changed.emit(updated.unlocked_runes)

        if previous.hero_builds != updated.hero_builds:
            self.builds_changed.emit(updated.hero_builds)

        self.state_changed.emit(updated)

        if offline_result is not None:
            self.offline_completed.emit(offline_result)

    def add_gold(self, amount: int) -> None:
        require_int("amount", amount)
        before = self.data
        self.commit(before, replace(before, gold=before.gold + amount))

    def spend_gold(self, amount: int) -> bool:
        self.assert_owner_thread()
        require_int("amount", amount)

        before = self.data
        if before.gold < amount:
            return False

        self.commit(before, replace(before, gold=before.gold - amount))
        return True

    def set_farm_profile(self, profile: FarmProfile) -> None:
        before = self.data
        self.commit(before, replace(before, farm=profile))

    def set_offline_upgrades(
        self,
        cap_level: int,
        efficiency_level: int,
    ) -> None:
        """Применение уже рассчитанных бонусов. Покупки — задача дерева рун."""
        before = self.data
        self.commit(
            before,
            replace(
                before,
                offline_cap_level=cap_level,
                offline_efficiency_level=efficiency_level,
            ),
        )

    def set_party(self, party: tuple[HeroState, ...]) -> None:
        before = self.data
        self.commit(before, replace(before, party=party, exp_cursor=0))
