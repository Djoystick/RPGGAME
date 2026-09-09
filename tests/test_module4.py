from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QCoreApplication

import config as C
from engine.combat_manager import CombatManager
from engine.save_manager import SaveManager
from engine.state import GameData, GameState
from models.item import EquipmentSlot, Item, Rarity
from ui.actions import UiActions


APP = QCoreApplication.instance() or QCoreApplication([])


class Module4UiActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = Path(self.temp_dir.name) / "save.json"
        self.saves = SaveManager(self.save_path)
        self.state = GameState.instance()

        test_item = Item(
            item_id="test-sword",
            rarity=Rarity.RARE,
            source_wave=1,
            sell_value=100,
            slot=EquipmentSlot.WEAPON,
            level=10,
        )

        initial_data = GameData(
            gold=50_000,
            stash=(test_item,),
            backpack=(),
        )
        self.saves.write(initial_data)
        self.state.load(initial_data)

        self.combat = CombatManager(self.state)
        self.actions = UiActions(self.state, self.saves, self.combat)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_transfer_item_stash_to_backpack_and_back(self) -> None:
        # Move from stash to backpack
        self.actions.move_items(("test-sword",), to_backpack=True)
        data = self.state.data
        self.assertEqual(len(data.stash), 0)
        self.assertEqual(len(data.backpack), 1)
        self.assertEqual(data.backpack[0].item_id, "test-sword")

        # Move back to stash
        self.actions.move_items(("test-sword",), to_backpack=False)
        data = self.state.data
        self.assertEqual(len(data.stash), 1)
        self.assertEqual(len(data.backpack), 0)

    def test_equip_and_unequip_item(self) -> None:
        # Put item in backpack first
        self.actions.move_items(("test-sword",), to_backpack=True)
        knight_id = self.state.data.party[0].hero_id

        # Equip to knight
        self.actions.equip(knight_id, "test-sword")
        data = self.state.data
        self.assertEqual(len(data.backpack), 0)

        # Check knight has weapon equipped
        build = next(b for b in data.hero_builds if b.hero_id == knight_id)
        self.assertTrue(any(i.item_id == "test-sword" for i in build.equipment))

        # Unequip from knight
        self.actions.unequip(knight_id, EquipmentSlot.WEAPON)
        data = self.state.data
        self.assertEqual(len(data.backpack), 1)
        self.assertEqual(data.backpack[0].item_id, "test-sword")

    def test_buy_rune_via_action(self) -> None:
        # Buy starting war rune
        initial_gold = self.state.data.gold
        self.actions.buy_rune("war.00")
        data = self.state.data
        self.assertIn("war.00", data.unlocked_runes)
        self.assertLess(data.gold, initial_gold)


if __name__ == "__main__":
    unittest.main()
