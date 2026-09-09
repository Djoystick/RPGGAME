from __future__ import annotations

import math
import random
import unittest
from dataclasses import asdict

from PySide6.QtCore import QCoreApplication

from engine.biomes import BIOME_ORDER, biome_for_wave, act_banner_for_biome
from engine.combat_core import (
    AilmentSystem,
    AilmentType,
    AILMENT_CAP,
    crushing_shatter,
)
from models.enemy import (
    BESTIARY,
    Act,
    TOTAL_ENEMY_TYPES,
    spawn_wave,
)
from models.item import (
    EquipmentSlot,
    Gem,
    GemType,
    Item,
    Rarity,
    apply_item_set_bonuses,
    generate_item,
    item_from_dict,
    roll_enemy_loot,
    roll_set_id,
    roll_socket_count,
    socket_gem,
    unsocket_gem,
)

APP = QCoreApplication.instance() or QCoreApplication([])


def _item(item_id: str = "i1", *, rarity=Rarity.RARE, sockets: int = 0) -> Item:
    return Item(
        item_id=item_id,
        rarity=rarity,
        source_wave=1,
        sell_value=100,
        slot=EquipmentSlot.WEAPON,
        level=10,
        sockets=sockets,
    )


def _gem(gem_id: str = "g1", gem_type=GemType.RUBY, level: int = 1) -> Gem:
    return Gem(gem_id=gem_id, gem_type=gem_type, level=level, quality=1.0)


class GemSocketTests(unittest.TestCase):
    def test_common_items_have_no_sockets(self) -> None:
        self.assertEqual(roll_socket_count(Rarity.COMMON, random.Random(1)), 0)
        self.assertEqual(roll_socket_count(Rarity.UNCOMMON, random.Random(1)), 0)

    def test_socket_cap_by_rarity(self) -> None:
        for rarity, hi in (
            (Rarity.RARE, 1), (Rarity.LEGENDARY, 2),
            (Rarity.IMMORTAL, 3), (Rarity.MYTHIC, 3),
        ):
            for seed in range(50):
                count = roll_socket_count(rarity, random.Random(seed))
                self.assertGreaterEqual(count, 1)
                self.assertLessEqual(count, hi)

    def test_socket_gem_folds_stats_into_item(self) -> None:
        item = _item(sockets=1)
        self.assertEqual(item.gems, ())
        before = item.stats.fire_bonus
        item, gem = socket_gem(item, _gem(), random.Random(2))
        self.assertIsNotNone(gem)
        self.assertEqual(len(item.gems), 1)
        self.assertGreater(item.stats.fire_bonus, before)

    def test_socket_gem_rejects_when_full(self) -> None:
        item = _item(sockets=1)
        item, _ = socket_gem(item, _gem("a"), random.Random(1))
        item, placed = socket_gem(item, _gem("b"), random.Random(2))
        self.assertIsNone(placed)
        self.assertEqual(len(item.gems), 1)

    def test_unsocket_removes_stats(self) -> None:
        item = _item(sockets=1)
        item, gem = socket_gem(item, _gem(), random.Random(1))
        fire = item.stats.fire_bonus
        item, removed = unsocket_gem(item, gem.gem_id)
        self.assertEqual(removed.gem_id, gem.gem_id)
        self.assertEqual(item.gems, ())
        self.assertLess(item.stats.fire_bonus, fire)

    def test_gem_stats_scale_with_level(self) -> None:
        low = _gem(level=1).stats
        high = _gem(level=10).stats
        self.assertGreater(high.fire_bonus, low.fire_bonus)

    def test_item_roundtrip_preserves_sockets_and_gems(self) -> None:
        item = _item(sockets=2)
        item, _ = socket_gem(item, _gem("g-a"), random.Random(1))
        item, _ = socket_gem(item, _gem("g-b"), random.Random(2))
        restored = item_from_dict(asdict(item))
        self.assertEqual(restored, item)
        self.assertEqual(len(restored.gems), 2)


class ItemSetTests(unittest.TestCase):
    def test_no_sets_gives_no_bonus(self) -> None:
        gear = (_item("a"), _item("b"))
        bonus, active = apply_item_set_bonuses(gear)
        self.assertEqual(active, ())
        self.assertEqual(bonus.fire_bonus, 0.0)

    def test_two_pieces_activate_set(self) -> None:
        from dataclasses import replace as dreplace

        a = dreplace(_item("a", rarity=Rarity.LEGENDARY), set_id="hell_ash")
        b = dreplace(_item("b", rarity=Rarity.LEGENDARY), set_id="hell_ash")
        bonus, active = apply_item_set_bonuses((a, b))
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0][1], 2)
        self.assertGreater(bonus.fire_bonus, 0)

    def test_threshold_step_uses_highest(self) -> None:
        from dataclasses import replace as dreplace

        gear = tuple(
            dreplace(_item(f"x{i}", rarity=Rarity.MYTHIC), set_id="hell_ash")
            for i in range(6)
        )
        bonus, active = apply_item_set_bonuses(gear)
        self.assertEqual(active[0][1], 6)
        # 6-бонус Пепла Преисподней включает CDR.
        self.assertGreater(bonus.cooldown_reduction, 0)

    def test_set_id_only_for_high_rarity(self) -> None:
        for seed in range(40):
            self.assertIsNone(
                roll_set_id(Rarity.COMMON, random.Random(seed))
            )
            self.assertIsNone(
                roll_set_id(Rarity.RARE, random.Random(seed))
            )
        found = any(
            roll_set_id(Rarity.LEGENDARY, random.Random(seed)) is not None
            for seed in range(200)
        )
        self.assertTrue(found)


class EnemyRichnessTests(unittest.TestCase):
    def test_at_least_sixteen_enemy_types(self) -> None:
        self.assertGreaterEqual(TOTAL_ENEMY_TYPES, 16)

    def test_each_act_has_rich_bestiary(self) -> None:
        for act in Act:
            self.assertGreaterEqual(len(tuple(BESTIARY[act])), 4)

    def test_template_ids_unique(self) -> None:
        ids = [t.template_id for act in Act for t in BESTIARY[act]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_boss_wave_still_single(self) -> None:
        enemies = spawn_wave(10, random.Random(1))
        self.assertEqual(len(enemies), 1)
        self.assertTrue(enemies[0].is_boss)


class BiomeTests(unittest.TestCase):
    def test_at_least_eight_biomes_with_unique_ids(self) -> None:
        self.assertGreaterEqual(len(BIOME_ORDER), 8)
        ids = [b.biome_id for b in BIOME_ORDER]
        self.assertEqual(len(ids), len(set(ids)))

    def test_biome_mapping_deterministic_and_cycles(self) -> None:
        seen = set()
        for wave in range(1, 16 * 16 + 1):
            biome = biome_for_wave(wave)
            seen.add(biome.biome_id)
            self.assertEqual(biome, biome_for_wave(wave))
        self.assertGreaterEqual(len(seen), 8)

    def test_banner_format(self) -> None:
        banner = act_banner_for_biome(biome_for_wave(1))
        self.assertIn("АКТ", banner)
        self.assertEqual(banner, banner.upper())


class AilmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system = AilmentSystem()

    def test_ignite_caps_stacks(self) -> None:
        for _ in range(20):
            self.system.inflict("u", AilmentType.IGNITE, 100)
        self.assertEqual(
            self.system.stacks("u", AilmentType.IGNITE),
            AILMENT_CAP[AilmentType.IGNITE],
        )

    def test_shock_increases_damage_taken(self) -> None:
        self.assertEqual(self.system.damage_taken_multiplier("u"), 1.0)
        self.system.inflict("u", AilmentType.SHOCK, 50)
        self.assertAlmostEqual(self.system.damage_taken_multiplier("u"), 1.25)

    def test_poison_eats_armor_and_healing(self) -> None:
        self.system.inflict("u", AilmentType.POISON, 100)
        self.system.inflict("u", AilmentType.POISON, 100)
        self.assertAlmostEqual(self.system.armor_multiplier("u"), 0.88)
        self.assertEqual(self.system.healing_multiplier("u"), 0.50)

    def test_chill_slows_and_freezes(self) -> None:
        self.system.inflict("u", AilmentType.CHILL, 0)
        self.assertAlmostEqual(self.system.speed_multiplier("u"), 0.60)
        for _ in range(6):
            self.system.inflict("u", AilmentType.CHILL, 0)
        self.assertTrue(self.system.is_frozen("u"))
        self.assertEqual(self.system.speed_multiplier("u"), 0.0)

    def test_ignite_ticks_and_expires(self) -> None:
        self.system.inflict("u", AilmentType.IGNITE, 100)
        total = 0.0
        # Прокручиваем 10 секунд (длительность горения 4 c).
        for _ in range(400):
            for tick in self.system.tick(0.05):
                total += tick.damage
        self.assertGreater(total, 0)
        self.assertEqual(self.system.stacks("u", AilmentType.IGNITE), 0)

    def test_crushing_shatter_doubles_against_frozen(self) -> None:
        self.assertEqual(crushing_shatter(1.0, frozen=True, crushing=True), 2.0)
        self.assertEqual(crushing_shatter(1.0, frozen=True, crushing=False), 1.0)
        self.assertEqual(crushing_shatter(1.0, frozen=False, crushing=True), 1.0)


if __name__ == "__main__":
    unittest.main()
