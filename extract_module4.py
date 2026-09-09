from pathlib import Path

def extract():
    with open("модуль4.md", "r", encoding="utf-8") as f:
        lines = f.readlines()

    slices = {
        'ui/panels/__init__.py': (130, 130),
        'ui/common.py': (134, 401),
        'ui/actions.py': (406, 624),
        'ui/gothic_frame.py': (631, 820),
        'ui/panels/hero_panel.py': (827, 1122),
        'ui/panels/stash_panel.py': (1129, 1229),
        'ui/panels/cube_panel.py': (1236, 1473),
        'ui/panels/runes_panel.py': (1480, 1748),
        'ui/main_window.py': (1769, 2098),
        'main.py': (2103, 2193),
    }

    for fname, (s, e) in slices.items():
        code = "".join(lines[s-1:e]).strip() + "\n"
        target_path = Path(fname)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as out:
            out.write(code)
        print(f"[OK] Сохранен {fname} ({len(code.splitlines())} строк)")

if __name__ == "__main__":
    extract()
