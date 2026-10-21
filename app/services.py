from __future__ import annotations

import sqlite3
import csv
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from pathlib import Path
from typing import Any

from .database import get_connection
from .i18n import display_status, t


Y_CONSTANT_CORRECTION = 0.5


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool_int(value: Any) -> int:
    if str(value) in {"1", "是", "yes", "Yes", "true", "True"}:
        return 1
    return 0


@dataclass
class CalcResult:
    base_plate_total: float
    die_seat_actual_height: float
    die_seat_height_delta: float
    base_template_delta: float
    theory_template_thickness_base: float
    theory_lower_x_pad_base: float
    theory_lower_y_pad_base: float
    history_template_correction: float
    history_x_correction: float
    history_y_correction: float
    recommend_template_thickness: float
    recommend_lower_x_pad: float
    recommend_lower_y_pad: float
    similar_case_count: int
    recommend_confidence: str


class ForgeRepository:
    def __init__(self) -> None:
        self.conn = get_connection()

    def close(self) -> None:
        self.conn.close()

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def _insert(self, sql: str, params: tuple[Any, ...]) -> int:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return int(cur.lastrowid)

    def list_product_processes(self) -> list[sqlite3.Row]:
        return self._fetch_all(
            "SELECT * FROM master_product_process ORDER BY is_active DESC, product_process_name"
        )

    def add_product_process(self, values: dict[str, Any]) -> int:
        now = now_iso()
        product_process_name = f"{values['product_name']}{values['process_name']}"
        return self._insert(
            """
            INSERT OR REPLACE INTO master_product_process (
              id, product_name, process_name, product_process_name,
              product_type, blade_direction, blade_size_grade,
              crown_rotation_angle_grade, energy_grade, target_thickness_default,
              is_active, invalid_reason, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_product_process WHERE product_process_name = ?), NULL),
              ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL,
              COALESCE((SELECT created_at FROM master_product_process WHERE product_process_name = ?), ?),
              ?
            )
            """,
            (
                product_process_name,
                values["product_name"],
                values["process_name"],
                product_process_name,
                values.get("product_type"),
                values.get("blade_direction"),
                values.get("blade_size_grade"),
                values.get("crown_rotation_angle_grade"),
                values.get("energy_grade"),
                safe_float(values.get("target_thickness_default"), 0.0),
                product_process_name,
                now,
                now,
            ),
        )

    def list_die_versions(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT * FROM master_die_version ORDER BY is_after_regrind_first_use DESC, die_no, die_version")

    def add_die_version(self, values: dict[str, Any]) -> int:
        now = now_iso()
        row_id = self._insert(
            """
            INSERT OR REPLACE INTO master_die_version (
              id, die_no, die_name, die_spec, die_version, die_status,
              use_count_bucket, is_after_regrind_first_use, remark, invalid_reason,
              created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_die_version WHERE die_no = ? AND die_version = ?), NULL),
              ?, ?, ?, ?, ?, ?, ?, ?, NULL,
              COALESCE((SELECT created_at FROM master_die_version WHERE die_no = ? AND die_version = ?), ?),
              ?
            )
            """,
            (
                values["die_no"],
                values["die_version"],
                values["die_no"],
                values.get("die_name"),
                values.get("die_spec"),
                values["die_version"],
                values.get("die_status"),
                values.get("use_count_bucket"),
                to_bool_int(values.get("is_after_regrind_first_use", 0)),
                values.get("remark"),
                values["die_no"],
                values["die_version"],
                now,
                now,
            ),
        )
        if to_bool_int(values.get("is_after_regrind_first_use", 0)) == 1:
            self.conn.execute(
                """
                UPDATE master_die_version
                SET after_repair_hit_count = 0, updated_at = ?
                WHERE die_no = ? AND die_version = ?
                """,
                (now, values["die_no"], values["die_version"]),
            )
            self.conn.commit()
        return row_id

    def list_die_seats(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT * FROM master_die_seat ORDER BY is_active DESC, die_seat_no")

    def add_die_seat(self, values: dict[str, Any]) -> int:
        now = now_iso()
        return self._insert(
            """
            INSERT OR REPLACE INTO master_die_seat (
              id, die_seat_no, theory_close_height, seat_position_name,
              seat_x_offset, seat_y_offset, base_template_700,
              guide_clearance_level, is_active, invalid_reason, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_die_seat WHERE die_seat_no = ?), NULL),
              ?, ?, ?, ?, ?, ?, ?, 1, NULL,
              COALESCE((SELECT created_at FROM master_die_seat WHERE die_seat_no = ?), ?),
              ?
            )
            """,
            (
                values["die_seat_no"],
                values["die_seat_no"],
                safe_float(values.get("theory_close_height"), 0.0),
                values.get("seat_position_name"),
                safe_float(values.get("seat_x_offset"), 0.0),
                safe_float(values.get("seat_y_offset"), 0.0),
                safe_float(values.get("base_template_700"), 0.0),
                values.get("guide_clearance_level"),
                values["die_seat_no"],
                now,
                now,
            ),
        )

    def list_blocks(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT * FROM master_block ORDER BY is_active DESC, block_no")

    def add_block(self, values: dict[str, Any]) -> int:
        now = now_iso()
        return self._insert(
            """
            INSERT OR REPLACE INTO master_block (
              id, block_no, block_size, theory_thickness,
              lower_x_base, lower_y_base, upper_x_base, upper_y_base,
              lower_block_plate_thickness, upper_block_plate_thickness, block_plate_delta,
              is_active, invalid_reason, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_block WHERE block_no = ?), NULL),
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL,
              COALESCE((SELECT created_at FROM master_block WHERE block_no = ?), ?),
              ?
            )
            """,
            (
                values["block_no"],
                values["block_no"],
                values.get("block_size"),
                safe_float(values.get("theory_thickness"), 0.0),
                safe_float(values.get("lower_x_base"), 0.0),
                safe_float(values.get("lower_y_base"), 0.0),
                safe_float(values.get("upper_x_base"), 0.0),
                safe_float(values.get("upper_y_base"), 0.0),
                safe_float(values.get("lower_block_plate_thickness"), 0.0),
                safe_float(values.get("upper_block_plate_thickness"), 0.0),
                safe_float(values.get("block_plate_delta"), 0.0),
                values["block_no"],
                now,
                now,
            ),
        )

    def list_base_plates(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT * FROM master_base_plate ORDER BY is_active DESC, plate_no")

    def add_base_plate(self, values: dict[str, Any]) -> int:
        now = now_iso()
        return self._insert(
            """
            INSERT OR REPLACE INTO master_base_plate (
              id, plate_no, plate_thickness, plate_remark, is_active, invalid_reason, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_base_plate WHERE plate_no = ?), NULL),
              ?, ?, ?, 1, NULL,
              COALESCE((SELECT created_at FROM master_base_plate WHERE plate_no = ?), ?),
              ?
            )
            """,
            (
                values["plate_no"],
                values["plate_no"],
                safe_float(values.get("plate_thickness"), 0.0),
                values.get("plate_remark"),
                values["plate_no"],
                now,
                now,
            ),
        )

    def list_rules(self) -> list[sqlite3.Row]:
        return self._fetch_all("SELECT * FROM master_compensation_rule ORDER BY rule_type, rule_key")

    def add_rule(self, values: dict[str, Any]) -> int:
        now = now_iso()
        return self._insert(
            """
            INSERT OR REPLACE INTO master_compensation_rule (
              id, rule_type, rule_key, x_comp, y_comp, template_comp, remark, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_compensation_rule WHERE rule_type = ? AND rule_key = ?), NULL),
              ?, ?, ?, ?, ?, ?,
              COALESCE((SELECT created_at FROM master_compensation_rule WHERE rule_type = ? AND rule_key = ?), ?),
              ?
            )
            """,
            (
                values["rule_type"],
                values["rule_key"],
                values["rule_type"],
                values["rule_key"],
                safe_float(values.get("x_comp"), 0.0),
                safe_float(values.get("y_comp"), 0.0),
                safe_float(values.get("template_comp"), 0.0),
                values.get("remark"),
                values["rule_type"],
                values["rule_key"],
                now,
                now,
            ),
        )

    def list_options(self, category: str, only_active: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM master_option WHERE category = ?"
        params: list[Any] = [category]
        if only_active:
            sql += " AND is_active = 1"
        sql += " ORDER BY sort_order, option_value"
        return self._fetch_all(sql, tuple(params))

    def add_option(self, values: dict[str, Any]) -> int:
        now = now_iso()
        sort_order = int(safe_float(values.get("sort_order"), 0))
        return self._insert(
            """
            INSERT OR REPLACE INTO master_option (
              id, category, option_value, sort_order, is_active, remark, created_at, updated_at
            ) VALUES (
              COALESCE((SELECT id FROM master_option WHERE category = ? AND option_value = ?), NULL),
              ?, ?, ?, 1, ?,
              COALESCE((SELECT created_at FROM master_option WHERE category = ? AND option_value = ?), ?),
              ?
            )
            """,
            (
                values["category"],
                values["option_value"],
                values["category"],
                values["option_value"],
                sort_order,
                values.get("remark"),
                values["category"],
                values["option_value"],
                now,
                now,
            ),
        )

    def invalidate_master_record(self, table: str, key_field: str, key_value: str, reason: str) -> None:
        now = now_iso()
        self.conn.execute(
            f"UPDATE {table} SET is_active = 0, invalid_reason = ?, updated_at = ? WHERE {key_field} = ?",
            (reason or "Manually deactivated", now, key_value),
        )
        self.conn.commit()

    def invalidate_master_record_multi(self, table: str, key_fields: list[str], key_values: list[str], reason: str) -> None:
        now = now_iso()
        where_clause = " AND ".join(f"{field} = ?" for field in key_fields)
        self.conn.execute(
            f"UPDATE {table} SET is_active = 0, invalid_reason = ?, updated_at = ? WHERE {where_clause}",
            (reason or "Manually deactivated", now, *key_values),
        )
        self.conn.commit()

    def activate_master_record(self, table: str, key_field: str, key_value: str) -> None:
        now = now_iso()
        self.conn.execute(
            f"UPDATE {table} SET is_active = 1, invalid_reason = NULL, updated_at = ? WHERE {key_field} = ?",
            (now, key_value),
        )
        self.conn.commit()

    def activate_master_record_multi(self, table: str, key_fields: list[str], key_values: list[str]) -> None:
        now = now_iso()
        where_clause = " AND ".join(f"{field} = ?" for field in key_fields)
        self.conn.execute(
            f"UPDATE {table} SET is_active = 1, invalid_reason = NULL, updated_at = ? WHERE {where_clause}",
            (now, *key_values),
        )
        self.conn.commit()

    def update_master_record(self, table: str, key_field: str, key_value: str, updates: dict[str, Any]) -> None:
        now = now_iso()
        parts = []
        params: list[Any] = []
        for key, value in updates.items():
            parts.append(f"{key} = ?")
            params.append(value)
        parts.append("updated_at = ?")
        params.append(now)
        params.append(key_value)
        sql = f"UPDATE {table} SET {', '.join(parts)} WHERE {key_field} = ?"
        self.conn.execute(sql, tuple(params))
        self.conn.commit()

    def update_die_seat_state(self, die_seat_no: str, guide_clearance_level: str) -> None:
        now = now_iso()
        self.conn.execute(
            "UPDATE master_die_seat SET guide_clearance_level = ?, updated_at = ? WHERE die_seat_no = ?",
            (guide_clearance_level, now, die_seat_no),
        )
        self.conn.commit()

    def update_die_seat_theory_height(self, die_seat_no: str, theory_close_height: float) -> None:
        now = now_iso()
        self.conn.execute(
            "UPDATE master_die_seat SET theory_close_height = ?, updated_at = ? WHERE die_seat_no = ?",
            (theory_close_height, now, die_seat_no),
        )
        self.conn.commit()

    def update_die_seat_base_template_wear(self, die_seat_no: str, base_template_wear: float) -> None:
        now = now_iso()
        self.conn.execute(
            "UPDATE master_die_seat SET base_template_wear = ?, updated_at = ? WHERE die_seat_no = ?",
            (base_template_wear, now, die_seat_no),
        )
        self.conn.commit()

    def update_block_state(self, block_no: str, is_active: int) -> None:
        now = now_iso()
        self.conn.execute(
            "UPDATE master_block SET is_active = ?, updated_at = ? WHERE block_no = ?",
            (is_active, now, block_no),
        )
        self.conn.commit()

    def update_die_version_counts(self, die_no: str, die_version: str, hit_count: int, reset_after_repair: bool = False) -> None:
        now = now_iso()
        if reset_after_repair:
            self.conn.execute(
                """
                UPDATE master_die_version
                SET after_repair_hit_count = 0,
                    is_after_regrind_first_use = 1,
                    updated_at = ?
                WHERE die_no = ? AND die_version = ?
                """,
                (now, die_no, die_version),
            )
        self.conn.execute(
            """
            UPDATE master_die_version
            SET total_hit_count = COALESCE(total_hit_count, 0) + ?,
                after_repair_hit_count = COALESCE(after_repair_hit_count, 0) + ?,
                is_after_regrind_first_use = 0,
                updated_at = ?
            WHERE die_no = ? AND die_version = ?
            """,
            (hit_count, hit_count, now, die_no, die_version),
        )
        self.conn.commit()

    def list_dies_for_product_process(self, product_process_name: str) -> list[sqlite3.Row]:
        # 第一版兼容策略：先按模具名称/编号粗匹配历史任务，再回退到全量模具
        rows = self._fetch_all(
            """
            SELECT DISTINCT d.*
            FROM master_die_version d
            JOIN job_install j ON j.die_no = d.die_no AND j.die_version = d.die_version
            WHERE j.product_process_name = ?
            ORDER BY d.die_no, d.die_version
            """,
            (product_process_name,),
        )
        if rows:
            return rows
        return self.list_die_versions()

    def get_product_process(self, product_process_name: str) -> sqlite3.Row | None:
        return self._fetch_one(
            "SELECT * FROM master_product_process WHERE product_process_name = ?",
            (product_process_name,),
        )

    def get_die_seat(self, die_seat_no: str) -> sqlite3.Row | None:
        return self._fetch_one("SELECT * FROM master_die_seat WHERE die_seat_no = ?", (die_seat_no,))

    def get_block(self, block_no: str) -> sqlite3.Row | None:
        return self._fetch_one("SELECT * FROM master_block WHERE block_no = ?", (block_no,))

    def get_plate_total(self, plate_nos: list[str]) -> float:
        values = [plate for plate in plate_nos if plate]
        if not values:
            return 0.0
        placeholders = ",".join("?" for _ in values)
        row = self._fetch_one(
            f"SELECT COALESCE(SUM(plate_thickness), 0) AS total FROM master_base_plate WHERE plate_no IN ({placeholders})",
            tuple(values),
        )
        return safe_float(row["total"] if row else 0.0)

    def get_rule_comp(self, rule_type: str, rule_key: str | None) -> float:
        if not rule_key:
            return 0.0
        row = self._fetch_one(
            "SELECT x_comp FROM master_compensation_rule WHERE rule_type = ? AND rule_key = ?",
            (rule_type, rule_key),
        )
        return safe_float(row["x_comp"] if row else 0.0)

    def calculate_preview(self, values: dict[str, Any]) -> CalcResult:
        product = self.get_product_process(values["product_process_name"])
        die_seat = self.get_die_seat(values["die_seat_no"])
        block = self.get_block(values["block_no"])
        if not product or not die_seat or not block:
            raise ValueError(t("缺少必要主数据，请先维护产品工序、模座和拼块。"))

        plate_total = self.get_plate_total(
            [
                values.get("base_plate_no_1", ""),
                values.get("base_plate_no_2", ""),
                values.get("base_plate_no_3", ""),
                values.get("base_plate_no_4", ""),
                values.get("base_plate_no_5", ""),
            ]
        )

        product_x_comp = self.get_rule_comp("product_type_x_comp", product["product_type"])
        prev_dir_comp = self.get_rule_comp("prev_blade_dir_x_comp", values.get("blade_direction"))

        die_seat_actual_height = safe_float(die_seat["theory_close_height"], 0.0)
        die_seat_height_delta = 0.0
        base_template_delta = 0.0

        theory_template = (
            safe_float(values.get("lower_die_actual_height"))
            + safe_float(block["lower_block_plate_thickness"])
            + safe_float(block["upper_block_plate_thickness"])
            - die_seat_actual_height
            + plate_total
            + safe_float(values.get("target_thickness"))
            - die_seat_height_delta
            - base_template_delta
            + safe_float(die_seat["base_template_700"])
            + safe_float(die_seat["base_template_wear"])
        )
        theory_x = (
            safe_float(die_seat["seat_x_offset"])
            + product_x_comp
            + safe_float(values.get("upper_x_ref"))
            - safe_float(values.get("lower_x_ref"))
            + safe_float(block["lower_x_base"])
            - safe_float(block["upper_x_base"])
            + prev_dir_comp
        )
        theory_y = (
            safe_float(die_seat["seat_y_offset"])
            + safe_float(values.get("upper_y_ref"))
            - safe_float(values.get("lower_y_ref"))
            + safe_float(block["lower_y_base"])
            - safe_float(block["upper_y_base"])
            - Y_CONSTANT_CORRECTION
        )

        history_template_correction, history_x_correction, history_y_correction, sample_count = self._get_history_corrections(
            values["product_process_name"],
            values["die_version"],
            values["block_no"],
            values.get("blade_direction"),
        )
        recommend_confidence = "high" if sample_count >= 20 else "medium" if sample_count >= 5 else "low"

        return CalcResult(
            base_plate_total=round(plate_total, 3),
            die_seat_actual_height=round(die_seat_actual_height, 3),
            die_seat_height_delta=round(die_seat_height_delta, 3),
            base_template_delta=round(base_template_delta, 3),
            theory_template_thickness_base=round(theory_template, 3),
            theory_lower_x_pad_base=round(theory_x, 3),
            theory_lower_y_pad_base=round(theory_y, 3),
            history_template_correction=round(history_template_correction, 3),
            history_x_correction=round(history_x_correction, 3),
            history_y_correction=round(history_y_correction, 3),
            recommend_template_thickness=round(theory_template + history_template_correction, 3),
            recommend_lower_x_pad=round(theory_x + history_x_correction, 3),
            recommend_lower_y_pad=round(theory_y + history_y_correction, 3),
            similar_case_count=sample_count,
            recommend_confidence=recommend_confidence,
        )

    def _get_history_corrections(self, product_process_name: str, die_version: str, block_no: str, blade_direction: str | None) -> tuple[float, float, float, int]:
        levels = [
            (
                """
                j.product_process_name = ? AND j.die_version = ? AND j.block_no = ?
                AND COALESCE(i.blade_direction, '') = COALESCE(?, '')
                """,
                (product_process_name, die_version, block_no, blade_direction or ""),
            ),
            ("j.product_process_name = ? AND j.die_version = ? AND j.block_no = ?", (product_process_name, die_version, block_no)),
            ("j.product_process_name = ? AND j.die_version = ?", (product_process_name, die_version)),
            ("j.product_process_name = ?", (product_process_name,)),
        ]
        for where_clause, params in levels:
            rows = self._fetch_all(
                f"""
                SELECT
                  j.job_date,
                  f.actual_template_thickness,
                  f.actual_lower_x_pad_root,
                  f.actual_lower_y_pad,
                  c.theory_template_thickness_base,
                  c.theory_lower_x_pad_base,
                  c.theory_lower_y_pad_base,
                  c.recommend_template_thickness,
                  c.recommend_lower_x_pad,
                  c.recommend_lower_y_pad
                FROM job_install j
                JOIN job_install_input i ON i.job_id = j.id
                JOIN job_first_piece_feedback f ON f.job_id = j.id
                JOIN job_sample_grade g ON g.job_id = j.id
                JOIN (
                  SELECT c1.*
                  FROM job_calc_snapshot c1
                  JOIN (
                    SELECT job_id, MAX(id) AS max_id FROM job_calc_snapshot GROUP BY job_id
                  ) latest ON latest.max_id = c1.id
                ) c ON c.job_id = j.id
                WHERE g.sample_grade = 'A' AND {where_clause}
                ORDER BY j.job_date DESC, j.id DESC
                """,
                params,
            )
            if rows:
                template_correction = self._choose_correction(
                    rows,
                    "actual_template_thickness",
                    "theory_template_thickness_base",
                    "recommend_template_thickness",
                )
                x_correction = self._choose_correction(
                    rows,
                    "actual_lower_x_pad_root",
                    "theory_lower_x_pad_base",
                    "recommend_lower_x_pad",
                )
                y_correction = self._choose_correction(
                    rows,
                    "actual_lower_y_pad",
                    "theory_lower_y_pad_base",
                    "recommend_lower_y_pad",
                )
                return template_correction, x_correction, y_correction, len(rows)
        return 0.0, 0.0, 0.0, 0

    def _choose_correction(
        self,
        rows: list[sqlite3.Row],
        actual_field: str,
        theory_field: str,
        recommend_field: str,
    ) -> float:
        success_rows = [
            row for row in rows
            if abs(safe_float(row[actual_field]) - safe_float(row[recommend_field])) <= 1.0
        ]
        # 近期成功样本优先；成功样本不足时退而使用全部近期样本
        source_rows = success_rows[:20] if len(success_rows) >= 3 else rows[:12]
        if not source_rows:
            return 0.0
        corrections = [
            safe_float(row[actual_field]) - safe_float(row[theory_field])
            for row in source_rows
        ]
        # 按时间衰减加权：最近一条权重最高，依次递减（线性衰减）
        n = len(corrections)
        weights = [n - i for i in range(n)]  # 第0条(最新)权重最大
        total_weight = sum(weights)
        weighted_sum = sum(c * w for c, w in zip(corrections, weights))
        return round(weighted_sum / total_weight, 3)

    def _generate_job_no(self) -> str:
        prefix = "JOB-"
        row = self._fetch_one(
            "SELECT MAX(CAST(SUBSTR(job_no, ?) AS INTEGER)) AS max_no FROM job_install WHERE job_no LIKE ?",
            (len(prefix) + 1, f"{prefix}%"),
        )
        next_no = int(safe_float(row["max_no"] if row and row["max_no"] is not None else 0)) + 1
        return f"{prefix}{next_no:06d}"

    def create_job(self, values: dict[str, Any], calc: CalcResult) -> int:
        now = now_iso()
        job_no = self._generate_job_no()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO job_install (
              job_no, job_status, job_date, shift_name, operator_name,
              product_process_name, die_no, die_version, die_seat_no, block_no,
              pass_flag, remark, created_at, updated_at
            ) VALUES (?, 'Calculated', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                job_no,
                values.get("job_date") or now,
                values["shift_name"],
                values["operator_name"],
                values["product_process_name"],
                values["die_no"],
                values["die_version"],
                values["die_seat_no"],
                values["block_no"],
                values.get("remark"),
                now,
                now,
            ),
        )
        job_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO job_install_input (
              job_id, base_plate_no_1, base_plate_no_2, base_plate_no_3, base_plate_no_4,
              base_plate_no_5,
              die_hit_count, upper_x_ref, upper_y_ref, lower_x_ref, lower_y_ref, lower_die_actual_height,
              target_thickness, upper_preheat_temp, lower_preheat_temp, billet_temp,
              lubrication_type, blade_direction, blade_size_grade, crown_rotation_angle_grade,
              energy_grade, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                values.get("base_plate_no_1"),
                values.get("base_plate_no_2"),
                values.get("base_plate_no_3"),
                values.get("base_plate_no_4"),
                values.get("base_plate_no_5"),
                int(safe_float(values.get("die_hit_count"), 0)),
                safe_float(values.get("upper_x_ref")),
                safe_float(values.get("upper_y_ref")),
                safe_float(values.get("lower_x_ref")),
                safe_float(values.get("lower_y_ref")),
                safe_float(values.get("lower_die_actual_height")),
                safe_float(values.get("target_thickness")),
                safe_float(values.get("upper_preheat_temp")),
                safe_float(values.get("lower_preheat_temp")),
                safe_float(values.get("billet_temp")),
                values.get("lubrication_type"),
                values.get("blade_direction"),
                values.get("blade_size_grade"),
                values.get("crown_rotation_angle_grade"),
                values.get("energy_grade"),
                now,
                now,
            ),
        )
        hit_count = int(safe_float(values.get("die_hit_count"), 0))
        if hit_count > 0:
            self.update_die_version_counts(values["die_no"], values["die_version"], hit_count)
        cur.execute(
            """
            INSERT INTO job_calc_snapshot (
              job_id, calc_version, base_plate_total, die_seat_actual_height,
              die_seat_height_delta, base_template_delta, theory_template_thickness_base,
              theory_lower_x_pad_base, theory_lower_y_pad_base, history_template_correction,
              history_x_correction, history_y_correction, recommend_template_thickness,
              recommend_lower_x_pad, recommend_lower_y_pad, similar_case_count,
              recommend_confidence, created_at
            ) VALUES (?, 'v1.30', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                calc.base_plate_total,
                calc.die_seat_actual_height,
                calc.die_seat_height_delta,
                calc.base_template_delta,
                calc.theory_template_thickness_base,
                calc.theory_lower_x_pad_base,
                calc.theory_lower_y_pad_base,
                calc.history_template_correction,
                calc.history_x_correction,
                calc.history_y_correction,
                calc.recommend_template_thickness,
                calc.recommend_lower_x_pad,
                calc.recommend_lower_y_pad,
                calc.similar_case_count,
                calc.recommend_confidence,
                now,
            ),
        )
        self.conn.commit()
        return job_id

    def list_jobs(self, only_feedback_pending: bool = False) -> list[sqlite3.Row]:
        sql = """
            SELECT id, job_no, job_status, job_date, product_process_name, die_no, die_version, block_no
            FROM job_install
        """
        if only_feedback_pending:
            sql += " WHERE job_status IN ('Calculated', 'Feedback Pending') "
        sql += " ORDER BY id DESC LIMIT 200"
        return self._fetch_all(sql)

    def save_job_and_feedback(
        self,
        job_values: dict[str, Any],
        calc: CalcResult,
        feedback: dict[str, Any],
        quality: dict[str, Any],
        adjustment: dict[str, Any] | None = None,
    ) -> int:
        job_id = self.create_job(job_values, calc)
        self.save_feedback(job_id, feedback, quality, adjustment)
        return job_id

    def get_job_summary(self, job_id: int) -> sqlite3.Row | None:
        return self._fetch_one(
            """
            SELECT
              j.*,
              c.recommend_template_thickness,
              c.recommend_lower_x_pad,
              c.recommend_lower_y_pad
            FROM job_install j
            LEFT JOIN (
              SELECT c1.*
              FROM job_calc_snapshot c1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_calc_snapshot
                GROUP BY job_id
              ) latest ON latest.max_id = c1.id
            ) c ON c.job_id = j.id
            WHERE j.id = ?
            """,
            (job_id,),
        )

    def save_feedback(
        self,
        job_id: int,
        feedback: dict[str, Any],
        quality: dict[str, Any],
        adjustment: dict[str, Any] | None = None,
    ) -> None:
        now = now_iso()
        cur = self.conn.cursor()
        cur.execute(
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
                safe_float(feedback.get("actual_template_thickness")),
                safe_float(feedback.get("actual_al_block_thickness")),
                safe_float(feedback.get("actual_thickness")),
                safe_float(feedback.get("actual_lower_x_pad_root")),
                safe_float(feedback.get("actual_lower_x_pad_tip")),
                safe_float(feedback.get("actual_lower_y_pad")),
                safe_float(feedback.get("measured_x_offset_root")),
                safe_float(feedback.get("measured_x_offset_tip")),
                safe_float(feedback.get("measured_y_offset")),
                safe_float(feedback.get("first_piece_thickness_delta")),
                to_bool_int(feedback.get("is_pass")),
                feedback.get("defect_type"),
                feedback.get("feedback_remark"),
                now,
                now,
            ),
        )

        completeness = self._get_data_completeness(feedback)
        sample_grade, reason = self._grade_sample(quality, completeness)
        cur.execute(
            """
            INSERT INTO job_sample_grade (
              job_id, sample_grade, measure_quality_level, die_install_quality_level,
              block_install_quality_level, guide_clearance_level, data_completeness_level,
              grade_reason, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
              sample_grade = excluded.sample_grade,
              measure_quality_level = excluded.measure_quality_level,
              die_install_quality_level = excluded.die_install_quality_level,
              block_install_quality_level = excluded.block_install_quality_level,
              guide_clearance_level = excluded.guide_clearance_level,
              data_completeness_level = excluded.data_completeness_level,
              grade_reason = excluded.grade_reason,
              updated_at = excluded.updated_at
            """,
            (
                job_id,
                sample_grade,
                quality["measure_quality_level"],
                quality["die_install_quality_level"],
                quality["block_install_quality_level"],
                quality["guide_clearance_level"],
                completeness,
                reason,
                now,
                now,
            ),
        )

        if adjustment and any(str(adjustment.get(key, "")).strip() for key in ("template_delta", "x_pad_delta", "y_pad_delta", "adjust_reason", "after_result")):
            row = self._fetch_one(
                "SELECT COALESCE(MAX(adjust_round), 0) AS max_round FROM job_adjustment WHERE job_id = ?",
                (job_id,),
            )
            next_round = int(safe_float(row["max_round"] if row else 0)) + 1
            cur.execute(
                """
                INSERT INTO job_adjustment (
                  job_id, adjust_round, template_delta, x_pad_delta, y_pad_delta,
                  adjust_reason, after_result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    next_round,
                    safe_float(adjustment.get("template_delta")),
                    safe_float(adjustment.get("x_pad_delta")),
                    safe_float(adjustment.get("y_pad_delta")),
                    adjustment.get("adjust_reason"),
                    adjustment.get("after_result"),
                    now,
                ),
            )

        pass_flag = to_bool_int(feedback.get("is_pass"))
        job_status = "Completed" if pass_flag == 1 else "Feedback Pending"
        cur.execute(
            "UPDATE job_install SET pass_flag = ?, job_status = ?, updated_at = ? WHERE id = ?",
            (pass_flag, job_status, now, job_id),
        )
        self.conn.commit()

    def _get_data_completeness(self, feedback: dict[str, Any]) -> str:
        required = [
            feedback.get("actual_template_thickness"),
            feedback.get("actual_lower_x_pad_root"),
            feedback.get("actual_lower_y_pad"),
            feedback.get("measured_x_offset_root"),
            feedback.get("measured_y_offset"),
        ]
        if all(value not in (None, "") for value in required):
            return "complete"
        if any(value not in (None, "") for value in required):
            return "partial"
        return "missing"

    def _grade_sample(self, quality: dict[str, Any], completeness: str) -> tuple[str, str]:
        quality_values = {
            quality["measure_quality_level"],
            quality["die_install_quality_level"],
            quality["block_install_quality_level"],
            quality["guide_clearance_level"],
        }
        if completeness == "missing" or "abnormal" in quality_values:
            return "C", "Key data missing or clearly abnormal"
        if completeness == "complete" and quality["measure_quality_level"] == "high" and quality["die_install_quality_level"] == "good" and quality["block_install_quality_level"] == "good" and quality["guide_clearance_level"] == "good":
            return "A", "Key data complete; good quality"
        return "B", "Data usable but does not meet Grade A criteria"

    def list_history_rows(self, product_process_name: str | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT
              j.id,
              j.job_no,
              j.job_date,
              j.product_process_name,
              j.die_no,
              j.die_version,
              j.block_no,
              j.job_status,
              c.recommend_template_thickness,
              c.recommend_lower_x_pad,
              c.recommend_lower_y_pad,
              f.actual_template_thickness,
              f.measured_x_offset_root,
              f.measured_y_offset,
              g.sample_grade
            FROM job_install j
            LEFT JOIN (
              SELECT c1.*
              FROM job_calc_snapshot c1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_calc_snapshot
                GROUP BY job_id
              ) latest ON latest.max_id = c1.id
            ) c ON c.job_id = j.id
            LEFT JOIN (
              SELECT f1.*
              FROM job_first_piece_feedback f1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_first_piece_feedback
                GROUP BY job_id
              ) latestf ON latestf.max_id = f1.id
            ) f ON f.job_id = j.id
            LEFT JOIN job_sample_grade g ON g.job_id = j.id
        """
        params: list[Any] = []
        if product_process_name:
            sql += " WHERE j.product_process_name = ? "
            params.append(product_process_name)
        sql += " ORDER BY j.id DESC LIMIT 300"
        rows = self._fetch_all(sql, tuple(params))
        normalized = []
        for row in rows:
            row_dict = dict(row)
            row_dict["job_status"] = display_status(str(row_dict.get("job_status")))
            normalized.append(row_dict)
        return normalized

    def get_success_stats(self) -> dict[str, Any]:
        rows = self._fetch_all(
            """
            SELECT
              j.job_date,
              c.recommend_template_thickness,
              c.recommend_lower_x_pad,
              c.recommend_lower_y_pad,
              f.actual_template_thickness,
              f.actual_lower_x_pad_root,
              f.actual_lower_y_pad
            FROM job_install j
            JOIN (
              SELECT c1.*
              FROM job_calc_snapshot c1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_calc_snapshot
                GROUP BY job_id
              ) latest ON latest.max_id = c1.id
            ) c ON c.job_id = j.id
            JOIN (
              SELECT f1.*
              FROM job_first_piece_feedback f1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_first_piece_feedback
                GROUP BY job_id
              ) latestf ON latestf.max_id = f1.id
            ) f ON f.job_id = j.id
            ORDER BY j.job_date
            """
        )

        def is_success(actual: Any, recommend: Any) -> int:
            return 1 if abs(safe_float(actual) - safe_float(recommend)) <= 1.0 else 0

        monthly: dict[str, dict[str, int]] = {}
        alltime = {
            "total": 0,
            "template_success": 0,
            "x_success": 0,
            "y_success": 0,
        }
        for row in rows:
            date_text = str(row["job_date"] or "")
            month_key = date_text[:7] if len(date_text) >= 7 else t("未知月份")
            monthly.setdefault(
                month_key,
                {"total": 0, "template_success": 0, "x_success": 0, "y_success": 0},
            )
            template_ok = is_success(row["actual_template_thickness"], row["recommend_template_thickness"])
            x_ok = is_success(row["actual_lower_x_pad_root"], row["recommend_lower_x_pad"])
            y_ok = is_success(row["actual_lower_y_pad"], row["recommend_lower_y_pad"])

            alltime["total"] += 1
            alltime["template_success"] += template_ok
            alltime["x_success"] += x_ok
            alltime["y_success"] += y_ok

            monthly[month_key]["total"] += 1
            monthly[month_key]["template_success"] += template_ok
            monthly[month_key]["x_success"] += x_ok
            monthly[month_key]["y_success"] += y_ok

        def enrich(item: dict[str, int]) -> dict[str, Any]:
            total = item["total"]
            if total == 0:
                return {**item, "template_rate": 0.0, "x_rate": 0.0, "y_rate": 0.0}
            return {
                **item,
                "template_rate": round(item["template_success"] * 100 / total, 2),
                "x_rate": round(item["x_success"] * 100 / total, 2),
                "y_rate": round(item["y_success"] * 100 / total, 2),
            }

        monthly_rows = [{"month": key, **enrich(value)} for key, value in sorted(monthly.items())]
        return {
            "alltime": enrich(alltime),
            "monthly": monthly_rows,
        }

    def export_analysis_csv(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._fetch_all(
            """
            SELECT
              j.job_no,
              j.job_status,
              j.job_date,
              j.shift_name,
              j.operator_name,
              j.product_process_name,
              j.die_no,
              j.die_version,
              j.die_seat_no,
              j.block_no,
              i.base_plate_no_1,
              i.base_plate_no_2,
              i.base_plate_no_3,
              i.base_plate_no_4,
              i.base_plate_no_5,
              i.upper_x_ref,
              i.upper_y_ref,
              i.lower_x_ref,
              i.lower_y_ref,
              i.lower_die_actual_height,
              i.target_thickness,
              i.blade_direction,
              i.blade_size_grade,
              i.crown_rotation_angle_grade,
              i.energy_grade,
              c.base_plate_total,
              c.theory_template_thickness_base,
              c.theory_lower_x_pad_base,
              c.theory_lower_y_pad_base,
              c.recommend_template_thickness,
              c.recommend_lower_x_pad,
              c.recommend_lower_y_pad,
              f.actual_template_thickness,
              f.actual_al_block_thickness,
              f.actual_thickness,
              f.actual_lower_x_pad_root,
              f.actual_lower_x_pad_tip,
              f.actual_lower_y_pad,
              f.measured_x_offset_root,
              f.measured_x_offset_tip,
              f.measured_y_offset,
              f.first_piece_thickness_delta,
              f.is_pass,
              f.defect_type,
              g.sample_grade,
              g.measure_quality_level,
              g.die_install_quality_level,
              g.block_install_quality_level,
              g.guide_clearance_level,
              CASE WHEN ABS(COALESCE(f.actual_template_thickness, 0) - COALESCE(c.recommend_template_thickness, 0)) <= 1 THEN 1 ELSE 0 END AS template_success_flag,
              CASE WHEN ABS(COALESCE(f.actual_lower_x_pad_root, 0) - COALESCE(c.recommend_lower_x_pad, 0)) <= 1 THEN 1 ELSE 0 END AS x_pad_success_flag,
              CASE WHEN ABS(COALESCE(f.actual_lower_y_pad, 0) - COALESCE(c.recommend_lower_y_pad, 0)) <= 1 THEN 1 ELSE 0 END AS y_pad_success_flag
            FROM job_install j
            LEFT JOIN job_install_input i ON i.job_id = j.id
            LEFT JOIN (
              SELECT c1.*
              FROM job_calc_snapshot c1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_calc_snapshot
                GROUP BY job_id
              ) latest ON latest.max_id = c1.id
            ) c ON c.job_id = j.id
            LEFT JOIN (
              SELECT f1.*
              FROM job_first_piece_feedback f1
              JOIN (
                SELECT job_id, MAX(id) AS max_id
                FROM job_first_piece_feedback
                GROUP BY job_id
              ) latestf ON latestf.max_id = f1.id
            ) f ON f.job_id = j.id
            LEFT JOIN job_sample_grade g ON g.job_id = j.id
            ORDER BY j.id
            """
        )
        if not rows:
            raise ValueError(t("当前没有可导出的数据。"))

        fieldnames = list(rows[0].keys())
        with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row[key] for key in fieldnames})
        return output_path
