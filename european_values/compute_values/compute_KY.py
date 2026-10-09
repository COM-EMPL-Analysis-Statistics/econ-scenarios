"""Capital-output ratio, depreciation and the implied rental rate and net return, EU-27 and US.

The paper takes the rental rate R = 0.115 and depreciation 0.05 from Moll, Rachel and Restrepo
(2022, p. 2671: "We take a capital-output ratio of K/Y = 3, which implies a rental rate of
capital R = 11.5%. We take a depreciation rate of 5% so that the return to capital equals
r_K = 6.5%"). With the paper's capital share 0.40, its K/Y = 0.40 / 0.115 = 3.5 is implied by
the identity s_K = R x K/Y, not measured. Moll et al.'s own 6.5% is the Gomme, Ravikumar and
Rupert (2011) return to business capital: net capital income over capital at replacement cost.

This script measures the same objects from national accounts for both economies:
  K/Y    net fixed assets at current replacement cost / nominal GDP
         EU: Eurostat nama_10_nfa_st (N11N, CRC_MEUR, TOTAL), summed over member states that
         report, with nama_10_gdp (B1GQ, CP_MEUR); US: BEA via FRED K1TTOTL1ES000 / GDPA
  delta  consumption of fixed capital / net fixed assets = (CFC/GDP) / (K/Y)
         EU: AMECO UKCT / UVGD; US: BEA via FRED M1TTOTL1ES000 / GDPA
  R      s_K / (K/Y), with s_K = 1 - s_L (US 0.40, EU 0.37)
  r      R - delta

Extracts are cached in european_values/data/. Run from the repository root:
    uv run python european_values/compute_values/compute_KY.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
EU27 = "BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split()
S_K = {"US": 0.40, "EU": 0.37}


def jsonstat(path: Path) -> dict[tuple[str, str], float]:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, sizes = d["id"], d["size"]
    inv = {k: {v: kk for kk, v in d["dimension"][k]["category"]["index"].items()} for k in ids}
    out = {}
    for flat, v in d["value"].items():
        i = int(flat)
        pos = {}
        for k, s in reversed(list(zip(ids, sizes))):
            pos[k] = i % s
            i //= s
        out[(inv["geo"][pos["geo"]], inv["time"][pos["time"]])] = v
    return out


def ameco(path: Path) -> dict[str, float]:
    s = json.loads(path.read_text(encoding="utf-8"))["series"]["docs"][0]
    return {p: v for p, v in zip(s["period"], s["value"]) if isinstance(v, (int, float))}


def fred(path: Path) -> dict[str, float]:
    rows = list(csv.reader(path.open(encoding="utf-8")))
    return {r[0][:4]: float(r[1]) for r in rows[1:] if r[1] not in (".", "")}


def eu_ky(year: str) -> tuple[float, int, float]:
    nfa = jsonstat(DATA / "eurostat_nama_10_nfa_st_CRC_EU27_2019_2024.json")
    gdp = jsonstat(DATA / "eurostat_nama_10_gdp_CP_EU27_2019_2024.json")
    have = [g for g in EU27 if (g, year) in nfa and (g, year) in gdp]
    k = sum(nfa[(g, year)] for g in have)
    y = sum(gdp[(g, year)] for g in have)
    y_all = sum(gdp[(g, year)] for g in EU27 if (g, year) in gdp)
    return k / y, len(have), y / y_all


def main() -> None:
    cfc_eu = ameco(DATA / "ameco_UKCT_EU27.json")
    gdp_eu = ameco(DATA / "ameco_UVGD_EU27.json")
    nfa_us = fred(DATA / "fred_K1TTOTL1ES000_us_net_fixed_assets.csv")
    gdp_us = fred(DATA / "fred_GDPA_us_gdp.csv")
    cfc_us = fred(DATA / "fred_M1TTOTL1ES000_us_cfc.csv")

    print(f"{'':10}{'K/Y':>7}{'CFC/GDP':>9}{'delta':>7}{'R=s_K/(K/Y)':>13}{'r=R-delta':>11}  coverage")
    for year in ("2019", "2022", "2023", "2024"):
        ky, n, cov = eu_ky(year)
        cfc = cfc_eu[year] / gdp_eu[year]
        delta = cfc / ky
        r_gross = S_K["EU"] / ky
        print(f"EU-27 {year}{ky:>7.2f}{cfc:>9.3f}{delta:>7.3f}{r_gross:>13.3f}{r_gross - delta:>11.3f}  {n} states, {cov:.0%} of GDP")
    for year in ("2019", "2022", "2023", "2024"):
        ky = nfa_us[year] / 1000 / gdp_us[year]
        cfc = cfc_us[year] / 1000 / gdp_us[year]
        delta = cfc / ky
        r_gross = S_K["US"] / ky
        print(f"US    {year}{ky:>7.2f}{cfc:>9.3f}{delta:>7.3f}{r_gross:>13.3f}{r_gross - delta:>11.3f}  BEA")
    print("\nPaper (US): R = 0.115 and delta = 0.05 from Moll et al. (2022, K/Y = 3 assumed);")
    print(f"            implied K/Y = 0.40 / 0.115 = {0.40 / 0.115:.2f}, r = 0.065")
    print(f"Retain R and delta for the EU: implied K/Y = 0.37 / 0.115 = {0.37 / 0.115:.2f}")


if __name__ == "__main__":
    main()
