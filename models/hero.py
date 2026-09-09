from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Sequence

from models.item import Item, ItemKind, item_from_dict
from models.stats import StatBlock

if TYPE_CHECKING:
    from engine.state import HeroState


XP_BASE = 100
STAT_POINTS_PER_LEVEL = 5
PRIMARY_STAT_KEYS = (
    "strength", "agility", "intelligence", "vitality", "luck",
)


class HeroClass(str, Enum):
    KNIGHT = "knight"
    ASSASSIN = "assassin"
    PYROMANCER = "pyromancer"
    RANGER = "ranger"
    NECROMANCER = "necromancer"
    PALADIN = "paladin"


CLASS_LIFESTEAL = {
    HeroClass.KNIGHT: 0.0,
    HeroClass.ASSASSIN: 0.03,
    HeroClass.PYROMANCER: 0.0,
    HeroClass.RANGER: 0.0,
    HeroClass.NECROMANCER: 0.04,
    HeroClass.PALADIN: 0.0,
}

CLASS_BONUSES = {
    HeroClass.KNIGHT: StatBlock(
        armor=10, block_chance=0.05, melee_bonus=0.15,
    ),
    HeroClass.ASSASSIN: StatBlock(
        crit_chance=0.05, attack_speed=0.15, evasion=0.03,
    ),
    HeroClass.PYROMANCER: StatBlock(
        fire_bonus=0.25, cast_speed=0.10,
    ),
    HeroClass.RANGER: StatBlock(
        projectile_bonus=0.20, attack_speed=0.15,
    ),
    HeroClass.NECROMANCER: StatBlock(
        chaos_bonus=0.20, summon_damage=0.30,
    ),
    HeroClass.PALADIN: StatBlock(
        block_chance=0.10, skill_heal=0.15, lightning_bonus=0.15,
    ),
}

CLASS_RANGE = {
    HeroClass.KNIGHT: 140.0,
    HeroClass.ASSASSIN: 140.0,
    HeroClass.PYROMANCER: 300.0,
    HeroClass.RANGER: 350.0,
    HeroClass.NECROMANCER: 300.0,
    HeroClass.PALADIN: 140.0,
}


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    unlock_level: int
    cooldown_seconds: float
    mana_cost: int
    power_multiplier: float
    effect: str
    duration_seconds: float = 0.0
    target: str = "enemy"


@dataclass(frozen=True)
class ClassDefinition:
    name: str
    base: StatBlock
    growth: StatBlock
    base_hp: int
    base_armor: int
    magical: bool
    skills: tuple[Skill, ...]


def primary(
    strength: float,
    agility: float,
    intelligence: float,
    vitality: float,
    luck: float,
) -> StatBlock:
    return StatBlock(
        strength=strength,
        agility=agility,
        intelligence=intelligence,
        vitality=vitality,
        luck=luck,
    )


CLASS_DEFINITIONS = MappingProxyType({
    HeroClass.KNIGHT: ClassDefinition(
        "Рыцарь", primary(12, 5, 3, 14, 4),
        primary(3, 1, 0.5, 4, 0.5), 100, 10, False,
        (
            Skill("knight_slash", "Рассекающий удар", 1, 4, 0, 1.8, "damage"),
            Skill("knight_guard", "Стальная стена", 5, 15, 15, 0.30,
                  "damage_reduction", 5, "self"),
            Skill("knight_shout", "Боевой клич", 15, 25, 25, 0.20,
                  "party_damage_buff", 8, "party"),
        ),
    ),
    HeroClass.ASSASSIN: ClassDefinition(
        "Ассасин", primary(7, 15, 4, 7, 8),
        primary(1.5, 4, 0.5, 2, 1.5), 60, 3, False,
        (
            Skill("assassin_stab", "Удар из тени", 1, 3, 8, 2.2, "damage"),
            Skill("assassin_poison", "Яд Бездны", 5, 9, 12, 0.5,
                  "poison_per_second", 5),
            Skill("assassin_veil", "Пелена", 15, 20, 20, 0.35,
                  "evasion_buff", 5, "self"),
        ),
    ),
    HeroClass.PYROMANCER: ClassDefinition(
        "Пиромант", primary(3, 6, 16, 6, 6),
        primary(0.5, 1, 4.5, 1.5, 1), 50, 2, True,
        (
            Skill("pyro_fireball", "Огненный шар", 1, 4, 10, 2.0, "damage"),
            Skill("pyro_flame", "Пожарище", 5, 10, 20, 0.7,
                  "burn_per_second", 4, "all_enemies"),
            Skill("pyro_meteor", "Метеор", 15, 24, 40, 4.0,
                  "damage", 0, "all_enemies"),
        ),
    ),
    HeroClass.RANGER: ClassDefinition(
        "Рейнджер", primary(7, 13, 5, 8, 7),
        primary(1.5, 3.5, 1, 2, 1.5), 70, 4, False,
        (
            Skill("ranger_shot", "Прицельный выстрел", 1, 4, 5, 2.1, "damage"),
            Skill("ranger_volley", "Залп", 5, 10, 15, 1.4,
                  "damage", 0, "all_enemies"),
            Skill("ranger_mark", "Метка охотника", 15, 18, 20, 0.25,
                  "damage_taken_debuff", 8),
        ),
    ),
    HeroClass.NECROMANCER: ClassDefinition(
        "Некромант", primary(4, 4, 15, 9, 6),
        primary(0.5, 0.5, 4, 2.5, 1), 65, 3, True,
        (
            Skill("necro_bolt", "Костяное копьё", 1, 4, 10, 1.9, "damage"),
            Skill("necro_drain", "Похищение жизни", 5, 10, 20, 1.4, "life_drain"),
            Skill("necro_summon", "Страж могилы", 15, 30, 35, 0.8,
                  "summon", 15, "self"),
        ),
    ),
    HeroClass.PALADIN: ClassDefinition(
        "Паладин", primary(10, 4, 9, 12, 5),
        primary(2.5, 0.5, 2, 3.5, 0.5), 90, 8, False,
        (
            Skill("paladin_smite", "Кара", 1, 5, 10, 2.0, "damage"),
            Skill("paladin_heal", "Святой свет", 5, 12, 25, 1.8,
                  "heal", 0, "lowest_hp_ally"),
            Skill("paladin_aegis", "Эгида", 15, 28, 40, 0.25,
                  "max_hp_shield", 8, "party"),
        ),
    ),
})


def total_exp_for_level(level: int) -> int:
    if type(level) is not int or level < 1:
        raise ValueError("Уровень должен быть целым >= 1")
    return XP_BASE * (level - 1) * level * (2 * level - 1) // 6


def level_from_exp(total_exp: int) -> int:
    if type(total_exp) is not int or total_exp < 0:
        raise ValueError("Опыт должен быть целым >= 0")

    low, high = 1, 2
    while total_exp_for_level(high) <= total_exp:
        low, high = high, high * 2

    while low + 1 < high:
        middle = (low + high) // 2
        if total_exp_for_level(middle) <= total_exp:
            low = middle
        else:
            high = middle
    return low


@dataclass(frozen=True)
class HeroBuild:
    hero_id: str
    hero_class: HeroClass | str
    equipment: tuple[Item, ...] = ()
    allocated_stats: tuple[int, ...] = (0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        if not isinstance(self.hero_id, str) or not self.hero_id:
            raise ValueError("Необходим hero_id")
        object.__setattr__(self, "hero_class", HeroClass(self.hero_class))

        if type(self.equipment) is not tuple:
            raise ValueError("equipment должна быть tuple")
        if not all(isinstance(item, Item) for item in self.equipment):
            raise ValueError("Некорректная экипировка")
        if len({item.slot for item in self.equipment}) != len(self.equipment):
            raise ValueError("Слот занят дважды")
        if len({item.item_id for item in self.equipment}) != len(self.equipment):
            raise ValueError("Предмет экипирован дважды")

        if (
            type(self.allocated_stats) is not tuple
            or len(self.allocated_stats) != 5
            or any(type(v) is not int or v < 0 for v in self.allocated_stats)
        ):
            raise ValueError("Некорректное распределение характеристик")

    def equip(self, item: Item) -> tuple[HeroBuild, Item | None]:
        previous = next(
            (entry for entry in self.equipment if entry.slot == item.slot),
            None,
        )
        equipment = tuple(
            entry for entry in self.equipment if entry.slot != item.slot
        ) + (item,)
        return replace(self, equipment=equipment), previous


@dataclass(frozen=True)
class SecondaryStats:
    # Поля, используемые старыми модулями.
    physical_damage: float
    magical_damage: float
    armor: float
    max_hp: int
    max_mana: int
    crit_chance: float
    crit_multiplier: float
    evasion: float

    magic_resistance: float = 0.0
    lifesteal: float = 0.0

    attack_speed: float = 1.0
    basic_requirement_reduction: int = 0
    cooldown_reduction: float = 0.0
    skill_range: float = 0.0
    basic_attack_range: float = 140.0
    cast_speed: float = 1.0

    physical_enhancement: float = 0.0
    fire_enhancement: float = 0.0
    cold_enhancement: float = 0.0
    lightning_enhancement: float = 0.0
    chaos_enhancement: float = 0.0

    multistrike: float = 0.0
    projectile_count: int = 0
    melee_damage: float = 0.0
    projectile_damage: float = 0.0
    aoe_damage: float = 0.0
    projectile_speed: float = 0.0
    summon_damage: float = 0.0

    fire_res: float = 0.0
    cold_res: float = 0.0
    lightning_res: float = 0.0
    chaos_res: float = 0.0
    block_chance: float = 0.0
    elemental_dodge: float = 0.0
    elemental_block: float = 0.0
    hp_regen: float = 0.0
    damage_absorption: float = 0.0

    movement_speed: int = 1000
    aoe_enhancement: float = 0.0
    skill_duration: float = 0.0
    hp_per_hit: float = 0.0
    hp_per_kill: float = 0.0
    skill_heal: float = 0.0
    all_skill_level: int = 0
    exp_gain: float = 0.0
    additional_exp: int = 0

    def resistance(self, element: str) -> float:
        return {
            "physical": 0.0,
            "fire": self.fire_res,
            "cold": self.cold_res,
            "lightning": self.lightning_res,
            "chaos": self.chaos_res,
            "magic": self.magic_resistance,
        }[element]

    def elemental_bonus(self, element: str) -> float:
        return {
            "physical": 0.0,  # Уже включён в physical_damage.
            "fire": self.fire_enhancement,
            "cold": self.cold_enhancement,
            "lightning": self.lightning_enhancement,
            "chaos": self.chaos_enhancement,
            "magic": 0.0,     # magical_bonus включён в magical_damage.
        }[element]


def _clamp(value: float, maximum: float) -> float:
    return max(0.0, min(maximum, value))


def experience_awards(
    base_per_wave: int,
    waves: int,
    stats: Sequence[SecondaryStats],
    cursor: int = 0,
) -> tuple[tuple[int, ...], int]:
    """
    Распределение за несколько волн эквивалентно последовательному
    начислению за каждую волну, включая округление индивидуальных бонусов.
    """
    if (
        type(base_per_wave) is not int or base_per_wave < 0
        or type(waves) is not int or waves < 0
        or not stats or not 0 <= cursor < len(stats)
    ):
        raise ValueError("Некорректные параметры распределения XP")

    count = len(stats)
    base, remainder = divmod(base_per_wave, count)
    extra_units = remainder * waves
    common_extra, tail = divmod(extra_units, count)

    result = []
    for index, secondary in enumerate(stats):
        extra_waves = common_extra + (
            1 if (index - cursor) % count < tail else 0
        )
        multiplier = max(
            Fraction(0),
            1 + Fraction(str(secondary.exp_gain)),
        )
        normal_award = math.floor(
            (base + secondary.additional_exp) * multiplier
        )
        extra_award = math.floor(
            (base + 1 + secondary.additional_exp) * multiplier
        )
        result.append(
            (waves - extra_waves) * normal_award
            + extra_waves * extra_award
        )

    return tuple(result), (cursor + extra_units) % count


# name, SecondaryStats attribute, display format.
ATTACK_ROWS = (
    ("Attack Damage", "physical_damage", "number"),
    ("Attack Speed", "attack_speed", "speed"),
    ("Critical Chance", "crit_chance", "percent"),
    ("Critical Damage", "crit_multiplier", "percent"),
    ("Basic Attack Requirement Reduction", "basic_requirement_reduction", "int"),
    ("Cooldown Reduction*", "cooldown_reduction", "percent"),
    ("Skill Range", "skill_range", "percent"),
    ("Basic Attack Range", "basic_attack_range", "number"),
    ("Cast Speed", "cast_speed", "speed"),
    ("Physical Damage Enhancement", "physical_enhancement", "percent"),
    ("Fire Damage Enhancement", "fire_enhancement", "percent"),
    ("Cold Damage Enhancement", "cold_enhancement", "percent"),
    ("Lightning Damage Enhancement", "lightning_enhancement", "percent"),
    ("Chaos Damage Enhancement", "chaos_enhancement", "percent"),
    ("Multistrike Enhancement", "multistrike", "speed"),
    ("Projectile Count Enhancement", "projectile_count", "int"),
    ("Increase Melee Damage", "melee_damage", "percent"),
    ("Increase Projectile Damage", "projectile_damage", "percent"),
    ("Increase Area Of Effect Damage", "aoe_damage", "percent"),
    ("Increase Projectile Speed", "projectile_speed", "percent"),
    ("Increase Summon Damage", "summon_damage", "percent"),
)

DEFENSE_ROWS = (
    ("Max HP", "max_hp", "int"),
    ("Armor*", "armor", "number"),
    ("Fire Resistance*", "fire_res", "percent"),
    ("Cold Resistance*", "cold_res", "percent"),
    ("Lightning Resistance*", "lightning_res", "percent"),
    ("Chaos Resistance*", "chaos_res", "percent"),
    ("Dodge Chance*", "evasion", "percent"),
    ("Block Chance*", "block_chance", "percent"),
    ("Elemental Dodge Chance*", "elemental_dodge", "percent"),
    ("Elemental Block Chance*", "elemental_block", "percent"),
    ("HP Regen Per Sec", "hp_regen", "number"),
    ("Damage Absorption*", "damage_absorption", "number"),
)

UTILITY_ROWS = (
    ("Movement Speed", "movement_speed", "int"),
    ("Area of Effect Enhancement", "aoe_enhancement", "total_percent"),
    ("Skill Duration Increase", "skill_duration", "percent"),
    ("HP Per Hit Enhancement", "hp_per_hit", "number"),
    ("Add HP Per Kill", "hp_per_kill", "number"),
    ("Life Leech Enhancement", "lifesteal", "percent"),
    ("Skill Heal Increase", "skill_heal", "percent"),
    ("Add All Skill Level", "all_skill_level", "int"),
    ("Exp Gain Enhancement", "exp_gain", "total_percent"),
    ("Additional Exp Enhancement", "additional_exp", "int"),
)

DETAILED_REGISTRY = {
    "Attack": ATTACK_ROWS,
    "Defense": DEFENSE_ROWS,
    "Utility": UTILITY_ROWS,
}


@dataclass(frozen=True)
class Hero:
    hero_id: str
    name: str
    hero_class: HeroClass | str
    total_exp: int = 0
    equipment: tuple[Item, ...] = ()
    allocated_stats: tuple[int, ...] = (0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hero_class", HeroClass(self.hero_class))
        HeroBuild(
            self.hero_id, self.hero_class,
            self.equipment, self.allocated_stats,
        )
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Герою необходимо имя")
        level_from_exp(self.total_exp)
        if self.free_stat_points < 0:
            raise ValueError("Распределено больше очков, чем заработано")

    @property
    def definition(self) -> ClassDefinition:
        return CLASS_DEFINITIONS[self.hero_class]

    @property
    def level(self) -> int:
        return level_from_exp(self.total_exp)

    @property
    def earned_stat_points(self) -> int:
        return (self.level - 1) * STAT_POINTS_PER_LEVEL

    @property
    def free_stat_points(self) -> int:
        return self.earned_stat_points - sum(self.allocated_stats)

    @property
    def exp_in_level(self) -> int:
        return self.total_exp - total_exp_for_level(self.level)

    @property
    def exp_to_next_level(self) -> int:
        return total_exp_for_level(self.level + 1) - self.total_exp

    @property
    def skills(self) -> tuple[Skill, ...]:
        return tuple(
            skill for skill in self.definition.skills
            if skill.unlock_level <= self.level
        )

    def gain_exp(self, amount: int) -> Hero:
        if type(amount) is not int or amount < 0:
            raise ValueError("Количество XP должно быть целым >= 0")
        return replace(self, total_exp=self.total_exp + amount)

    def primary_stats(self, bonuses: StatBlock = StatBlock()) -> StatBlock:
        stats = (
            self.definition.base
            + self.definition.growth.scaled(self.level - 1)
            + CLASS_BONUSES[self.hero_class]
            + bonuses
            + StatBlock(**dict(zip(PRIMARY_STAT_KEYS, self.allocated_stats)))
        )
        for item in self.equipment:
            stats = stats + item.stats
        return stats

    def secondary_stats(
        self,
        bonuses: StatBlock = StatBlock(),
    ) -> SecondaryStats:
        s = self.primary_stats(bonuses)
        has_shield = any(item.kind == ItemKind.SHIELD for item in self.equipment)

        physical = (
            5 + 2.0 * s.strength + 1.2 * s.agility + s.damage
        ) * max(0.0, 1 + s.physical_bonus)

        magical = (
            5 + 2.5 * s.intelligence + 0.3 * s.luck + s.damage
        ) * max(0.0, 1 + s.magical_bonus)

        fire_res = _clamp(0.0015 * s.vitality + s.fire_res, 0.75)
        cold_res = _clamp(0.0015 * s.vitality + s.cold_res, 0.75)
        lightning_res = _clamp(0.0015 * s.vitality + s.lightning_res, 0.75)
        chaos_res = _clamp(0.0010 * s.vitality + s.chaos_res, 0.75)

        return SecondaryStats(
            physical_damage=max(0.0, physical),
            magical_damage=max(0.0, magical),
            armor=max(
                0.0,
                self.definition.base_armor
                + 1.5 * s.vitality + 0.5 * s.strength + s.armor,
            ),
            max_hp=max(1, math.floor(
                (self.definition.base_hp + 12 * s.vitality + s.max_hp)
                * max(0.0, 1 + s.hp_bonus)
            )),
            max_mana=max(0, math.floor(30 + 8 * s.intelligence + s.mana)),
            crit_chance=_clamp(
                0.05 + 0.001 * s.agility + 0.002 * s.luck + s.crit_chance,
                0.75,
            ),
            crit_multiplier=max(1.0, 1.5 + 0.005 * s.strength + s.crit_damage),
            evasion=_clamp(0.0015 * s.agility + s.evasion, 0.60),
            magic_resistance=(fire_res + cold_res + lightning_res) / 3,
            lifesteal=_clamp(
                CLASS_LIFESTEAL[self.hero_class] + s.life_leech, 1.0
            ),
            attack_speed=max(0.2, 1 + 0.015 * s.agility + s.attack_speed),
            basic_requirement_reduction=max(0, math.floor(s.basic_requirement_reduction)),
            cooldown_reduction=_clamp(0.002 * s.intelligence + s.cooldown_reduction, 0.75),
            skill_range=max(-0.8, s.skill_range),
            basic_attack_range=max(20.0, CLASS_RANGE[self.hero_class] + s.basic_attack_range),
            cast_speed=max(0.2, 1 + 0.01 * s.intelligence + s.cast_speed),
            physical_enhancement=s.physical_bonus,
            fire_enhancement=s.fire_bonus,
            cold_enhancement=s.cold_bonus,
            lightning_enhancement=s.lightning_bonus,
            chaos_enhancement=s.chaos_bonus,
            multistrike=max(0.0, s.multistrike),
            projectile_count=max(0, math.floor(s.projectile_count)),
            melee_damage=s.melee_bonus,
            projectile_damage=s.projectile_bonus,
            aoe_damage=s.aoe_damage,
            projectile_speed=max(-0.8, s.projectile_speed),
            summon_damage=s.summon_damage,
            fire_res=fire_res,
            cold_res=cold_res,
            lightning_res=lightning_res,
            chaos_res=chaos_res,
            block_chance=_clamp(
                (0.15 if has_shield else 0.0)
                + 0.001 * s.strength + s.block_chance, 0.75,
            ),
            elemental_dodge=_clamp(s.elemental_dodge, 0.60),
            elemental_block=_clamp(s.elemental_block, 0.75),
            hp_regen=max(0.0, 0.25 * s.vitality + s.hp_regen),
            damage_absorption=max(0.0, s.damage_absorption),
            movement_speed=max(100, 1000 + int(10 * s.agility + s.movement_speed)),
            aoe_enhancement=max(-0.9, s.aoe_enhancement),
            skill_duration=max(-0.9, s.skill_duration),
            hp_per_hit=max(0.0, s.hp_per_hit),
            hp_per_kill=max(0.0, s.hp_per_kill),
            skill_heal=max(-1.0, s.skill_heal),
            all_skill_level=max(0, math.floor(s.all_skill_level)),
            exp_gain=max(-1.0, s.exp_gain),
            additional_exp=max(0, math.floor(s.additional_exp)),
        )

    def detailed_stats(
        self,
        bonuses: StatBlock = StatBlock(),
        *,
        secondary: SecondaryStats | None = None,
    ) -> dict[str, list[tuple[str, str]]]:
        stats = secondary if secondary is not None else self.secondary_stats(bonuses)

        def formatted(value: float, mode: str) -> str:
            if mode == "percent":
                return f"{value * 100:.1f}%"
            if mode == "total_percent":
                return f"{(1 + value) * 100:.1f}%"
            if mode == "int":
                return f"{int(value):,}"
            if mode == "speed":
                return f"{value:.2f}"
            return f"{value:,.1f}"

        return {
            section: [
                (name, formatted(getattr(stats, attribute), mode))
                for name, attribute, mode in rows
            ]
            for section, rows in DETAILED_REGISTRY.items()
        }

    @classmethod
    def from_state(
        cls,
        snapshot: HeroState,
        build: HeroBuild | None = None,
    ) -> Hero:
        build = build or default_build(snapshot.hero_id)
        if snapshot.hero_id != build.hero_id:
            raise ValueError("Снимок и сборка принадлежат разным героям")
        return cls(
            snapshot.hero_id, snapshot.name, build.hero_class,
            snapshot.total_exp, build.equipment, build.allocated_stats,
        )


def default_build(hero_id: str) -> HeroBuild:
    legacy = {
        "warlock": HeroClass.NECROMANCER,
        "priest": HeroClass.PALADIN,
    }
    if hero_id in legacy:
        hero_class = legacy[hero_id]
    else:
        try:
            hero_class = HeroClass(hero_id)
        except ValueError:
            hero_class = HeroClass.KNIGHT
    return HeroBuild(hero_id, hero_class)


def build_from_dict(payload: dict[str, Any]) -> HeroBuild:
    raw = dict(payload)
    raw["equipment"] = tuple(
        item_from_dict(item) for item in raw.get("equipment", ())
    )
    raw["allocated_stats"] = tuple(raw.get("allocated_stats", (0, 0, 0, 0, 0)))
    return HeroBuild(**raw)
