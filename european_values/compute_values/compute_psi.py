"""EU automation share of AI use (psi) from the Anthropic Economic Index country breakdown.

Antropic's psi is the share of AI-performed task instances that capital performs outright rather
than assisting a worker. Its low rung (0.50) is "similar to the current automation-like share of
use (Appel et al., 2025)": the share of Claude.ai conversations classified as automation
(directive, feedback loop) rather than augmentation (validation, task iteration, learning). The
API share (about 0.77) sits near the substantial rung. The Economic Index publishes the Claude.ai
split by country, so the EU-27 share can be read directly; the API split is global only.

Inputs (downloaded from huggingface.co/datasets/Anthropic/EconomicIndex on first run, cached
outside the repository in <temp>/aei_economic_index, or in $AEI_CACHE):
  release_2025_09_15/data/output/aei_enriched_claude_ai_2025-08-04_to_2025-08-11.csv
      variable automation_pct by country, one week of August 2025, weight usage_count
  release_2026_06_26/data/aei_claude_ai_2026-06-26.csv
      metric collaboration_bucket_automation_pct, category overall, April and May 2026,
      weight usage_pct (share of global usage)
  data/eurostat_lfsi_emp_a_2025_all.json   employment aged 20-64, all member states, for an employment-
      weighted EU-27 variant

Output: data/aei_automation_by_country.csv, the compact extract (period, geo_id, automation and
augmentation shares, usage weight) for every published geography.

Run from the repository root:  uv run python european_values/compute_values/compute_psi.py
"""

from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

from compute_d_anchor import jsonstat_by_geo

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "aei_automation_by_country.csv"
CACHE = Path(os.environ.get("AEI_CACHE", tempfile.gettempdir())) / "aei_economic_index"
BASE = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/"
FILES = {
    "2025-08": "release_2025_09_15/data/output/aei_enriched_claude_ai_2025-08-04_to_2025-08-11.csv",
    "2026": "release_2026_06_26/data/aei_claude_ai_2026-06-26.csv",
}
EU27 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ", "DNK": "DK",
    "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "EL", "HUN": "HU", "IRL": "IE",
    "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU", "MLT": "MT", "NLD": "NL", "POL": "PL",
    "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI", "ESP": "ES", "SWE": "SE",
}
US_PSI = {"modest": 0.50, "substantial": 0.75, "extreme": 0.90}


def fetch(key: str) -> Path:
    path = CACHE / Path(FILES[key]).name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"downloading {FILES[key]} ...")
        urllib.request.urlretrieve(BASE + FILES[key], path)
    return path


def extract_2025() -> pd.DataFrame:
    df = pd.read_csv(fetch("2025-08"))
    df = df[df["geography"].isin(["country", "global"])]
    w = df[df["variable"].isin(["automation_pct", "augmentation_pct", "usage_count"])]
    w = w.pivot_table(index="geo_id", columns="variable", values="value").reset_index()
    w["period"] = "2025-08"
    return w.rename(columns={"usage_count": "usage_weight"})


def extract_2026() -> pd.DataFrame:
    df = pd.read_csv(fetch("2026"))
    df = df[(df["category_name"] == "overall") & (df["geo_level"].isin(["country", "global"]))]
    keep = {
        "collaboration_bucket_automation_pct": "automation_pct",
        "collaboration_bucket_augmentation_pct": "augmentation_pct",
        "usage_pct": "usage_weight",
    }
    w = df[df["metric_id"].isin(keep)]
    w = w.pivot_table(index=["geo_id", "date_start"], columns="metric_id", values="value").reset_index()
    w = w.rename(columns=keep)
    w["period"] = w["date_start"].str[:7]
    return w.drop(columns="date_start")


def summarise(ext: pd.DataFrame) -> None:
    emp = jsonstat_by_geo(DATA / "eurostat_lfsi_emp_a_2025_all.json", "")
    print(f"{'period':<9}{'EU-27 (usage w.)':>17}{'EU-27 (emp. w.)':>16}{'US':>7}{'UK':>7}{'global':>8}{'EU/US':>7}")
    for period, g in ext.groupby("period"):
        g = g.set_index("geo_id")
        eu = g[g.index.isin(EU27)].dropna(subset=["automation_pct", "usage_weight"])
        eu_w = eu["automation_pct"].mul(eu["usage_weight"]).sum() / eu["usage_weight"].sum()
        ew = pd.Series({k: emp[v] for k, v in EU27.items()}).reindex(eu.index)
        eu_e = eu["automation_pct"].mul(ew).sum() / ew.sum()
        us, uk, gl = (g.loc[k, "automation_pct"] for k in ("USA", "GBR", "GLOBAL"))
        print(f"{period:<9}{eu_w:>17.1f}{eu_e:>16.1f}{us:>7.1f}{uk:>7.1f}{gl:>8.1f}{eu_w / us:>7.2f}")
    recent = ext[ext["period"].str.startswith("2026")]
    eu = recent[recent["geo_id"].isin(EU27)].groupby("geo_id")["automation_pct"].mean().sort_values()
    print("\nEU-27 members, automation share of Claude.ai use, mean of April-May 2026:")
    print(eu.round(1).to_string())
    us_now = recent[recent["geo_id"] == "USA"]["automation_pct"].mean()
    eu_now = recent[recent["geo_id"].isin(EU27)]
    eu_now = eu_now["automation_pct"].mul(eu_now["usage_weight"]).sum() / eu_now["usage_weight"].sum()
    ratio = eu_now / us_now
    scaled = {k: round(float(v * ratio), 2) for k, v in US_PSI.items()}
    print(f"\nAntropic psi ladder {US_PSI}; scaled by the 2026 EU/US ratio {ratio:.2f}: {scaled}")


def main() -> None:
    ext = pd.concat([extract_2025(), extract_2026()], ignore_index=True)
    ext = ext[["period", "geo_id", "automation_pct", "augmentation_pct", "usage_weight"]]
    ext.sort_values(["period", "geo_id"]).to_csv(OUT, index=False, float_format="%.4f")
    print(f"wrote {OUT.relative_to(DATA.parent.parent)} ({len(ext)} rows)\n")
    summarise(ext)


if __name__ == "__main__":
    main()
