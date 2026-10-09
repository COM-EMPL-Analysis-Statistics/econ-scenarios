"""Cognitive share of EU-27 employment from the EU Labour Force Survey, by ISCO-08 group.

The paper defines cognitive work as SOC major groups 11-29 (management, business, computer,
engineering, science, community service, legal, education, arts, healthcare practitioners),
41 (sales) and 43 (office and administrative support). The ISCO-08 counterpart at the two-digit
level is major groups 1-4 (managers, professionals, technicians and associate professionals,
clerical support) plus sub-major group 52 (sales workers). The rest of major group 5 (personal
service, personal care, protective services) corresponds to SOC 31-39, which the paper excludes.

Data: Eurostat lfsa_egai2d, employment by detailed occupation, EU27_2020, both sexes, 15 years or
over, thousand persons. The extract is cached in european_values/data/ and refetched with --fetch. Armed forces
(OC0) are excluded from both numerator and denominator, as the CPS counts civilian employment;
"no response" (NRP) is excluded from the denominator, which allocates it proportionally.

Run from the repository root:  uv run python european_values/compute_values/compute_share_C.py [--fetch]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "data" / "eurostat_lfsa_egai2d_EU27_2024_2025.json"
URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lfsa_egai2d"
    "?geo=EU27_2020&sex=T&age=Y_GE15&time=2024&time=2025&format=JSON&lang=EN"
)

MAPPINGS = {
    "ISCO 1-4 + 52 (paper's SOC 11-29, 41, 43)": ["OC1", "OC2", "OC3", "OC4", "OC52"],
    "ISCO 1-4 (no sales)": ["OC1", "OC2", "OC3", "OC4"],
    "ISCO 1-5 (all service and sales)": ["OC1", "OC2", "OC3", "OC4", "OC5"],
}


def load(fetch: bool = False) -> dict:
    if fetch or not CACHE.exists():
        with urllib.request.urlopen(URL, timeout=60) as r:  # noqa: S310
            CACHE.write_bytes(r.read())
    return json.loads(CACHE.read_text(encoding="utf-8"))


def table(d: dict) -> dict[str, dict[str, float]]:
    """{year: {isco_code: thousand persons}} from the JSON-stat response."""
    ids, sizes = d["id"], d["size"]
    index = {k: {v: kk for kk, v in d["dimension"][k]["category"]["index"].items()} for k in ids}
    out: dict[str, dict[str, float]] = {}
    for flat, v in d["value"].items():
        i = int(flat)
        pos = {}
        for k, s in reversed(list(zip(ids, sizes))):
            pos[k] = i % s
            i //= s
        year = index["time"][pos["time"]]
        occ = index["isco08"][pos["isco08"]]
        out.setdefault(year, {})[occ] = v
    return out


def shares(t: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for year, row in sorted(t.items()):
        civilian = row["TOTAL"] - row.get("NRP", 0.0) - row.get("OC0", 0.0)
        out[year] = {name: sum(row[c] for c in codes) / civilian for name, codes in MAPPINGS.items()}
        out[year]["civilian employment, thousands"] = civilian
    return out


def main() -> None:
    d = load(fetch="--fetch" in sys.argv)
    t = table(d)
    for year, s in shares(t).items():
        print(f"EU-27, {year}: civilian employment {s.pop('civilian employment, thousands'):,.0f} thousand")
        for name, v in s.items():
            print(f"  {v:.4f}  {name}")
    print("US, CPS 2025, SOC 11-29, 41, 43: 0.6235 (code default)")


if __name__ == "__main__":
    main()
