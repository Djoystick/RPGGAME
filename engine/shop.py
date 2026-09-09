from __future__ import annotations

import random
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Sequence

import config as C
from engine.state import GameData
from models.hero import level_from_exp
from models.item import (
    ACT_IDS,
    Item,
    RARITY_ORDER,
    Rarity,
    generate_item,
)

__all__ = [
    "MERCHANT_MARKUP",
    "MERCHANT_ROLL_COUNT",
    "MERCHANT_LEVELS_SPREAD",
    "MerchantError",
    "compute_sell_gold",
    "sell_rarity_ids",
    "merchant_level",
    "roll_merchant_stock",
    "can_place",
    "buy_data",
    "junk_ids",
]


class MerchantError(ValueError):
    """Ошибка торговой механики Лавки Бездны."""


# Торговая наценка: цена покупки = базовой ценности предмета * markup.
MERCHANT_MARKUP = 2.5
# Сколько уникальных товаров одновременно выставлено на прилавке.
MERCHANT_ROLL_COUNT = 6
# Разброс уровней внутри одной полки лавки.
MERCHANT_LEVELS_SPREAD = 4

# Веса редкостей прилавка: лавка торгует «готовым» лотом чуть лучше,
# чем средний дроп, но никогда не открывает Mythic (его можно только найти).
SHOP_RARITY_WEIGHTS = (
    # common  uncommon  rare   legendary  immortal  mythic
    0.10,     0.34,     0.40,  0.13,      0.03,     0.0,
)


def compute_sell_gold(
    items: Sequence[Item],
    sale_bonus: float = 0.0,
) -> int:
    """Сколько золота принесёт продажа набора предметов.

    Цена каждой вещи округляется вниз независимо (как при авто-продаже
    переполненного тайника), затем суммируется.
    """
    if not all(isinstance(item, Item) for item in items):
        raise MerchantError("Некорректный список предметов")

    ratio = 1 + Fraction(str(sale_bonus))
    total = 0
    for item in items:
        total += int(Fraction(item.sell_value) * ratio)
    return int(total)


def merchant_level(data: GameData) -> int:
    """Уровень лавки привязан к среднему уровню активного отряда."""
    if not data.party:
        return 1
    avg = sum(level_from_exp(hero.total_exp) for hero in data.party)
    return max(1, round(avg / len(data.party)))


def _rolled_level(base: int, rng: random.Random) -> int:
    low = max(1, base - MERCHANT_LEVELS_SPREAD)
    return rng.randint(low, base + MERCHANT_LEVELS_SPREAD)


def roll_merchant_stock(
    data: GameData,
    *,
    count: int = MERCHANT_ROLL_COUNT,
    rng: random.Random | None = None,
) -> tuple[Item, ...]:
    """Сформировать полку лавки: готовые предметы для покупки.

    Товары не попадают в сохранение сами по себе — их держит лишь открытая
    лавка, поэтому возвращённые предметы можно свободно пересобирать на
    каждом «обновлении прилавка».
    """
    if not isinstance(data, GameData):
        raise MerchantError("Ожидается GameData")
    if type(count) is not int or count < 1 or count > 20:
        raise MerchantError("Число товаров должно быть от 1 до 20")

    generator = rng if rng is not None else random.Random()
    base_level = merchant_level(data)
    wave = max(1, data.current_wave)
    act = ACT_IDS[min((wave - 1) // 30, len(ACT_IDS) - 1)]

    stock = []
    for _ in range(count):
        rarity = generator.choices(
            RARITY_ORDER,
            weights=SHOP_RARITY_WEIGHTS,
            k=1,
        )[0]
        level = _rolled_level(base_level, generator)
        stock.append(
            generate_item(
                level,
                rarity,
                source_wave=wave,
                act=act,
                rng=generator,
            )
        )
    return tuple(stock)


def merchant_price(item: Item) -> int:
    """Цена товара в лавке (из его базовой ценности и наценки)."""
    return max(1, round(item.sell_value * MERCHANT_MARKUP))


def can_place(data: GameData, amount: int = 1) -> bool:
    """Есть ли свободное место под покупку (рюкзак, затем тайник)."""
    return (
        len(data.backpack) + amount <= C.DEFAULT_BACKPACK_CAPACITY
        or len(data.stash) + amount <= data.stash_capacity
    )


def buy_data(data: GameData, item: Item) -> GameData:
    """Чистая трансформация: потратить цену и положить купленный товар.

    Предмет вставляется в рюкзак, если там есть место, иначе в тайник.
    Находит конфликты item_id и перестраховывается от дублей.
    """
    if not isinstance(data, GameData) or not isinstance(item, Item):
        raise MerchantError("Некорректные данные сделки")

    price = merchant_price(item)
    if data.gold < price:
        raise MerchantError("Недостаточно золота для покупки")

    known_ids = {entry.item_id for entry in (*data.stash, *data.backpack)}
    known_ids.update(
        entry.item_id
        for build in data.hero_builds
        for entry in build.equipment
    )
    fresh = item
    suffix = 0
    while fresh.item_id in known_ids:
        suffix += 1
        fresh = replace(fresh, item_id=f"{item.item_id}-buy-{suffix}")

    backpack = data.backpack
    stash = data.stash

    if len(backpack) < C.DEFAULT_BACKPACK_CAPACITY:
        backpack = backpack + (fresh,)
    elif len(stash) < data.stash_capacity:
        stash = stash + (fresh,)
    else:
        raise MerchantError("В рюкзаке и тайнике нет места под покупку")

    return replace(
        data,
        gold=data.gold - price,
        backpack=backpack,
        stash=stash,
    )


def junk_ids(data: GameData) -> tuple[str, ...]:
    """id всех «мусорных» предметов (common/uncommon) в рюкзаке и тайнике."""
    ids = []
    for item in (*data.backpack, *data.stash):
        if item.rarity in (Rarity.COMMON, Rarity.UNCOMMON):
            ids.append(item.item_id)
    return tuple(ids)


def sell_rarity_ids(
    data: GameData,
    ids: Sequence[str] = (),
    *,
    sale_bonus: float | None = None,
) -> GameData:
    """Чистая трансформация: продать предметы из рюкзака/тайника за золото.

    Значение редкости подставлять нельзя — идентификаторы принадлежат
    конкретным предметам. Если какой-то id не найден в контейнерах — ошибка.
    """
    if not isinstance(data, GameData):
        raise MerchantError("Ожидается GameData")

    selected = set(ids)
    if not selected:
        raise MerchantError("Сначала выберите предметы для продажи")

    bonus = data.farm.sale_bonus if sale_bonus is None else sale_bonus

    sellable = [
        entry for entry in (*data.backpack, *data.stash)
        if entry.item_id in selected
    ]
    if len(sellable) != len(selected):
        raise MerchantError(
            "Часть предметов уже продана либо экипирована героем"
        )

    gold_gain = compute_sell_gold(sellable, bonus)

    remaining_backpack = tuple(
        entry for entry in data.backpack if entry.item_id not in selected
    )
    remaining_stash = tuple(
        entry for entry in data.stash if entry.item_id not in selected
    )

    return replace(
        data,
        gold=data.gold + gold_gain,
        backpack=remaining_backpack,
        stash=remaining_stash,
    )


@dataclass(frozen=True)
class SellOutcome:
    """Итог одной операции продажи: прирост золота и число проданных вещей."""

    gold_gain: int
    count: int
