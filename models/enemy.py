from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


WAVES_PER_ACT = 30
BOSS_EVERY = 10
BOSS_TIME_LIMIT = 45.0


class Act(str, Enum):
    CRYPTS = "crypts"
    FOREST = "forest"
    CALDERA = "caldera"
    CITADEL = "citadel"


ACT_NAMES = {
    Act.CRYPTS: "Крипты",
    Act.FOREST: "Проклятый лес",
    Act.CALDERA: "Кальдера",
    Act.CITADEL: "Цитадель",
}


class EnemyRank(str, Enum):
    NORMAL = "normal"
    ELITE = "elite"
    BOSS = "boss"


class EnemyAffix(str, Enum):
    VAMPIRIC = "vampiric"
    STONE_SKIN = "stone_skin"
    EXTRA_FAST = "extra_fast"
    REFLECTIVE = "reflective"


@dataclass(frozen=True)
class EnemyTemplate:
    template_id: str
    name: str
    act: Act
    hp: float
    damage: float
    armor: float
    attack_interval: float
    speed: float
    magical: bool = False


BESTIARY = {
    Act.CRYPTS: (
        EnemyTemplate("skeleton", "Костяной страж", Act.CRYPTS,
                      150, 20, 10, 1.7, 48),
        EnemyTemplate("wraith", "Призрак", Act.CRYPTS,
                      110, 24, 3, 1.9, 58, True),
    ),
    Act.FOREST: (
        EnemyTemplate("wolf", "Теневой волк", Act.FOREST,
                      160, 25, 6, 1.25, 76),
        EnemyTemplate("dryad", "Осквернённая дриада", Act.FOREST,
                      180, 24, 12, 1.8, 44, True),
    ),
    Act.CALDERA: (
        EnemyTemplate("imp", "Пепельный бес", Act.CALDERA,
                      145, 32, 9, 1.4, 65, True),
        EnemyTemplate("golem", "Обсидиановый голем", Act.CALDERA,
                      280, 35, 32, 2.2, 32),
    ),
    Act.CITADEL: (
        EnemyTemplate("sentinel", "Страж Цитадели", Act.CITADEL,
                      260, 38, 28, 1.6, 48),
        EnemyTemplate("inquisitor", "Инквизитор Бездны", Act.CITADEL,
                      200, 43, 15, 1.8, 50, True),
    ),
}

BESTIARY[Act.CRYPTS] += (
    EnemyTemplate(
        "bat", "Могильная нетопырь", Act.CRYPTS,
        85, 15, 2, 1.15, 82,
    ),
)

BESTIARY[Act.FOREST] += (
    EnemyTemplate(
        "spider", "Паук-погребальщик", Act.FOREST,
        125, 23, 8, 1.30, 65,
    ),
)

# Дополнительная гамма монстров (v1.4.0) — богатый бестиарий.
BESTIARY[Act.CRYPTS] += (
    EnemyTemplate("bone_archer", "Костяной лучник", Act.CRYPTS,
                  120, 26, 8, 1.9, 42, True),
    EnemyTemplate("grave_horror", "Могильный ужас", Act.CRYPTS,
                  200, 28, 16, 1.8, 40),
    EnemyTemplate("funeral_wraith", "Погребальная тень", Act.CRYPTS,
                  105, 25, 3, 1.6, 66, True),
)
BESTIARY[Act.FOREST] += (
    EnemyTemplate("plague_ghoul", "Чумной упырь", Act.FOREST,
                  190, 27, 10, 1.4, 60),
    EnemyTemplate("bog_witch", "Болотная ведьма", Act.FOREST,
                  150, 30, 6, 2.0, 40, True),
    EnemyTemplate("mangrove_brute", "Мангровый ломовик", Act.FOREST,
                  250, 33, 20, 2.1, 34),
)
BESTIARY[Act.CALDERA] += (
    EnemyTemplate("cinder_spawn", "Угольное отродье", Act.CALDERA,
                  130, 34, 8, 1.3, 70, True),
    EnemyTemplate("magma_giant", "Магматический колосс", Act.CALDERA,
                  330, 40, 38, 2.4, 26),
    EnemyTemplate("ash_reaver", "Пеплолов", Act.CALDERA,
                  220, 37, 20, 1.6, 46),
)
BESTIARY[Act.CITADEL] += (
    EnemyTemplate("void_reaper", "Теневой жнец", Act.CITADEL,
                  230, 45, 12, 1.7, 56, True),
    EnemyTemplate("distortion_eye", "Глаз искажения", Act.CITADEL,
                  170, 40, 10, 1.4, 60, True),
    EnemyTemplate("rift_herald", "Глашатай разлома", Act.CITADEL,
                  300, 48, 26, 1.9, 40),
)

# Прочность, чтобы бестиарий выглядел «обильным»: всего уникальных типов.
def _total_enemy_types() -> int:
    return sum(len(tuple(value)) for value in BESTIARY.values())


TOTAL_ENEMY_TYPES = _total_enemy_types()

# Боссы актов получают собственный масштаб отрисовки (пол-экрана арены).
BOSS_SPRITE_SIZE = 60          # базовый спрайт босса в логических px
BOSS_AURA = True               # багрово-золотая аура на боссах актов
BOSS_ELITE_AURA = "#c0202f"

BOSS_NAMES = {
    Act.CRYPTS: "Костяной Архонт",
    Act.FOREST: "Сердце Гнили",
    Act.CALDERA: "Владыка Пепла",
    Act.CITADEL: "Хранитель Разлома",
}

# Визуальные «роды» для элитных ауров по актам.
ELITE_AURA_COLORS = {
    Act.CRYPTS: "#9f9cff",
    Act.FOREST: "#7fe08a",
    Act.CALDERA: "#ff9340",
    Act.CITADEL: "#c85bff",
}


@dataclass
class Enemy:
    """Изменяемая боевая сущность. В save.json напрямую не сохраняется."""

    enemy_id: str
    template_id: str
    name: str
    act: Act
    rank: EnemyRank
    affixes: tuple[EnemyAffix, ...]

    max_hp: float
    hp: float
    damage: float
    armor: float
    attack_interval: float
    speed: float
    magical: bool

    x: float
    y: float
    attack_timer: float = 0.5

    rage: float = 0.0
    rage_max: float = 100.0

    animation: str = "run"
    animation_left: float = 0.0
    corpse_left: float = 0.65

    marked_until: float = 0.0
    marked_bonus: float = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def is_boss(self) -> bool:
        return self.rank == EnemyRank.BOSS

    @property
    def enraged(self) -> bool:
        return self.is_boss and self.rage >= self.rage_max

    @property
    def effective_damage(self) -> float:
        return self.damage * (1.6 if self.enraged else 1.0)

    @property
    def effective_interval(self) -> float:
        return self.attack_interval * (0.7 if self.enraged else 1.0)


def act_for_wave(wave: int) -> Act:
    if type(wave) is not int or wave < 1:
        raise ValueError("Номер волны должен быть целым >= 1")
    index = min((wave - 1) // WAVES_PER_ACT, len(Act) - 1)
    return tuple(Act)[index]


def spawn_wave(
    wave: int,
    rng: random.Random | None = None,
    *,
    generation: int = 0,
) -> list[Enemy]:
    act = act_for_wave(wave)
    generator = rng if rng is not None else random.Random()

    boss_wave = wave % BOSS_EVERY == 0
    count = 1 if boss_wave else min(6, 3 + (wave - 1) // 20)

    # Общая прогрессия сложности, без сброса при переходе акта.
    hp_scale = (1.0 + 0.09 * (wave - 1)) ** 1.35
    damage_scale = (1.0 + 0.06 * (wave - 1)) ** 1.15

    result = []

    for index in range(count):
        template = generator.choice(BESTIARY[act])

        if boss_wave:
            rank = EnemyRank.BOSS
            affixes = ()
        elif generator.random() < min(0.35, 0.12 + wave * 0.002):
            rank = EnemyRank.ELITE
            amount = 2 if wave >= 40 else 1
            affixes = tuple(generator.sample(tuple(EnemyAffix), amount))
        else:
            rank = EnemyRank.NORMAL
            affixes = ()

        hp_multiplier = {
            EnemyRank.NORMAL: 1.0,
            EnemyRank.ELITE: 1.9,
            EnemyRank.BOSS: 7.0,
        }[rank]

        attack_multiplier = {
            EnemyRank.NORMAL: 1.0,
            EnemyRank.ELITE: 1.35,
            EnemyRank.BOSS: 1.8,
        }[rank]

        armor = template.armor + wave * 0.7
        interval = template.attack_interval
        speed = template.speed

        if EnemyAffix.STONE_SKIN in affixes:
            armor = armor * 2 + 25

        if EnemyAffix.EXTRA_FAST in affixes:
            interval *= 0.70
            speed *= 1.55

        max_hp = template.hp * hp_scale * hp_multiplier

        result.append(Enemy(
            enemy_id=f"enemy-{generation}-{wave}-{index}",
            template_id=template.template_id,
            name=BOSS_NAMES[act] if boss_wave else template.name,
            act=act,
            rank=rank,
            affixes=affixes,
            max_hp=max_hp,
            hp=max_hp,
            damage=template.damage * damage_scale * attack_multiplier,
            armor=armor,
            attack_interval=interval,
            speed=speed,
            magical=template.magical,
            x=460.0 + index * 48,
            y=99.0 + (index % 2) * 12,
        ))

    return result
