# Changelog: Desktop Abyss: Taskbar Chronicle

All notable changes to this project will be documented in this file.

## [v1.2.0] - 2026-09-10
### Added
- **Module 7 (Visual Combat, Biomes & Act Loot)**:
  - **4 Procedural Multilayer Parallax Biomes**:
    - *Fallen Catacombs (Crypts)*: gothic pointed arches, stone wall fissures, ancient gravestones with crosses, hanging chains, and braziers with flickering green soulfire.
    - *Corrupted Thicket (Forest)*: twisted gnarled trees, winding roots, glowing turquoise fungal clusters, and floating bioluminescent spores.
    - *Ash Caldera (Caldera)*: jagged obsidian cliffs, molten lava veins, bubbling volcanic glow, rising embers, and ash flurries.
    - *Abyss Citadel (Citadel)*: monumental cathedral stained-glass windows glowing with void light, floating monoliths, eldritch summoning circles with glowing runes.
  - **Atmospheric Floor Effects**: creeping layered ground fog with radial gradient transparency in Crypts, floating embers in Caldera, spores in Forest.
  - **Multilayer Runic Energy Dome**: pulsing shield perimeter, inner radial glow, rotating rune glyphs (`ᚨ ᚱ ᛟ`), and impact ripples upon absorbing damage.
  - **Smart Hero Formation**: tank vanguard (Knight/Paladin at x=155..186), flank skirmisher (Assassin at x=135..169), ranged artillery (Ranger at x=105), and deep backline spellcasters (Pyromancer/Necromancer at x=75..78).
  - **Real-Time Combat VFX & Projectiles**:
    - Ranger arrows with flight trails.
    - Pyromancer fireballs with flaming tail particles.
    - Necromancer bone spears and soul skulls.
    - Paladin holy light columns (`smite`).
    - Curved blade swoosh slash trails for melee attacks.
    - Golden spark bursts on critical hits and azure rune shields on blocks.
  - **Rich Loot Explosion & Loot Orbs**:
    - Slain elites (60% drop chance) and bosses (100% guaranteed 2–4 items) launch glowing loot orbs arcing across the battlefield.
    - Rarity-colored item burst on landing with animated top-right loot notification banner (`[✦ Легендарный: Погребальный Эспадон Тлена]`).
  - **40 Equipment Archetypes & 48 Act Affixes**:
    - Weapons: Greatswords, Falchions, Daggers, Stilettos, Twin Blades, Archmage Staves, Wands, Soul Scythes, Willow Bows, Crossbows, War Hammers, Rosewood Maces, Flails.
    - Offhands: Targes, Tower Shields, Bucklers, Grimoires, Ancestor Skulls, Storm Orbs, Quivers, Void Arrows.
    - Armors: Heavy Plate, Leather Garb, Mystic Robes with distinct visual silhouettes and archetype icons.
    - Act-specific affixes with Russian gender inflections.
  - **Save Integrity**:
    - `reward_claims` journal tracking wave-enemy drop claims to prevent duplicate loot abuse upon reloads.
    - Schema version upgraded to v6 with full backward compatibility for v1–v5.

## [v1.1.0] - 2026-09-09
### Added
- **Module 5 (Compact Desktop Widget & Procedural Pixel Art)**:
  - Redesigned form factor into an authentic desktop battle widget (540×168 logical pixels) sitting on the taskbar with pin-on-top and minimize support.
  - Single-drawer architecture (`PanelDrawer`) opening above the widget for HERO, STASH, CUBE, and RUNES panels.
  - Procedural 32×32 pixel-art sprite generator (`gfx/sprite_loader.py`) for all 6 hero classes, weapons, shields, and bestiary monsters (bat, spider, archon, fire lord).
  - Procedural pixel-art item icons and rich dark Gothic tooltips (`ui/common.py`) with rarity glows, affix descriptions, slot indicators, and flavor lore.
  - Stat point distribution system with `+` buttons and reactive free/earned point calculation.
  - Redesigned compact `StashPanel` with auto-sorting and equipment slot filtering.

- **Module 6 (Detailed Stats & Full Combat Math)**:
  - Full implementation of all 43 character attributes across Attack (21), Defense (12), and Utility (10) matching *Taskbar Hero*.
  - Comprehensive mathematical formulas in `models/stats.py` and `models/hero.py` factoring in class affinities, primary attributes, gear affixes, passive runes, and point allocations.
  - Combat engine integration in `engine/combat_manager.py`: Attack Speed interval scaling, Cooldown Reduction (CDR), Block Chance (60% physical mitigation), Dodge Chance, HP Regen/sec during combat, HP Per Hit, HP Per Kill, Life Leech %, elemental damage and individual resistances (Fire, Cold, Lightning, Chaos), and Exp Gain multiplier.
  - Authentic Gothic modal window `DetailedStatsWindow` (`ui/detailed_stats_window.py`) with character background silhouette, scrollable categories, and real-time stat synchronization.
  - Save schema version updated to v5 with seamless migration support for v1–v4 saves.
  - 31 new unit tests in `tests/test_detailed_stats.py`; 100 out of 100 unit tests passing.

## [v1.0.0] - 2026-09-09
### Added
- **Module 1 (Core Engine & Offline Progression)**:
  - `config.py` with Gothic color palette, storage paths, and balance constants.
  - `engine/state.py` with thread-safe `GameState` singleton, reactive PySide6 signals.
  - `engine/save_manager.py` with atomic JSON persistence via `QSaveFile`.
  - `engine/offline_manager.py` for mathematical idle progression (2 to 12-hour offline caps, 60-100% efficiency, auto-selling stash overflows).
  - 12 comprehensive unit tests for offline math.

- **Module 2 (Models, Runes Tree, Synthesis Cube)**:
  - 6 playable character classes: Knight, Assassin, Pyromancer, Ranger, Necromancer, Templar with primary and secondary attribute formulas.
  - 10 equipment slots with 6 rarity tiers (Common to Mythic) and procedural affix generation.
  - Sprawling constellation passive tree (`engine/runes_tree.py`) with 5 sectors (War, Ether, Vitality, Greed, Chronomancy) and exponential gold scaling.
  - Transmutation cube (`engine/cube_synth.py`) with tier synthesis probabilities and auto-fill.
  - 27 unit tests for equipment, cube synthesis, and runes.

- **Module 3 (Bestiary & Combat Manager)**:
  - 4-act enemy bestiary (`models/enemy.py`): Crypts, Forest, Caldera, Citadel with normal, elite (affixes), and boss waves.
  - Real-time squad combat engine (`engine/combat_manager.py`) with party barrier, class auto-skills, 180ms i-frames.
  - Animation FSM (`gfx/animations.py`) and procedural pixel fallback renderers (`gfx/sprite_loader.py`).
  - Standalone battle viewport (`ui/battle_stage.py`) with floating damage text, boss rage timers, and wave counters.
  - 27 unit tests for combat simulation and damage calculations.

- **Module 4 (Gothic Interface & Panels)**:
  - Custom Gothic window frame (`ui/gothic_frame.py`) with demonic crests, rune borders, and smooth dragging.
  - Full modular layout (`ui/main_window.py`): STASH, HERO, CUBE, and RUNES interactive panels.
  - Item management controller (`ui/actions.py`) supporting transfers, equipment, synthesis, and rune purchases.
  - Compact taskbar mode and window pin-on-top functionality.
  - 3 unit tests for UI actions; all 69 tests passing with 100% success.
