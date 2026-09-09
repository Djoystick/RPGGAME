from __future__ import annotations

import random
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from engine.offline_manager import OfflineManager
from engine.save_manager import SaveError, SaveManager
from engine.state import FarmProfile, GameData, GameState


APP = QCoreApplication.instance() or QCoreApplication([])


class OfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = OfflineManager()
        self.data = GameData(
            last_active_timestamp=1_000.0,
            farm=FarmProfile(drop_chance=0.0),
        )

    def test_base_cap_and_rewards(self) -> None:
        # Отсутствие 24 часа, потолок 2 часа, эффективность 60%.
        result = self.manager.calculate(
            self.data,
            now=1_000 + 24 * 3600,
        )

        self.assertEqual(result.credited_seconds, 7200)
        self.assertEqual(result.effective_seconds, 4320)
        self.assertEqual(result.waves_cleared, 360)
        self.assertEqual(result.total_gold, 36_000)
        self.assertEqual(result.total_exp, 10_800)
        self.assertEqual(result.after.current_wave, 361)

        self.assertEqual(
            [hero.total_exp for hero in result.after.party],
            [2700, 2700, 2700, 2700],
        )

    def test_maximum_upgrade(self) -> None:
        data = replace(
            self.data,
            offline_cap_level=5,
            offline_efficiency_level=3,
        )
        result = self.manager.calculate(
            data,
            now=1_000 + 24 * 3600,
        )

        self.assertEqual(result.credited_seconds, 12 * 3600)
        self.assertEqual(result.waves_cleared, 3600)

    def test_partial_wave_survives_restart(self) -> None:
        first = self.manager.calculate(self.data, now=1010)
        self.assertEqual(first.waves_cleared, 0)
        self.assertEqual(Fraction(first.after.wave_fraction), Fraction(1, 2))

        second = self.manager.calculate(first.after, now=1020)
        whole = self.manager.calculate(self.data, now=1020)

        self.assertEqual(second.waves_cleared, 1)
        self.assertEqual(second.after.gold, whole.after.gold)
        self.assertEqual(second.after.party, whole.after.party)
        self.assertEqual(second.after.wave_fraction, whole.after.wave_fraction)

    def test_same_timestamp_has_no_second_reward(self) -> None:
        first = self.manager.calculate(self.data, now=8200)
        second = self.manager.calculate(first.after, now=8200)

        self.assertEqual(second.waves_cleared, 0)
        self.assertEqual(second.total_gold, 0)
        self.assertEqual(second.total_exp, 0)
        self.assertEqual(second.after, first.after)

    def test_clock_rollback_does_not_rewind_timestamp(self) -> None:
        result = self.manager.calculate(self.data, now=900)

        self.assertTrue(result.clock_rollback)
        self.assertEqual(result.elapsed_seconds, 0)
        self.assertEqual(result.total_gold, 0)
        self.assertEqual(result.after.last_active_timestamp, 1000)

    def test_exp_remainder_rotates(self) -> None:
        data = replace(
            self.data,
            farm=replace(self.data.farm, exp_per_wave=1),
        )

        for step in range(1, 5):
            # 20 реальных секунд * 60% = одна волна по 12 секунд.
            data = self.manager.calculate(
                data,
                now=1000 + step * 20,
            ).after

        self.assertEqual(
            [hero.total_exp for hero in data.party],
            [1, 1, 1, 1],
        )
        self.assertEqual(data.exp_cursor, 0)

    def test_stash_overflow_is_sold(self) -> None:
        data = replace(
            self.data,
            stash_capacity=1,
            farm=replace(self.data.farm, drop_chance=1.0),
        )

        result = self.manager.calculate(
            data,
            now=1060,
            rng=random.Random(42),
        )

        self.assertEqual(result.waves_cleared, 3)
        self.assertEqual(result.items_stored, 1)
        self.assertEqual(result.items_sold, 2)
        self.assertEqual(len(result.after.stash), 1)
        self.assertGreater(result.sale_gold, 0)

    def test_save_round_trip(self) -> None:
        data = replace(self.data, gold=10**15, wave_fraction="1/3")

        with tempfile.TemporaryDirectory() as directory:
            saves = SaveManager(Path(directory) / "save.json")
            saves.write(data)
            self.assertEqual(saves.load(), data)

    def test_failed_save_does_not_grant_rewards(self) -> None:
        class BrokenSaveManager(SaveManager):
            def write(self, data: GameData) -> None:
                raise SaveError("Имитируем ошибку диска")

        state = GameState.instance()
        state.load(self.data)

        with self.assertRaises(SaveError):
            self.manager.claim(
                state,
                BrokenSaveManager(),
                now=8200,
            )

        self.assertIs(state.data, self.data)

    def test_claim_persists_timestamp_and_rewards_together(self) -> None:
        state = GameState.instance()
        state.load(self.data)

        with tempfile.TemporaryDirectory() as directory:
            saves = SaveManager(Path(directory) / "save.json")
            result = self.manager.claim(state, saves, now=8200)

            self.assertEqual(saves.load(), result.after)
            self.assertEqual(state.data, result.after)

            # Имитируем следующий запуск в тот же момент.
            state.load(saves.load())
            repeated = self.manager.claim(state, saves, now=8200)
            self.assertEqual(repeated.total_gold, 0)

    def test_singleton(self) -> None:
        self.assertIs(GameState(), GameState.instance())

    def test_invalid_clear_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FarmProfile(average_wave_clear_seconds=0)


if __name__ == "__main__":
    unittest.main()
