from __future__ import annotations

import random
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from engine.runes_tree import RunesTree
from engine.save_manager import SaveManager
from engine.state import GameData, GameState
from models.item import Item, Rarity, RARITY_ORDER, generate_item


MIN_INGREDIENTS = 4
MAX_INGREDIENTS = 12
MAX_LEVEL_SPREAD = 15

BASE_CRITICAL_CHANCE = 0.024


class SynthesisError(ValueError):
    pass


@dataclass(frozen=True)
class SynthesisResult:
    before: GameData
    after: GameData
    consumed_ids: tuple[str, ...]
    item: Item
    probabilities: Mapping[Rarity, float]


class CubeSynth:
    def __init__(self, runes: RunesTree | None = None) -> None:
        self.runes = runes if runes is not None else RunesTree()

    def validate(self, ingredients: tuple[Item, ...]) -> None:
        if not MIN_INGREDIENTS <= len(ingredients) <= MAX_INGREDIENTS:
            raise SynthesisError("Нужно от 4 до 12 предметов")
        if not all(isinstance(item, Item) for item in ingredients):
            raise SynthesisError("Некорректные ингредиенты")
        if len({item.item_id for item in ingredients}) != len(ingredients):
            raise SynthesisError("Один предмет указан несколько раз")

        rarities = {item.rarity for item in ingredients}
        if len(rarities) != 1:
            raise SynthesisError("Ингредиенты должны иметь одну редкость")

        rarity = ingredients[0].rarity
        if rarity == Rarity.MYTHIC:
            raise SynthesisError("Mythic — максимальная редкость")

        levels = [item.level for item in ingredients]
        if max(levels) - min(levels) > MAX_LEVEL_SPREAD:
            raise SynthesisError("Слишком большой диапазон уровней")

    def probabilities(
        self,
        ingredients: tuple[Item, ...],
        critical_bonus: float = 0.0,
    ) -> Mapping[Rarity, float]:
        self.validate(ingredients)

        if not 0.0 <= critical_bonus <= 1.0:
            raise SynthesisError("Некорректный бонус синтеза")

        count = len(ingredients)
        tier = RARITY_ORDER.index(ingredients[0].rarity)

        # 4 предмета: 40% оставить ранг.
        # 12 предметов: 0% оставить ранг.
        same = 0.40 * (MAX_INGREDIENTS - count) / (
            MAX_INGREDIENTS - MIN_INGREDIENTS
        )

        critical = min(
            1.0 - same,
            BASE_CRITICAL_CHANCE * count / MAX_INGREDIENTS + critical_bonus,
        )
        upgrade = 1.0 - same - critical

        probabilities: dict[Rarity, float] = {}

        for offset, chance in ((0, same), (1, upgrade), (2, critical)):
            result_tier = min(tier + offset, len(RARITY_ORDER) - 1)
            rarity = RARITY_ORDER[result_tier]
            probabilities[rarity] = probabilities.get(rarity, 0.0) + chance

        return MappingProxyType(probabilities)

    def autofill(
        self,
        stash: tuple[Item, ...],
        *,
        rarity: Rarity | str | None = None,
        excluded_ids: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        """
        Детерминированно выбирает крупнейшую подходящую группу.
        При равенстве: меньшая редкость, меньший уровень, item_id.

        excluded_ids предназначен для будущих блокировок/избранных предметов.
        """
        rarity_filter = None if rarity is None else Rarity(rarity)
        best: tuple[Item, ...] = ()

        for tier in RARITY_ORDER[:-1]:
            if rarity_filter is not None and tier != rarity_filter:
                continue

            candidates = sorted(
                (
                    item for item in stash
                    if item.rarity == tier
                    and item.item_id not in excluded_ids
                ),
                key=lambda item: (item.level, item.item_id),
            )

            for start, first in enumerate(candidates):
                group = tuple(
                    item
                    for item in candidates[start:start + MAX_INGREDIENTS]
                    if item.level <= first.level + MAX_LEVEL_SPREAD
                )

                if len(group) >= MIN_INGREDIENTS and len(group) > len(best):
                    best = group

        return tuple(item.item_id for item in best)

    def calculate(
        self,
        data: GameData,
        ingredient_ids: tuple[str, ...],
        *,
        rng: random.Random | None = None,
    ) -> SynthesisResult:
        if len(set(ingredient_ids)) != len(ingredient_ids):
            raise SynthesisError("Повторяющийся идентификатор")

        stash_by_id = {item.item_id: item for item in data.stash}

        try:
            ingredients = tuple(
                stash_by_id[item_id] for item_id in ingredient_ids
            )
        except KeyError as exc:
            raise SynthesisError("Предмет отсутствует в тайнике") from exc

        bonus = self.runes.effects(data.unlocked_runes).synthesis_bonus
        probabilities = self.probabilities(ingredients, bonus)

        generator = rng if rng is not None else random.Random()

        rarities = tuple(probabilities)
        result_rarity = generator.choices(
            rarities,
            weights=tuple(probabilities.values()),
            k=1,
        )[0]

        level = sum(item.level for item in ingredients) // len(ingredients)
        slot = generator.choice(ingredients).slot

        item = generate_item(
            level,
            result_rarity,
            slot=slot,
            source_wave=max(entry.source_wave for entry in ingredients),
            rng=generator,
        )

        # Не допускаем конфликт даже с экипированными предметами.
        known_ids = set(stash_by_id)
        known_ids.update(
            entry.item_id
            for build in data.hero_builds
            for entry in build.equipment
        )
        known_ids.update(item.item_id for item in data.backpack)
        while item.item_id in known_ids:
            item = replace(
                item,
                item_id=f"item-{generator.getrandbits(128):032x}",
            )

        consumed = set(ingredient_ids)
        stash = tuple(
            entry for entry in data.stash
            if entry.item_id not in consumed
        ) + (item,)

        after = replace(data, stash=stash)

        return SynthesisResult(
            before=data,
            after=after,
            consumed_ids=ingredient_ids,
            item=item,
            probabilities=probabilities,
        )

    def transmute(
        self,
        state: GameState,
        saves: SaveManager,
        ingredient_ids: tuple[str, ...],
        *,
        rng: random.Random | None = None,
    ) -> SynthesisResult:
        state.assert_owner_thread()
        result = self.calculate(state.data, ingredient_ids, rng=rng)

        saves.write(result.after)
        state.commit(result.before, result.after)

        return result
