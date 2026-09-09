from __future__ import annotations

import json
import random
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from engine.cube_synth import CubeSynth, SynthesisError
from engine.runes_tree import RuneError, RunesTree, Sector
from engine.save_manager import SaveError, SaveManager
from engine.state import GameData, GameState
from models.hero import (
    Hero,
    HeroBuild,
    HeroClass,
    total_exp_for_level,
)
from models.item import (
    EquipmentSlot,
    Item,
    Rarity,
    generate_item,
)


APP = QCoreApplication.instance() or QCoreApplication([])


def make_items(
    count: int,
    rarity: Rarity = Rarity.RARE,
    level: int = 20,
) -> tuple[Item, ...]:
    rng = random.Random(12345)
    return tuple(
        generate_item(
            level,
            rarity,
            source_wave=100,
            rng=rng,
        )
        for _ in range(count)
    )


class ItemTests(unittest.TestCase):
    def test_six_rarities_and_ten_slots(self) -> None:
        self.assertEqual(len(Rarity), 6)
        self.assertEqual(len(EquipmentSlot), 10)

    def test_generation_is_reproducible(self) -> None:
        first = generate_item(
            25,
            Rarity.LEGENDARY,
            rng=random.Random(7),
        )
        second = generate_item(
            25,
            Rarity.LEGENDARY,
            rng=random.Random(7),
        )
        self.assertEqual(first, second)

    def test_affixes_follow_rarity(self) -> None:
        common = generate_item(10, Rarity.COMMON, rng=random.Random(1))
        uncommon = generate_item(10, Rarity.UNCOMMON, rng=random.Random(1))
        rare = generate_item(10, Rarity.RARE, rng=random.Random(1))

        self.assertIsNone(common.prefix_id)
        self.assertIsNone(common.suffix_id)
        self.assertIsNotNone(uncommon.prefix_id)
        self.assertIsNone(uncommon.suffix_id)
        self.assertIsNotNone(rare.prefix_id)
        self.assertIsNotNone(rare.suffix_id)

    def test_higher_level_increases_base_power(self) -> None:
        low = generate_item(
            1, Rarity.COMMON,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(5),
        )
        high = generate_item(
            50, Rarity.COMMON,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(5),
        )
        self.assertGreater(high.stats.damage, low.stats.damage)
        self.assertGreater(high.sell_value, low.sell_value)

    def test_duplicate_equipment_slot_is_rejected(self) -> None:
        first = generate_item(
            10, Rarity.RARE,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(1),
        )
        second = generate_item(
            10, Rarity.RARE,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(2),
        )

        with self.assertRaises(ValueError):
            HeroBuild("knight", HeroClass.KNIGHT, (first, second))


class HeroTests(unittest.TestCase):
    def test_six_classes_have_skills(self) -> None:
        self.assertEqual(len(HeroClass), 6)
        for hero_class in HeroClass:
            hero = Hero("hero", "Тест", hero_class)
            self.assertEqual(hero.level, 1)
            self.assertEqual(len(hero.skills), 1)
            self.assertGreater(hero.secondary_stats().max_hp, 0)

    def test_exact_exp_boundaries(self) -> None:
        hero = Hero("knight", "Рыцарь", HeroClass.KNIGHT)

        self.assertEqual(hero.gain_exp(99).level, 1)
        self.assertEqual(hero.gain_exp(100).level, 2)

        level_25 = hero.gain_exp(total_exp_for_level(25))
        self.assertEqual(level_25.level, 25)
        self.assertEqual(level_25.exp_in_level, 0)
        self.assertEqual(len(level_25.skills), 3)

    def test_equipment_changes_secondary_stats(self) -> None:
        hero = Hero("knight", "Рыцарь", HeroClass.KNIGHT)
        weapon = generate_item(
            20, Rarity.LEGENDARY,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(1),
        )
        equipped = replace(hero, equipment=(weapon,))

        self.assertGreater(
            equipped.secondary_stats().physical_damage,
            hero.secondary_stats().physical_damage,
        )


class RuneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = RunesTree()
        self.data = GameData(gold=10**12)

    def test_tree_size_and_sector_counts(self) -> None:
        self.assertEqual(len(self.tree.nodes), 151)
        self.assertEqual(len(self.tree.edges), 150)

        for sector in Sector:
            count = sum(
                node.sector == sector
                for node in self.tree.nodes.values()
            )
            self.assertEqual(count, 30)

        self.assertGreaterEqual(
            max(node.cost for node in self.tree.nodes.values()),
            250_000_000,
        )

    def test_prerequisite_is_required(self) -> None:
        with self.assertRaises(RuneError):
            self.tree.calculate_purchase(self.data, "war.01")

    def test_purchase_deducts_gold_and_cannot_repeat(self) -> None:
        node = self.tree.nodes["war.00"]
        after = self.tree.calculate_purchase(self.data, node.node_id)

        self.assertEqual(after.gold, self.data.gold - node.cost)
        self.assertIn(node.node_id, after.unlocked_runes)

        with self.assertRaises(RuneError):
            self.tree.calculate_purchase(after, node.node_id)

    def test_insufficient_gold(self) -> None:
        with self.assertRaises(RuneError):
            self.tree.calculate_purchase(
                replace(self.data, gold=0),
                "war.00",
            )

    def test_full_offline_upgrades(self) -> None:
        data = self.data

        for index in (0, 1, 3, 7, 15):
            data = self.tree.calculate_purchase(
                data,
                f"chronomancy.{index:02d}",
            )

        for index in (2, 5, 11):
            data = self.tree.calculate_purchase(
                data,
                f"chronomancy.{index:02d}",
            )

        self.assertEqual(data.offline_cap_seconds, 12 * 3600)
        self.assertEqual(data.offline_efficiency, 1.0)

    def test_economy_bonus_is_not_double_applied(self) -> None:
        data = self.tree.calculate_purchase(self.data, "greed.00")
        self.assertAlmostEqual(data.farm.gold_bonus, 0.03)

        self.tree.effects(data.unlocked_runes)
        self.tree.effects(data.unlocked_runes)

        self.assertAlmostEqual(data.farm.gold_bonus, 0.03)

    def test_runes_change_computed_squad(self) -> None:
        before = self.tree.squad(self.data)
        after_data = self.tree.calculate_purchase(self.data, "war.00")
        after = self.tree.squad(after_data)

        self.assertGreater(
            after[0].stats.physical_damage,
            before[0].stats.physical_damage,
        )


class CubeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cube = CubeSynth()

    def test_full_rare_cube_probabilities(self) -> None:
        probabilities = self.cube.probabilities(make_items(12))

        self.assertAlmostEqual(probabilities[Rarity.RARE], 0.0)
        self.assertAlmostEqual(probabilities[Rarity.LEGENDARY], 0.976)
        self.assertAlmostEqual(probabilities[Rarity.IMMORTAL], 0.024)
        self.assertAlmostEqual(sum(probabilities.values()), 1.0)

    def test_synthesis_rune_adds_five_percentage_points(self) -> None:
        probabilities = self.cube.probabilities(
            make_items(12),
            critical_bonus=0.05,
        )
        self.assertAlmostEqual(probabilities[Rarity.IMMORTAL], 0.074)
        self.assertAlmostEqual(probabilities[Rarity.LEGENDARY], 0.926)

    def test_immortal_folds_upgrade_into_mythic(self) -> None:
        probabilities = self.cube.probabilities(
            make_items(12, Rarity.IMMORTAL)
        )
        self.assertAlmostEqual(probabilities[Rarity.MYTHIC], 1.0)
        self.assertAlmostEqual(sum(probabilities.values()), 1.0)

    def test_invalid_recipes(self) -> None:
        with self.assertRaises(SynthesisError):
            self.cube.probabilities(make_items(3))

        with self.assertRaises(SynthesisError):
            self.cube.probabilities(make_items(13))

        items = make_items(4)
        mixed = items[:3] + (
            replace(items[3], rarity=Rarity.COMMON),
        )
        with self.assertRaises(SynthesisError):
            self.cube.probabilities(mixed)

        wide_levels = items[:3] + (
            replace(items[3], level=100),
        )
        with self.assertRaises(SynthesisError):
            self.cube.probabilities(wide_levels)

        with self.assertRaises(SynthesisError):
            self.cube.probabilities(make_items(4, Rarity.MYTHIC))

    def test_consumes_exactly_selected_items(self) -> None:
        items = make_items(12)
        data = GameData(stash=items)

        selected = tuple(item.item_id for item in items[:4])
        result = self.cube.calculate(
            data,
            selected,
            rng=random.Random(10),
        )

        self.assertEqual(len(result.after.stash), 9)
        self.assertEqual(result.before, data)
        self.assertEqual(data.stash, items)

        remaining_ids = {item.item_id for item in result.after.stash}
        self.assertFalse(set(selected) & remaining_ids)
        self.assertTrue(
            {item.item_id for item in items[4:]} <= remaining_ids
        )
        self.assertIn(result.item.item_id, remaining_ids)

    def test_duplicate_or_missing_ids_rejected(self) -> None:
        items = make_items(4)
        data = GameData(stash=items)

        with self.assertRaises(SynthesisError):
            self.cube.calculate(data, (items[0].item_id,) * 4)

        with self.assertRaises(SynthesisError):
            self.cube.calculate(
                data,
                tuple(item.item_id for item in items[:3]) + ("missing",),
            )

    def test_autofill_respects_filter_and_exclusions(self) -> None:
        items = make_items(12)
        excluded = frozenset(item.item_id for item in items[:2])

        selected = self.cube.autofill(
            items,
            rarity=Rarity.RARE,
            excluded_ids=excluded,
        )

        self.assertEqual(len(selected), 10)
        self.assertFalse(set(selected) & excluded)

    def test_autofill_rejects_incompatible_level_groups(self) -> None:
        items = make_items(4)
        items = tuple(
            replace(item, level=1 + index * 50)
            for index, item in enumerate(items)
        )
        self.assertEqual(self.cube.autofill(items), ())


class PersistenceTests(unittest.TestCase):
    def test_new_models_round_trip(self) -> None:
        weapon = generate_item(
            20, Rarity.LEGENDARY,
            slot=EquipmentSlot.WEAPON,
            rng=random.Random(8),
        )
        stash_item = generate_item(
            15, Rarity.RARE,
            rng=random.Random(9),
        )

        data = GameData(
            gold=10**12,
            stash=(stash_item,),
            hero_builds=(
                HeroBuild("knight", HeroClass.KNIGHT, (weapon,)),
            ),
        )
        data = RunesTree().calculate_purchase(data, "war.00")

        with tempfile.TemporaryDirectory() as directory:
            saves = SaveManager(Path(directory) / "save.json")
            saves.write(data)
            self.assertEqual(saves.load(), data)

    def test_version_one_migration(self) -> None:
        data = GameData()
        raw = asdict(data)
        raw.pop("hero_builds")
        raw.pop("unlocked_runes")

        raw["stash"] = [{
            "item_id": "legacy-item",
            "rarity": "rare",
            "source_wave": 5,
            "sell_value": 50,
        }]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            path.write_text(
                json.dumps({"schema_version": 1, "state": raw}),
                encoding="utf-8",
            )

            restored = SaveManager(path).load()

        self.assertEqual(restored.unlocked_runes, ())
        self.assertEqual(restored.hero_builds, ())
        self.assertEqual(restored.stash[0].item_id, "legacy-item")
        self.assertEqual(restored.stash[0].sell_value, 50)

    def test_failed_cube_save_keeps_original_state(self) -> None:
        class BrokenSaves(SaveManager):
            def write(self, data: GameData) -> None:
                raise SaveError("Имитируем отказ диска")

        items = make_items(4)
        data = GameData(stash=items)
        state = GameState.instance()
        state.load(data)

        with self.assertRaises(SaveError):
            CubeSynth().transmute(
                state,
                BrokenSaves(),
                tuple(item.item_id for item in items),
                rng=random.Random(1),
            )

        self.assertIs(state.data, data)

    def test_rune_purchase_is_persisted(self) -> None:
        state = GameState.instance()
        state.load(GameData(gold=100_000))

        with tempfile.TemporaryDirectory() as directory:
            saves = SaveManager(Path(directory) / "save.json")
            after = RunesTree().buy(state, saves, "war.00")

            self.assertEqual(saves.load(), after)
            self.assertEqual(state.data, after)


if __name__ == "__main__":
    unittest.main()
