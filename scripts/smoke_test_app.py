from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import ensure_database
from app.excel_importer import import_workbook
from app.services import ForgeRepository


def main() -> None:
    ensure_database()
    repo = ForgeRepository()
    try:
        workbook = Path(__file__).resolve().parents[2] / "die_setup_workbook.xlsx"
        if workbook.exists():
            summary = import_workbook(repo.conn, workbook)
            print("Excel import complete:", summary)
        else:
            print("Historical workbook not found; skipping import.")

        products = repo.list_product_processes()
        die_versions = repo.list_die_versions()
        seats = repo.list_die_seats()
        blocks = repo.list_blocks()
        plates = repo.list_base_plates()

        print(f"Product processes: {len(products)}")
        print(f"Die versions: {len(die_versions)}")
        print(f"Die seats: {len(seats)}")
        print(f"Blocks: {len(blocks)}")
        print(f"Base plates: {len(plates)}")

        if not (products and die_versions and seats and blocks):
            print("Not enough master data; ending smoke test.")
            return

        first_die = die_versions[0]
        preview = repo.calculate_preview(
            {
                "product_process_name": products[0]["product_process_name"],
                "die_no": first_die["die_no"],
                "die_version": first_die["die_version"],
                "die_seat_no": seats[0]["die_seat_no"],
                "block_no": blocks[0]["block_no"],
                "base_plate_no_1": plates[0]["plate_no"] if plates else "",
                "base_plate_no_2": "",
                "base_plate_no_3": "",
                "base_plate_no_4": "",
                "upper_x_ref": 0.0,
                "upper_y_ref": 0.0,
                "lower_x_ref": 0.0,
                "lower_y_ref": 0.0,
                "lower_die_actual_height": 650.0,
                "target_thickness": 1.0,
                "blade_direction": "",
            }
        )
        print("Preview calculation passed:")
        print("  Recommended template thickness:", preview.recommend_template_thickness)
        print("  Recommended X shim:", preview.recommend_lower_x_pad)
        print("  Recommended Y shim:", preview.recommend_lower_y_pad)
    finally:
        repo.close()


if __name__ == "__main__":
    main()
