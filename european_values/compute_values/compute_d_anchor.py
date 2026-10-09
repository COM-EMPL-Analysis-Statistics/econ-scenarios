"""EU / US AI-adoption ratios behind d_anchor.

Antropic's d_anchor = 0.10 is a judgement from the Census BTOS 2026 AI supplement. The EU value
scales it by the EU / US ratio on the comparable adoption measures:

  worker side   Bick, Blandin, Deming, Fuchs-Schuendeln and Jessen (2026), "Mind the Gap",
                St. Louis Fed WP 2026-003, Figures 2 and 3a: share of workers using generative AI
                for work and share of all work hours spent using it, survey of Jan-Feb 2026.
                Country figures are transcribed below; the EU-5 value weights them by 2025
                employment aged 20-64 (Eurostat lfsi_emp_a, extract in data/).
  firm side     Eurostat isoc_eb_ai, enterprises with 10+ employees, 2025: AI used for production
                processes (E_AI_PPP) and any AI technology (E_AI_TANY), EU-27, extract
                eurostat_isoc_eb_ai_ppp_2024_2025.json in data/ (the 2023-2025 extract holds
                the by-size and generative-AI series);
                the US figures are those Bick et al. report from BTOS (7% production, early
                2025) and project for any purpose (34%).

Run from the repository root:  uv run python european_values/compute_values/compute_d_anchor.py
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Bick et al. (2026), Figure 2 and Figure 3a, percent, Jan-Feb 2026.
WORKERS_USING = {"US": 43.0, "UK": 36.3, "SE": 35.6, "NL": 35.6, "DE": 31.5, "FR": 28.1, "IT": 25.6}
HOURS_SHARE = {"US": 5.2, "UK": 2.8, "SE": 2.5, "NL": 2.2, "DE": 1.7, "FR": 1.5, "IT": 1.6}
EU5 = ["DE", "FR", "IT", "NL", "SE"]
US_FIRMS_PRODUCTION = 7.0  # BTOS, Q1 2025, "AI in producing goods or services"
US_FIRMS_ANY = 34.0  # Bick et al. projection from the production rate


def jsonstat_by_geo(path: Path, key: str) -> dict[str, float]:
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
        if "indic_is" in ids and inv["indic_is"][pos["indic_is"]] != key:
            continue
        if "time" in ids and inv["time"][pos["time"]] != "2025":
            continue
        if "size_emp" in ids and inv["size_emp"][pos["size_emp"]] != "GE10":
            continue
        out[inv["geo"][pos["geo"]]] = v
    return out


def main() -> None:
    emp = jsonstat_by_geo(DATA / "eurostat_lfsi_emp_a_2025.json", "")
    w = {g: emp[g] for g in EU5}
    tot = sum(w.values())
    using = sum(WORKERS_USING[g] * w[g] for g in EU5) / tot
    hours = sum(HOURS_SHARE[g] * w[g] for g in EU5) / tot
    firms = jsonstat_by_geo(DATA / "eurostat_isoc_eb_ai_ppp_2024_2025.json", "E_AI_PPP")
    firms_any = jsonstat_by_geo(DATA / "eurostat_isoc_eb_ai_ppp_2024_2025.json", "E_AI_TANY")
    eu_prod, eu_any = firms["EU27_2020"], firms_any["EU27_2020"]

    print(f"EU-5 = {tot / emp['EU27_2020']:.0%} of EU-27 employment aged 20-64 (2025)")
    print(f"{'measure':<52}{'US':>7}{'EU':>7}{'ratio':>8}")
    rows = [
        ("workers using genAI for work, 2026 (EU-5 weighted)", WORKERS_USING["US"], using),
        ("share of all work hours using genAI, 2026 (EU-5)", HOURS_SHARE["US"], hours),
        ("firms using AI for production, 2025 (EU-27, 10+)", US_FIRMS_PRODUCTION, eu_prod),
        ("firms using AI for any purpose, 2025 (EU-27, 10+)", US_FIRMS_ANY, eu_any),
    ]
    for label, us, eu in rows:
        print(f"{label:<52}{us:>7.1f}{eu:>7.1f}{eu / us:>8.2f}")
    print("\nd_anchor EU = 0.10 x 0.6 = 0.06 (firm-side ratio); range 0.03 (hours) to 0.07 (headcount)")


if __name__ == "__main__":
    main()
