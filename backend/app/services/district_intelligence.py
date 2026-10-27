from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from statistics import median

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA = json.loads((DATA_DIR / "nisr_district_intelligence.json").read_text(encoding="utf-8"))
BOUNDARIES = json.loads((DATA_DIR / "rwanda_district_boundaries_2022.geojson").read_text(encoding="utf-8"))
RECORDS: list[dict] = DATA["records"]
INDICATORS: dict[str, dict] = DATA["indicators"]
MIN_PRIVATE_FARMS = 5
MIN_PRIVATE_OWNERS = 3


def options() -> dict:
    provinces = sorted({r["province"] for r in RECORDS if r["province"]})
    districts = sorted({(r["province"], r["district"]) for r in RECORDS if r["district"]})
    crops = sorted({r["crop"] for r in RECORDS if r["crop"]})
    return {
        "years": sorted({r["year"] for r in RECORDS}, reverse=True),
        "seasons": [{"value": "A", "label": "Season A"}, {"value": "B", "label": "Season B"}],
        "provinces": provinces,
        "districts": [{"province": province, "district": district} for province, district in districts],
        "crops": crops,
        "indicators": [{"value": key, **value} for key, value in INDICATORS.items()],
        "dataset_version": DATA["dataset_version"],
        "coverage": {"districts": 30, "years": [2024, 2025, 2026], "seasons": ["A", "B"]},
    }


def _matching(*, year=None, season=None, province=None, district=None, crop=None, indicator=None, level=None) -> list[dict]:
    category = INDICATORS.get(indicator or "", {}).get("category")
    rows = []
    for row in RECORDS:
        if year is not None and row["year"] != year:
            continue
        if season and row["season"] != season:
            continue
        if province and row["province"] != province:
            continue
        if district and row["district"] != district:
            continue
        if indicator and row["indicator"] != indicator:
            continue
        if level and row["geography_level"] != level:
            continue
        if category == "crop" and crop and row["crop"] != crop:
            continue
        rows.append(row)
    return rows


def _geography_level(province: str | None, district: str | None) -> str:
    return "district" if district or province else "national"


def dashboard(*, year: int, season: str, province: str | None, district: str | None, crop: str | None, indicator: str) -> dict:
    if indicator not in INDICATORS:
        raise ValueError("Unknown agricultural indicator")
    meta = INDICATORS[indicator]
    if meta["category"] != "crop":
        crop = None
    level = _geography_level(province, district)
    current = _matching(year=year, season=season, province=province, district=district, crop=crop, indicator=indicator, level=level)

    if level == "national":
        trend_rows = _matching(crop=crop, indicator=indicator, level="national")
        map_rows = _matching(year=year, season=season, crop=crop, indicator=indicator, level="district")
    else:
        trend_rows = _matching(province=province, district=district, crop=crop, indicator=indicator, level="district")
        map_rows = _matching(year=year, season=season, province=province, crop=crop, indicator=indicator, level="district")

    trend = sorted(
        [{"period": f'{r["year"]} {r["season"]}', "year": r["year"], "season": r["season"], "value": r["value"], "unit": r["unit"]} for r in trend_rows],
        key=lambda row: (row["year"], row["season"]),
    )
    if level == "national":
        comparison_base = _matching(year=year, season=season, indicator=indicator, level="national")
    else:
        comparison_base = _matching(year=year, season=season, province=province, district=district, indicator=indicator, level="district")
    crop_comparison = []
    if meta["category"] == "crop":
        crop_comparison = sorted(
            [{"crop": r["crop"], "value": r["value"], "unit": r["unit"]} for r in comparison_base if r["crop"]],
            key=lambda row: row["value"], reverse=True,
        )[:12]

    seasonal = []
    for value in ("A", "B"):
        matches = _matching(year=year, season=value, province=province, district=district, crop=crop, indicator=indicator, level=level)
        if matches:
            seasonal.append({"season": value, "value": matches[0]["value"], "unit": matches[0]["unit"]})

    current_value = current[0]["value"] if len(current) == 1 else (round(median(r["value"] for r in current), 3) if current else None)
    previous = [row for row in trend if (row["year"], row["season"]) < (year, season)]
    previous_row = previous[-1] if previous else None
    change = None
    if current_value is not None and previous_row and previous_row["value"] != 0:
        change = {
            "from_period": previous_row["period"],
            "absolute": round(current_value - previous_row["value"], 3),
            "percent": round((current_value - previous_row["value"]) / previous_row["value"] * 100, 1),
        }

    map_values = [{"district": r["district"], "province": r["province"], "value": r["value"], "unit": r["unit"]} for r in map_rows]
    all_districts = {f["properties"]["district"] for f in BOUNDARIES["features"]}
    present = {row["district"] for row in map_values}
    missing = sorted(all_districts - present)
    source_seasons = sorted({r["source_season"] for r in current + trend_rows + map_rows})
    sources = [{"season": key, **DATA["sources"][key]} for key in source_seasons]
    observation_period = "; ".join(f'Season {s["season"]}: {s["observation_period"]}' for s in sources)

    return {
        "selection": {"year": year, "season": season, "province": province, "district": district, "crop": crop, "indicator": indicator},
        "indicator": {"value": indicator, **meta},
        "summary": {
            "value": current_value, "unit": meta["unit"], "records": len(current),
            "geography": district or province or "Rwanda", "change": change,
        },
        "trend": trend, "crop_comparison": crop_comparison, "seasonal_comparison": seasonal,
        "map": {"values": map_values, "available": bool(map_values), "districts_with_data": len(present), "districts_total": 30},
        "coverage": {
            "dataset_version": DATA["dataset_version"], "observation_period": observation_period,
            "district_records": len(map_values), "missing_districts": missing,
            "note": "District crop and practice tables are available for 2026 Seasons A and B. Earlier comparison years in this curated release are national crop totals only.",
        },
        "sources": sources,
        "methodology": DATA["curation_method"],
        "sampling_notes": [source["sample_note"] for source in sources],
        "boundary_source": DATA["boundary_source"],
        "private_farm_aggregate": {
            "included": False, "status": "not_available_no_opt_in",
            "message": "Farm and sensor observations are not mixed with official NISR statistics. No explicit analytics opt-in records are available.",
            "disclosure_rule": f"Any future private district aggregate must include at least {MIN_PRIVATE_FARMS} farms from at least {MIN_PRIVATE_OWNERS} owners; otherwise it is suppressed.",
        },
    }


def boundaries() -> dict:
    return BOUNDARIES


def export_rows(**filters) -> list[dict]:
    indicator = filters["indicator"]
    level = _geography_level(filters.get("province"), filters.get("district"))
    return _matching(level=level, **filters)


def csv_export(**filters) -> bytes:
    rows = export_rows(**filters)
    stream = io.StringIO(newline="")
    columns = ["year", "season", "province", "district", "geography_level", "crop", "indicator", "value", "unit", "source_table"]
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def pdf_export(**filters) -> bytes:
    report = dashboard(**filters)
    rows = export_rows(**filters)
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title="Agrinox — District Agricultural Intelligence")
    styles = getSampleStyleSheet()
    story = [Paragraph("Agrinox — District Agricultural Intelligence", styles["Title"]), Spacer(1, 4 * mm)]
    selection = report["selection"]
    story.append(Paragraph(f"Official NISR aggregate export · {selection['year']} Season {selection['season']} · {report['indicator']['label']} · {selection.get('district') or selection.get('province') or 'Rwanda'}", styles["Heading2"]))
    story.append(Paragraph(f"Source period: {report['coverage']['observation_period'] or 'No matching observation'}", styles["BodyText"]))
    story.append(Paragraph(f"Method: {report['methodology']}", styles["BodyText"]))
    story.append(Spacer(1, 4 * mm))
    table_data = [["Year", "Season", "Province", "District", "Crop", "Indicator", "Value", "Unit"]]
    for row in rows[:250]:
        table_data.append([row["year"], row["season"], row.get("province") or "Rwanda", row.get("district") or "—", row.get("crop") or "—", INDICATORS[row["indicator"]]["label"], f'{row["value"]:,.3f}', row["unit"]])
    if len(table_data) == 1:
        table_data.append(["—", "—", "—", "—", "—", "No published aggregate for this filter", "—", "—"])
    table = Table(table_data, repeatRows=1, colWidths=[16*mm, 17*mm, 34*mm, 30*mm, 32*mm, 48*mm, 25*mm, 30*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#284d35")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#aab5ad")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f2")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Private farm or sensor observations are excluded from this export.", styles["BodyText"]))
    document.build(story)
    return output.getvalue()
