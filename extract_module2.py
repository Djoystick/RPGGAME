import os
import re
from pathlib import Path

def extract():
    with open("модуль2.md", "r", encoding="utf-8") as f:
        text = f.read()

    # The 7 primary new files in Module 2
    target_files = [
        "models/__init__.py",
        "models/stats.py",
        "models/item.py",
        "models/hero.py",
        "engine/runes_tree.py",
        "engine/cube_synth.py",
        "tests/test_module2.py"
    ]

    for target in target_files:
        # Look for ## `target` or ### `target`
        header = f"`{target}`"
        pos = text.find(header)
        if pos == -1:
            print(f"[!] Не найден заголовок для: {target}")
            continue

        # Find the next ```python or ```text
        code_start = text.find("```", pos)
        if code_start == -1:
            print(f"[!] Не найдено начало кода для: {target}")
            continue

        # Skip the ```python line
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
