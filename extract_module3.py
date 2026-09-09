import os
from pathlib import Path

def extract():
    with open("модуль3.md", "r", encoding="utf-8") as f:
        text = f.read()

    target_files = [
        "models/enemy.py",
        "engine/combat_manager.py",
        "gfx/__init__.py",
        "gfx/animations.py",
        "gfx/sprite_loader.py",
        "ui/__init__.py",
        "ui/battle_stage.py",
        "tests/test_module3.py",
        "main_battle.py"
    ]

    for target in target_files:
        header = f"`{target}`"
        pos = text.find(header)
        if pos == -1:
            print(f"[!] Не найден заголовок для: {target}")
            continue

        # Find code start
        code_start = text.find("```", pos)
        if code_start == -1:
            print(f"[!] Не найдено начало кода для: {target}")
            continue

        # Skip language line
        code_start = text.find("\n", code_start) + 1
        code_end = text.find("```", code_start)
        if code_end == -1:
            print(f"[!] Не найден конец кода для: {target}")
            continue

        code = text[code_start:code_end].strip()

        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as out:
            out.write(code + "\n")
        print(f"[OK] Создан: {target} ({len(code.splitlines())} строк)")

if __name__ == "__main__":
    extract()
