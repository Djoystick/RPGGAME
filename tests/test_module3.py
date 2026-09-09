from __future__ import annotations

import random
import unittest
from dataclasses import replace

from PySide6.QtCore import QCoreApplication

from engine.combat_manager import (
    CombatManager,
    HERO_IFRAMES,
    roll_damage,
)
from engine.state import FarmProfile, GameData, GameState
from gfx.animations import AnimationController, AnimationState
from models.enemy import (
    Act,
    EnemyAffix,
    EnemyRank,
    act_for_wave,
    spawn_wave,
)
from models.hero import total_exp_for_level


APP = QCoreApplication.instance() or QCoreApplication([])


class DamageTests(unittest.TestCase):
    def test_physical_armor_formula(self) -> None:
        hit = roll_damage(100, 100, rng=random.Random(1))
        self.assertAlmostEqual(hit.damage, 50)

    def test_magic_uses_half_armor(self) -> None:
        hit = roll_damage(100, 100, magical=True, rng=random.Random(1))
        self.assertAlmostEqual(hit.damage, 100 / 1.5)

    def test_guaranteed_critical(self) -> None:
        hit = roll_damage(
            100, 0,
            crit_chance=1.0,
            crit_multiplier=2.0,
            rng=random.Random(1),
        )
        self.assertTrue(hit.critical)
        self.assertEqual(hit.damage, 200)

    def test_guaranteed_evasion(self) -> None:
        hit = roll_damage(100, 0, evasion=1.0, rng=random.Random(1))
        self.assertTrue(hit.dodged)
        self.assertEqual(hit.damage, 0)

    def test_invalid_parameters(self) -> None:
        with self.assertRaises(ValueError):
            roll_damage(-1, 0)
        with self.assertRaises(ValueError):
            roll_damage(1, 0, evasion=1.5)
        with self.assertRaises(ValueError):
            roll_damage(float("nan"), 0)


class EnemyTests(unittest.TestCase):
    def test_act_boundaries(self) -> None:
        self.assertEqual(act_for_wave(1), Act.CRYPTS)
        self.assertEqual(act_for_wave(30), Act.CRYPTS)
        self.assertEqual(act_for_wave(31), Act.FOREST)
        self.assertEqual(act_for_wave(61), Act.CALDERA)
        self.assertEqual(act_for_wave(91), Act.CITADEL)
        self.assertEqual(act_for_wave(1000), Act.CITADEL)

    def test_boss_wave(self) -> None:
        enemies = spawn_wave(10, random.Random(1))
        self.assertEqual(len(enemies), 1)
        self.assertEqual(enemies[0].rank, EnemyRank.BOSS)
        self.assertEqual(enemies[0].rage, 0)

        enemies[0].rage = enemies[0].rage_max
        self.assertTrue(enemies[0].enraged)
        self.assertGreater(enemies[0].effective_damage, enemies[0].damage)

    def test_generation_is_reproducible(self) -> None:
        first = spawn_wave(45, random.Random(123))
        second = spawn_wave(45, random.Random(123))
        self.assertEqual(first, second)

    def test_elite_affixes_are_valid_and_unique(self) -> None:
        elites = []

        for seed in range(30):
            elites.extend(
                enemy for enemy in spawn_wave(45, random.Random(seed))
                if enemy.rank == EnemyRank.ELITE
            )

        self.assertTrue(elites)

        for enemy in elites:
            self.assertEqual(len(enemy.affixes), 2)
            self.assertEqual(len(set(enemy.affixes)), 2)
            self.assertTrue(all(isinstance(a, EnemyAffix) for a in enemy.affixes))

    def test_later_wave_has_more_health(self) -> None:
        first = spawn_wave(1, random.Random(8))
        later = spawn_wave(21, random.Random(8))
        self.assertGreater(
            sum(enemy.max_hp for enemy in later),
            sum(enemy.max_hp for enemy in first),
        )


class AnimationTests(unittest.TestCase):
    def test_same_state_does_not_reset_frame(self) -> None:
        animation = AnimationController()
        animation.set_state(AnimationState.ATTACK)
        animation.advance(0.20)

        frame = animation.frame_index
        elapsed = animation.elapsed

        self.assertFalse(animation.set_state(AnimationState.ATTACK))
        self.assertEqual(animation.frame_index, frame)
        self.assertEqual(animation.elapsed, elapsed)

    def test_death_holds_last_frame(self) -> None:
        animation = AnimationController()
        animation.set_state(AnimationState.DIE)
        animation.advance(100)

        self.assertEqual(animation.frame_index, 3)
        self.assertEqual(animation.state, AnimationState.DIE)
        self.assertTrue(animation.finished)

    def test_idle_loops(self) -> None:
        animation = AnimationController()
        animation.advance(0.80)
        self.assertEqual(animation.frame_index, 0)


class CombatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = GameState.instance()
        self.state.load(GameData(
            last_active_timestamp=1000,
            farm=FarmProfile(drop_chance=0.0),
        ))
        self.combat = CombatManager(self.state, rng=random.Random(17))
        self.combat.start()

    def tearDown(self) -> None:
        self.combat.stop()

    def test_start_spawns_party_and_wave(self) -> None:
        self.assertEqual(len(self.combat.heroes), 4)
        self.assertEqual(len(self.combat.enemies), 3)
        self.assertGreater(self.combat.barrier, 0)
        self.assertEqual(self.combat.phase, "battle")

    def test_start_is_idempotent(self) -> None:
        ids = tuple(enemy.enemy_id for enemy in self.combat.enemies)
        self.combat.start()
        self.assertEqual(
            tuple(enemy.enemy_id for enemy in self.combat.enemies),
            ids,
        )

    def test_fixed_step_partition(self) -> None:
        self.combat.advance(0.025)
        self.assertAlmostEqual(self.combat.time, 0.0)
        self.combat.advance(0.025)
        self.assertAlmostEqual(self.combat.time, 0.05)

    def test_iframes_prevent_repeated_damage(self) -> None:
        hero = self.combat.heroes[0]
        hero.stats = replace(hero.stats, evasion=0.0)
        self.combat.barrier = 0

        first = self.combat._hit_hero(hero, 30, False)
        hp = hero.hp
        second = self.combat._hit_hero(hero, 30, False)

        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(hero.hp, hp)

        self.combat.time += HERO_IFRAMES + 0.001
        third = self.combat._hit_hero(hero, 30, False)
        self.assertGreater(third, 0)

    def test_damage_does_not_interrupt_attack(self) -> None:
        hero = self.combat.heroes[0]
        hero.stats = replace(hero.stats, evasion=0.0)
        hero.animation = "attack"
        hero.animation_left = 0.30
        self.combat.barrier = 0

        self.combat._hit_hero(hero, 10, False)

        self.assertEqual(hero.animation, "attack")
        self.assertEqual(hero.animation_left, 0.30)
        self.assertGreater(hero.invulnerable_until, self.combat.time)

    def test_barrier_absorbs_damage(self) -> None:
        hero = self.combat.heroes[0]
        hero.stats = replace(hero.stats, evasion=0.0)

        hp = hero.hp
        barrier = self.combat.barrier

        dealt = self.combat._hit_hero(hero, 10, False)

        self.assertEqual(dealt, 0)
        self.assertEqual(hero.hp, hp)
        self.assertLess(self.combat.barrier, barrier)

    def test_cooldowns_are_independent(self) -> None:
        first, second = self.combat.heroes[:2]

        first_id = first.hero.skills[0].skill_id
        second_id = second.hero.skills[0].skill_id

        first.skill_cooldowns[first_id] = 4.0
        second.skill_cooldowns[second_id] = 7.0

        self.combat.advance(0.5)

        self.assertAlmostEqual(first.skill_cooldowns[first_id], 3.5)
        self.assertAlmostEqual(second.skill_cooldowns[second_id], 6.5)

    def test_auto_skill_uses_cooldown(self) -> None:
        uses = []
        self.combat.skill_used.connect(
            lambda hero_id, skill_id: uses.append((hero_id, skill_id))
        )

        for enemy in self.combat.enemies:
            enemy.x = 260
            enemy.hp = enemy.max_hp = 100_000
            enemy.damage = 0

        self.combat.advance(0.05)
        count = len(uses)

        self.assertEqual(count, 4)
        self.combat.advance(0.20)
        self.assertEqual(len(uses), count)

        for hero in self.combat.heroes:
            skill = hero.hero.skills[0]
            self.assertGreater(hero.skill_cooldowns[skill.skill_id], 0)

    def test_wave_reward_is_given_once(self) -> None:
        for enemy in self.combat.enemies:
            enemy.hp = 0

        self.combat.advance(0.05)

        self.assertEqual(self.state.data.cleared_waves, 1)
        self.assertEqual(self.state.data.gold, 100)
        self.assertEqual(
            sum(hero.total_exp for hero in self.state.data.party),
            30,
        )

        self.combat.advance(0.50)
        self.assertEqual(self.state.data.cleared_waves, 1)
        self.assertEqual(self.state.data.gold, 100)

    def test_new_wave_spawns_after_intermission(self) -> None:
        for enemy in self.combat.enemies:
            enemy.hp = 0

        self.combat.advance(0.05)
        self.combat.advance(1.1)

        self.assertEqual(self.combat.frame().wave, 2)
        self.assertEqual(self.combat.phase, "battle")
        self.assertTrue(any(enemy.alive for enemy in self.combat.enemies))

    def test_wipe_does_not_grant_rewards(self) -> None:
        for hero in self.combat.heroes:
            hero.hp = 0
            hero.animation = "die"

        self.combat.advance(0.05)

        self.assertEqual(self.combat.phase, "defeat")
        self.assertEqual(self.state.data.gold, 0)
        self.assertEqual(self.state.data.cleared_waves, 0)

        self.combat.advance(3.1)

        self.assertEqual(self.combat.phase, "battle")
        self.assertTrue(all(hero.alive for hero in self.combat.heroes))

    def test_partial_progress_is_flushed(self) -> None:
        for enemy in self.combat.enemies:
            enemy.hp *= 0.5

        self.combat.flush()

        from fractions import Fraction
        self.assertAlmostEqual(
            float(Fraction(self.state.data.wave_fraction)),
            0.5,
        )

    def test_healing_is_capped(self) -> None:
        hero = self.combat.heroes[0]
        hero.hp = 1

        self.combat._heal(hero, 10**9)

        self.assertEqual(hero.hp, hero.stats.max_hp)

    def test_all_level_fifteen_skill_effects_are_supported(self) -> None:
        self.combat.stop()

        data = self.state.data
        party = tuple(
            replace(
                hero,
                total_exp=total_exp_for_level(15),
                hp=hero.max_hp,
            )
            for hero in data.party
        )
        self.state.load(replace(data, party=party, wave_fraction="0"))

        combat = CombatManager(self.state, rng=random.Random(1))
        combat.start()

        try:
            for enemy in combat.enemies:
                enemy.x = 250
                enemy.hp = enemy.max_hp = 10**8
                enemy.damage = 0

            for hero in combat.heroes:
                hero.hp *= 0.5

            combat.barrier = 0

            for hero in combat.heroes:
                for skill in hero.hero.skills:
                    # Метод может вернуть False для ненужного сейчас щита/хила,
                    # но не должен встретить неизвестную семантику.
                    combat._cast(hero, skill)

            combat.advance(2.0)
        finally:
            combat.stop()


if __name__ == "__main__":
    unittest.main()
