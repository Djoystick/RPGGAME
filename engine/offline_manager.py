from __future__ import annotations

from engine.runes_tree import RunesTree
from models.hero import experience_awards

import math
import random
import time
from dataclasses import dataclass, replace
from fractions import Fraction

import config as C
from engine.save_manager import SaveManager
from engine.state import GameData, GameState, ItemDrop, require_number
from models.item import generate_item


def rational(value: int | float | str) -> Fraction:
    """Без двоичных float-артефактов при преобразовании коэффициентов."""
    return Fraction(str(value))


@dataclass(frozen=True)
class OfflineResult:
    before: GameData
    after: GameData

    elapsed_seconds: float
    credited_seconds: float
    effective_seconds: float
    discarded_seconds: float

    waves_cleared: int
    wave_gold: int
    sale_gold: int
    total_exp: int

    items_stored: int
    items_sold: int
    clock_rollback: bool

    @property
    def total_gold(self) -> int:
        return self.wave_gold + self.sale_gold

    @property
    def items_rolled(self) -> int:
        return self.items_stored + self.items_sold

    @property
    def cap_reached(self) -> bool:
        return self.elapsed_seconds >= self.before.offline_cap_seconds


class OfflineManager:
    def calculate(
        self,
        data: GameData,
        now: float | None = None,
        rng: random.Random | None = None,
    ) -> OfflineResult:
        """
        Рассчитать новый снимок, не изменяя GameState и файл сохранения.

        rng можно передать для воспроизводимых тестов.
        Профиль фарма фиксируется на весь оффлайн-интервал.
        """
        timestamp = time.time() if now is None else now
        require_number("now", timestamp)

        generator = rng if rng is not None else random.Random()

        previous_time = rational(data.last_active_timestamp)
        current_time = rational(timestamp)

        raw_seconds = max(Fraction(0), current_time - previous_time)
        credited_seconds = min(
            raw_seconds,
            Fraction(data.offline_cap_seconds),
        )
        effective_seconds = (
            credited_seconds * rational(data.offline_efficiency)
        )

        progress = (
            Fraction(data.wave_fraction)
            + effective_seconds
            / rational(data.farm.average_wave_clear_seconds)
        )
        waves = math.floor(progress)
        remainder = progress - waves

        # Единое правило округления, независимое от размера оффлайн-пакета.
        gold_per_wave = math.floor(
            data.farm.gold_per_wave
            * (1 + rational(data.farm.gold_bonus))
        )
        wave_gold = waves * gold_per_wave
        members = RunesTree().squad(data)
        gains, exp_cursor = experience_awards(
            data.farm.exp_per_wave,
            waves,
            [member.stats for member in members],
            data.exp_cursor,
        )

        total_exp = sum(gains)

        party = tuple(
            replace(
                hero,
                total_exp=hero.total_exp + gains[index],
            )
            for index, hero in enumerate(data.party)
        )

        stash = list(data.stash)
        known_item_ids = {item.item_id for item in stash}
        known_item_ids.update(
            item.item_id
            for build in data.hero_builds
            for item in build.equipment
        )
        known_item_ids.update(item.item_id for item in data.backpack)
        items_stored = 0
        items_sold = 0
        sale_gold = 0

        rarity_names = [row[0] for row in C.LOOT_TABLE]
        rarity_weights = [row[1] for row in C.LOOT_TABLE]
        base_prices = {row[0]: row[2] for row in C.LOOT_TABLE}

        for wave_number in range(
            data.current_wave,
            data.current_wave + waves,
        ):
            if generator.random() >= data.farm.drop_chance:
                continue

            rarity = generator.choices(
                rarity_names,
                weights=rarity_weights,
                k=1,
            )[0]

            base_sell_value = base_prices[rarity]

            if len(stash) >= data.stash_capacity:
                # Начальное правило утилизации:
                # любой избыточный предмет автоматически продаётся.
                items_sold += 1
                sale_gold += math.floor(
                    base_sell_value
                    * (1 + rational(data.farm.sale_bonus))
                )
                continue

            item_id = f"offline-{generator.getrandbits(128):032x}"
            while item_id in known_item_ids:
                item_id = f"offline-{generator.getrandbits(128):032x}"

            # Стартовый баланс: один уровень предмета на каждые 100 волн.
            # Цену продажи сохраняем прежней, чтобы не менять экономику Модуля 1.
            item = generate_item(
                level=1 + (wave_number - 1) // 100,
                rarity=rarity,
                source_wave=wave_number,
                rng=generator,
            )
            item = replace(
                item,
                item_id=item_id,
                sell_value=base_sell_value,
            )
            known_item_ids.add(item_id)
            stash.append(item)
            items_stored += 1

        after = replace(
            data,
            gold=data.gold + wave_gold + sale_gold,
            cleared_waves=data.cleared_waves + waves,
            wave_fraction=str(remainder),
            party=party,
            exp_cursor=exp_cursor,
            stash=tuple(stash),

            # Обрабатываем весь интервал, включая отброшенное сверх cap.
            # Иначе повторный запуск мог бы получить ещё одну порцию наград.
            last_active_timestamp=max(
                timestamp,
                data.last_active_timestamp,
            ),
        )

        return OfflineResult(
            before=data,
            after=after,
            elapsed_seconds=float(raw_seconds),
            credited_seconds=float(credited_seconds),
            effective_seconds=float(effective_seconds),
            discarded_seconds=float(raw_seconds - credited_seconds),
            waves_cleared=waves,
            wave_gold=wave_gold,
            sale_gold=sale_gold,
            total_exp=total_exp,
            items_stored=items_stored,
            items_sold=items_sold,
            clock_rollback=current_time < previous_time,
        )

    def claim(
        self,
        state: GameState,
        saves: SaveManager,
        now: float | None = None,
        rng: random.Random | None = None,
    ) -> OfflineResult:
        """
        Вызывается один раз после загрузки сохранения.

        1. Рассчитать кандидат.
        2. Атомарно записать награды и timestamp.
        3. Обновить GameState и послать сигналы.

        Если запись не удалась, состояние в памяти остаётся прежним.
        """
        state.assert_owner_thread()
        result = self.calculate(state.data, now=now, rng=rng)

        saves.write(result.after)
        state.commit(
            result.before,
            result.after,
            offline_result=result,
        )

        return result
