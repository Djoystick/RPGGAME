from __future__ import annotations

import random
import unittest
from dataclasses import asdict, fields, replace

from PySide6.QtCore import QCoreApplication

from engine.combat_manager import (
    BASIC_INTERVALS, HERO_IFRAMES, CombatManager, combined_chance,
)
from engine.state import FarmProfile, GameData, GameState
from models.hero import (
    DETAILED_REGISTRY, Hero, HeroClass,
    experience_awards, total_exp_for_level,
)
from models.item import (
    EquipmentSlot, Item, ItemKind, Rarity,
    generate_item, item_from_dict,
)
from models.stats import StatBlock


APP = QCoreApplication.instance() or QCoreApplication([])


class FixedRandom(random.Random):
    def random(self) -> float:
        return 0.99


class StatModelTests(unittest.TestCase):
    def test_registry_has_exactly_43_unique_names(self) -> None:
        hero = Hero("knight", "Рыцарь", HeroClass.KNIGHT)
        detailed = hero.detailed_stats()

        self.assertEqual(list(detailed), ["Attack", "Defense", "Utility"])
        self.assertEqual(len(detailed["Attack"]), 21)
        self.assertEqual(len(detailed["Defense"]), 12)
        self.assertEqual(len(detailed["Utility"]), 10)

        names = [name for rows in detailed.values() for name, _ in rows]
        self.assertEqual(len(names), 43)
        self.assertEqual(len(set(names)), 43)

    def test_every_statblock_field_adds_and_scales(self) -> None:
        values = {definition.name: 2.0 for definition in fields(StatBlock)}
        block = StatBlock(**values)
        result = (block + block).scaled(0.5)

        for definition in fields(StatBlock):
            self.assertEqual(getattr(result, definition.name), 2.0)

    def test_old_constructor_and_old_item_are_supported(self) -> None:
        self.assertEqual(StatBlock(damage=3).damage, 3)
        item = item_from_dict({
            "item_id": "legacy",
            "rarity": "rare",
            "source_wave": 1,
            "sell_value": 50,
        })
        self.assertEqual(item.kind, ItemKind.GENERIC)
        self.assertEqual(item.stats.exp_gain, 0)

    def test_attack_formulas(self) -> None:
        hero = Hero("knight", "Рыцарь", HeroClass.KNIGHT)
        bonus = StatBlock(
            damage=10,
            physical_bonus=0.25,
            attack_speed=0.20,
            crit_damage=0.10,
            cooldown_reduction=0.05,
        )
        primary = hero.primary_stats(bonus)
        secondary = hero.secondary_stats(bonus)

        self.assertAlmostEqual(
            secondary.physical_damage,
            (5 + 2 * primary.strength + 1.2 * primary.agility + 10) * 1.25,
        )
        self.assertAlmostEqual(
            secondary.attack_speed,
            1 + 0.015 * primary.agility + primary.attack_speed,
        )
        self.assertAlmostEqual(
            secondary.crit_multiplier,
            1.5 + 0.005 * primary.strength + 0.10,
        )
        self.assertAlmostEqual(
            secondary.cooldown_reduction,
            0.002 * primary.intelligence + 0.05,
        )

    def test_resistance_and_probability_caps(self) -> None:
        hero = Hero("knight", "Рыцарь", HeroClass.KNIGHT)
        stats = hero.secondary_stats(StatBlock(
            fire_res=10, cold_res=10, lightning_res=10, chaos_res=10,
            crit_chance=10, evasion=10, block_chance=10,
            cooldown_reduction=10,
        ))

        self.assertEqual(stats.fire_res, 0.75)
        self.assertEqual(stats.cold_res, 0.75)
        self.assertEqual(stats.lightning_res, 0.75)
        self.assertEqual(stats.chaos_res, 0.75)
        self.assertEqual(stats.evasion, 0.60)
        self.assertEqual(stats.block_chance, 0.75)
        self.assertEqual(stats.crit_chance, 0.75)
        self.assertEqual(stats.cooldown_reduction, 0.75)

    def test_class_affinities(self) -> None:
        pyro = Hero("p", "Пиромант", HeroClass.PYROMANCER).secondary_stats()
        necro = Hero("n", "Некромант", HeroClass.NECROMANCER).secondary_stats()
        ranger = Hero("r", "Рейнджер", HeroClass.RANGER).secondary_stats()
        paladin = Hero("h", "Паладин", HeroClass.PALADIN).secondary_stats()

        self.assertEqual(pyro.fire_enhancement, 0.25)
        self.assertEqual(necro.chaos_enhancement, 0.20)
        self.assertEqual(necro.summon_damage, 0.30)
        self.assertEqual(necro.lifesteal, 0.04)
        self.assertEqual(ranger.projectile_damage, 0.20)
        self.assertEqual(ranger.basic_attack_range, 350)
        self.assertEqual(paladin.skill_heal, 0.15)
        self.assertEqual(paladin.lightning_enhancement, 0.15)

    def test_shield_grants_base_block(self) -> None:
        shield = Item(
            "shield", Rarity.COMMON, 1, 10,
            slot=EquipmentSlot.OFFHAND,
            kind=ItemKind.SHIELD,
        )
        hero = Hero("k", "Рыцарь", HeroClass.KNIGHT)
        equipped = replace(hero, equipment=(shield,))

        self.assertAlmostEqual(
            equipped.secondary_stats().block_chance
            - hero.secondary_stats().block_chance,
            0.15,
        )

    def test_allocated_stats_and_free_points(self) -> None:
        hero = Hero(
            "k", "Рыцарь", HeroClass.KNIGHT,
            total_exp=total_exp_for_level(3),
            allocated_stats=(3, 2, 0, 0, 0),
        )
        self.assertEqual(hero.free_stat_points, 5)

        unallocated = replace(hero, allocated_stats=(0, 0, 0, 0, 0))
        self.assertEqual(
            hero.primary_stats().strength - unallocated.primary_stats().strength,
            3,
        )

    def test_item_roundtrip_with_new_affixes(self) -> None:
        for rarity in Rarity:
            item = generate_item(20, rarity, rng=random.Random(12))
            self.assertEqual(item_from_dict(asdict(item)), item)

    def test_all_registry_attributes_exist(self) -> None:
        stats = Hero("k", "Рыцарь", HeroClass.KNIGHT).secondary_stats()
        for rows in DETAILED_REGISTRY.values():
            for _, attribute, _ in rows:
                self.assertTrue(hasattr(stats, attribute))

    def test_xp_bonus_is_individual(self) -> None:
        base = Hero("k", "Рыцарь", HeroClass.KNIGHT).secondary_stats()
        boosted = replace(base, exp_gain=0.5, additional_exp=2)

        awards, cursor = experience_awards(40, 1, (boosted, base, base, base))
        self.assertEqual(awards, (18, 10, 10, 10))
        self.assertEqual(cursor, 0)

    def test_xp_bulk_matches_sequential_waves(self) -> None:
        base = Hero("k", "Рыцарь", HeroClass.KNIGHT).secondary_stats()
        stats = (
            replace(base, exp_gain=0.35, additional_exp=2),
            base,
            replace(base, exp_gain=0.75),
            base,
        )
        bulk, bulk_cursor = experience_awards(31, 17, stats, 2)

        accumulated = [0, 0, 0, 0]
        cursor = 2
        for _ in range(17):
            awards, cursor = experience_awards(31, 1, stats, cursor)
            accumulated = [
                total + gained for total, gained in zip(accumulated, awards)
            ]

        self.assertEqual(tuple(accumulated), bulk)
        self.assertEqual(cursor, bulk_cursor)


class CombatMathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = GameState.instance()
        self.state.load(GameData(
            last_active_timestamp=1000,
            farm=FarmProfile(drop_chance=0),
        ))
        self.combat = CombatManager(self.state, rng=random.Random(5))
        self.combat.start()
        self.combat.rng = FixedRandom()

        self.hero = self.combat.heroes[0]
        self.enemy = self.combat.enemies[0]
        self.enemy.affixes = ()
        self.enemy.hp = self.enemy.max_hp = 10000
        self.enemy.armor = 0
        self.combat.barrier = 0

        self.hero.stats = replace(
            self.hero.stats,
            armor=0,
            evasion=0,
            block_chance=0,
            crit_chance=0,
            lifesteal=0,
            damage_absorption=0,
            elemental_dodge=0,
            elemental_block=0,
        )

    def tearDown(self) -> None:
        self.combat.stop()

    def test_attack_speed_changes_interval(self) -> None:
        self.hero.stats = replace(self.hero.stats, attack_speed=2)
        self.assertEqual(
            self.combat.basic_interval(self.hero),
            BASIC_INTERVALS[self.hero.hero.hero_class] / 2,
        )

    def test_cdr_changes_skill_cooldown(self) -> None:
        self.hero.stats = replace(self.hero.stats, cooldown_reduction=0.75)
        skill = self.hero.hero.skills[0]
        self.assertEqual(
            self.combat.skill_cooldown(self.hero, skill),
            skill.cooldown_seconds * 0.25,
        )

    def test_regen_occurs_in_combat(self) -> None:
        self.hero.stats = replace(self.hero.stats, hp_regen=10)
        self.hero.hp = 100
        for enemy in self.combat.enemies:
            enemy.x = 10000
        # _step без _sync_heroes позволяет изолировать тестовый модификатор.
        self.combat._step(0.05, 0.05)
        self.assertAlmostEqual(self.hero.hp, 100.5)

    def test_lifesteal_and_hp_on_hit(self) -> None:
        self.hero.hp = 100
        self.hero.stats = replace(
            self.hero.stats, lifesteal=0.10, hp_per_hit=7
        )
        dealt = self.combat._hit_enemy(
            self.hero, self.enemy, 50, False,
            allow_crit=False, allow_splash=False,
        )
        self.assertEqual(dealt, 50)
        self.assertEqual(self.hero.hp, 112)

    def test_hp_on_kill_only_once(self) -> None:
        self.hero.hp = 100
        self.hero.stats = replace(self.hero.stats, hp_per_kill=20)
        self.enemy.hp = 10

        self.combat._hit_enemy(self.hero, self.enemy, 100, False)
        self.assertEqual(self.hero.hp, 120)

        self.combat._hit_enemy(self.hero, self.enemy, 100, False)
        self.assertEqual(self.hero.hp, 120)

    def test_block_absorbs_sixty_percent(self) -> None:
        self.hero.stats = replace(self.hero.stats, block_chance=1)
        events = []
        self.combat.damage_event.connect(events.append)

        dealt = self.combat._hit_hero(self.hero, 100, False)

        self.assertEqual(dealt, 40)
        self.assertTrue(any(event.kind == "block" for event in events))

    def test_elemental_resistance_uses_selected_element(self) -> None:
        self.hero.stats = replace(
            self.hero.stats, fire_res=0.75, cold_res=0
        )
        first = self.combat._hit_hero(
            self.hero, 100, True, element="fire"
        )
        self.combat.time += HERO_IFRAMES + 0.01
        second = self.combat._hit_hero(
            self.hero, 100, True, element="cold"
        )

        self.assertEqual(first, 25)
        self.assertEqual(second, 100)

    def test_flat_absorption(self) -> None:
        self.hero.stats = replace(self.hero.stats, damage_absorption=12)
        self.assertEqual(
            self.combat._hit_hero(self.hero, 30, False),
            18,
        )

    def test_iframes_still_prevent_collision_spam(self) -> None:
        first = self.combat._hit_hero(self.hero, 20, False)
        second = self.combat._hit_hero(self.hero, 20, False)
        self.assertEqual(first, 20)
        self.assertEqual(second, 0)

    def test_elemental_dodge(self) -> None:
        self.hero.stats = replace(self.hero.stats, elemental_dodge=1)
        self.assertEqual(
            self.combat._hit_hero(self.hero, 100, True, element="fire"),
            0,
        )

    def test_combined_probability(self) -> None:
        self.assertAlmostEqual(combined_chance(0.2, 0.25), 0.4)

    def test_element_and_attack_tags_affect_damage(self) -> None:
        self.hero.stats = replace(
            self.hero.stats,
            fire_enhancement=0.25,
            projectile_damage=0.20,
            aoe_damage=0.50,
        )
        dealt = self.combat._hit_enemy(
            self.hero, self.enemy, 100, True,
            element="fire",
            tags=frozenset({"projectile", "aoe"}),
            allow_crit=False,
        )
        self.assertAlmostEqual(dealt, 100 * 1.25 * 1.20 * 1.50)

    def test_summon_damage(self) -> None:
        self.hero.stats = replace(self.hero.stats, summon_damage=0.30)
        dealt = self.combat._hit_enemy(
            self.hero, self.enemy, 100, True,
            element="chaos",
            tags=frozenset({"summon"}),
            allow_crit=False,
        )
        self.assertEqual(dealt, 130)

    def test_projectile_count_and_multistrike(self) -> None:
        self.hero.stats = replace(
            self.hero.stats, projectile_count=2, multistrike=1
        )
        self.combat._dispatch(
            self.hero, self.enemy, 10, "physical",
            frozenset({"projectile"}),
        )
        self.assertEqual(len(self.combat._impacts), 6)

    def test_projectile_speed_changes_arrival(self) -> None:
        tags = frozenset({"projectile"})
        self.hero.stats = replace(self.hero.stats, projectile_speed=0)
        self.combat._dispatch(self.hero, self.enemy, 10, "physical", tags)
        slow = self.combat._impacts[0].remaining

        self.combat._impacts.clear()
        self.hero.stats = replace(self.hero.stats, projectile_speed=1)
        self.combat._dispatch(self.hero, self.enemy, 10, "physical", tags)
        fast = self.combat._impacts[0].remaining

        self.assertAlmostEqual(fast, slow / 2)

    def test_projectile_does_not_hit_immediately(self) -> None:
        before = self.enemy.hp
        self.combat._dispatch(
            self.hero, self.enemy, 10, "physical",
            frozenset({"projectile"}),
        )
        self.combat._tick_impacts(0.01)
        self.assertEqual(self.enemy.hp, before)
        self.combat._tick_impacts(10)
        self.assertLess(self.enemy.hp, before)

    def test_aoe_radius(self) -> None:
        second = self.combat.enemies[1]
        self.enemy.x, self.enemy.y = 200, 100
        second.x, second.y = 320, 100
        self.combat.enemies[2].x = 1000

        self.hero.stats = replace(self.hero.stats, aoe_enhancement=0)
        self.assertEqual(len(self.combat._area_targets(self.hero, self.enemy)), 1)

        self.hero.stats = replace(self.hero.stats, aoe_enhancement=1)
        self.assertEqual(len(self.combat._area_targets(self.hero, self.enemy)), 2)

    def test_skill_level_and_duration(self) -> None:
        skill = replace(
            self.hero.hero.skills[0],
            duration_seconds=10,
        )
        self.hero.stats = replace(
            self.hero.stats,
            all_skill_level=3,
            skill_duration=0.5,
        )
        self.assertAlmostEqual(
            self.combat.skill_power(self.hero, skill),
            skill.power_multiplier * 1.3,
        )
        self.assertEqual(self.combat.skill_duration(self.hero, skill), 15)

    def test_wave_xp_uses_runtime_stats(self) -> None:
        self.hero.stats = replace(
            self.hero.stats, exp_gain=1, additional_exp=2
        )
        expected, _ = experience_awards(
            self.state.data.farm.exp_per_wave,
            1,
            [hero.stats for hero in self.combat.heroes],
        )
        self.combat._finish_wave()

        self.assertEqual(
            tuple(hero.total_exp for hero in self.state.data.party),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
