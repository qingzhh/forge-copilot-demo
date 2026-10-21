from __future__ import annotations

import csv
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .services import now_iso, safe_float


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


# The original factory workbook uses Chinese sheet names.  The demo accepts
# English sheet names first and falls back to the Chinese originals, so both
# the sanitized demo workbook and a legacy workbook import correctly.
SHEET_ALIASES: dict[str, list[str]] = {
    "Base Plates": ["Base Plates", "底板厚度"],
    "Die Seats": ["Die Seats", "模座尺寸"],
    "Blocks": ["Blocks", "拼块尺寸"],
    "Blade Types": ["Blade Types", "叶片类型"],
    "Calculation": ["Calculation", "计算"],
}


def excel_date_to_iso(value: Any) -> str:
    if isinstance(value, (int, float)):
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=float(value))).strftime("%Y-%m-%d")
    return str(value or "")


class XlsxReader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.archive = zipfile.ZipFile(path)
        self.shared_strings = self._load_shared_strings()
        self.sheet_targets = self._load_sheet_targets()

    def close(self) -> None:
        self.archive.close()

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.archive.namelist():
            return []
        root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        strings: list[str] = []
        for si in root.findall("a:si", NS):
            texts = [node.text or "" for node in si.iterfind(".//a:t", NS)]
            strings.append("".join(texts))
        return strings

    def _load_sheet_targets(self) -> dict[str, str]:
        wb = ET.fromstring(self.archive.read("xl/workbook.xml"))
        rels = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        result: dict[str, str] = {}
        for sheet in wb.find("a:sheets", NS):
            name = sheet.attrib["name"]
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            result[name] = "xl/" + rel_map[rid]
        return result

    def first_sheet(self, names: list[str]) -> str | None:
        for name in names:
            if name in self.sheet_targets:
                return name
        return None

    def iter_rows_any(self, names: list[str], start_row: int = 1) -> list[tuple[int, dict[str, Any]]]:
        name = self.first_sheet(names)
        if name is None:
            return []
        return self.iter_rows(name, start_row=start_row)

    def iter_rows(self, sheet_name: str, start_row: int = 1) -> list[tuple[int, dict[str, Any]]]:
        target = self.sheet_targets[sheet_name]
        root = ET.fromstring(self.archive.read(target))
        sheet_data = root.find("a:sheetData", NS)
        rows: list[tuple[int, dict[str, Any]]] = []
        if sheet_data is None:
            return rows
        for row in sheet_data.findall("a:row", NS):
            row_num = int(row.attrib["r"])
            if row_num < start_row:
                continue
            values: dict[str, Any] = {}
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                values[col] = self._parse_cell(cell)
            rows.append((row_num, values))
        return rows

    def _parse_cell(self, cell: ET.Element) -> Any:
        cell_type = cell.attrib.get("t")
        value_node = cell.find("a:v", NS)
        if cell_type == "inlineStr":
            texts = [node.text or "" for node in cell.iterfind(".//a:t", NS)]
            return "".join(texts)
        if value_node is None:
            return ""
        raw = value_node.text or ""
        if cell_type == "s":
            return self.shared_strings[int(raw)]
        if cell_type == "str":
            return raw
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw


def import_workbook(conn: sqlite3.Connection, workbook_path: Path) -> dict[str, Any]:
    reader = XlsxReader(workbook_path)
    try:
        summary = {"master_rows": 0, "history_rows": 0, "feedback_rows": 0, "skipped_rows": 0}
        _import_base_plates(conn, reader, summary)
        _import_die_seats(conn, reader, summary)
        _import_blocks(conn, reader, summary)
        _import_rules(conn, reader, summary)
        _import_product_processes(conn, reader, summary)
        calc_sheet = reader.first_sheet(SHEET_ALIASES["Calculation"])
        if calc_sheet is not None:
            _import_history_sheet(conn, reader, calc_sheet, "1", summary)
        conn.commit()
        _log_import(conn, workbook_path, summary)
        conn.commit()
        return summary
    finally:
        reader.close()


def import_analysis_csv(conn: sqlite3.Connection, csv_path: Path) -> dict[str, Any]:
    summary = {"history_rows": 0, "feedback_rows": 0, "skipped_rows": 0}
    now = now_iso()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            job_no = str(row.get("job_no", "")).strip()
            if not job_no:
                summary["skipped_rows"] += 1
                continue
            exists = conn.execute("SELECT id FROM job_install WHERE job_no = ?", (job_no,)).fetchone()
            if exists:
                summary["skipped_rows"] += 1
                continue

            conn.execute(
                """
                INSERT INTO job_install (
                  job_no, job_status, job_date, shift_name, operator_name,
                  product_process_name, die_no, die_version, die_seat_no, block_no,
                  pass_flag, remark, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_no,
                    row.get("job_status") or "Imported History",
                    row.get("job_date") or "",
                    row.get("shift_name") or "Imported",
                    row.get("operator_name") or "CSV Import",
                    row.get("product_process_name") or "",
                    row.get("die_no") or "",
                    row.get("die_version") or "v1.00",
                    row.get("die_seat_no") or "",
                    row.get("block_no") or "",
                    1 if str(row.get("is_pass", "")).strip() == "1" else None,
                    f"CSV import from {csv_path.name}",
                    now,
                    now,
                ),
            )
            job_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                INSERT INTO job_install_input (
                  job_id, base_plate_no_1, base_plate_no_2, base_plate_no_3, base_plate_no_4, base_plate_no_5,
                  upper_x_ref, upper_y_ref, lower_x_ref, lower_y_ref, lower_die_actual_height,
                  target_thickness, upper_preheat_temp, lower_preheat_temp, billet_temp,
                  lubrication_type, blade_direction, blade_size_grade, crown_rotation_angle_grade,
                  energy_grade, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    row.get("base_plate_no_1") or None,
                    row.get("base_plate_no_2") or None,
                    row.get("base_plate_no_3") or None,
                    row.get("base_plate_no_4") or None,
                    row.get("base_plate_no_5") or None,
                    safe_float(row.get("upper_x_ref")),
                    safe_float(row.get("upper_y_ref")),
                    safe_float(row.get("lower_x_ref")),
                    safe_float(row.get("lower_y_ref")),
                    safe_float(row.get("lower_die_actual_height")),
                    safe_float(row.get("target_thickness")),
                    row.get("blade_direction") or None,
                    row.get("blade_size_grade") or None,
                    row.get("crown_rotation_angle_grade") or None,
                    row.get("energy_grade") or None,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO job_calc_snapshot (
                  job_id, calc_version, base_plate_total, die_seat_actual_height,
                  die_seat_height_delta, base_template_delta, theory_template_thickness_base,
                  theory_lower_x_pad_base, theory_lower_y_pad_base, history_template_correction,
                  history_x_correction, history_y_correction, recommend_template_thickness,
                  recommend_lower_x_pad, recommend_lower_y_pad, similar_case_count,
                  recommend_confidence, created_at
                ) VALUES (?, 'csv_import', ?, NULL, NULL, NULL, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0, 'low', ?)
                """,
                (
                    job_id,
                    safe_float(row.get("base_plate_total")),
                    safe_float(row.get("theory_template_thickness_base")),
                    safe_float(row.get("theory_lower_x_pad_base")),
                    safe_float(row.get("theory_lower_y_pad_base")),
                    safe_float(row.get("recommend_template_thickness")),
                    safe_float(row.get("recommend_lower_x_pad")),
                    safe_float(row.get("recommend_lower_y_pad")),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO job_first_piece_feedback (
                  job_id, actual_template_thickness, actual_al_block_thickness, actual_thickness,
                  actual_lower_x_pad_root, actual_lower_x_pad_tip, actual_lower_y_pad,
                  measured_x_offset_root, measured_x_offset_tip, measured_y_offset,
                  first_piece_thickness_delta, is_pass, defect_type, feedback_remark,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    safe_float(row.get("actual_template_thickness")),
                    safe_float(row.get("actual_al_block_thickness")),
                    safe_float(row.get("actual_thickness")),
                    safe_float(row.get("actual_lower_x_pad_root")),
                    safe_float(row.get("actual_lower_x_pad_tip")),
                    safe_float(row.get("actual_lower_y_pad")),
                    safe_float(row.get("measured_x_offset_root")),
                    safe_float(row.get("measured_x_offset_tip")),
                    safe_float(row.get("measured_y_offset")),
                    safe_float(row.get("first_piece_thickness_delta")),
                    1 if str(row.get("is_pass", "")).strip() == "1" else 0,
                    row.get("defect_type") or None,
                    f"CSV import from {csv_path.name}",
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO job_sample_grade (
                  job_id, sample_grade, measure_quality_level, die_install_quality_level,
                  block_install_quality_level, guide_clearance_level, data_completeness_level,
                  grade_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'complete', ?, ?, ?)
                """,
                (
                    job_id,
                    row.get("sample_grade") or "A",
                    row.get("measure_quality_level") or "medium",
                    row.get("die_install_quality_level") or "good",
                    row.get("block_install_quality_level") or "good",
                    row.get("guide_clearance_level") or "good",
                    f"CSV import from {csv_path.name}",
                    now,
                    now,
                ),
            )
            summary["history_rows"] += 1
            summary["feedback_rows"] += 1

    conn.execute(
        """
        INSERT INTO sys_import_log (
          import_type, source_file, total_rows, success_rows, failed_rows, log_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "analysis_csv",
            str(csv_path),
            summary["history_rows"] + summary["skipped_rows"],
            summary["history_rows"],
            summary["skipped_rows"],
            str(summary),
            now,
        ),
    )
    conn.commit()
    return summary


def _import_base_plates(conn: sqlite3.Connection, reader: XlsxReader, summary: dict[str, Any]) -> None:
    now = now_iso()
    for _, row in reader.iter_rows_any(SHEET_ALIASES["Base Plates"], start_row=2):
        plate_no = str(row.get("A", "")).strip()
        if not plate_no:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO master_base_plate (
              id, plate_no, plate_thickness, plate_remark, is_active, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_base_plate WHERE plate_no = ?), NULL),
              ?, ?, ?, 1,
              COALESCE((SELECT created_at FROM master_base_plate WHERE plate_no = ?), ?),
              ?
            )
            """,
            (plate_no, plate_no, safe_float(row.get("B")), str(row.get("C", "")).strip() or None, plate_no, now, now),
        )
        summary["master_rows"] += 1


def _import_die_seats(conn: sqlite3.Connection, reader: XlsxReader, summary: dict[str, Any]) -> None:
    now = now_iso()
    last_seat_no = ""
    for _, row in reader.iter_rows_any(SHEET_ALIASES["Die Seats"], start_row=2):
        seat_no = str(row.get("A", "")).strip() or last_seat_no
        if not seat_no:
            continue
        last_seat_no = seat_no
        conn.execute(
            """
            INSERT OR REPLACE INTO master_die_seat (
              id, die_seat_no, theory_close_height, seat_position_name,
              seat_x_offset, seat_y_offset, base_template_700, guide_clearance_level,
              is_active, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_die_seat WHERE die_seat_no = ?), NULL),
              ?, ?, ?, 0, 0, ?, 'good', 1,
              COALESCE((SELECT created_at FROM master_die_seat WHERE die_seat_no = ?), ?),
              ?
            )
            """,
            (seat_no, seat_no, safe_float(row.get("B")), str(row.get("C", "")).strip() or None, safe_float(row.get("D")), seat_no, now, now),
        )
        summary["master_rows"] += 1


def _import_blocks(conn: sqlite3.Connection, reader: XlsxReader, summary: dict[str, Any]) -> None:
    now = now_iso()
    for _, row in reader.iter_rows_any(SHEET_ALIASES["Blocks"], start_row=4):
        block_no = str(row.get("A", "")).strip()
        if not block_no or block_no in ("标刻", "Marking"):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO master_block (
              id, block_no, block_size, theory_thickness, lower_x_base, lower_y_base,
              upper_x_base, upper_y_base, lower_block_plate_thickness, upper_block_plate_thickness,
              block_plate_delta, is_active, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_block WHERE block_no = ?), NULL),
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
              COALESCE((SELECT created_at FROM master_block WHERE block_no = ?), ?),
              ?
            )
            """,
            (
                block_no,
                block_no,
                str(row.get("C", "")).strip() or None,
                safe_float(row.get("D")),
                safe_float(row.get("O")),
                safe_float(row.get("Q")),
                safe_float(row.get("S")),
                safe_float(row.get("U")),
                safe_float(row.get("M")),
                safe_float(row.get("N")),
                safe_float(row.get("D")) - safe_float(row.get("M")) - safe_float(row.get("N")),
                block_no,
                now,
                now,
            ),
        )
        summary["master_rows"] += 1


def _import_rules(conn: sqlite3.Connection, reader: XlsxReader, summary: dict[str, Any]) -> None:
    now = now_iso()
    for _, row in reader.iter_rows_any(SHEET_ALIASES["Blade Types"], start_row=2):
        product_type = str(row.get("A", "")).strip()
        if product_type:
            conn.execute(
                """
                INSERT OR REPLACE INTO master_compensation_rule (
                  id, rule_type, rule_key, x_comp, y_comp, template_comp, remark, created_at, updated_at
                ) VALUES (
                  COALESCE((SELECT id FROM master_compensation_rule WHERE rule_type = 'product_type_x_comp' AND rule_key = ?), NULL),
                  'product_type_x_comp', ?, ?, 0, 0, NULL,
                  COALESCE((SELECT created_at FROM master_compensation_rule WHERE rule_type = 'product_type_x_comp' AND rule_key = ?), ?),
                  ?
                )
                """,
                (product_type, product_type, safe_float(row.get("B")), product_type, now, now),
            )
            summary["master_rows"] += 1
        prev_dir = str(row.get("D", "")).strip()
        if prev_dir and prev_dir != "/":
            conn.execute(
                """
                INSERT OR REPLACE INTO master_compensation_rule (
                  id, rule_type, rule_key, x_comp, y_comp, template_comp, remark, created_at, updated_at
                ) VALUES (
                  COALESCE((SELECT id FROM master_compensation_rule WHERE rule_type = 'prev_blade_dir_x_comp' AND rule_key = ?), NULL),
                  'prev_blade_dir_x_comp', ?, ?, 0, 0, NULL,
                  COALESCE((SELECT created_at FROM master_compensation_rule WHERE rule_type = 'prev_blade_dir_x_comp' AND rule_key = ?), ?),
                  ?
                )
                """,
                (prev_dir, prev_dir, safe_float(row.get("E")), prev_dir, now, now),
            )
            summary["master_rows"] += 1


def _import_product_processes(conn: sqlite3.Connection, reader: XlsxReader, summary: dict[str, Any]) -> None:
    now = now_iso()
    for _, row in reader.iter_rows("Sheet1", start_row=2):
        product_process_name = str(row.get("C", "")).strip()
        if not product_process_name:
            continue
        product_name = str(row.get("A", "")).strip()
        process_name = str(row.get("B", "")).strip()
        die_no = str(row.get("F", "")).strip()
        die_spec = str(row.get("W", "")).strip() or None
        conn.execute(
            """
            INSERT OR REPLACE INTO master_product_process (
              id, product_name, process_name, product_process_name,
              product_type, blade_direction, blade_size_grade, crown_rotation_angle_grade,
              energy_grade, target_thickness_default, is_active, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_product_process WHERE product_process_name = ?), NULL),
              ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, 1,
              COALESCE((SELECT created_at FROM master_product_process WHERE product_process_name = ?), ?),
              ?
            )
            """,
            (product_process_name, product_name, process_name, product_process_name, product_process_name, now, now),
        )
        if die_no:
            conn.execute(
                """
                INSERT OR IGNORE INTO master_die_version (
                  die_no, die_name, die_spec, die_version, die_status,
                  use_count_bucket, total_hit_count, after_repair_hit_count, is_after_regrind_first_use, remark, created_at, updated_at
                ) VALUES (?, ?, ?, 'v1.00', NULL, NULL, 0, 0, 0, NULL, ?, ?)
                """,
                (die_no, None, die_spec, now, now),
            )
        summary["master_rows"] += 1


def _import_history_sheet(conn: sqlite3.Connection, reader: XlsxReader, sheet_name: str, sheet_alias: str, summary: dict[str, Any]) -> None:
    now = now_iso()
    for row_num, row in reader.iter_rows(sheet_name, start_row=3):
        product_process_name = str(row.get("B", "")).strip()
        die_no = str(row.get("H", "")).strip()
        die_seat_no = str(row.get("N", "")).strip()
        block_no = str(row.get("X", "")).strip()
        if not product_process_name or not die_no or not die_seat_no or not block_no:
            summary["skipped_rows"] += 1
            continue
        job_no = f"IMP-{int(sheet_alias) * 10000 + row_num:06d}"
        exists = conn.execute("SELECT id FROM job_install WHERE job_no = ?", (job_no,)).fetchone()
        if exists:
            summary["skipped_rows"] += 1
            continue
        required_feedback = [row.get("AT"), row.get("BA"), row.get("BE"), row.get("BB"), row.get("BF")]
        if not all(value not in ("", None) for value in required_feedback):
            summary["skipped_rows"] += 1
            continue
        if safe_float(row.get("AT")) <= 0:
            summary["skipped_rows"] += 1
            continue

        conn.execute(
            """
            INSERT INTO job_install (
              job_no, job_status, job_date, shift_name, operator_name,
              product_process_name, die_no, die_version, die_seat_no, block_no,
              pass_flag, remark, created_at, updated_at
            ) VALUES (?, 'Imported History', ?, 'Imported', 'Imported History', ?, ?, 'v1.00', ?, ?, NULL, ?, ?, ?)
            """,
            (job_no, excel_date_to_iso(row.get("A")), product_process_name, die_no, die_seat_no, block_no, f"Imported from sheet {sheet_name} row {row_num}", now, now),
        )
        job_id = int(conn.execute("SELECT id FROM job_install WHERE job_no = ?", (job_no,)).fetchone()[0])
        conn.execute(
            """
            INSERT INTO job_install_input (
              job_id, base_plate_no_1, base_plate_no_2, base_plate_no_3, base_plate_no_4,
              upper_x_ref, upper_y_ref, lower_x_ref, lower_y_ref, lower_die_actual_height,
              target_thickness, upper_preheat_temp, lower_preheat_temp, billet_temp,
              lubrication_type, blade_direction, blade_size_grade, crown_rotation_angle_grade,
              energy_grade, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                str(row.get("O", "")).strip() or None,
                str(row.get("P", "")).strip() or None,
                str(row.get("Q", "")).strip() or None,
                str(row.get("R", "")).strip() or None,
                safe_float(row.get("I")),
                safe_float(row.get("J")),
                safe_float(row.get("K")),
                safe_float(row.get("L")),
                safe_float(row.get("M")),
                safe_float(row.get("G")),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO job_calc_snapshot (
              job_id, calc_version, base_plate_total, die_seat_actual_height,
              die_seat_height_delta, base_template_delta, theory_template_thickness_base,
              theory_lower_x_pad_base, theory_lower_y_pad_base, history_template_correction,
              history_x_correction, history_y_correction, recommend_template_thickness,
              recommend_lower_x_pad, recommend_lower_y_pad, similar_case_count,
              recommend_confidence, created_at
            ) VALUES (?, 'v1.00-import', ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0, 'low', ?)
            """,
            (
                job_id,
                safe_float(row.get("W")),
                safe_float(row.get("AB")),
                safe_float(row.get("AE")),
                safe_float(row.get("AF")),
                safe_float(row.get("AS")),
                safe_float(row.get("AY")),
                safe_float(row.get("AZ")),
                safe_float(row.get("AS")),
                safe_float(row.get("AY")),
                safe_float(row.get("AZ")),
                now,
            ),
        )
        summary["history_rows"] += 1
        conn.execute(
            """
            INSERT INTO job_first_piece_feedback (
              job_id, actual_template_thickness, actual_al_block_thickness, actual_thickness,
              actual_lower_x_pad_root, actual_lower_x_pad_tip, actual_lower_y_pad,
              measured_x_offset_root, measured_x_offset_tip, measured_y_offset,
              first_piece_thickness_delta, is_pass, defect_type, feedback_remark,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)
            """,
            (
                job_id,
                safe_float(row.get("AT")),
                safe_float(row.get("AU")),
                safe_float(row.get("AV")),
                safe_float(row.get("BA")),
                safe_float(row.get("BC")),
                safe_float(row.get("BE")),
                safe_float(row.get("BB")),
                safe_float(row.get("BD")),
                safe_float(row.get("BF")),
                safe_float(row.get("AW")),
                f"Imported from sheet {sheet_name} row {row_num}",
                now,
                now,
            ),
        )
        summary["feedback_rows"] += 1
        conn.execute(
            """
            INSERT INTO job_sample_grade (
              job_id, sample_grade, measure_quality_level, die_install_quality_level,
              block_install_quality_level, guide_clearance_level, data_completeness_level,
              grade_reason, created_at, updated_at
            ) VALUES (?, ?, 'medium', 'good', 'good', 'good', ?, ?, ?, ?)
            """,
            (job_id, "A", "complete", f"Auto-graded on import (sheet {sheet_name} row {row_num})", now, now),
        )


def _log_import(conn: sqlite3.Connection, workbook_path: Path, summary: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO sys_import_log (
          import_type, source_file, total_rows, success_rows, failed_rows, log_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "excel_workbook",
            str(workbook_path),
            summary["master_rows"] + summary["history_rows"],
            summary["master_rows"] + summary["history_rows"],
            summary["skipped_rows"],
            str(summary),
            now_iso(),
        ),
    )
