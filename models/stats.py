from __future__ import annotations

import math
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class StatBlock:
    # Первичные атрибуты.
    strength: float = 0.0
    agility: float = 0.0
    intelligence: float = 0.0
    vitality: float = 0.0
    luck: float = 0.0

    # Совместимые поля предыдущих модулей.
    damage: float = 0.0
    armor: float = 0.0
    max_hp: float = 0.0
    mana: float = 0.0
    physical_bonus: float = 0.0
    magical_bonus: float = 0.0
    hp_bonus: float = 0.0
    crit_chance: float = 0.0
    crit_damage: float = 0.0
    evasion: float = 0.0

    # Attack.
    attack_speed: float = 0.0
    basic_requirement_reduction: float = 0.0
    cooldown_reduction: float = 0.0
    skill_range: float = 0.0
    basic_attack_range: float = 0.0
    cast_speed: float = 0.0
    fire_bonus: float = 0.0
    cold_bonus: float = 0.0
    lightning_bonus: float = 0.0
    chaos_bonus: float = 0.0
    multistrike: float = 0.0
    projectile_count: float = 0.0
    melee_bonus: float = 0.0
    projectile_bonus: float = 0.0
    aoe_damage: float = 0.0
    projectile_speed: float = 0.0
    summon_damage: float = 0.0

    # Defense.
    fire_res: float = 0.0
    cold_res: float = 0.0
    lightning_res: float = 0.0
    chaos_res: float = 0.0
    block_chance: float = 0.0
    elemental_dodge: float = 0.0
    elemental_block: float = 0.0
    hp_regen: float = 0.0
    damage_absorption: float = 0.0

    # Utility.
    movement_speed: float = 0.0
    aoe_enhancement: float = 0.0
    skill_duration: float = 0.0
    hp_per_hit: float = 0.0
    hp_per_kill: float = 0.0
    life_leech: float = 0.0
    skill_heal: float = 0.0
    all_skill_level: float = 0.0
    exp_gain: float = 0.0
    additional_exp: float = 0.0

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(
                    f"Некорректное значение {definition.name}: {value}"
                )

    def __add__(self, other: StatBlock) -> StatBlock:
        if not isinstance(other, StatBlock):
            return NotImplemented
        return StatBlock(**{
            definition.name: (
                getattr(self, definition.name)
                + getattr(other, definition.name)
            )
            for definition in fields(self)
        })

    def __sub__(self, other: StatBlock) -> StatBlock:
        if not isinstance(other, StatBlock):
            return NotImplemented
        return StatBlock(**{
            definition.name: (
                getattr(self, definition.name)
                - getattr(other, definition.name)
            )
            for definition in fields(self)
        })

    def scaled(self, factor: float) -> StatBlock:
        if type(factor) not in (int, float) or not math.isfinite(factor):
            raise ValueError("Множитель должен быть конечным числом")
        return StatBlock(**{
            definition.name: getattr(self, definition.name) * factor
            for definition in fields(self)
        })
