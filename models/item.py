from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from models.stats import StatBlock


class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    LEGENDARY = "legendary"
    IMMORTAL = "immortal"
    MYTHIC = "mythic"


RARITY_ORDER = tuple(Rarity)

RARITY_POWER = {
    Rarity.COMMON: 1.0,
    Rarity.UNCOMMON: 1.25,
    Rarity.RARE: 1.65,
    Rarity.LEGENDARY: 2.40,
    Rarity.IMMORTAL: 3.50,
    Rarity.MYTHIC: 5.00,
}


class EquipmentSlot(str, Enum):
    WEAPON = "weapon"
    OFFHAND = "offhand"
    HEAD = "head"
    CHEST = "chest"
    GLOVES = "gloves"
    BOOTS = "boots"
    BELT = "belt"
    AMULET = "amulet"
    RING_1 = "ring_1"
    RING_2 = "ring_2"


class ItemKind(str, Enum):
    GENERIC = "generic"
    WEAPON = "weapon"
    FOCUS = "focus"
    SHIELD = "shield"


ACT_IDS = ("crypts", "forest", "caldera", "citadel")

ACT_NAMES = {
    "crypts": "Катакомбы Падших",
    "forest": "Осквернённая Чаща",
    "caldera": "Пепельная Кальдера",
    "citadel": "Цитадель Бездны",
}

ACT_LORE = {
    "crypts": (
        "На металле проступают имена тех, чьи могилы давно забыты.",
        "Холод усыпальницы остался внутри, даже когда погасли погребальные свечи.",
        "Хранитель катакомб слышал шёпот этой реликвии прежде собственного имени.",
    ),
    "forest": (
        "Корни оплели реликвию, но не смогли поглотить заключённую в ней волю.",
        "В тишине слышно, как под кожей предмета движется ядовитый сок.",
        "Чаща возвращает свои дары только тем, кого уже считает добычей.",
    ),
    "caldera": (
        "Последний удар кузнеца растворился в грохоте извержения.",
        "В трещинах ещё течёт огонь, не знающий ни воздуха, ни времени.",
        "Обсидиан помнит форму пламени, из которого был рождён.",
    ),
    "citadel": (
        "Эта вещь отбрасывает тень в сторону ещё не наступившего рассвета.",
        "За гранью камня мерцает зал, которого нет ни на одной карте.",
        "Создатель реликвии исчез из истории, но его клятва продолжает действовать.",
    ),
}

SLOT_NAMES = {
    EquipmentSlot.WEAPON: "Клинок",
    EquipmentSlot.OFFHAND: "Фокус",
    EquipmentSlot.HEAD: "Венец",
    EquipmentSlot.CHEST: "Доспех",
    EquipmentSlot.GLOVES: "Перчатки",
    EquipmentSlot.BOOTS: "Сапоги",
    EquipmentSlot.BELT: "Пояс",
    EquipmentSlot.AMULET: "Амулет",
    EquipmentSlot.RING_1: "Кольцо",
    EquipmentSlot.RING_2: "Перстень",
}

SLOT_BASE_STATS = {
    EquipmentSlot.WEAPON: StatBlock(damage=8),
    EquipmentSlot.OFFHAND: StatBlock(armor=4, mana=8),
    EquipmentSlot.HEAD: StatBlock(armor=3, intelligence=1),
    EquipmentSlot.CHEST: StatBlock(armor=8, max_hp=20),
    EquipmentSlot.GLOVES: StatBlock(armor=2, agility=1),
    EquipmentSlot.BOOTS: StatBlock(armor=2, agility=1),
    EquipmentSlot.BELT: StatBlock(max_hp=15, vitality=1),
    EquipmentSlot.AMULET: StatBlock(intelligence=2, mana=10),
    EquipmentSlot.RING_1: StatBlock(luck=1, damage=2),
    EquipmentSlot.RING_2: StatBlock(luck=1, damage=2),
}


@dataclass(frozen=True)
class AffixDefinition:
    affix_id: str
    name: str
    stats: StatBlock


def affix(
    affix_id: str,
    name: str,
    **stats: float,
) -> AffixDefinition:
    return AffixDefinition(affix_id, name, StatBlock(**stats))


# Идентификаторы предыдущих версий сохранены.
BASE_PREFIXES = (
    affix("brutal", "Жестокий", strength=2),
    affix("nimble", "Проворный", agility=2),
    affix("occult", "Оккультный", intelligence=2),
    affix("stout", "Несокрушимый", vitality=2),
    affix("lucky", "Благословенный", luck=2),
    affix("sharp", "Острый", damage=3),
    affix("flaming", "Пылающий", fire_bonus=0.04),
    affix("frozen", "Ледяной", cold_bonus=0.04),
    affix("storm", "Грозовой", lightning_bonus=0.04),
    affix("void", "Пустотный", chaos_bonus=0.04),
    affix("swift", "Стремительный", attack_speed=0.04),
    affix("echoing", "Отражённый", multistrike=0.08),
    affix("volley", "Многоликий", projectile_count=1),
    affix("far", "Дальновидный", basic_attack_range=8, skill_range=0.04),
    affix("ritual", "Ритуальный", cast_speed=0.04),
    affix("sweeping", "Размашистый", melee_bonus=0.04),
    affix("ballistic", "Пронзающий", projectile_bonus=0.04),
    affix("devastating", "Опустошающий", aoe_damage=0.04),
    affix("summoner", "Призывающий", summon_damage=0.04),
    affix("efficient", "Неутомимый", basic_requirement_reduction=1),
)

BASE_SUFFIXES = (
    affix("of_war", "Войны", physical_bonus=0.02),
    affix("of_ether", "Эфира", magical_bonus=0.02),
    affix("of_life", "Жизни", max_hp=12),
    affix("of_precision", "Точности", crit_chance=0.005),
    affix("of_shadow", "Тени", evasion=0.005),
    affix("of_ruin", "Разрушения", crit_damage=0.03),
    affix("of_embers", "Углей", fire_res=0.025),
    affix("of_winter", "Зимы", cold_res=0.025),
    affix("of_thunder", "Грома", lightning_res=0.025),
    affix("of_silence", "Безмолвия", chaos_res=0.025),
    affix("of_recovery", "Восстановления", hp_regen=0.5),
    affix("of_time", "Времени", cooldown_reduction=0.015),
    affix("of_guard", "Стража", block_chance=0.015),
    affix("of_feasting", "Пира", hp_per_hit=1.5),
    affix("of_execution", "Казни", hp_per_kill=4),
    affix("of_vampire", "Вампира", life_leech=0.01),
    affix("of_wisdom", "Мудрости", exp_gain=0.025),
    affix("of_learning", "Познания", additional_exp=2),
    affix("of_warding", "Оберега", damage_absorption=1.5),
    affix("of_mirage", "Миража", elemental_dodge=0.01),
    affix("of_aegis", "Эгиды", elemental_block=0.015),
    affix("of_haste", "Спешки", movement_speed=25),
    affix("of_expansion", "Расширения", aoe_enhancement=0.04),
    affix("of_eternity", "Вечности", skill_duration=0.04),
    affix("of_mercy", "Милосердия", skill_heal=0.04),
    affix("of_mastery", "Мастерства", all_skill_level=1),
    affix("of_flight", "Полёта", projectile_speed=0.05),
)

ACT_PREFIXES = {
    "crypts": (
        affix("crypt_bone", "Костяной", armor=3, vitality=1),
        affix("crypt_funeral", "Погребальный", chaos_bonus=0.035),
        affix("crypt_catacomb", "Катакомбный", cold_res=0.03),
        affix("crypt_grave", "Могильный", hp_per_kill=3),
        affix("crypt_pale", "Бледный", cold_bonus=0.035),
        affix("crypt_ossuary", "Оссуарный", summon_damage=0.04),
    ),
    "forest": (
        affix("forest_corrupt", "Осквернённый", chaos_bonus=0.035),
        affix("forest_thorn", "Терновый", physical_bonus=0.03),
        affix("forest_whisper", "Шепчущий", evasion=0.015),
        affix("forest_moss", "Мшистый", hp_regen=0.6),
        affix("forest_feral", "Звериный", attack_speed=0.04),
        affix("forest_spore", "Споровый", skill_duration=0.05),
    ),
    "caldera": (
        affix("caldera_obsidian", "Обсидиановый", armor=4, crit_damage=0.02),
        affix("caldera_magma", "Магматический", fire_bonus=0.045),
        affix("caldera_fireborn", "Огнерождённый", fire_res=0.035),
        affix("caldera_cinder", "Угольный", damage=3),
        affix("caldera_furnace", "Горновой", melee_bonus=0.04),
        affix("caldera_scorched", "Опалённый", aoe_damage=0.04),
    ),
    "citadel": (
        affix("citadel_ether", "Эфирный", magical_bonus=0.04),
        affix("citadel_ancient", "Предвечный", all_skill_level=1),
        affix("citadel_astral", "Астральный", lightning_bonus=0.04),
        affix("citadel_rift", "Разломный", projectile_count=1),
        affix("citadel_timeless", "Вневременной", cooldown_reduction=0.02),
        affix("citadel_sovereign", "Державный", block_chance=0.02),
    ),
}

ACT_SUFFIXES = {
    "crypts": (
        affix("crypt_decay", "Тлена", chaos_res=0.03),
        affix("crypt_tomb", "Усыпальницы", max_hp=16),
        affix("crypt_coldblood", "Хладной крови", life_leech=0.012),
        affix("crypt_requiem", "Реквиема", skill_heal=0.04),
        affix("crypt_silence", "Мёртвой тишины", elemental_dodge=0.015),
        affix("crypt_ancestors", "Предков", exp_gain=0.03),
    ),
    "forest": (
        affix("forest_rot", "Гнили", hp_per_hit=2),
        affix("forest_dew", "Ядовитой росы", chaos_bonus=0.04),
        affix("forest_predator", "Хищника", crit_chance=0.008),
        affix("forest_roots", "Глубоких корней", damage_absorption=2),
        affix("forest_hunt", "Дикой охоты", projectile_bonus=0.04),
        affix("forest_moon", "Бледной луны", movement_speed=35),
    ),
    "caldera": (
        affix("caldera_ash", "Пепла", fire_res=0.03),
        affix("caldera_eruption", "Извержения", aoe_enhancement=0.06),
        affix("caldera_lava", "Жгучей лавы", fire_bonus=0.04),
        affix("caldera_sparks", "Искр", projectile_speed=0.06),
        affix("caldera_crucible", "Тигля", block_chance=0.02),
        affix("caldera_slag", "Чёрного шлака", armor=5),
    ),
    "citadel": (
        affix("citadel_abyss", "Бездны", chaos_bonus=0.045),
        affix("citadel_fracture", "Разлома", elemental_block=0.02),
        affix("citadel_eternity", "Вечности", skill_duration=0.06),
        affix("citadel_stars", "Погасших звёзд", mana=18),
        affix("citadel_dominion", "Владычества", summon_damage=0.05),
        affix("citadel_memory", "Последней памяти", additional_exp=3),
    ),
}

PREFIXES = BASE_PREFIXES + tuple(
    entry for entries in ACT_PREFIXES.values() for entry in entries
)
SUFFIXES = BASE_SUFFIXES + tuple(
    entry for entries in ACT_SUFFIXES.values() for entry in entries
)

PREFIX_BY_ID = {entry.affix_id: entry for entry in PREFIXES}
SUFFIX_BY_ID = {entry.affix_id: entry for entry in SUFFIXES}


@dataclass(frozen=True)
class ItemArchetype:
    archetype_id: str
    name: str
    slot: EquipmentSlot
    kind: ItemKind
    visual: str
    stats: StatBlock
    favored_act: str | None = None
    gender: str = "m"


def archetype(
    key: str,
    name: str,
    slot: EquipmentSlot,
    visual: str,
    *,
    kind: ItemKind = ItemKind.GENERIC,
    act: str | None = None,
    gender: str = "m",
    **stats: float,
) -> ItemArchetype:
    return ItemArchetype(
        key, name, slot, kind, visual,
        StatBlock(**stats), act, gender,
    )


W = EquipmentSlot.WEAPON
O = EquipmentSlot.OFFHAND

ARCHETYPES = (
    archetype("knight_sword", "Меч рыцаря", W, "sword",
              kind=ItemKind.WEAPON, damage=8, strength=1),
    archetype("espadon", "Двуручный эспадон", W, "greatsword",
              kind=ItemKind.WEAPON, damage=12, melee_bonus=0.02),
    archetype("falchion", "Изогнутый фальшион", W, "sabre",
              kind=ItemKind.WEAPON, damage=8, crit_chance=0.005),
    archetype("assassin_dagger", "Кинжал убийцы", W, "dagger",
              kind=ItemKind.WEAPON, damage=5, attack_speed=0.04),
    archetype("abyss_stiletto", "Стилет Бездны", W, "dagger",
              kind=ItemKind.WEAPON, act="citadel", damage=5, crit_damage=0.05),
    archetype("twin_blades", "Парные клинки", W, "dual",
              kind=ItemKind.WEAPON, gender="p", damage=6, multistrike=0.05),
    archetype("archmage_staff", "Посох архимага", W, "staff",
              kind=ItemKind.WEAPON, intelligence=3, damage=5, mana=10),
    archetype("occult_wand", "Оккультный жезл", W, "wand",
              kind=ItemKind.WEAPON, damage=4, cast_speed=0.05),
    archetype("soul_scythe", "Коса жнеца душ", W, "scythe",
              kind=ItemKind.WEAPON, act="crypts", gender="f",
              damage=7, chaos_bonus=0.03, summon_damage=0.03),
    archetype("willow_bow", "Ивовый лук", W, "bow",
              kind=ItemKind.WEAPON, act="forest", damage=7, agility=1),
    archetype("composite_bow", "Композитный лук", W, "bow",
              kind=ItemKind.WEAPON, damage=9, projectile_bonus=0.02),
    archetype("heavy_crossbow", "Тяжёлый арбалет", W, "crossbow",
              kind=ItemKind.WEAPON, damage=11, projectile_speed=0.04),
    archetype("war_hammer", "Боевой молот", W, "hammer",
              kind=ItemKind.WEAPON, act="caldera", damage=10, strength=2),
    archetype("rosewood_mace", "Палисандровая булава", W, "mace",
              kind=ItemKind.WEAPON, gender="f", damage=7, skill_heal=0.03),
    archetype("righteous_flail", "Праведный цеп", W, "flail",
              kind=ItemKind.WEAPON, damage=8, lightning_bonus=0.03),

    archetype("knight_targe", "Рыцарский тарч", O, "shield",
              kind=ItemKind.SHIELD, armor=8),
    archetype("tower_shield", "Башенный щит", O, "tower",
              kind=ItemKind.SHIELD, armor=12, damage_absorption=1),
    archetype("steel_buckler", "Стальной баклер", O, "buckler",
              kind=ItemKind.SHIELD, armor=5, block_chance=0.025),
    archetype("grimoire", "Гримуар заклинателя", O, "book",
              kind=ItemKind.FOCUS, intelligence=2, mana=14),
    archetype("ancestor_skull", "Череп предка", O, "skull",
              kind=ItemKind.FOCUS, act="crypts", summon_damage=0.04, mana=8),
    archetype("storm_orb", "Сфера бури", O, "orb",
              kind=ItemKind.FOCUS, gender="f", lightning_bonus=0.04, mana=10),
    archetype("hunter_quiver", "Охотничий колчан", O, "quiver",
              act="forest", projectile_bonus=0.04, attack_speed=0.02),
    archetype("void_arrows", "Стрелы пустоты", O, "arrows",
              act="citadel", gender="p", projectile_count=1),

    archetype("plate_armor", "Тяжёлый панцирь", EquipmentSlot.CHEST, "plate",
              armor=12, block_chance=0.01, damage_absorption=1),
    archetype("leather_armor", "Кожаный доспех", EquipmentSlot.CHEST, "leather",
              act="forest", armor=5, evasion=0.01,
              attack_speed=0.02, projectile_bonus=0.02),
    archetype("silk_robe", "Тканевая мантия", EquipmentSlot.CHEST, "robe",
              gender="f", armor=2, mana=20,
              cooldown_reduction=0.01, cast_speed=0.03),

    archetype("horned_helm", "Рогатый шлем", EquipmentSlot.HEAD, "helm",
              armor=5, strength=1),
    archetype("shadow_hood", "Капюшон теней", EquipmentSlot.HEAD, "hood",
              evasion=0.015, crit_chance=0.005),
    archetype("ritual_crown", "Ритуальная корона", EquipmentSlot.HEAD, "crown",
              gender="f", intelligence=2, mana=10),

    archetype("steel_gauntlets", "Стальные рукавицы", EquipmentSlot.GLOVES,
              "gloves", gender="p", armor=4, strength=1),
    archetype("hunter_gloves", "Перчатки охотника", EquipmentSlot.GLOVES,
              "gloves", gender="p", agility=2, attack_speed=0.02),

    archetype("iron_boots", "Железные сапоги", EquipmentSlot.BOOTS,
              "boots", gender="p", armor=4, vitality=1),
    archetype("shadow_boots", "Сапоги теневого пути", EquipmentSlot.BOOTS,
              "boots", gender="p", movement_speed=40, evasion=0.01),

    archetype("war_belt", "Пояс воителя", EquipmentSlot.BELT,
              "belt", max_hp=18, strength=1),
    archetype("runic_belt", "Рунический кушак", EquipmentSlot.BELT,
              "belt", mana=12, damage_absorption=1),

    archetype("blood_amulet", "Кровавый амулет", EquipmentSlot.AMULET,
              "amulet", act="crypts", life_leech=0.01, max_hp=12),
    archetype("star_amulet", "Звёздный медальон", EquipmentSlot.AMULET,
              "amulet", act="citadel", intelligence=2, exp_gain=0.02),

    archetype("runic_ring", "Рунический перстень", EquipmentSlot.RING_1,
              "ring", luck=1, crit_chance=0.005),
    archetype("ember_ring", "Перстень углей", EquipmentSlot.RING_2,
              "ring", act="caldera", fire_bonus=0.025, fire_res=0.02),
    archetype("oath_ring", "Кольцо клятвы", EquipmentSlot.RING_2,
              "signet", gender="n", block_chance=0.01, skill_heal=0.02),
)

ARCHETYPE_BY_ID = {entry.archetype_id: entry for entry in ARCHETYPES}

ELITE_RARITY_WEIGHTS = (15, 30, 40, 12, 2.7, 0.3)
BOSS_RARITY_WEIGHTS = (0, 15, 48, 29, 7, 1)

# =========================================================================
#  Самоцветы и гнёзда (Gems & Sockets)
# =========================================================================


class GemType(str, Enum):
    """Пять граней силы + алмаз. Каждый камень — свой родной стихийный/утилит."""

    RUBY = "ruby"             # Огонь
    SAPPHIRE = "sapphire"     # Холод
    TOPAZ = "topaz"           # Молния
    EMERALD = "emerald"       # Яд / вампиризм
    AMETHYST = "amethyst"     # Хаос / барьер
    DIAMOND = "diamond"       # Крит / поглощение


# Базовый вклад камня уровня 1 (масштабируется уровнем предмета).
GEM_BASE = {
    GemType.RUBY: StatBlock(fire_bonus=0.04, fire_res=0.015),
    GemType.SAPPHIRE: StatBlock(cold_bonus=0.04, cold_res=0.015),
    GemType.TOPAZ: StatBlock(lightning_bonus=0.04, lightning_res=0.015),
    GemType.EMERALD: StatBlock(life_leech=0.012, agility=1),
    GemType.AMETHYST: StatBlock(chaos_bonus=0.04, damage_absorption=1),
    GemType.DIAMOND: StatBlock(crit_chance=0.015, crit_damage=0.04),
}

GEM_NAMES = {
    GemType.RUBY: "Рубин",
    GemType.SAPPHIRE: "Сапфир",
    GemType.TOPAZ: "Топаз",
    GemType.EMERALD: "Изумруд",
    GemType.AMETHYST: "Аметист",
    GemType.DIAMOND: "Алмаз",
}

# Цвета сияния камней (для иконок/лучей лута).
GEM_COLORS = {
    GemType.RUBY: "#ff5a4d",
    GemType.SAPPHIRE: "#4da6ff",
    GemType.TOPAZ: "#ffd14d",
    GemType.EMERALD: "#59e09a",
    GemType.AMETHYST: "#c24dff",
    GemType.DIAMOND: "#cfe8ff",
}

GEM_ORDER = tuple(GemType)


def _gem_stats(gem_type: GemType, level: int, quality: float) -> StatBlock:
    positive_int("level", level)
    scale = (1.0 + (level - 1) * 0.16) * quality
    return GEM_BASE[gem_type].scaled(scale)


@dataclass(frozen=True)
class Gem:
    gem_id: str
    gem_type: GemType | str
    level: int = 1
    quality: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.gem_id, str) or not self.gem_id:
            raise ValueError("Самоцвету необходим gem_id")
        object.__setattr__(self, "gem_type", GemType(self.gem_type))
        positive_int("level", self.level)
        if (
            type(self.quality) not in (int, float)
            or not math.isfinite(self.quality)
            or self.quality <= 0
        ):
            raise ValueError("Некорректное качество самоцвета")

    @property
    def display_name(self) -> str:
        return f"{GEM_NAMES[self.gem_type]} Lv.{self.level}"

    @property
    def stats(self) -> StatBlock:
        return _gem_stats(self.gem_type, self.level, self.quality)

    @property
    def color(self) -> str:
        return GEM_COLORS[self.gem_type]


# Число гнёзд по редкости: обычный 0, редкий 1, далее растёт до 3.
def roll_socket_count(
    rarity: Rarity | str,
    rng: random.Random | None = None,
) -> int:
    """Сколько гнёзд «пробьётся» в предмете данной редкости."""
    rarity = Rarity(rarity)
    tier = RARITY_ORDER.index(rarity)
    if tier < 2:
        return 0
    generator = rng if rng is not None else random.Random()
    capacity = min(tier - 1, 3)
    # С некоторой вероятностью гнёзд меньше максимума.
    roll = generator.random()
    if roll < 0.35:
        return max(1, capacity - 1)
    if roll < 0.65:
        return max(1, capacity - 2)
    return capacity


def _fresh_gem_id(gem_type: GemType, generator: random.Random) -> str:
    return f"gem-{gem_type.value}-{generator.getrandbits(96):024x}"


def socket_gem(
    item: Item,
    gem: Gem,
    rng: random.Random | None = None,
) -> tuple[Item, Gem | None]:
    """Вставить самоцвет в свободное гнездо.

    Статы камня сворачиваются прямо в `item.stats`, поэтому экипировка и
    Detailed Stats учитывают самоцветы без отдельной логики. Возвращает
    (новый предмет, камень) — либо (предмет без изменений, None), если все
    гнёзда заняты или редкость не позволяет.
    """
    if not isinstance(item, Item) or not isinstance(gem, Gem):
        raise ValueError("Некорректные аргументы вставки самоцвета")
    if len(item.gems) >= item.sockets:
        return item, None
    generator = rng if rng is not None else random.Random()
    gem_id = gem.gem_id
    known = {entry.gem_id for entry in item.gems}
    while gem_id in known:
        gem_id = _fresh_gem_id(gem.gem_type, generator)
    gem = replace(gem, gem_id=gem_id)
    return (
        replace(
            item,
            gems=item.gems + (gem,),
            stats=item.stats + gem.stats,
        ),
        gem,
    )


def unsocket_gem(item: Item, gem_id: str) -> tuple[Item, Gem | None]:
    """Вынуть камень из предмета, вернув и обновлённый предмет, и камень."""
    if not isinstance(item, Item):
        raise ValueError("Ожидается предмет")
    target = next((entry for entry in item.gems if entry.gem_id == gem_id), None)
    if target is None:
        return item, None
    return (
        replace(
            item,
            gems=tuple(entry for entry in item.gems if entry.gem_id != gem_id),
            stats=item.stats - target.stats,
        ),
        target,
    )


def gem_stats(items: tuple[Item, ...]) -> StatBlock:
    """Суммарный вклад всех самоцветов в наборе предметов (для справки)."""
    total = StatBlock()
    for item in items:
        for gem in item.gems:
            total = total + gem.stats
    return total


def item_from_gem_dict(gem: dict) -> Gem:
    return Gem(**gem)


# =========================================================================
#  Комплекты экипировки (Item Sets)
# =========================================================================


@dataclass(frozen=True)
class ItemSet:
    set_id: str
    name: str
    lore: str
    # Бонусы за 2, 4 и 6 надетых предметов комплекта.
    bonuses: tuple[StatBlock, StatBlock, StatBlock]
    color: str = "#ffd17b"


SET_TWO, SET_FOUR, SET_SIX = 0, 1, 2

ITEM_SETS = (
    ItemSet(
        "inquisitor_oath", "Клятва Инквизитора",
        "Священное пламя выжигает скверну из недр Бездны.",
        (
            StatBlock(fire_bonus=0.05, block_chance=0.02),
            StatBlock(crit_damage=0.15, damage_absorption=3),
            StatBlock(max_hp=180, hp_per_hit=6, all_skill_level=1),
        ),
    ),
    ItemSet(
        "hell_ash", "Пепел Преисподней",
        "Кальдера помнит каждого, кто осмелился смотреть в её сердце.",
        (
            StatBlock(fire_bonus=0.07, fire_res=0.04),
            StatBlock(chaos_bonus=0.06, mana=30),
            StatBlock(cooldown_reduction=0.08, skill_duration=0.10),
        ),
    ),
    ItemSet(
        "veil_eternal_darkness", "Саван Вечной Тьмы",
        "Тьма не забирает — она одаривает тех, кто пришёл за ней.",
        (
            StatBlock(chaos_bonus=0.06, life_leech=0.015),
            StatBlock(evasion=0.04, crit_chance=0.02),
            StatBlock(projectile_count=1, damage_absorption=5, hp_regen=2),
        ),
    ),
    ItemSet(
        "frost_torment", "Ледяная Пытка",
        "Пик Мучений выстудил сталь до состояния тишины.",
        (
            StatBlock(cold_bonus=0.06, cold_res=0.04),
            StatBlock(block_chance=0.02, armor=15),
            StatBlock(strength=8, agility=8, crit_damage=0.20),
        ),
    ),
    ItemSet(
        "rotborne", "Рождённый Гнилью",
        "Топи растят урожай, который дозревает под кожей врага.",
        (
            StatBlock(agility=2, damage=6),
            StatBlock(attack_speed=0.06, life_leech=0.02),
            StatBlock(max_hp=150, hp_per_hit=8, evasion=0.05),
        ),
    ),
    ItemSet(
        "storm_warden", "Страж Бури",
        "Каждое звено этой кольчуги — застывшая молния.",
        (
            StatBlock(lightning_bonus=0.06, lightning_res=0.04),
            StatBlock(projectile_bonus=0.05, attack_speed=0.03),
            StatBlock(multistrike=0.10, movement_speed=80, agility=6),
        ),
    ),
    ItemSet(
        "grave_herald", "Глашатай Могил",
        "Костяной венец не снимают — его заслуживают смертью.",
        (
            StatBlock(summon_damage=0.05, intelligence=3),
            StatBlock(mana=25, crit_chance=0.02),
            StatBlock(skill_duration=0.15, hp_per_kill=15, chaos_res=0.06),
        ),
    ),
    ItemSet(
        "sacred_light", "Священный Свет",
        "Нимб не слепит врагов — он сжигает их суть.",
        (
            StatBlock(max_hp=60, skill_heal=0.04),
            StatBlock(armor=12, block_chance=0.03),
            StatBlock(all_skill_level=1, hp_regen=2, damage_absorption=6),
        ),
    ),
)

ITEM_SET_BY_ID = {entry.set_id: entry for entry in ITEM_SETS}
# Рарности, способные носить комплект.
SET_ELIGIBLE_TIERS = (Rarity.LEGENDARY, Rarity.IMMORTAL, Rarity.MYTHIC)


def roll_set_id(
    rarity: Rarity | str,
    rng: random.Random | None = None,
) -> str | None:
    """Назначить предмету комплект (только высоким редкостям)."""
    rarity = Rarity(rarity)
    if rarity not in SET_ELIGIBLE_TIERS:
        return None
    generator = rng if rng is not None else random.Random()
    chance = 0.30 if rarity == Rarity.LEGENDARY else 0.55
    if generator.random() >= chance:
        return None
    return generator.choice(ITEM_SETS).set_id


def apply_item_set_bonuses(
    equipment: tuple[Item, ...],
) -> tuple[StatBlock, tuple[ItemSet, int, int]]:
    """Бонусы комплектов по надетым предметам.

    Возвращает (суммарный StatBlock, список активных (сет, порог, кол-во)).
    Пороги 2 / 4 / 6: учитывается самый высокий пройденный порог на сет.
    """
    if not isinstance(equipment, tuple):
        raise ValueError("equipment должна быть tuple")

    counts: dict[str, int] = {}
    for item in equipment:
        if item.set_id:
            counts[item.set_id] = counts.get(item.set_id, 0) + 1

    bonus = StatBlock()
    active: list = []
    for set_id, count in counts.items():
        if count < 2:
            continue
        entry = ITEM_SET_BY_ID.get(set_id)
        if entry is None:
            continue
        threshold = 2 if count < 4 else (4 if count < 6 else 6)
        threshold_index = {2: 0, 4: 1, 6: 2}[threshold]
        bonus = bonus + entry.bonuses[threshold_index]
        active.append((entry, threshold, count))

    return bonus, tuple(active)



def positive_int(name: str, value: int, minimum: int = 1) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} должен быть целым >= {minimum}")


def act_from_wave(wave: int) -> str:
    positive_int("wave", wave)
    return ACT_IDS[min((wave - 1) // 30, 3)]


def inflect_prefix(name: str, gender: str) -> str:
    if gender == "m":
        return name

    if name.endswith("ий"):
        stem = name[:-2]
        if name.endswith(("ский", "цкий")):
            return stem + {"f": "ая", "n": "ое", "p": "ие"}[gender]
        return stem + {"f": "яя", "n": "ее", "p": "ие"}[gender]

    if name.endswith(("ый", "ой")):
        stem = name[:-2]
        return stem + {"f": "ая", "n": "ое", "p": "ые"}[gender]

    return name


@dataclass(frozen=True)
class Item:
    item_id: str
    rarity: Rarity | str
    source_wave: int
    sell_value: int

    slot: EquipmentSlot | str = EquipmentSlot.WEAPON
    level: int = 1
    base_name: str = "Реликвия Бездны"
    prefix_id: str | None = None
    suffix_id: str | None = None
    stats: StatBlock = field(default_factory=StatBlock)
    kind: ItemKind | str = ItemKind.GENERIC

    archetype_id: str | None = None
    origin_act: str | None = None
    lore: str = ""
    # Самоцветы и комплекты (v1.4.0).
    sockets: int = 0
    gems: tuple[Gem, ...] = ()
    set_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id:
            raise ValueError("Предмету необходим item_id")

        object.__setattr__(self, "rarity", Rarity(self.rarity))
        object.__setattr__(self, "slot", EquipmentSlot(self.slot))
        object.__setattr__(self, "kind", ItemKind(self.kind))

        positive_int("source_wave", self.source_wave)
        positive_int("sell_value", self.sell_value, 0)
        positive_int("level", self.level)

        if not isinstance(self.base_name, str) or not self.base_name:
            raise ValueError("Предмету необходимо имя")
        if not isinstance(self.stats, StatBlock):
            raise ValueError("stats должен быть StatBlock")
        if not isinstance(self.lore, str):
            raise ValueError("lore должна быть строкой")

        if self.prefix_id is not None and self.prefix_id not in PREFIX_BY_ID:
            raise ValueError("Неизвестный префикс")
        if self.suffix_id is not None and self.suffix_id not in SUFFIX_BY_ID:
            raise ValueError("Неизвестный суффикс")
        if self.origin_act is not None and self.origin_act not in ACT_IDS:
            raise ValueError("Неизвестный акт")
        if self.kind in (ItemKind.SHIELD, ItemKind.FOCUS):
            if self.slot != EquipmentSlot.OFFHAND:
                raise ValueError("Щит/фокус должен занимать OFFHAND")

        if type(self.sockets) is not int or not 0 <= self.sockets <= 3:
            raise ValueError("Число гнёзд должно быть целым в диапазоне 0..3")
        if type(self.gems) is not tuple or not all(
            isinstance(gem, Gem) for gem in self.gems
        ):
            raise ValueError("gems должна быть tuple из Gem")
        if len(self.gems) > self.sockets:
            raise ValueError("Самоцветов больше, чем гнёзд")
        if self.set_id is not None and self.set_id not in ITEM_SET_BY_ID:
            raise ValueError("Неизвестный комплект")

        if self.archetype_id is not None:
            archetype_data = ARCHETYPE_BY_ID.get(self.archetype_id)
            if archetype_data is None:
                raise ValueError("Неизвестный архетип")
            if archetype_data.slot != self.slot:
                raise ValueError("Архетип не соответствует слоту")
            if archetype_data.kind != self.kind:
                raise ValueError("Архетип не соответствует типу предмета")

    @property
    def display_name(self) -> str:
        archetype_data = ARCHETYPE_BY_ID.get(self.archetype_id)
        gender = archetype_data.gender if archetype_data else "m"

        parts = []
        if self.prefix_id:
            parts.append(inflect_prefix(
                PREFIX_BY_ID[self.prefix_id].name, gender
            ))
        parts.append(self.base_name)
        if self.suffix_id:
            parts.append(SUFFIX_BY_ID[self.suffix_id].name)
        return " ".join(parts)

    @property
    def visual_key(self) -> str:
        archetype_data = ARCHETYPE_BY_ID.get(self.archetype_id)
        if archetype_data:
            return archetype_data.visual
        if self.kind == ItemKind.SHIELD:
            return "shield"
        return {
            EquipmentSlot.WEAPON: "sword",
            EquipmentSlot.OFFHAND: "orb",
            EquipmentSlot.HEAD: "helm",
            EquipmentSlot.CHEST: "plate",
            EquipmentSlot.GLOVES: "gloves",
            EquipmentSlot.BOOTS: "boots",
            EquipmentSlot.BELT: "belt",
            EquipmentSlot.AMULET: "amulet",
            EquipmentSlot.RING_1: "ring",
            EquipmentSlot.RING_2: "signet",
        }[self.slot]


def generate_item(
    level: int,
    rarity: Rarity | str,
    *,
    slot: EquipmentSlot | str | None = None,
    source_wave: int = 1,
    rng: random.Random | None = None,
    act: str | None = None,
    archetype_id: str | None = None,
) -> Item:
    positive_int("level", level)
    positive_int("source_wave", source_wave)

    generator = rng if rng is not None else random.Random()
    rarity = Rarity(rarity)
    act = act or act_from_wave(source_wave)

    if act not in ACT_IDS:
        raise ValueError("Неизвестный акт")

    requested_slot = EquipmentSlot(slot) if slot is not None else None

    if archetype_id is not None:
        base = ARCHETYPE_BY_ID[archetype_id]
        if requested_slot is not None and base.slot != requested_slot:
            raise ValueError("Архетип несовместим с запрошенным слотом")
    else:
        if requested_slot is None:
            requested_slot = generator.choice(tuple(EquipmentSlot))

        candidates = [
            entry for entry in ARCHETYPES
            if entry.slot == requested_slot
        ]
        base = generator.choices(
            candidates,
            weights=[
                3.0 if entry.favored_act == act else 1.0
                for entry in candidates
            ],
            k=1,
        )[0]

    tier = RARITY_ORDER.index(rarity)
    power = RARITY_POWER[rarity]
    quality = generator.uniform(0.90, 1.10)

    stats = base.stats.scaled(
        (1 + (level - 1) * 0.12) * power * quality
    )

    prefix = None
    suffix = None

    if tier >= 1:
        pool = ACT_PREFIXES[act] if generator.random() < 0.75 else BASE_PREFIXES
        prefix = generator.choice(pool)

    if tier >= 2:
        pool = ACT_SUFFIXES[act] if generator.random() < 0.75 else BASE_SUFFIXES
        suffix = generator.choice(pool)

    affix_scale = power * (1 + (level - 1) * 0.025)
    if prefix:
        stats = stats + prefix.stats.scaled(affix_scale)
    if suffix:
        stats = stats + suffix.stats.scaled(affix_scale)

    return Item(
        item_id=f"item-{generator.getrandbits(128):032x}",
        rarity=rarity,
        source_wave=source_wave,
        sell_value=max(1, int(10 * level * power)),
        slot=base.slot,
        level=level,
        base_name=base.name,
        prefix_id=prefix.affix_id if prefix else None,
        suffix_id=suffix.affix_id if suffix else None,
        stats=stats,
        kind=base.kind,
        archetype_id=base.archetype_id,
        origin_act=act,
        lore=generator.choice(ACT_LORE[act]),
    )


def _roll_gem(rng: random.Random, level: int) -> Gem:
    """Создать самоцвет случайной грани уровня предмета."""
    gem_type = rng.choice(GEM_ORDER)
    quality = rng.uniform(0.85, 1.15)
    return Gem(
        gem_id=_fresh_gem_id(gem_type, rng),
        gem_type=gem_type,
        level=level,
        quality=quality,
    )


def _enrich_drop(item: Item, rng: random.Random) -> Item:
    """Обилие лута: гнёзда с самоцветами и редкие комплекты на трофеях."""
    sockets = roll_socket_count(item.rarity, rng)
    enriched = replace(item, sockets=sockets)

    # Самоцветы с вероятностью ~80% на гнездо.
    for _ in range(sockets):
        if rng.random() < 0.80:
            enriched, _ = socket_gem(enriched, _roll_gem(rng, item.level), rng)

    # Комплект на высоких редкостях.
    set_id = roll_set_id(item.rarity, rng)
    if set_id is not None:
        enriched = replace(enriched, set_id=set_id)

    # Самоцветы и комплекты увеличивают ценность трофея.
    if enriched.gems or enriched.set_id:
        power = 1.0 + 0.10 * len(enriched.gems) + (0.15 if enriched.set_id else 0)
        enriched = replace(
            enriched,
            sell_value=max(enriched.sell_value, int(enriched.sell_value * power)),
        )
    return enriched


def roll_enemy_loot(
    wave: int,
    rank: str,
    rng: random.Random,
) -> tuple[Item, ...]:
    positive_int("wave", wave)
    rank = getattr(rank, "value", rank)

    if rank == "boss":
        count = rng.randint(2, 4)
        weights = BOSS_RARITY_WEIGHTS
    elif rank == "elite":
        if rng.random() >= 0.60:
            return ()
        count = 1
        weights = ELITE_RARITY_WEIGHTS
    else:
        return ()

    # Отдельный баланс предметов за элитников и боссов.
    level = 1 + (wave - 1) // 5
    return tuple(
        _enrich_drop(
            generate_item(
                level,
                rng.choices(RARITY_ORDER, weights=weights, k=1)[0],
                source_wave=wave,
                act=act_from_wave(wave),
                rng=rng,
            ),
            rng,
        )
        for _ in range(count)
    )


def item_from_dict(payload: dict[str, Any]) -> Item:
    raw = dict(payload)
    raw["stats"] = StatBlock(**raw.get("stats", {}))
    raw["gems"] = tuple(
        Gem(**entry) if isinstance(entry, dict) else entry
        for entry in raw.get("gems", ())
    )
    raw["sockets"] = raw.get("sockets", 0)
    raw["set_id"] = raw.get("set_id")
    return Item(**raw)
