import os
import re
from pathlib import Path

def extract():
    with open("модуль1.md", "r", encoding="utf-8") as f:
        text = f.read()

    # Match pattern: ### `path/to/file` followed by ```language \n code ```
    pattern = re.compile(r'###\s+`([^`]+)`\s*\n+```[^\n]*\n(.*?)```', re.DOTALL)
    matches = pattern.findall(text)

    print(f"Найдено {len(matches)} файлов для извлечения:")
    for filepath_str, code in matches:
        target_path = Path(filepath_str.strip())
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write clean code
        with open(target_path, "w", encoding="utf-8") as out:
            out.write(code.rstrip() + "\n")
        print(f" -> Успешно создан: {target_path} ({len(code.splitlines())} строк)")

if __name__ == "__main__":
    extract()
