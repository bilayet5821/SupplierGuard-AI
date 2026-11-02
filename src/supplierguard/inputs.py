from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .models import PurchaseRequestLine


def load_purchase_request(csv_path: str | Path) -> dict[str, PurchaseRequestLine]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        result = {
            row["Item"].strip(): PurchaseRequestLine(
                pr_number=row["PR number"].strip(),
                item_code=row["Item"].strip(),
                description=row["Description"].strip(),
                unit=row["Unit"].strip(),
                quantity_requested=Decimal(row["Quantity requested"].replace(",", "")),
                maximum_unit_price_bdt=Decimal(
                    row["Maximum unit price (BDT)"].replace(",", "")
                ),
            )
            for row in rows
        }
    if not result:
        raise ValueError(f"Purchase request is empty: {path}")
    return result
