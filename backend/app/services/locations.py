from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Cell, District, Province, Sector, Village


def options(db: Session, model, parent_field: str | None = None, parent_code=None) -> list[dict]:
    statement = select(model)
    if parent_field is not None:
        statement = statement.where(getattr(model, parent_field) == parent_code)
    records = db.scalars(statement.order_by(model.name)).all()
    return [{"code": item.code, "name": item.name} for item in records]


def validate_hierarchy(db: Session, *, province_code: int, district_code: int, sector_code: str, cell_code: int, village_code: int) -> dict:
    province = db.get(Province, province_code)
    district = db.get(District, district_code)
    sector = db.get(Sector, sector_code)
    cell = db.get(Cell, cell_code)
    village = db.get(Village, village_code)
    valid = (
        province and district and sector and cell and village
        and district.province_code == province.code
        and sector.district_code == district.code
        and cell.sector_code == sector.code
        and village.cell_code == cell.code
    )
    if not valid:
        raise HTTPException(status_code=422, detail="The selected Rwanda administrative hierarchy is invalid or incomplete")
    return {"province": province.name, "district": district.name, "sector": sector.name, "cell": cell.name, "village": village.name}
