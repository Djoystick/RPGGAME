from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType

import config as C
from engine.save_manager import SaveManager
from engine.state import GameData, GameState
from models.hero import Hero, SecondaryStats
from models.stats import StatBlock


class RuneError(ValueError):
    pass


class Sector(str, Enum):
    WAR = "war"
    ETHER = "ether"
    VITALITY = "vitality"
    GREED = "greed"
    CHRONOMANCY = "chronomancy"


SECTOR_NAMES = {
    Sector.WAR: "Война",
    Sector.ETHER: "Эфир",
    Sector.VITALITY: "Живучесть",
    Sector.GREED: "Алчность",
    Sector.CHRONOMANCY: "Хрономантия",
}


@dataclass(frozen=True)
class RuneEffects:
    stats: StatBlock = field(default_factory=StatBlock)
    gold_bonus: float = 0.0
    sale_bonus: float = 0.0
    drop_bonus: float = 0.0

    cap_steps: int = 0
    efficiency_steps: int = 0

    synthesis_bonus: float = 0.0
    active_speed_bonus: float = 0.0

    keystones: tuple[str, ...] = ()

    def __add__(self, other: RuneEffects) -> RuneEffects:
        return RuneEffects(
            stats=self.stats + other.stats,
            gold_bonus=self.gold_bonus + other.gold_bonus,
            sale_bonus=self.sale_bonus + other.sale_bonus,
            drop_bonus=self.drop_bonus + other.drop_bonus,
            cap_steps=self.cap_steps + other.cap_steps,
            efficiency_steps=self.efficiency_steps + other.efficiency_steps,
            synthesis_bonus=self.synthesis_bonus + other.synthesis_bonus,
            active_speed_bonus=self.active_speed_bonus + other.active_speed_bonus,
            keystones=tuple(sorted(set(self.keystones + other.keystones))),
        )


@dataclass(frozen=True)
class RuneNode:
    node_id: str
    name: str
    sector: Sector | None
    cost: int
    prerequisites: tuple[str, ...]
    effects: RuneEffects
    position: tuple[float, float]
    keystone: bool = False


@dataclass(frozen=True)
class SquadMember:
    hero: Hero
    stats: SecondaryStats


def node_cost(index: int, keystone: bool = False) -> int:
    """
    C(i) = ceil_to_1000(5000 * 1.45^i).
    Расчёт через целые числа, без float в экономике.
    """
    numerator = 5000 * 145**index
    denominator = 100**index

    cost = (
        (numerator + denominator * 1000 - 1)
        // (denominator * 1000)
        * 1000
    )

    return max(cost, 250_000_000) if keystone else cost


def normal_effect(sector: Sector, index: int) -> RuneEffects:
    if sector == Sector.WAR:
        options = (
            RuneEffects(stats=StatBlock(physical_bonus=0.02)),
            RuneEffects(stats=StatBlock(strength=2)),
            RuneEffects(stats=StatBlock(crit_damage=0.05)),
            RuneEffects(stats=StatBlock(crit_chance=0.01)),
        )
    elif sector == Sector.ETHER:
        options = (
            RuneEffects(stats=StatBlock(magical_bonus=0.02)),
            RuneEffects(stats=StatBlock(intelligence=2)),
            RuneEffects(stats=StatBlock(mana=10)),
        )
    elif sector == Sector.VITALITY:
        options = (
            RuneEffects(stats=StatBlock(hp_bonus=0.03)),
            RuneEffects(stats=StatBlock(armor=4)),
            RuneEffects(stats=StatBlock(vitality=2)),
            RuneEffects(stats=StatBlock(evasion=0.008)),
        )
    elif sector == Sector.GREED:
        options = (
            RuneEffects(gold_bonus=0.03),
            RuneEffects(sale_bonus=0.02),
            RuneEffects(drop_bonus=0.002),
        )
    else:
        options = (
            RuneEffects(stats=StatBlock(mana=5)),
            RuneEffects(stats=StatBlock(luck=1)),
            RuneEffects(stats=StatBlock(max_hp=5)),
        )

    return options[index % len(options)]


def build_nodes() -> dict[str, RuneNode]:
    nodes = {
        "nexus": RuneNode(
            "nexus",
            "Сердце Бездны",
            None,
            0,
            (),
            RuneEffects(),
            (0.0, 0.0),
        )
    }

    # Цепь родителей в двоичном дереве:
    # 0 -> 1 -> 3 -> 7 -> 15.
    cap_nodes = {
        0: "Сон Бездны I — 3 часа",
        1: "Сон Бездны II — 4 часа",
        3: "Сон Бездны III — 6 часов",
        7: "Вневременной Покой — 8 часов",
        15: "Вечность Бездны — 12 часов",
    }

    # Вторая последовательная ветка: 0 -> 2 -> 5 -> 11.
    efficiency_nodes = {
        2: "Ясновидение I — 75%",
        5: "Ясновидение II — 90%",
        11: "Ясновидение III — 100%",
    }

    great_runes = {
        Sector.WAR: (
            ("Берсерк Бездны", "berserker"),
            ("Титанический Размах", "titan_sweep"),
        ),
        Sector.ETHER: (
            ("Сверхновая", "supernova"),
            ("Эфирный Щит", "ether_shield"),
        ),
        Sector.VITALITY: (
            ("Железный Монолит", "iron_monolith"),
            ("Второе Дыхание", "second_wind"),
        ),
        Sector.GREED: (
            ("Золотая Лихорадка", "gold_fever"),
            ("Алхимический Синтез", "alchemical_synthesis"),
        ),
        Sector.CHRONOMANCY: (
            ("Ускорение I", "active_speed_1"),
            ("Ускорение II", "active_speed_2"),
        ),
    }

    for sector_index, sector in enumerate(Sector):
        angle = sector_index * math.tau / len(Sector) - math.pi / 2

        for index in range(30):
            node_id = f"{sector.value}.{index:02d}"
            parent = (
                "nexus"
                if index == 0
                else f"{sector.value}.{(index - 1) // 2:02d}"
            )

            depth = (index + 1).bit_length() - 1
            first_at_depth = 2**depth - 1
            position_in_depth = index - first_at_depth
            count_at_depth = 2**depth

            spread = (
                (position_in_depth + 0.5) / count_at_depth - 0.5
            ) * 0.95
            radius = 160 + depth * 120

            position = (
                math.cos(angle + spread) * radius,
                math.sin(angle + spread) * radius,
            )

            effect = normal_effect(sector, index)
            name = f"{SECTOR_NAMES[sector]} — узел {index + 1}"
            is_keystone = index in (28, 29)

            if sector == Sector.CHRONOMANCY:
                if index in cap_nodes:
                    name = cap_nodes[index]
                    effect = RuneEffects(cap_steps=1)
                elif index in efficiency_nodes:
                    name = efficiency_nodes[index]
                    effect = RuneEffects(efficiency_steps=1)

            if is_keystone:
                name, flag = great_runes[sector][index - 28]
                effect = RuneEffects(keystones=(flag,))

                if flag == "alchemical_synthesis":
                    effect = RuneEffects(
                        synthesis_bonus=0.05,
                        keystones=(flag,),
                    )
                elif flag in ("active_speed_1", "active_speed_2"):
                    effect = RuneEffects(
                        active_speed_bonus=0.25,
                        keystones=(flag,),
                    )

            nodes[node_id] = RuneNode(
                node_id=node_id,
                name=name,
                sector=sector,
                cost=node_cost(index, is_keystone),
                prerequisites=(parent,),
                effects=effect,
                position=position,
                keystone=is_keystone,
            )

    return nodes


class RunesTree:
    def __init__(self) -> None:
        self.nodes = MappingProxyType(build_nodes())

    @property
    def edges(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (parent, node.node_id)
            for node in self.nodes.values()
            for parent in node.prerequisites
        )

    def validate_unlocked(self, unlocked: tuple[str, ...]) -> None:
        if type(unlocked) is not tuple:
            raise RuneError("Список рун должен быть tuple")
        if len(unlocked) != len(set(unlocked)):
            raise RuneError("Повторяющиеся руны")
        if "nexus" in unlocked:
            raise RuneError("Центр открыт автоматически и не сохраняется")

        owned = set(unlocked) | {"nexus"}

        for node_id in unlocked:
            if node_id not in self.nodes:
                raise RuneError(f"Неизвестная руна: {node_id}")
            if not set(self.nodes[node_id].prerequisites) <= owned:
                raise RuneError(f"Нарушены связи руны {node_id}")

    def effects(self, unlocked: tuple[str, ...]) -> RuneEffects:
        self.validate_unlocked(unlocked)
        result = RuneEffects()

        # Одинаковый порядок суммирования для любого порядка покупок.
        for node_id in sorted(unlocked):
            result = result + self.nodes[node_id].effects

        return result

    def calculate_purchase(self, data: GameData, node_id: str) -> GameData:
        self.validate_unlocked(data.unlocked_runes)

        if node_id not in self.nodes or node_id == "nexus":
            raise RuneError("Эту руну нельзя купить")
        if node_id in data.unlocked_runes:
            raise RuneError("Руна уже куплена")

        node = self.nodes[node_id]
        owned = set(data.unlocked_runes) | {"nexus"}

        if not set(node.prerequisites) <= owned:
            raise RuneError("Сначала откройте связанные предыдущие узлы")
        if data.gold < node.cost:
            raise RuneError("Недостаточно золота")

        effect = node.effects

        # Прибавляем только эффект новой руны.
        # Полный набор рун повторно в farm не применяется.
        farm = replace(
            data.farm,
            gold_bonus=data.farm.gold_bonus + effect.gold_bonus,
            sale_bonus=data.farm.sale_bonus + effect.sale_bonus,
            drop_chance=min(1.0, data.farm.drop_chance + effect.drop_bonus),
        )

        return replace(
            data,
            gold=data.gold - node.cost,
            farm=farm,
            unlocked_runes=tuple(sorted((*data.unlocked_runes, node_id))),
            offline_cap_level=min(
                len(C.OFFLINE_CAP_SECONDS) - 1,
                data.offline_cap_level + effect.cap_steps,
            ),
            offline_efficiency_level=min(
                len(C.OFFLINE_EFFICIENCIES) - 1,
                data.offline_efficiency_level + effect.efficiency_steps,
            ),
        )

    def buy(
        self,
        state: GameState,
        saves: SaveManager,
        node_id: str,
    ) -> GameData:
        state.assert_owner_thread()
        before = state.data
        after = self.calculate_purchase(before, node_id)

        saves.write(after)
        state.commit(before, after)
        return after

    def squad(self, data: GameData) -> tuple[SquadMember, ...]:
        """Вычисленные характеристики активного отряда с экипировкой и рунами."""
        effects = self.effects(data.unlocked_runes)
        builds = {build.hero_id: build for build in data.hero_builds}
        members = []

        for snapshot in data.party:
            hero = Hero.from_state(snapshot, builds.get(snapshot.hero_id))
            stats = hero.secondary_stats(effects.stats)

            # Этот Keystone безусловный — его можно применить уже сейчас.
            if "iron_monolith" in effects.keystones:
                stats = replace(
                    stats,
                    armor=stats.armor * 1.5,
                    evasion=0.0,
                )

            members.append(SquadMember(hero, stats))

        return tuple(members)
