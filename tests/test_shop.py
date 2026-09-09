from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from engine.combat_manager import CombatManager
from engine.save_manager import SaveManager
from engine.shop import (
    MERCHANT_MARKUP,
    MerchantError,
    buy_data,
    compute_sell_gold,
    junk_ids,
    merchant_level,
    merchant_price,
    roll_merchant_stock,
    sell_rarity_ids,
)
from engine.state import GameData, GameState
from models.item import EquipmentSlot, Item, Rarity
from ui.actions import UiActions

APP = QCoreApplication.instance() or QCoreApplication([])


def make_item(item_id: str, *, rarity=Rarity.COMMON, value=100) -> Item:
    return Item(
        item_id=item_id,
        rarity=rarity,
        source_wave=1,
        sell_value=value,
        slot=EquipmentSlot.WEAPON,
        level=5,
    )


class ShopEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        # Класс/датафрейм уровня волны 1 и золота на 100k.
        self.data = GameData(gold=100_000)

    def test_compute_sell_gold_base_and_bonus(self) -> None:
        items = (make_item("a", value=100), make_item("b", value=250))
        self.assertEqual(compute_sell_gold(items), 350)
        self.assertEqual(compute_sell_gold(items, 0.10), 385)

    def test_sell_rarity_ids_removes_and_credits(self) -> None:
        data = GameData(
            gold=0,
            stash=(make_item("s1", value=100), make_item("s2", value=200)),
            backpack=(make_item("b1", value=50),),
        )
        updated = sell_rarity_ids(data, ("s1", "b1"))
        self.assertEqual(updated.gold, 150)
        self.assertEqual([i.item_id for i in updated.stash], ["s2"])
        self.assertEqual(list(updated.backpack), [])

    def test_sell_rejects_unknown_id(self) -> None:
        data = GameData(stash=(make_item("s1"),))
        with self.assertRaises(MerchantError):
            sell_rarity_ids(data, ("s1", "ghost"))

    def test_sell_respects_equipped_items_are_not_sellable(self) -> None:
        # Предмет на герое не входит ни в рюкзак, ни в тайник -> ошибка.
        data = GameData(stash=())
        with self.assertRaises(MerchantError):
            sell_rarity_ids(data, ("equipped-item",))

    def test_junk_ids_filters_rarity(self) -> None:
        data = GameData(
            backpack=(
                make_item("c", rarity=Rarity.COMMON),
                make_item("u", rarity=Rarity.UNCOMMON),
                make_item("r", rarity=Rarity.RARE),
            )
        )
        self.assertEqual(set(junk_ids(data)), {"c", "u"})

    def test_merchant_level_tracks_party(self) -> None:
        data = GameData()
        self.assertEqual(merchant_level(data), 1)

    def test_roll_stock_deterministic_and_valid(self) -> None:
        rng = random.Random(7)
        stock = roll_merchant_stock(self.data, rng=rng)
        again = roll_merchant_stock(self.data, rng=random.Random(7))
        self.assertEqual(len(stock), 6)
        # Детерминизм при одном сиде.
        self.assertEqual(
            [i.item_id for i in stock],
            [i.item_id for i in again],
        )
        for item in stock:
            self.assertGreaterEqual(item.level, 1)
            self.assertNotEqual(item.rarity, Rarity.MYTHIC)

    def test_merchant_price_is_marked_up(self) -> None:
        item = make_item("x", value=400)
        self.assertEqual(merchant_price(item), round(400 * MERCHANT_MARKUP))

    def test_buy_fails_without_gold(self) -> None:
        data = GameData(gold=0)
        offer = make_item("o1", value=500)
        with self.assertRaises(MerchantError):
            buy_data(data, offer)

    def test_buy_places_in_backpack_then_stash(self) -> None:
        item = make_item("o", value=100)
        data = buy_data(self.data, item)
        self.assertEqual(data.gold, 100_000 - round(100 * MERCHANT_MARKUP))
        self.assertEqual(len(data.backpack), 1)
        self.assertEqual(data.backpack[0].slot, item.slot)

    def test_buy_into_full_backpack_uses_stash(self) -> None:
        import config as C

        full = tuple(make_item(f"k{i}") for i in range(C.DEFAULT_BACKPACK_CAPACITY))
        data = GameData(gold=1_000_000, backpack=full)
        data = buy_data(data, make_item("o", value=50))
        self.assertEqual(len(data.backpack), C.DEFAULT_BACKPACK_CAPACITY)
        self.assertEqual(len(data.stash), 1)

    def test_buy_rejects_when_everything_full(self) -> None:
        import config as C

        full_bp = tuple(make_item(f"b{i}") for i in range(C.DEFAULT_BACKPACK_CAPACITY))
        full_st = tuple(make_item(f"s{i}") for i in range(C.DEFAULT_STASH_CAPACITY))
        data = GameData(gold=1_000_000, backpack=full_bp, stash=full_st)
        with self.assertRaises(MerchantError):
            buy_data(data, make_item("o", value=50))


class ShopActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = Path(self.temp_dir.name) / "save.json"
        self.saves = SaveManager(self.save_path)
        self.state = GameState.instance()

        initial = GameData(
            gold=1_000_000,
            stash=(
                make_item("leg", rarity=Rarity.LEGENDARY, value=900),
                make_item("junk", rarity=Rarity.COMMON, value=10),
            ),
            backpack=(make_item("bp", rarity=Rarity.RARE, value=300),),
        )
        self.saves.write(initial)
        self.state.load(initial)
        combat = CombatManager(self.state)
        self.actions = UiActions(self.state, self.saves, combat)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sell_items_action(self) -> None:
        gold = self.actions.sell_items(("junk",))
        self.assertEqual(gold, 10)
        self.assertEqual(self.state.data.gold, 1_000_010)

    def test_sell_junk_auto(self) -> None:
        gained = self.actions.sell_junk()
        self.assertEqual(gained, 10)
        ids = {i.item_id for i in self.state.data.stash}
        self.assertIn("leg", ids)
        self.assertNotIn("junk", ids)

    def test_buy_offer_action(self) -> None:
        stock = self.actions.roll_stock(count=1)
        offer = stock[0]
        price = merchant_price(offer)
        before = self.state.data.gold
        self.actions.buy_offer(offer)
        data = self.state.data
        self.assertEqual(data.gold, before - price)
        self.assertIn(offer.item_id, {i.item_id for i in data.backpack})


if __name__ == "__main__":
    unittest.main()
