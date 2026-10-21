"""Generate the synthetic demo dataset for ForgeCopilot.

All data produced here is FABRICATED for demonstration: generic product
names, demo dies/blocks/plates and simulated setup jobs with simulated
first-piece feedback.  It contains no real production data.

The generator drives the application's own service layer
(``ForgeRepository``), so the demo database is exactly what the app itself
would have produced: master data, jobs, calculation snapshots, feedback and
sample grades.

Usage:
    python scripts/generate_demo_data.py [--jobs 48]

Afterwards, run the app (``python app/main.py``) or the self-check
(``python app/main.py --self-check``).  A history CSV in the app's own
analysis format is also written to ``sample_data/demo_history.csv``.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import ensure_database
from app.services import ForgeRepository

SEED = 42

SHIFTS = ["Day Shift", "Swing Shift", "Night Shift", "Day 12h Shift", "Night 12h Shift"]
OPERATORS = ["Operator A", "Operator B", "Operator C"]

# Product names in records are numeric codes only (sanitization rule for
# this public edition); product *types* stay generic industry terms.
PRODUCTS = [
    # product_name (numeric code), process, product_type, direction, size, crown, energy, target
    ("1001 · ", "Finish Forging", "Compressor Blade", "R", "Medium", "Medium Angle", "Medium", 22.0),
    ("1002 · ", "Finish Forging", "Compressor Blade", "L", "Large", "Large Angle", "High", 26.5),
    ("1003 · ", "Finish Forging", "Turbine Blade R", "R", "Large", "Medium Angle", "High", 30.0),
    ("1004 · ", "Pre-forging", "Turbine Blade L", "L", "Medium", "Small Angle", "Medium", 34.0),
    ("1005 · ", "Die Forging", "Diaphragm Blade R", "R", "Small", "Small Angle", "Low", 12.0),
    ("1006 · ", "Die Forging", "Diaphragm Blade L", "L", "Small", "Medium Angle", "Low", 12.5),
    ("1007 · ", "Hot Sizing", "Structural Part", "/", "Medium", "Medium Angle", "Medium", 18.0),
    ("1008 · ", "Finish Forging", "Tool-holder Blade", "Forward", "Small", "Small Angle", "Low", 9.0),
]

DIES = [
    ("DIE-101", "Demo Die 101", "spec-A", "v1.00"),
    ("DIE-102", "Demo Die 102", "spec-A", "v1.00"),
    ("DIE-103", "Demo Die 103", "spec-B", "v1.10"),
    ("DIE-104", "Demo Die 104", "spec-B", "v1.00"),
    ("DIE-105", "Demo Die 105", "spec-C", "v1.10"),
    ("DIE-106", "Demo Die 106", "spec-C", "v1.00"),
]

SEATS = [
    ("SEAT-01", 512.0, 0.30, -0.20, 8.0, 0.20),
    ("SEAT-02", 508.5, -0.40, 0.25, 8.5, 0.35),
]

BLOCKS = [
    # block_no, lower_x, lower_y, upper_x, upper_y, lower_plate, upper_plate
    ("BLK-01", 1.20, 0.80, 1.00, 0.90, 18.0, 16.0),
    ("BLK-02", 0.90, 1.10, 1.10, 0.70, 20.0, 15.0),
    ("BLK-03", 1.50, 0.60, 1.30, 0.80, 16.0, 18.0),
    ("BLK-04", 0.70, 1.30, 0.80, 1.20, 22.0, 14.0),
    ("BLK-05", 1.10, 0.90, 0.95, 1.05, 19.0, 17.0),
    ("BLK-06", 1.35, 0.75, 1.15, 0.85, 17.0, 19.0),
]

PLATES = [("PL-01", 5.0), ("PL-02", 8.0), ("PL-03", 10.0), ("PL-04", 12.0),
          ("PL-05", 15.0), ("PL-06", 20.0), ("PL-07", 25.0), ("PL-08", 30.0)]

PRODUCT_TYPE_X_COMP = {
    "Structural Part": 0.20, "Compressor Blade": -0.35, "Turbine Blade R": 0.45,
    "Turbine Blade L": -0.45, "Diaphragm Blade R": 0.30, "Diaphragm Blade L": -0.30,
    "Tool-holder Blade": 0.10,
}
PREV_DIR_X_COMP = {"R": 0.25, "L": -0.25, "Forward": 0.10, "Reverse": -0.10, "/": 0.0}


def _deviation(rng: random.Random, success: bool) -> float:
    """A deviation that lands within +/-1 iff ``success`` is true."""
    if success:
        return round(rng.uniform(-1.0, 1.0), 2)
    magnitude = rng.uniform(1.05, 2.8)
    return round(magnitude if rng.random() < 0.5 else -magnitude, 2)


def _pattern(count: int, rate: float, rng: random.Random) -> list[bool]:
    """A shuffled success/fail pattern matching ``rate`` exactly."""
    hits = int(round(count * rate))
    pattern = [True] * hits + [False] * (count - hits)
    rng.shuffle(pattern)
    return pattern


def seed_master_data(repo: ForgeRepository) -> None:
    for seat_no, close_h, x_off, y_off, t700, wear in SEATS:
        repo.add_die_seat({
            "die_seat_no": seat_no, "theory_close_height": close_h,
            "seat_position_name": "Demo position", "seat_x_offset": x_off,
            "seat_y_offset": y_off, "base_template_700": t700,
            "base_template_wear": wear, "guide_clearance_level": "good",
        })
    for block_no, lx, ly, ux, uy, lp, up in BLOCKS:
        repo.add_block({
            "block_no": block_no, "block_size": "demo", "theory_thickness": lp + up,
            "lower_x_base": lx, "lower_y_base": ly, "upper_x_base": ux, "upper_y_base": uy,
            "lower_block_plate_thickness": lp, "upper_block_plate_thickness": up,
            "block_plate_delta": round(lp - up, 2),
        })
    for plate_no, thickness in PLATES:
        repo.add_base_plate({"plate_no": plate_no, "plate_thickness": thickness, "plate_remark": "demo plate"})
    for die_no, die_name, spec, version in DIES:
        repo.add_die_version({
            "die_no": die_no, "die_name": die_name, "die_spec": spec, "die_version": version,
            "die_status": "active", "use_count_bucket": "100-500", "total_hit_count": 320,
            "after_repair_hit_count": 40, "is_after_regrind_first_use": 0, "remark": "demo die",
        })
    for name, process, ptype, direction, size, crown, energy, target in PRODUCTS:
        repo.add_product_process({
            "product_name": name, "process_name": process, "product_type": ptype,
            "blade_direction": direction, "blade_size_grade": size,
            "crown_rotation_angle_grade": crown, "energy_grade": energy,
            "target_thickness_default": target,
        })
    for rule_key, comp in PRODUCT_TYPE_X_COMP.items():
        repo.add_rule({"rule_type": "product_type_x_comp", "rule_key": rule_key,
                       "x_comp": comp, "y_comp": 0.0, "template_comp": 0.0, "remark": "demo rule"})
    for rule_key, comp in PREV_DIR_X_COMP.items():
        repo.add_rule({"rule_type": "prev_blade_dir_x_comp", "rule_key": rule_key,
                       "x_comp": comp, "y_comp": 0.0, "template_comp": 0.0, "remark": "demo rule"})


def generate_jobs(repo: ForgeRepository, count: int) -> None:
    rng = random.Random(SEED)
    # Target first-piece success rates for the synthetic dataset.  The
    # qualitative pattern mirrors production experience (template hardest,
    # Y shim easiest) without copying any real figures.
    pat_t = _pattern(count, 0.50, rng)
    pat_x = _pattern(count, 0.60, rng)
    pat_y = _pattern(count, 0.80, rng)
    start = date(2026, 4, 5)
    for i in range(count):
        job_day = start + timedelta(days=int(i * (172 / max(count - 1, 1))) + rng.randint(0, 2))
        product = rng.choice(PRODUCTS)
        die = rng.choice(DIES)
        seat = rng.choice(SEATS)
        block = rng.choice(BLOCKS)
        plates = rng.sample(PLATES, rng.randint(1, 3))
        plate_nos = [p[0] for p in plates] + [""] * (5 - len(plates))
        target = product[7] + rng.uniform(-1.5, 1.5)
        values = {
            "job_date": job_day.isoformat(),
            "shift_name": rng.choice(SHIFTS),
            "operator_name": rng.choice(OPERATORS),
            "product_process_name": f"{product[0]}{product[1]}",
            "die_no": die[0], "die_version": die[3],
            "die_seat_no": seat[0], "block_no": block[0],
            "base_plate_no_1": plate_nos[0], "base_plate_no_2": plate_nos[1],
            "base_plate_no_3": plate_nos[2], "base_plate_no_4": plate_nos[3],
            "base_plate_no_5": plate_nos[4],
            "die_hit_count": rng.randint(0, 60),
            "upper_x_ref": round(rng.uniform(-0.6, 0.6), 2),
            "upper_y_ref": round(rng.uniform(-0.6, 0.6), 2),
            "lower_x_ref": round(rng.uniform(-0.6, 0.6), 2),
            "lower_y_ref": round(rng.uniform(-0.6, 0.6), 2),
            "lower_die_actual_height": round(505.0 + rng.uniform(-3.0, 3.0), 2),
            "target_thickness": round(target, 2),
            "upper_preheat_temp": 320.0, "lower_preheat_temp": 300.0, "billet_temp": 1180.0,
            "lubrication_type": "graphite",
            "blade_direction": product[3], "blade_size_grade": product[4],
            "crown_rotation_angle_grade": product[5], "energy_grade": product[6],
            "remark": "synthetic demo job",
        }
        calc = repo.calculate_preview(values)
        job_id = repo.create_job(values, calc)

        d_t = _deviation(rng, pat_t[i])
        d_x = _deviation(rng, pat_x[i])
        d_y = _deviation(rng, pat_y[i])
        is_pass = 1 if (abs(d_t) <= 1 and abs(d_x) <= 1 and abs(d_y) <= 1) else 0
        suspect = rng.random() < 0.15
        feedback = {
            "actual_template_thickness": round(calc.recommend_template_thickness + d_t, 2),
            "actual_al_block_thickness": 10.0,
            "actual_thickness": round(target + d_t * 0.3, 2),
            "actual_lower_x_pad_root": round(calc.recommend_lower_x_pad + d_x, 2),
            "actual_lower_x_pad_tip": round(calc.recommend_lower_x_pad + d_x + rng.uniform(-0.3, 0.3), 2),
            "actual_lower_y_pad": round(calc.recommend_lower_y_pad + d_y, 2),
            "measured_x_offset_root": d_x,
            "measured_x_offset_tip": round(d_x + rng.uniform(-0.3, 0.3), 2),
            "measured_y_offset": d_y,
            "first_piece_thickness_delta": round(d_t * 0.3, 2),
            "is_pass": is_pass,
            "defect_type": "" if is_pass else rng.choice(["Undersize", "Offset", "Surface Mark"]),
            "feedback_remark": "synthetic demo feedback",
        }
        quality = {
            "measure_quality_level": "medium" if suspect else "high",
            "die_install_quality_level": "suspect" if suspect else "good",
            "block_install_quality_level": "good",
            "guide_clearance_level": "good",
        }
        repo.save_feedback(job_id, feedback, quality)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ForgeCopilot synthetic demo data")
    parser.add_argument("--jobs", type=int, default=48, help="number of synthetic jobs (default: 48)")
    args = parser.parse_args()

    ensure_database()
    repo = ForgeRepository()
    try:
        if repo.list_product_processes():
            print("Database already has master data; skipping generation to avoid duplicates.")
            return
        seed_master_data(repo)
        generate_jobs(repo, args.jobs)
        stats = repo.get_success_stats()
        print(f"Demo data generated: {args.jobs} synthetic jobs")
        print(f"All-time success rates (synthetic): {stats['alltime']}")
        out = Path(__file__).resolve().parents[1] / "sample_data" / "demo_history.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        repo.export_analysis_csv(out)
        print(f"History CSV written to: {out}")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
