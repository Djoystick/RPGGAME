from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from fractions import Fraction

from PySide6.QtCore import QObject, Signal

import config as C
from engine.runes_tree import RunesTree
from engine.state import GameState
from models.enemy import (
    Act, BOSS_TIME_LIMIT, Enemy, EnemyAffix,
    act_for_wave, spawn_wave,
)
from models.hero import (
    Hero, HeroClass, SecondaryStats, Skill, experience_awards,
)
from models.item import generate_item


FIXED_STEP = 0.05
HERO_IFRAMES = 0.18
BARRIER_RATIO = 0.20
BETWEEN_WAVES = 1.0
DEFEAT_DELAY = 3.0
BASE_ATTACK_COST = 2.0
BASE_PROJECTILE_SPEED = 320.0

HERO_POSITIONS = (
    (78.0, 104.0), (108.0, 116.0),
    (136.0, 97.0), (164.0, 113.0),
)

BASIC_INTERVALS = {
    HeroClass.KNIGHT: 1.20,
    HeroClass.ASSASSIN: 0.75,
    HeroClass.PYROMANCER: 1.40,
    HeroClass.RANGER: 0.95,
    HeroClass.NECROMANCER: 1.45,
    HeroClass.PALADIN: 1.30,
}

ELEMENTS = {"physical", "fire", "cold", "lightning", "chaos", "magic"}

CLASS_ELEMENT = {
    HeroClass.KNIGHT: "physical",
    HeroClass.ASSASSIN: "physical",
    HeroClass.PYROMANCER: "fire",
    HeroClass.RANGER: "physical",
    HeroClass.NECROMANCER: "chaos",
    HeroClass.PALADIN: "physical",
}

ENEMY_ELEMENT = {
    "wraith": "cold",
    "dryad": "chaos",
    "imp": "fire",
    "inquisitor": "lightning",
}


def combined_chance(first: float, second: float) -> float:
    first = max(0.0, min(1.0, first))
    second = max(0.0, min(1.0, second))
    return 1 - (1 - first) * (1 - second)


@dataclass(frozen=True)
class Hit:
    damage: float
    critical: bool = False
    dodged: bool = False


def roll_damage(
    power: float,
    armor: float,
    *,
    magical: bool = False,
    crit_chance: float = 0.0,
    crit_multiplier: float = 1.5,
    evasion: float = 0.0,
    rng: random.Random | None = None,
) -> Hit:
    values = (power, armor, crit_chance, crit_multiplier, evasion)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Параметры урона должны быть конечными")
    if power < 0 or armor < 0 or crit_multiplier < 1:
        raise ValueError("Некорректные параметры урона")
    if not 0 <= crit_chance <= 1 or not 0 <= evasion <= 1:
        raise ValueError("Вероятности должны находиться в [0, 1]")

    generator = rng if rng is not None else random.Random()
    if generator.random() < evasion:
        return Hit(0.0, dodged=True)

    critical = generator.random() < crit_chance
    effective_armor = armor * (0.5 if magical else 1.0)
    damage = power * 100 / (100 + effective_armor)
    if critical:
        damage *= crit_multiplier
    return Hit(damage, critical=critical)


@dataclass(frozen=True)
class DamageEvent:
    target_id: str
    x: float
    y: float
    amount: float
    kind: str
    critical: bool = False


@dataclass(frozen=True)
class ActorFrame:
    actor_id: str
    sprite_key: str
    name: str
    x: float
    y: float
    hp: float
    max_hp: float
    animation: str
    enemy: bool
    elite: bool = False
    boss: bool = False
    rage: float = 0.0
    mana: float = 0.0
    max_mana: float = 0.0


@dataclass(frozen=True)
class CombatFrame:
    wave: int
    act: Act
    phase: str
    time: float
    progress: float
    barrier: float
    barrier_max: float
    boss_remaining: float | None
    actors: tuple[ActorFrame, ...]


@dataclass
class HeroRuntime:
    hero: Hero
    stats: SecondaryStats
    hp: float
    mana: float
    x: float
    y: float

    basic_timer: float = 0.25
    skill_cooldowns: dict[str, float] = field(default_factory=dict)
    invulnerable_until: float = 0.0

    animation: str = "idle"
    animation_left: float = 0.0
    buffs: dict[str, tuple[float, float]] = field(default_factory=dict)

    pending_skill: Skill | None = None
    cast_left: float = 0.0

    summon_left: float = 0.0
    summon_timer: float = 0.0
    summon_power: float = 0.0

    shield: float = 0.0
    shield_until: float = 0.0
    second_wind_ready: float = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def buff(self, name: str, now: float) -> float:
        until, amount = self.buffs.get(name, (0.0, 0.0))
        return amount if until > now else 0.0


@dataclass
class PendingImpact:
    owner_id: str
    enemy_id: str
    power: float
    element: str
    tags: frozenset[str]
    remaining: float
    drain: float = 0.0


@dataclass
class DamageOverTime:
    owner_id: str
    enemy_id: str
    power: float
    remaining: float
    magical: bool
    timer: float = 1.0
    element: str = "chaos"
    tags: frozenset[str] = frozenset()


class CombatManager(QObject):
    frame_changed = Signal(object)
    damage_event = Signal(object)
    skill_used = Signal(str, str)
    wave_finished = Signal(object)
    party_defeated = Signal(object)

    def __init__(
        self,
        state: GameState,
        *,
        rng: random.Random | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.rng = rng if rng is not None else random.Random()
        self.runes = RunesTree()

        self.running = False
        self.phase = "stopped"
        self.time = 0.0

        self._accumulator = 0.0
        self._phase_left = 0.0
        self._generation = 0
        self._wave = state.data.current_wave
        self._wave_elapsed = 0.0
        self._wave_real_elapsed = 0.0
        self._wave_total_hp = 1.0
        self._continued_wave = False

        self._heroes: dict[str, HeroRuntime] = {}
        self._enemies: list[Enemy] = []
        self._dots: list[DamageOverTime] = []
        self._impacts: list[PendingImpact] = []

        self.barrier = 0.0
        self.barrier_max = 0.0
        self._effects = self.runes.effects(state.data.unlocked_runes)

    @property
    def heroes(self) -> tuple[HeroRuntime, ...]:
        return tuple(self._heroes.values())

    @property
    def enemies(self) -> tuple[Enemy, ...]:
        return tuple(self._enemies)

    def start(self) -> None:
        self.state.assert_owner_thread()
        if self.running:
            return
        self._sync_heroes()
        self.running = True
        self._accumulator = 0.0
        self._spawn()
        self.frame_changed.emit(self.frame())

    def stop(self) -> None:
        self.state.assert_owner_thread()
        if self.running:
            self.flush()
        self.running = False
        self.phase = "stopped"
        self._impacts.clear()
        self._dots.clear()

    def _sync_heroes(self) -> None:
        members = self.runes.squad(self.state.data)
        if not 3 <= len(members) <= 4:
            raise ValueError("Боевой отряд должен содержать 3–4 героев")

        snapshots = {hero.hero_id: hero for hero in self.state.data.party}
        updated: dict[str, HeroRuntime] = {}

        for index, member in enumerate(members):
            hero_id = member.hero.hero_id
            runtime = self._heroes.get(hero_id)

            if runtime is None:
                snapshot = snapshots[hero_id]
                runtime = HeroRuntime(
                    member.hero, member.stats,
                    member.stats.max_hp * snapshot.hp / snapshot.max_hp,
                    float(member.stats.max_mana),
                    *HERO_POSITIONS[index],
                )
            else:
                ratio = runtime.hp / runtime.stats.max_hp
                runtime.hero = member.hero
                runtime.stats = member.stats
                runtime.hp = max(0.0, min(member.stats.max_hp, ratio * member.stats.max_hp))
                runtime.mana = min(runtime.mana, member.stats.max_mana)

            for skill in member.hero.skills:
                runtime.skill_cooldowns.setdefault(skill.skill_id, 0.0)
            updated[hero_id] = runtime

        old_max = self.barrier_max
        self._heroes = updated
        self._effects = self.runes.effects(self.state.data.unlocked_runes)

        self.barrier_max = BARRIER_RATIO * sum(
            hero.stats.max_hp for hero in self._heroes.values()
        )
        self.barrier = (
            self.barrier_max if old_max == 0
            else min(self.barrier_max, self.barrier * self.barrier_max / old_max)
        )

    def _spawn(self) -> None:
        self._sync_heroes()
        self._generation += 1
        self._wave = self.state.data.current_wave
        self._enemies = spawn_wave(
            self._wave, self.rng, generation=self._generation
        )
        self._wave_total_hp = sum(enemy.max_hp for enemy in self._enemies)

        partial = float(Fraction(self.state.data.wave_fraction))
        self._continued_wave = partial > 0

        for enemy in self._enemies:
            enemy.hp = max(0.001, enemy.max_hp * (1 - partial))

        for hero in self._heroes.values():
            hero.pending_skill = None
            hero.cast_left = 0.0

        self._dots.clear()
        self._impacts.clear()
        self._wave_elapsed = 0.0
        self._wave_real_elapsed = 0.0
        self.phase = "battle"

    def advance(self, seconds: float) -> None:
        self.state.assert_owner_thread()
        if not math.isfinite(seconds) or not 0 <= seconds <= 60:
            raise ValueError("advance принимает от 0 до 60 секунд")
        if not self.running:
            return

        self._sync_heroes()
        speed = 1 + self._effects.active_speed_bonus
        self._accumulator += seconds * speed

        while self._accumulator + 1e-12 >= FIXED_STEP:
            self._accumulator = max(0.0, self._accumulator - FIXED_STEP)
            self._step(FIXED_STEP, FIXED_STEP / speed)

        self.frame_changed.emit(self.frame())

    @staticmethod
    def _animate(actor: HeroRuntime | Enemy, state: str, duration: float) -> None:
        if actor.animation == "die":
            return
        if state == "hurt" and actor.animation in ("attack", "cast"):
            return
        if actor.animation == state:
            return
        actor.animation = state
        actor.animation_left = duration

    def _step(self, dt: float, real_dt: float) -> None:
        self.time += dt

        for actor in (*self._heroes.values(), *self._enemies):
            if actor.animation != "die" and actor.animation_left > 0:
                actor.animation_left = max(0.0, actor.animation_left - dt)
                if actor.animation_left == 0:
                    actor.animation = "idle"

        for hero in self._heroes.values():
            hero.basic_timer = max(0.0, hero.basic_timer - dt)
            for skill_id in hero.skill_cooldowns:
                hero.skill_cooldowns[skill_id] = max(
                    0.0, hero.skill_cooldowns[skill_id] - dt
                )
            if hero.alive:
                hero.mana = min(
                    hero.stats.max_mana,
                    hero.mana + (3 + hero.stats.max_mana * 0.01) * dt,
                )
            if self.time >= hero.shield_until:
                hero.shield = 0.0

        if self.phase != "battle":
            self._phase_left -= dt
            if self._phase_left <= 0:
                if self.phase == "defeat":
                    for index, hero in enumerate(self._heroes.values()):
                        hero.hp = float(hero.stats.max_hp)
                        hero.mana = float(hero.stats.max_mana)
                        hero.x, hero.y = HERO_POSITIONS[index]
                        hero.invulnerable_until = 0.0
                        hero.animation = "idle"
                        hero.animation_left = 0.0
                        hero.buffs.clear()
                        hero.shield = 0.0
                        hero.summon_left = 0.0
                    self.barrier = self.barrier_max
                    self.flush()
                else:
                    self.barrier = min(
                        self.barrier_max, self.barrier + self.barrier_max * 0.25
                    )
                self._spawn()
            return

        self._wave_elapsed += dt
        self._wave_real_elapsed += real_dt

        for hero in self._heroes.values():
            if hero.alive:
                hero.hp = min(
                    hero.stats.max_hp, hero.hp + hero.stats.hp_regen * dt
                )

        self._tick_impacts(dt)
        self._tick_dots(dt)
        self._tick_heroes(dt)

        if not any(hero.alive for hero in self._heroes.values()):
            self._defeat("Отряд пал")
            return
        if not any(enemy.alive for enemy in self._enemies):
            self._finish_wave()
            return

        self._tick_enemies(dt)

        if not any(hero.alive for hero in self._heroes.values()):
            self._defeat("Отряд пал")
        elif (
            any(enemy.is_boss and enemy.alive for enemy in self._enemies)
            and self._wave_elapsed >= BOSS_TIME_LIMIT
        ):
            self._defeat("Истекло время боя с боссом")

    def _target(self) -> Enemy | None:
        return min(
            (enemy for enemy in self._enemies if enemy.alive),
            key=lambda enemy: enemy.x,
            default=None,
        )

    @staticmethod
    def basic_interval(hero: HeroRuntime) -> float:
        return BASIC_INTERVALS[hero.hero.hero_class] / max(0.2, hero.stats.attack_speed)

    @staticmethod
    def skill_cooldown(hero: HeroRuntime, skill: Skill) -> float:
        return skill.cooldown_seconds * (
            1 - min(0.75, hero.stats.cooldown_reduction)
        )

    @staticmethod
    def skill_duration(hero: HeroRuntime, skill: Skill) -> float:
        return skill.duration_seconds * (1 + hero.stats.skill_duration)

    @staticmethod
    def skill_power(hero: HeroRuntime, skill: Skill) -> float:
        return skill.power_multiplier * (1 + 0.10 * hero.stats.all_skill_level)

    @staticmethod
    def _distance(hero: HeroRuntime, enemy: Enemy) -> float:
        return math.hypot(hero.x - enemy.x, hero.y - enemy.y)

    def _skill_cost(self, hero: HeroRuntime, skill: Skill) -> float:
        berserk = (
            "berserker" in self._effects.keystones
            and hero.hp < hero.stats.max_hp * 0.40
        )
        return skill.mana_cost * (2 if berserk else 1)

    def _can_cast(self, hero: HeroRuntime, skill: Skill, target: Enemy) -> bool:
        if skill.effect == "heal":
            return any(
                ally.alive and ally.hp < ally.stats.max_hp * 0.9
                for ally in self._heroes.values()
            )
        if skill.effect == "max_hp_shield":
            return any(
                ally.alive and ally.shield <= 0
                for ally in self._heroes.values()
            )
        if skill.target in ("self", "party", "lowest_hp_ally"):
            return True

        reach = (hero.stats.basic_attack_range + 80) * (1 + hero.stats.skill_range)
        return self._distance(hero, target) <= reach

    def _tick_heroes(self, dt: float) -> None:
        for index, hero in enumerate(tuple(self._heroes.values())):
            if not hero.alive:
                hero.pending_skill = None
                continue

            if hero.pending_skill is not None:
                hero.cast_left = max(0.0, hero.cast_left - dt)
                if hero.cast_left <= 1e-9:
                    skill = hero.pending_skill
                    hero.pending_skill = None
                    self._cast(hero, skill)
                continue

            target = self._target()
            if target is None:
                break

            if hero.summon_left > 0:
                hero.summon_left = max(0.0, hero.summon_left - dt)
                hero.summon_timer -= dt
                if hero.summon_timer <= 1e-9:
                    hero.summon_timer += 1.0
                    self._hit_enemy(
                        hero, target, hero.summon_power, True,
                        element="chaos", tags=frozenset({"summon"}),
                    )

            target = self._target()
            if target is None:
                break

            if hero.animation in ("attack", "cast", "hurt"):
                continue

            cast = False
            for skill in hero.hero.skills:
                cost = self._skill_cost(hero, skill)
                if (
                    hero.skill_cooldowns[skill.skill_id] <= 1e-9
                    and hero.mana >= cost
                    and self._can_cast(hero, skill, target)
                ):
                    hero.mana -= cost
                    hero.skill_cooldowns[skill.skill_id] = self.skill_cooldown(hero, skill)
                    hero.pending_skill = skill
                    hero.cast_left = 0.45 / hero.stats.cast_speed
                    self._animate(hero, "cast", hero.cast_left)
                    self.skill_used.emit(hero.hero.hero_id, skill.skill_id)
                    cast = True
                    break

            if cast:
                continue

            reach = hero.stats.basic_attack_range
            if self._distance(hero, target) > reach:
                destination = min(195.0, max(HERO_POSITIONS[index][0], target.x - reach + 2))
                movement = hero.stats.movement_speed * 0.06 * dt
                hero.x += max(-movement, min(movement, destination - hero.x))
                if hero.animation in ("idle", "run"):
                    hero.animation = "run"
                continue

            if hero.animation == "run":
                hero.animation = "idle"

            cost = max(0.0, BASE_ATTACK_COST - hero.stats.basic_requirement_reduction)
            if hero.basic_timer <= 1e-9 and hero.mana >= cost:
                hero.mana -= cost
                hero.basic_timer = self.basic_interval(hero)
                self._animate(hero, "attack", min(0.35, hero.basic_timer * 0.8))

                element = CLASS_ELEMENT[hero.hero.hero_class]
                ranged = hero.hero.hero_class in (
                    HeroClass.PYROMANCER, HeroClass.RANGER, HeroClass.NECROMANCER,
                )
                power = (
                    hero.stats.physical_damage
                    if element == "physical" else hero.stats.magical_damage
                )
                tags = frozenset({"projectile" if ranged else "melee"})
                self._dispatch(hero, target, power, element, tags)

    def _repeat_count(self, enhancement: float) -> int:
        whole = math.floor(enhancement)
        return 1 + whole + int(self.rng.random() < enhancement - whole)

    def _dispatch(
        self,
        hero: HeroRuntime,
        target: Enemy,
        power: float,
        element: str,
        tags: frozenset[str],
        *,
        drain: float = 0.0,
        repeat: bool = True,
    ) -> None:
        repetitions = self._repeat_count(hero.stats.multistrike) if repeat else 1
        projectiles = 1 + hero.stats.projectile_count if "projectile" in tags else 1

        travel = 0.0
        if "projectile" in tags:
            speed = BASE_PROJECTILE_SPEED * (1 + hero.stats.projectile_speed)
            travel = self._distance(hero, target) / speed

        for repetition in range(repetitions):
            for projectile in range(projectiles):
                self._impacts.append(PendingImpact(
                    hero.hero.hero_id,
                    target.enemy_id,
                    power,
                    element,
                    tags,
                    travel + repetition * 0.10 + projectile * 0.025,
                    drain,
                ))

    def _tick_impacts(self, dt: float) -> None:
        enemies = {enemy.enemy_id: enemy for enemy in self._enemies}
        pending: list[PendingImpact] = []

        for impact in self._impacts:
            impact.remaining -= dt
            owner = self._heroes.get(impact.owner_id)
            target = enemies.get(impact.enemy_id)

            if owner is None or target is None or not target.alive:
                continue
            if impact.remaining > 1e-9:
                pending.append(impact)
                continue

            # Уже выпущенный снаряд может попасть после смерти владельца.
            if not owner.alive and "projectile" not in impact.tags:
                continue

            dealt = self._hit_enemy(
                owner, target, impact.power,
                impact.element != "physical",
                element=impact.element,
                tags=impact.tags,
            )
            if impact.drain > 0:
                self._heal(owner, dealt * impact.drain * (1 + owner.stats.skill_heal))

        self._impacts = pending

    def _area_targets(self, hero: HeroRuntime, target: Enemy) -> list[Enemy]:
        radius = 80 * (1 + hero.stats.aoe_enhancement)
        return [
            enemy for enemy in self._enemies
            if enemy.alive
            and math.hypot(enemy.x - target.x, enemy.y - target.y) <= radius
        ]

    def _cast(self, hero: HeroRuntime, skill: Skill) -> bool:
        if not hero.alive:
            return False

        effect = skill.effect
        magnitude = self.skill_power(hero, skill)
        duration = self.skill_duration(hero, skill)

        if effect == "heal":
            allies = [ally for ally in self._heroes.values() if ally.alive]
            if not allies:
                return False
            target_hero = min(allies, key=lambda ally: ally.hp / ally.stats.max_hp)
            self._heal(
                target_hero,
                hero.stats.magical_damage * magnitude * (1 + hero.stats.skill_heal),
            )
            return True

        if effect in ("damage_reduction", "evasion_buff"):
            key = "reduction" if effect == "damage_reduction" else "evasion"
            hero.buffs[key] = (self.time + duration, magnitude)
            return True

        if effect == "party_damage_buff":
            for ally in self._heroes.values():
                ally.buffs["damage"] = (self.time + duration, magnitude)
            return True

        if effect == "max_hp_shield":
            for ally in self._heroes.values():
                if ally.alive:
                    ally.shield = max(ally.shield, ally.stats.max_hp * magnitude)
                    ally.shield_until = self.time + duration
            return True

        if effect == "summon":
            hero.summon_left = duration
            hero.summon_timer = 0.0
            hero.summon_power = hero.stats.magical_damage * magnitude
            return True

        target = self._target()
        if target is None:
            return False

        if effect == "damage_taken_debuff":
            target.marked_until = self.time + duration
            target.marked_bonus = magnitude
            return True

        area = skill.target == "all_enemies"
        targets = self._area_targets(hero, target) if area else [target]

        element = CLASS_ELEMENT[hero.hero.hero_class]
        if skill.skill_id == "paladin_smite":
            element = "lightning"
        elif effect == "poison_per_second":
            element = "chaos"
        elif effect == "burn_per_second":
            element = "fire"

        ranged = (
            hero.hero.hero_class in (
                HeroClass.PYROMANCER, HeroClass.RANGER, HeroClass.NECROMANCER,
            )
            and effect not in ("burn_per_second", "poison_per_second")
        )
        tags = set()
        if area:
            tags.add("aoe")
        if ranged:
            tags.add("projectile")
        elif element == "physical":
            tags.add("melee")

        base = (
            hero.stats.physical_damage
            if element == "physical" else hero.stats.magical_damage
        )
        power = base * magnitude

        if effect in ("poison_per_second", "burn_per_second"):
            for enemy in targets:
                self._dots.append(DamageOverTime(
                    hero.hero.hero_id, enemy.enemy_id,
                    power, duration, True,
                    element=element, tags=frozenset(tags),
                ))
            return True

        if effect not in ("damage", "life_drain"):
            raise ValueError(f"Неизвестный эффект навыка: {effect}")

        for enemy in targets:
            self._dispatch(
                hero, enemy, power, element, frozenset(tags),
                drain=0.35 if effect == "life_drain" else 0.0,
                repeat=False,
            )
        return True

    def _tick_dots(self, dt: float) -> None:
        enemies = {enemy.enemy_id: enemy for enemy in self._enemies}
        remaining: list[DamageOverTime] = []

        for dot in self._dots:
            owner = self._heroes.get(dot.owner_id)
            enemy = enemies.get(dot.enemy_id)
            if owner is None or enemy is None or not enemy.alive:
                continue

            # Пропорциональная последняя доля секунды не теряется.
            portion = min(dt, dot.remaining)
            dot.remaining -= portion

            self._hit_enemy(
                owner, enemy, dot.power * portion, True,
                element=dot.element,
                tags=dot.tags,
                allow_crit=False,
                allow_splash=False,
                on_hit=False,
                show_event=False,
            )

            if dot.remaining > 1e-9 and enemy.alive:
                remaining.append(dot)

        self._dots = remaining

    def _hit_enemy(
        self,
        hero: HeroRuntime,
        enemy: Enemy,
        power: float,
        magical: bool,
        *,
        element: str | None = None,
        tags: frozenset[str] = frozenset(),
        allow_crit: bool = True,
        allow_splash: bool = True,
        on_hit: bool = True,
        show_event: bool = True,
    ) -> float:
        if not enemy.alive:
            return 0.0

        element = element or ("magic" if magical else "physical")
        if element not in ELEMENTS:
            raise ValueError("Неизвестный тип урона")

        s = hero.stats
        adjusted = power * max(0.0, 1 + s.elemental_bonus(element))

        for tag, bonus in (
            ("melee", s.melee_damage),
            ("projectile", s.projectile_damage),
            ("aoe", s.aoe_damage),
            ("summon", s.summon_damage),
        ):
            if tag in tags:
                adjusted *= max(0.0, 1 + bonus)

        adjusted *= 1 + hero.buff("damage", self.time)
        if (
            "berserker" in self._effects.keystones
            and hero.hp < s.max_hp * 0.40
        ):
            adjusted *= 1.8

        if enemy.marked_until > self.time:
            adjusted *= 1 + enemy.marked_bonus

        crit_multiplier = s.crit_multiplier
        if element != "physical" and "supernova" in self._effects.keystones:
            crit_multiplier *= 1.5

        hit = roll_damage(
            adjusted, enemy.armor,
            magical=element != "physical",
            crit_chance=s.crit_chance if allow_crit else 0.0,
            crit_multiplier=crit_multiplier,
            rng=self.rng,
        )

        dealt = min(enemy.hp, hit.damage)
        enemy.hp = max(0.0, enemy.hp - dealt)

        if show_event and dealt > 0:
            self.damage_event.emit(DamageEvent(
                enemy.enemy_id, enemy.x, enemy.y - 32,
                dealt, "physical" if element == "physical" else "magical",
                hit.critical,
            ))

        if enemy.is_boss:
            enemy.rage = min(
                enemy.rage_max,
                enemy.rage + dealt / enemy.max_hp * 30,
            )

        killed = not enemy.alive
        if killed:
            enemy.animation = "die"
            enemy.animation_left = 0.0
        elif on_hit:
            self._animate(enemy, "hurt", 0.20)

        if dealt > 0:
            healing = dealt * s.lifesteal
            if on_hit:
                healing += s.hp_per_hit
            if killed:
                healing += s.hp_per_kill
            self._heal(hero, healing, show=show_event)

        if (
            on_hit and dealt > 0 and hero.alive
            and EnemyAffix.REFLECTIVE in enemy.affixes
        ):
            self._hit_hero(hero, dealt * 0.12, True, element="chaos")

        if (
            allow_splash and on_hit and "melee" in tags
            and "titan_sweep" in self._effects.keystones
            and hero.alive
        ):
            radius = 80 * (1 + s.aoe_enhancement)
            neighbor = next(
                (
                    entry for entry in self._enemies
                    if entry.alive and entry is not enemy
                    and abs(entry.x - enemy.x) <= radius
                ),
                None,
            )
            if neighbor:
                self._hit_enemy(
                    hero, neighbor, power * 0.40, False,
                    element="physical",
                    tags=frozenset({"melee", "aoe"}),
                    allow_crit=False, allow_splash=False,
                )

        return dealt

    def _hit_hero(
        self,
        hero: HeroRuntime,
        power: float,
        magical: bool,
        *,
        element: str | None = None,
    ) -> float:
        if not hero.alive or self.time < hero.invulnerable_until:
            return 0.0
        if not math.isfinite(power) or power < 0:
            raise ValueError("Некорректный входящий урон")

        element = element or ("magic" if magical else "physical")
        if element not in ELEMENTS:
            raise ValueError("Неизвестный тип урона")
        elemental = element != "physical"
        s = hero.stats

        dodge = min(0.95, s.evasion + hero.buff("evasion", self.time))
        block = s.block_chance
        if elemental:
            dodge = combined_chance(dodge, s.elemental_dodge)
            block = combined_chance(block, s.elemental_block)

        hero.invulnerable_until = self.time + HERO_IFRAMES

        if self.rng.random() < dodge:
            self.damage_event.emit(DamageEvent(
                hero.hero.hero_id, hero.x, hero.y - 32, 0, "dodge",
            ))
            return 0.0

        blocked = self.rng.random() < block
        damage = power * (0.40 if blocked else 1.0)

        if blocked:
            self.damage_event.emit(DamageEvent(
                hero.hero.hero_id, hero.x, hero.y - 39,
                power * 0.60, "block",
            ))

        if elemental:
            damage *= 1 - s.resistance(element)
        else:
            damage *= 100 / (100 + s.armor)

        damage *= 1 - min(0.90, hero.buff("reduction", self.time))
        damage = max(0.0, damage - s.damage_absorption)

        personal = min(hero.shield, damage)
        hero.shield -= personal
        damage -= personal

        shared = min(self.barrier, damage)
        self.barrier -= shared
        damage -= shared

        if "ether_shield" in self._effects.keystones:
            mana_absorb = min(hero.mana, damage * 0.30)
            hero.mana -= mana_absorb
            damage -= mana_absorb

        dealt = min(hero.hp, damage)
        hero.hp = max(0.0, hero.hp - dealt)

        self.damage_event.emit(DamageEvent(
            hero.hero.hero_id, hero.x, hero.y - 32,
            dealt,
            ("magical" if elemental else "physical") if dealt > 0 else "barrier",
        ))

        if not hero.alive:
            hero.animation = "die"
            hero.animation_left = 0.0
            hero.pending_skill = None
        elif dealt > 0:
            self._animate(hero, "hurt", 0.20)

        if (
            hero.alive
            and "second_wind" in self._effects.keystones
            and hero.hp < s.max_hp * 0.20
            and self.time >= hero.second_wind_ready
        ):
            hero.second_wind_ready = self.time + 60
            self._heal(hero, s.max_hp * 0.30)

        return dealt

    def _heal(self, hero: HeroRuntime, amount: float, *, show: bool = True) -> None:
        if not hero.alive or amount <= 0:
            return
        restored = min(hero.stats.max_hp - hero.hp, amount)
        if restored <= 0:
            return
        hero.hp += restored

        if show:
            self.damage_event.emit(DamageEvent(
                hero.hero.hero_id, hero.x, hero.y - 32,
                restored, "heal",
            ))

    def _tick_enemies(self, dt: float) -> None:
        for index, enemy in enumerate(self._enemies):
            if not enemy.alive:
                enemy.corpse_left -= dt
                continue

            if enemy.is_boss:
                enemy.rage = min(
                    enemy.rage_max,
                    enemy.rage + dt * enemy.rage_max / 30,
                )

            enemy.attack_timer = max(0.0, enemy.attack_timer - dt)
            destination = 225 + (index % 3) * 20

            if enemy.x > destination:
                enemy.x = max(destination, enemy.x - enemy.speed * dt)
                if enemy.animation in ("idle", "run"):
                    enemy.animation = "run"
                continue

            if enemy.animation == "run":
                enemy.animation = "idle"

            allies = [hero for hero in self._heroes.values() if hero.alive]
            if not allies:
                return

            if enemy.attack_timer <= 1e-9:
                target = self.rng.choice(allies) if enemy.magical else allies[0]
                self._animate(enemy, "attack", 0.35)
                enemy.attack_timer = enemy.effective_interval

                element = (
                    ENEMY_ELEMENT.get(enemy.template_id, "chaos")
                    if enemy.magical else "physical"
                )
                dealt = self._hit_hero(
                    target, enemy.effective_damage, enemy.magical,
                    element=element,
                )

                if EnemyAffix.VAMPIRIC in enemy.affixes and dealt > 0:
                    restored = min(enemy.max_hp - enemy.hp, dealt * 0.25)
                    enemy.hp += restored
                    if restored > 0:
                        self.damage_event.emit(DamageEvent(
                            enemy.enemy_id, enemy.x, enemy.y - 32,
                            restored, "heal",
                        ))

    def _party_snapshots(self):
        result = []
        for snapshot in self.state.data.party:
            runtime = self._heroes.get(snapshot.hero_id)
            if runtime is None:
                result.append(snapshot)
                continue
            hp = (
                0 if not runtime.alive
                else max(1, min(
                    snapshot.max_hp,
                    math.ceil(runtime.hp / runtime.stats.max_hp * snapshot.max_hp),
                ))
            )
            result.append(replace(snapshot, hp=hp))
        return tuple(result)

    def _progress(self) -> float:
        if self.phase == "between":
            return 1.0
        if self.phase != "battle":
            return 0.0
        return max(0.0, min(
            1.0,
            1 - sum(enemy.hp for enemy in self._enemies) / self._wave_total_hp,
        ))

    def flush(self) -> None:
        self.state.assert_owner_thread()
        if not self._heroes:
            return
        before = self.state.data
        progress = self._progress() if self.phase == "battle" else 0.0

        self.state.commit(before, replace(
            before,
            party=self._party_snapshots(),
            wave_fraction=str(Fraction(str(min(progress, 0.999999999)))),
        ))

    def _finish_wave(self) -> None:
        self.phase = "between"
        self._phase_left = BETWEEN_WAVES
        self._dots.clear()
        self._impacts.clear()

        before = self.state.data
        profile = before.farm

        gold = math.floor(
            profile.gold_per_wave * (1 + Fraction(str(profile.gold_bonus)))
        )
        if self._wave % 10 == 0 and "gold_fever" in self._effects.keystones:
            gold *= 4

        secondary = [
            self._heroes[snapshot.hero_id].stats
            for snapshot in before.party
        ]
        gains, cursor = experience_awards(
            profile.exp_per_wave, 1, secondary, before.exp_cursor,
        )
        party = tuple(
            replace(snapshot, total_exp=snapshot.total_exp + gains[index])
            for index, snapshot in enumerate(self._party_snapshots())
        )

        stash = list(before.stash)
        if self.rng.random() < profile.drop_chance:
            rarity = self.rng.choices(
                [entry[0] for entry in C.LOOT_TABLE],
                weights=[entry[1] for entry in C.LOOT_TABLE],
                k=1,
            )[0]
            price = {entry[0]: entry[2] for entry in C.LOOT_TABLE}[rarity]

            if len(stash) >= before.stash_capacity:
                gold += math.floor(
                    price * (1 + Fraction(str(profile.sale_bonus)))
                )
            else:
                item = generate_item(
                    1 + (self._wave - 1) // 100,
                    rarity, source_wave=self._wave, rng=self.rng,
                )
                known = {
                    entry.item_id
                    for entry in (*before.stash, *before.backpack)
                }
                known.update(
                    entry.item_id
                    for build in before.hero_builds
                    for entry in build.equipment
                )
                while item.item_id in known:
                    item = replace(
                        item, item_id=f"item-{self.rng.getrandbits(128):032x}"
                    )
                stash.append(replace(item, sell_value=price))

        farm = profile
        if not self._continued_wave:
            measured = max(C.MIN_WAVE_CLEAR_SECONDS, self._wave_real_elapsed)
            farm = replace(
                profile,
                average_wave_clear_seconds=max(
                    C.MIN_WAVE_CLEAR_SECONDS,
                    profile.average_wave_clear_seconds * 0.85 + measured * 0.15,
                ),
            )

        self.state.commit(before, replace(
            before,
            gold=before.gold + gold,
            party=party,
            stash=tuple(stash),
            cleared_waves=before.cleared_waves + 1,
            wave_fraction="0",
            exp_cursor=cursor,
            farm=farm,
        ))
        self.wave_finished.emit(self._wave)

    def _defeat(self, reason: str) -> None:
        self.phase = "defeat"
        self._phase_left = DEFEAT_DELAY
        self._dots.clear()
        self._impacts.clear()
        for hero in self._heroes.values():
            hero.pending_skill = None

        before = self.state.data
        self.state.commit(before, replace(
            before,
            party=self._party_snapshots(),
            wave_fraction="0",
        ))
        self.party_defeated.emit(reason)

    def frame(self) -> CombatFrame:
        actors = [
            ActorFrame(
                hero.hero.hero_id, hero.hero.hero_class.value, hero.hero.name,
                hero.x, hero.y, hero.hp, hero.stats.max_hp,
                hero.animation, False,
                mana=hero.mana, max_mana=hero.stats.max_mana,
            )
            for hero in self._heroes.values()
        ]

        for enemy in self._enemies:
            if not enemy.alive and enemy.corpse_left <= 0:
                continue
            actors.append(ActorFrame(
                enemy.enemy_id, enemy.template_id, enemy.name,
                enemy.x, enemy.y, enemy.hp, enemy.max_hp,
                enemy.animation, True,
                elite=bool(enemy.affixes),
                boss=enemy.is_boss,
                rage=enemy.rage / enemy.rage_max,
            ))

        boss = any(enemy.is_boss for enemy in self._enemies)
        return CombatFrame(
            self._wave, act_for_wave(self._wave), self.phase, self.time,
            self._progress(), self.barrier, self.barrier_max,
            max(0.0, BOSS_TIME_LIMIT - self._wave_elapsed)
            if boss and self.phase == "battle" else None,
            tuple(actors),
        )
