"""Import the MIT-licensed rwanda-locations/locations.json hierarchy into SQLite."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import Cell, District, Province, Sector, Village  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "rwanda-locations" / "locations.json")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = json.loads(args.source.read_text(encoding="utf-8"))
    required = {"province_code", "province_name", "district_code", "district_name", "sector_code", "sector_name", "cell_code", "cell_name", "village_code", "village_name"}
    if not isinstance(rows, list) or not rows or any(not required.issubset(row) for row in rows):
        raise SystemExit("Source is not a valid Rwanda village hierarchy dataset")

    provinces = {(int(row["province_code"]), str(row["province_name"]).strip()) for row in rows}
    districts = {(int(row["district_code"]), int(row["province_code"]), str(row["district_name"]).strip()) for row in rows}
    sectors = {(str(row["sector_code"]), int(row["district_code"]), str(row["sector_name"]).strip()) for row in rows}
    cells = {(int(row["cell_code"]), str(row["sector_code"]), str(row["cell_name"]).strip()) for row in rows}
    villages = {(int(row["village_code"]), int(row["cell_code"]), str(row["village_name"]).strip()) for row in rows}

    if len(provinces) != 5 or len(districts) != 30 or len(villages) != len(rows):
        raise SystemExit("Dataset coverage or unique codes failed validation")

    with SessionLocal.begin() as db:
        existing = db.scalar(select(func.count()).select_from(Village))
        if existing and not args.replace:
            print(f"Location data already loaded ({existing} villages); use --replace to refresh")
            return
        if args.replace:
            for model in (Village, Cell, Sector, District, Province):
                db.execute(delete(model))
        db.add_all(Province(code=code, name=name) for code, name in sorted(provinces))
        db.flush()
        db.add_all(District(code=code, province_code=parent, name=name) for code, parent, name in sorted(districts))
        db.flush()
        db.add_all(Sector(code=code, district_code=parent, name=name) for code, parent, name in sorted(sectors))
        db.flush()
        db.add_all(Cell(code=code, sector_code=parent, name=name) for code, parent, name in sorted(cells))
        db.flush()
        db.add_all(Village(code=code, cell_code=parent, name=name) for code, parent, name in sorted(villages))
    print(f"Imported {len(provinces)} provinces, {len(districts)} districts, {len(sectors)} sectors, {len(cells)} cells and {len(villages)} villages")


if __name__ == "__main__":
    main()
