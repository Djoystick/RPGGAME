from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, replace
from fractions import Fraction

from PySide6.QtCore import QObject, Signal

from engine import combat_core as core
from engine.combat_core import (
    ActorFrame,
    DamageEvent,
    HeroRuntime,
    Hit,
    PendingImpact,
    combined_chance,
    roll_damage,
)
from engine.save_manager import SaveError, SaveManager
from engine.state import GameState
from models.enemy import Enemy
from models.hero import HeroClass
from models.item import Item, roll_enemy_loot


# Совместимые публичные константы.
FIXED_STEP = core.FIXED_STEP
HERO_IFRAMES = core.HERO_IFRAMES
BASIC_INTERVALS = core.BASIC_INTERVALS
BARRIER_RATIO = core.BARRIER_RATIO
BETWEEN_WAVES = core.BETWEEN_WAVES
DEFEAT_DELAY = core.DEFEAT_DELAY
BASE_ATTACK_COST = core.BASE_ATTACK_COST
BASE_PROJECTILE_SPEED = core.BASE_PROJECTILE_SPEED

HERO_POSITIONS = (
    (155.0, 112.0),
    (135.0, 95.0),
    (105.0, 115.0),
    (75.0, 100.0),
)

CLASS_POSITIONS = {
    HeroClass.KNIGHT: (155.0, 112.0),
    HeroClass.PALADIN: (155.0, 112.0),
    HeroClass.ASSASSIN: (135.0, 95.0),
    HeroClass.RANGER: (105.0, 115.0),
    HeroClass.PYROMANCER: (75.0, 100.0),
    HeroClass.NECROMANCER: (75.0, 100.0),
}


@dataclass(frozen=True)
class ProjectileFrame:
    projectile_id: int
    owner_id: str
    target_id: str
    kind: str
    x: float
    y: float
    target_x: float
    target_y: float
    progress: float
    angle: float


@dataclass(frozen=True)
class CombatFrame(core.CombatFrame):
    projectiles: tuple[ProjectileFrame, ...] = ()


@dataclass(frozen=True)
class VfxEvent:
    kind: str
    x: float
    y: float
    element: str = "physical"
    critical: bool = False


@dataclass(frozen=True)
class LootEvent:
    item: Item
    x: float
    y: float
    stored: bool
    sale_gold: int = 0


@dataclass
class VisualImpact(PendingImpact):
    visual_id: int = 0
    visual_kind: str = ""
    start_x: float = 0.0
    start_y: float = 0.0
    launch_time: float = 0.0
    travel_time: float = 0.0


@dataclass(frozen=True)
class PendingLoot:
    key: str
    wave: int
    x: float
    y: float
    items: tuple[Item, ...]


class CombatManager(core.CombatManager):
    vfx_event = Signal(object)
    loot_event = Signal(object)
    combat_error = Signal(str)

    def __init__(
        self,
        state: GameState,
        *,
        rng: random.Random | None = None,
        saves: SaveManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(state, rng=rng, parent=parent)
        self.saves = saves

        self._visual_serial = 0
        self._pending_loot: list[PendingLoot] = []
        self._formation_signature = None
        self._home_positions: dict[str, tuple[float, float]] = {}
        self._last_save_error = ""

    def _sync_heroes(self) -> None:
        previous_ids = set(self._heroes)
        super()._sync_heroes()

        signature = tuple(
            (hero.hero.hero_id, hero.hero.hero_class)
            for hero in self._heroes.values()
        )
        if signature == self._formation_signature:
            return

        self._formation_signature = signature
        self._home_positions.clear()

        occupied: dict[tuple[float, float], int] = {}
        for hero in self._heroes.values():
            base = CLASS_POSITIONS[hero.hero.hero_class]
            duplicate = occupied.get(base, 0)
            occupied[base] = duplicate + 1

            # Два танка или два мага не занимают один пиксель.
            x = base[0] - duplicate * 25
            y = base[1] - duplicate * 20
            home = (max(38.0, x), max(69.0, y))

            self._home_positions[hero.hero.hero_id] = home
            if hero.hero.hero_id not in previous_ids:
                hero.x, hero.y = home
            else:
                hero.x, hero.y = home

    def _spawn(self) -> None:
        super()._spawn()
        for hero in self._heroes.values():
            hero.x, hero.y = self._home_positions[hero.hero.hero_id]

    def _tick_heroes(self, dt: float) -> None:
        """
        Сохраняет правила core: AS, CDR, стоимость атак, касты,
        призыв и дальность. Меняет только привязку движения к построению.
        """
        for hero in tuple(self._heroes.values()):
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
                        element="chaos",
                        tags=frozenset({"summon"}),
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
                    hero.skill_cooldowns[skill.skill_id] = self.skill_cooldown(
                        hero, skill
                    )
                    hero.pending_skill = skill
                    hero.cast_left = 0.45 / hero.stats.cast_speed
                    self._animate(hero, "cast", hero.cast_left)
                    self.skill_used.emit(hero.hero.hero_id, skill.skill_id)
                    cast = True
                    break

            if cast:
                continue

            home_x, _ = self._home_positions[hero.hero.hero_id]
            reach = hero.stats.basic_attack_range

            if self._distance(hero, target) > reach:
                destination = min(
                    195.0,
                    max(home_x, target.x - reach + 2),
                )
                movement = hero.stats.movement_speed * 0.06 * dt
                hero.x += max(
                    -movement,
                    min(movement, destination - hero.x),
                )
                if hero.animation in ("idle", "run"):
                    hero.animation = "run"
                continue

            if hero.animation == "run":
                hero.animation = "idle"

            cost = max(
                0.0,
                BASE_ATTACK_COST - hero.stats.basic_requirement_reduction,
            )

            if hero.basic_timer <= 1e-9 and hero.mana >= cost:
                hero.mana -= cost
                hero.basic_timer = self.basic_interval(hero)
                self._animate(
                    hero, "attack",
                    min(0.35, hero.basic_timer * 0.8),
                )

                element = core.CLASS_ELEMENT[hero.hero.hero_class]
                ranged = hero.hero.hero_class in (
                    HeroClass.PYROMANCER,
                    HeroClass.RANGER,
                    HeroClass.NECROMANCER,
                )
                power = (
                    hero.stats.physical_damage
                    if element == "physical"
                    else hero.stats.magical_damage
                )
                self._dispatch(
                    hero,
                    target,
                    power,
                    element,
                    frozenset({"projectile" if ranged else "melee"}),
                )

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
        repetitions = (
            self._repeat_count(hero.stats.multistrike)
            if repeat else 1
        )
        projectiles = (
            1 + hero.stats.projectile_count
            if "projectile" in tags else 1
        )

        ranged = "projectile" in tags
        travel = 0.0

        if ranged:
            speed = BASE_PROJECTILE_SPEED * (
                1 + hero.stats.projectile_speed
            )
            travel = self._distance(hero, target) / speed

        kind = {
            HeroClass.RANGER: "arrow",
            HeroClass.PYROMANCER: "fireball",
            HeroClass.NECROMANCER: "necrotic",
        }.get(hero.hero.hero_class, "arcane")

        for repetition in range(repetitions):
            for projectile in range(projectiles):
                delay = repetition * 0.10 + projectile * 0.025
                self._visual_serial += 1

                self._impacts.append(VisualImpact(
                    owner_id=hero.hero.hero_id,
                    enemy_id=target.enemy_id,
                    power=power,
                    element=element,
                    tags=tags,
                    remaining=travel + delay,
                    drain=drain,
                    visual_id=self._visual_serial,
                    visual_kind=kind if ranged else "",
                    start_x=hero.x + 9,
                    start_y=hero.y - 23,
                    launch_time=self.time + delay,
                    travel_time=max(travel, 0.001),
                ))

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
        was_alive = enemy.alive
        if not was_alive:
            return 0.0

        dealt = super()._hit_enemy(
            hero, enemy, power, magical,
            element=element,
            tags=tags,
            allow_crit=allow_crit,
            allow_splash=allow_splash,
            on_hit=on_hit,
            show_event=show_event,
        )

        resolved_element = element or (
            "magic" if magical else "physical"
        )

        if dealt > 0 and on_hit:
            if (
                hero.hero.hero_class == HeroClass.PALADIN
                and resolved_element == "lightning"
            ):
                self.vfx_event.emit(VfxEvent(
                    "holy", enemy.x, enemy.y - 18, "lightning"
                ))
            elif "melee" in tags:
                self.vfx_event.emit(VfxEvent(
                    "slash", enemy.x, enemy.y - 20, resolved_element
                ))

            self.vfx_event.emit(VfxEvent(
                "impact", enemy.x, enemy.y - 20, resolved_element
            ))

        if was_alive and not enemy.alive:
            self._queue_death_loot(enemy)

        return dealt

    def _hit_hero(
        self,
        hero: HeroRuntime,
        power: float,
        magical: bool,
        *,
        element: str | None = None,
    ) -> float:
        barrier_before = self.barrier
        result = super()._hit_hero(
            hero, power, magical, element=element
        )

        if self.barrier < barrier_before:
            self.vfx_event.emit(VfxEvent(
                "barrier", hero.x, hero.y - 18, "magic"
            ))
        return result

    def _queue_death_loot(self, enemy: Enemy) -> None:
        index = enemy.enemy_id.rsplit("-", 1)[-1]
        key = f"{self._wave}:{index}"

        if key in self.state.data.reward_claims:
            return
        if any(record.key == key for record in self._pending_loot):
            return

        items = roll_enemy_loot(
            self._wave,
            enemy.rank.value,
            self.rng,
        )

        # Пустой ролл тоже фиксируется: перезапуск не даёт новый шанс.
        self._pending_loot.append(PendingLoot(
            key=key,
            wave=self._wave,
            x=enemy.x,
            y=enemy.y,
            items=items,
        ))

    def _settle_loot(self) -> None:
        if not self._pending_loot:
            return

        before = self.state.data
        claims = set(before.reward_claims)
        stash = list(before.stash)
        gold = before.gold
        events: list[LootEvent] = []

        occupied_ids = {
            item.item_id
            for item in (*before.stash, *before.backpack)
        }
        occupied_ids.update(
            item.item_id
            for build in before.hero_builds
            for item in build.equipment
        )

        for record in self._pending_loot:
            if record.key in claims:
                continue

            claims.add(record.key)

            for original_item in record.items:
                item = original_item
                while item.item_id in occupied_ids:
                    item = replace(
                        item,
                        item_id=f"item-{self.rng.getrandbits(128):032x}",
                    )
                occupied_ids.add(item.item_id)

                stored = len(stash) < before.stash_capacity
                sale = 0

                if stored:
                    stash.append(item)
                else:
                    sale = math.floor(
                        item.sell_value
                        * (1 + Fraction(str(before.farm.sale_bonus)))
                    )
                    gold += sale

                events.append(LootEvent(
                    item, record.x, record.y, stored, sale
                ))

        # Нужны текущая и предыдущая волны; история не растёт бесконечно.
        oldest = max(1, before.current_wave - 1)
        claims = {
            key for key in claims
            if int(key.split(":")[0]) >= oldest
        }

        progress = self._progress() if self.phase == "battle" else 0.0

        after = replace(
            before,
            gold=gold,
            stash=tuple(stash),
            party=self._party_snapshots(),
            wave_fraction=str(Fraction(str(min(progress, 0.999999999)))),
            reward_claims=tuple(sorted(claims)),
        )

        if self.saves is not None:
            after = replace(
                after,
                last_active_timestamp=max(
                    time.time(), after.last_active_timestamp
                ),
            )
            self.saves.write(after)

        self.state.commit(before, after)
        self._pending_loot.clear()
        self._last_save_error = ""

        for event in events:
            self.loot_event.emit(event)

    def _step(self, dt: float, real_dt: float) -> None:
        try:
            # При отказе диска сначала завершаем прошлую выдачу.
            self._settle_loot()
        except SaveError as exc:
            self._report_save_error(exc)
            return

        super()._step(dt, real_dt)

        try:
            self._settle_loot()
        except SaveError as exc:
            self._report_save_error(exc)

    def _report_save_error(self, exc: Exception) -> None:
        message = str(exc)
        if message != self._last_save_error:
            self._last_save_error = message
            self.combat_error.emit(
                "Бой приостановлен: не удалось сохранить лут. " + message
            )

    def flush(self) -> None:
        self._settle_loot()
        super().flush()

    def frame(self) -> CombatFrame:
        base = super().frame()
        enemies = {enemy.enemy_id: enemy for enemy in self._enemies}
        projectiles = []

        for impact in self._impacts:
            if not isinstance(impact, VisualImpact):
                continue
            if not impact.visual_kind:
                continue
            if self.time < impact.launch_time:
                continue

            target = enemies.get(impact.enemy_id)
            if target is None or not target.alive:
                continue

            progress = max(
                0.0,
                min(1.0, 1 - impact.remaining / impact.travel_time),
            )
            tx, ty = target.x, target.y - 20
            x = impact.start_x + (tx - impact.start_x) * progress
            y = impact.start_y + (ty - impact.start_y) * progress
            angle = math.atan2(ty - impact.start_y, tx - impact.start_x)

            projectiles.append(ProjectileFrame(
                impact.visual_id,
                impact.owner_id,
                impact.enemy_id,
                impact.visual_kind,
                x, y, tx, ty, progress, angle,
            ))

        return CombatFrame(
            wave=base.wave,
            act=base.act,
            phase=base.phase,
            time=base.time,
            progress=base.progress,
            barrier=base.barrier,
            barrier_max=base.barrier_max,
            boss_remaining=base.boss_remaining,
            actors=base.actors,
            projectiles=tuple(projectiles),
        )
