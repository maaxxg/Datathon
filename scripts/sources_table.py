"""Print the README sources table (Markdown) from backend/app/layers.yaml.

Usage: backend/.venv/bin/python scripts/sources_table.py
Paste the output into README.md section "Izvori podataka i licence".
"""
from pathlib import Path

import yaml

LAYERS = Path(__file__).resolve().parents[1] / "backend" / "app" / "layers.yaml"


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    layers = yaml.safe_load(LAYERS.read_text(encoding="utf-8"))["layers"]
    print("| Ključ | Naziv | Izdavač | Licenca | Poveznica |")
    print("|---|---|---|---|---|")
    for key, item in layers.items():
        print(f"| `{key}` | {cell(item['title'])} | {cell(item['publisher'])} | "
              f"{cell(item['licence'])} | {cell(item['url'])} |")


if __name__ == "__main__":
    main()
