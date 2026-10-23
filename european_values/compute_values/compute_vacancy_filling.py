"""EU-27 vacancy filling within a month (pi_bar_mean, Table 1 panel D), from Eurostat, with the
US JOLTS figure recomputed the same way as a check.

The paper: 0.65 of vacancies are filled within a month, from a daily filling rate of 4.0% over 26
working days (JOLTS 2010-19, Davis, Faberman and Haltiwanger 2013). In a steady state the daily
rate is hires per working day over the vacancy stock, f_d = H / (26 V), and the share filled within
a month is 1 - (1 - f_d)^26. On JOLTS 2010-19 this simple version gives 0.63 against the paper's
0.65 (their exact method also counts vacancies posted and filled within the month).

EU inputs (extracts cached in european_values/data/):
  jvs_q_nace2     job vacancy rate, EU-27, NACE B-S, all firm sizes, seasonally adjusted (the EU
                  aggregate is published as a rate only): V = JVR / (1 - JVR) x occupied posts
  namq_10_a10_e   employees, EU-27, national accounts: occupied posts = total less agriculture
  lfsq_egdn2      employed persons with job tenure under 3 months, EU-27, 15-74: hires per
                  quarter (those still employed at the interview), H = that / 3 per month

Run from the repository root:  uv run python european_values/compute_values/compute_vacancy_filling.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
DAYS = 26
QUARTERS = [f"{y}-Q{q}" for y in (2022, 2023, 2024, 2025) for q in (1, 2, 3, 4)][:14]  # 2022-Q1 to 2025-Q2


def table(path: Path) -> tuple[list[str], dict[tuple[str, ...], float]]:
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
    return ids, out


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def fill_share(hires_per_month: float, vacancies: float) -> tuple[float, float]:
    f_d = hires_per_month / (DAYS * vacancies)
    return f_d, 1.0 - (1.0 - f_d) ** DAYS


def us_jolts() -> tuple[float, float, float, float]:
    def avg(name: str) -> float:
        rows = list(csv.DictReader((DATA / name).open(encoding="utf-8")))
        col = [c for c in rows[0] if c != "observation_date"][0]
        return mean([float(r[col]) for r in rows if r["observation_date"][:4] in {str(y) for y in range(2010, 2020)} and r[col] not in (".", "")])

    H, V = avg("fred_JTSHIL_us_hires.csv"), avg("fred_JTSJOL_us_openings.csv")
    return H, V, *fill_share(H, V)


def eu() -> dict[str, float]:
    _, jv = table(DATA / "eurostat_jvs_q_nace2_EU27_2022_2025.json")
    jvr = mean([jv[("Q", "SA", "B-S", "TOTAL", "JVR", "EU27_2020", q)] for q in QUARTERS]) / 100.0
    _, na = table(DATA / "eurostat_namq_10_a10_e_employees_EU27_2022_2025.json")
    emp = mean([na[("Q", "THS_PER", "TOTAL", "NSA", "SAL_DC", "EU27_2020", q)] - na[("Q", "THS_PER", "A", "NSA", "SAL_DC", "EU27_2020", q)] for q in QUARTERS])
    _, eg = table(DATA / "eurostat_lfsq_egdn2_EU27_2022_2025.json")
    new = mean([eg[("Q", "THS_PER", "T", "Y15-74", "M_LT3", "TOTAL", "EU27_2020", q)] for q in QUARTERS])
    V = jvr / (1.0 - jvr) * emp
    H = new / 3.0
    f_d, share = fill_share(H, V)
    return {"jvr": jvr, "occupied": emp, "vacancies": V, "hires": H, "f_d": f_d, "share": share}


def main() -> None:
    H, V, f_d, share = us_jolts()
    print(f"US JOLTS 2010-19: hires {H:,.0f} thousand a month, openings {V:,.0f} thousand; daily fill {f_d:.4f}; filled within a month {share:.3f} (paper: 0.040 and 0.65)")
    r = eu()
    print(f"EU-27 2022-Q1 to 2025-Q2: vacancy rate {r['jvr']:.3%}, occupied posts {r['occupied']:,.0f} thousand, vacancies {r['vacancies']:,.0f} thousand")
    print(f"  hires {r['hires']:,.0f} thousand a month (tenure under 3 months / 3); daily fill {r['f_d']:.4f}; filled within a month {r['share']:.3f}")
    print(f"  scaled to the paper's method (0.65 / {share:.3f}): {r['share'] * 0.65 / share:.3f}")


if __name__ == "__main__":
    main()
