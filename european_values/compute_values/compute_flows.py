"""EU-27 labour market flows in normal times: the pool U_bar, the finding rate, q_bar_annual and
the separation relatives by group (Table 1, panel D), from Eurostat.

The paper: U_bar is the unemployed with a previous job over the labour force (CPS 2025);
q_bar_annual (0.11) is the annual separation rate that, with U_bar and the monthly CPS finding
rate f, balances inflows and outflows of the pool: q = 12 f U / (1 - U); sep_rel are the monthly
E-to-U hazards by group (IPUMS-CPS 2010-19) relative to the average.

EU sources (extracts cached in european_values/data/):
  lfsi_long_q   quarterly transitions between employment, unemployment and inactivity, EU-27,
                15-74, seasonally adjusted (Eurostat experimental statistics): thousand persons
                from 2022-Q1, shares of the origin stock (one decimal) back to 2015
  lfsa_ugpis    unemployed by occupation of the last job (ISCO-08 1-digit), EU-27, annual
  lfsa_egai2d   employment by ISCO-08 2-digit group, EU-27, annual (also used for share_C)

Quarterly transition shares are converted to monthly ones with the time-aggregation correction
of Shimer (2012): the monthly transition matrix is the matrix exponential of one third of the
matrix logarithm of the quarterly one, so that workers who move twice within a quarter are
counted. Cognitive = ISCO 1-4 plus 52; the unemployed of major group 5, published at 1-digit
only, are split by the employment shares of 52 and 51+53+54.

Run from the repository root:  uv run python european_values/compute_values/compute_flows.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm, logm

DATA = Path(__file__).resolve().parent.parent / "data"
STATES = ("EMP", "UNE", "INAC")
PERIODS = {"2022Q1-2025Q2": ("2022-Q1", "2025-Q2", "ths"), "2015-2019": ("2015-Q1", "2019-Q4", "pc")}
UNIT_OF = {"EMP": "PC_EMP", "UNE": "PC_UNE", "INAC": "PC_INAC"}
YEAR = "2025"


def table(path: Path) -> tuple[list[str], dict[str, list[str]], dict[tuple[str, ...], float]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids, size = d["id"], d["size"]
    cats = {k: list(d["dimension"][k]["category"]["index"]) for k in ids}
    out = {}
    for flat, v in d["value"].items():
        n, key = int(flat), []
        for k, s in zip(reversed(ids), reversed(size)):
            key.append(cats[k][n % s])
            n //= s
        out[tuple(reversed(key))] = v
    return ids, cats, out


def quarterly_matrices(kind: str) -> dict[str, np.ndarray]:
    """Quarterly transition matrix (origin rows, shares of the origin stock) per quarter."""
    if kind == "ths":
        _, cats, v = table(DATA / "eurostat_lfsi_long_q_EU27_2015_2025.json")
        cell = lambda a, b, q: v.get(("Q", "THS_PER", "SA", f"{a}_{b}", "T", "EU27_2020", q))
    else:
        _, cats, v = table(DATA / "eurostat_lfsi_long_q_EU27_2015_2025_pc.json")
        cell = lambda a, b, q: v.get(("Q", UNIT_OF[a], "SA", f"{a}_{b}", "T", "EU27_2020", q))
    out = {}
    for q in cats["time"]:
        rows = [[cell(a, b, q) for b in STATES] for a in STATES]
        if any(x is None for r in rows for x in r):
            continue
        m = np.array(rows, dtype=float)
        out[q] = m / m.sum(axis=1, keepdims=True)
    return out


def monthly(P: np.ndarray) -> np.ndarray:
    """Monthly transition matrix behind a quarterly one (Shimer 2012 time-aggregation correction)."""
    return np.real(expm(logm(P) / 3.0))


def pool_and_groups(year: str) -> dict[str, float]:
    _, _, u = table(DATA / "eurostat_lfsa_ugpis_EU27_2015_2025.json")
    _, _, e = table(DATA / "eurostat_lfsa_egai2d_EU27_2024_2025.json")
    U = {k: u.get(("A", "THS_PER", "T", k, "EU27_2020", year), 0.0) for k in ("TOTAL", "OC1", "OC2", "OC3", "OC4", "OC5", "OC0", "NAP_NEMP_Y8", "NRP")}
    E = {k: e[("A", k, "Y_GE15", "T", "THS_PER", "EU27_2020", year)] for k in ("TOTAL", "OC1", "OC2", "OC3", "OC4", "OC5", "OC52", "OC0", "NRP")}
    u_prev = U["TOTAL"] - U["NAP_NEMP_Y8"] - U["OC0"]  # had a civilian job in the last 8 years; no-response kept
    e_civ = E["TOTAL"] - E["OC0"] - E["NRP"]
    sales = E["OC52"] / E["OC5"]
    u_c = U["OC1"] + U["OC2"] + U["OC3"] + U["OC4"] + sales * U["OC5"]
    e_c = E["OC1"] + E["OC2"] + E["OC3"] + E["OC4"] + E["OC52"]
    u_known = U["TOTAL"] - U["NAP_NEMP_Y8"] - U["OC0"] - U["NRP"]
    ratio = u_known / e_civ
    return {
        "U_bar": u_prev / (e_civ + u_prev),
        "share_C": e_c / e_civ,
        "rel_C": (u_c / e_c) / ratio,
        "rel_N": ((u_known - u_c) / (e_civ - e_c)) / ratio,
        "u_prev_ths": u_prev,
        "emp_ths": e_civ,
        "sales_share_of_OC5": sales,
    }


def main() -> None:
    g = pool_and_groups(YEAR)
    print(f"EU-27 {YEAR}: unemployed with a previous job {g['u_prev_ths']:,.0f} thousand, civilian employment {g['emp_ths']:,.0f} thousand")
    print(f"  U_bar = {g['U_bar']:.4f}   share_C = {g['share_C']:.4f}   sep_rel = ({g['rel_C']:.3f}, {g['rel_N']:.3f})   (stock ratios; OC5 split with sales share {g['sales_share_of_OC5']:.3f})")
    print(f"  check: share_C*rel_C + (1-share_C)*rel_N = {g['share_C']*g['rel_C'] + (1-g['share_C'])*g['rel_N']:.4f}")
    rows = []
    for name, (a, b, kind) in PERIODS.items():
        Pq = quarterly_matrices(kind)
        qs = [q for q in Pq if a <= q <= b]
        P = np.mean([Pq[q] for q in qs], axis=0)
        M = monthly(P)
        f_q, s_q = P[1, 0], P[0, 1]
        f_m, s_m = M[1, 0], M[0, 1]
        f_naive = 1 - (1 - f_q) ** (1 / 3)
        q_annual = 12 * f_m * g["U_bar"] / (1 - g["U_bar"])
        rows.append((name, len(qs), f_q, f_m, f_naive, s_q, s_m, q_annual))
    print(f"\n{'period':<16}{'quarters':>9}{'f quarterly':>13}{'f monthly':>11}{'f naive':>9}{'s quarterly':>13}{'s monthly':>11}{'q_bar_annual':>14}")
    for r in rows:
        print(f"{r[0]:<16}{r[1]:>9}{r[2]:>13.4f}{r[3]:>11.4f}{r[4]:>9.4f}{r[5]:>13.4f}{r[6]:>11.5f}{r[7]:>14.4f}")
    print("\nUS for comparison: f monthly 0.219 (CPS 2010-19), E-to-U monthly 0.0122, U_bar 0.038, q_bar_annual 0.11, sep_rel (0.69, 1.52)")


if __name__ == "__main__":
    main()
