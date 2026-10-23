"""Eloundou et al. (2024) LLM task exposure reweighted by EU-27 employment.

Antropic's m_2030 values (0.2 / 0.3 / 0.5) are "the low end, middle, and near the high end of
rated feasibility (Eloundou et al., 2024)": the employment-weighted averages of Eloundou's three
exposure measures over US occupations. Those measures are the share of an occupation's tasks for
which an LLM (alpha), an LLM with software built on it (beta, half weight on the second level) or
the widest definition (gamma, full weight) cuts the time needed by at least half. The ratings are
a property of the technology; only the employment weights are national. This script applies the
same occupation ratings to EU-27 employment.

Inputs, all in european_values/data/:
  eloundou_occ_level.csv     occupation-level ratings (GPT-4 "dv" and human), O*NET-SOC codes,
                             from github.com/openai/GPTs-are-GPTs (MIT), data/occ_level.csv
  oews_national_May2021.csv  US employment by SOC occupation, OEWS May 2021, from the same repo
  ibs_soc10_isco08.dta       SOC 2010 to ISCO-08 (4-digit) crosswalk, IBS Warsaw
                             (ibs.org.pl, onetsoc_to_isco_cws_ibs-2.zip)
  eurostat_lfsa_egai2d_EU27_2024_2025.json   EU-27 employment by ISCO-08 2-digit group
  eulfs_employment_isco3d_2024.csv           EU-27 employment by ISCO-08 3-digit group, from the
                             EU-LFS yearly microdata 2024 (compute_isco3d_lfs.R)

Method. O*NET-SOC codes are truncated to 6-digit SOC and ratings averaged within a SOC. Each
SOC is spread equally over the ISCO 2-digit groups the crosswalk maps it to. A group's rating
is the US-employment-weighted mean of the SOCs in it. The EU value is the EU-employment-weighted
mean of the group ratings. The US value computed the same way (through groups) equals the
direct US value up to the crosswalk's many-to-many splits, which measures the approximation.
Public EU data stop at 2-digit ISCO, so with them the EU weights act on the between-group mix
only. The EU-LFS microdata give the mix at 3 digits (the finest level in the scientific-use
files); the same steps at 3 digits make the within-group mix European too, and that run is the
one the table uses. Residual codes ending in 0 (occupation stated at 1 or 2 digits only, about
half a percent of employment) and the armed forces are left out of the 3-digit weights.

Run from the repository root:  uv run python european_values/compute_values/compute_exposure.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
MEASURES = ["alpha", "beta", "gamma"]
RATERS = ["dv", "human"]


def eu_employment(year: str = "2025") -> pd.Series:
    """EU-27 civilian employment by ISCO 2-digit group (OC11 ... OC96), thousand persons."""
    d = json.loads((DATA / "eurostat_lfsa_egai2d_EU27_2024_2025.json").read_text(encoding="utf-8"))
    ids, sizes = d["id"], d["size"]
    inv = {k: {v: kk for kk, v in d["dimension"][k]["category"]["index"].items()} for k in ids}
    rows = {}
    for flat, v in d["value"].items():
        i = int(flat)
        pos = {}
        for k, s in reversed(list(zip(ids, sizes))):
            pos[k] = i % s
            i //= s
        if inv["time"][pos["time"]] == year:
            rows[inv["isco08"][pos["isco08"]]] = v
    two_digit = {k[2:]: v for k, v in rows.items() if k.startswith("OC") and len(k) == 4 and k[2] != "0"}
    return pd.Series(two_digit, name="eu_emp").sort_index()


def eu_employment3() -> pd.Series:
    """EU-27 employment by ISCO 3-digit minor group from the LFS microdata, thousand persons."""
    d = pd.read_csv(DATA / "eulfs_employment_isco3d_2024.csv", dtype={"isco3d": str, "isco2d": str})
    d = d[d["employment_ths"].notna() & ~d["isco3d"].str.endswith("0") & (d["isco3d"].str[0] != "0")]
    return d.set_index("isco3d")["employment_ths"].rename("eu_emp").sort_index()


def main() -> None:
    occ = pd.read_csv(DATA / "eloundou_occ_level.csv")
    occ["soc"] = occ["O*NET-SOC Code"].str[:7].str.replace("-", "", regex=False)
    cols = [f"{r}_rating_{m}" for r in RATERS for m in MEASURES]
    by_soc = occ.groupby("soc")[cols].mean()
    # Anthropic's observed exposure (Massenkoff and McCrory 2026): share of an occupation's tasks
    # seen being done with Claude, weighted toward automation; the basis of m_anchor = 0.14.
    obs = pd.read_csv(DATA / "anthropic_job_exposure.csv", dtype={"occ_code": str})
    obs["soc"] = obs["occ_code"].str.replace("-", "", regex=False)
    by_soc = by_soc.join(obs.set_index("soc")["observed_exposure"].rename("anthropic_observed"), how="outer")
    cols = cols + ["anthropic_observed"]

    oews = pd.read_csv(DATA / "oews_national_May2021.csv", encoding="utf-8-sig", dtype=str)
    oews = oews[oews["O_GROUP"] == "detailed"].copy()
    oews["soc"] = oews["OCC_CODE"].str.replace("-", "", regex=False)
    oews["emp"] = pd.to_numeric(oews["TOT_EMP"].str.replace(",", ""), errors="coerce")
    us = oews[["soc", "emp"]].dropna().merge(by_soc, left_on="soc", right_index=True, how="inner")
    cover = us["emp"].sum() / oews["emp"].sum()

    def wmean(df: pd.DataFrame, w: str) -> pd.Series:
        out = {}
        for c in cols:
            ok = df[c].notna()
            out[c] = (df.loc[ok, c] * df.loc[ok, w]).sum() / df.loc[ok, w].sum()
        return pd.Series(out)

    us_direct = wmean(us, "emp")

    cw = pd.read_stata(DATA / "ibs_soc10_isco08.dta")
    cw["soc"] = cw["soc10"].astype(str).str.zfill(6)
    cw["isco4"] = cw["isco08"].astype(str).str.zfill(4)

    def by_group(digits: int, eu: pd.Series) -> tuple[pd.DataFrame, float, list[str], pd.Series, pd.Series, float]:
        """Group ratings at ``digits`` of ISCO, US and EU weighted means, and the EU coverage."""
        c = cw.assign(isco=cw["isco4"].str[:digits])[["soc", "isco"]].drop_duplicates()
        c["w"] = 1.0 / c.groupby("soc")["isco"].transform("count")
        spread = us.merge(c, on="soc", how="inner")
        matched = spread.drop_duplicates("soc")["emp"].sum() / us["emp"].sum()
        spread["emp_w"] = spread["emp"] * spread["w"]
        groups = spread.groupby("isco").apply(lambda g: wmean(g, "emp_w"), include_groups=False)
        groups["us_emp"] = spread.groupby("isco")["emp_w"].sum()
        groups = groups[groups.index.str[0] != "0"]  # armed forces, outside the civilian comparison
        groups = groups.join(eu, how="left")
        missing = groups[groups["eu_emp"].isna()].index.tolist()
        groups["eu_emp"] = groups["eu_emp"].fillna(0.0)
        return groups, matched, missing, wmean(groups, "us_emp"), wmean(groups, "eu_emp"), groups["eu_emp"].sum() / eu.sum()

    eu2, eu3 = eu_employment(), eu_employment3()
    groups, matched, missing, us_via_groups, eu_value2, eu_cover2 = by_group(2, eu2)
    groups3, matched3, missing3, us_via_groups3, eu_value, eu_cover3 = by_group(3, eu3)

    print(f"US occupations matched to ratings: {cover:.1%} of OEWS employment; to the crosswalk: {matched:.1%}")
    print(f"EU employment covered by groups with a rating: {eu_cover2:.1%} at 2 digits" + (f" (rated groups without EU employment: {missing})" if missing else "")
          + f", {eu_cover3:.1%} at 3 digits" + (f" ({len(missing3)} rated minor groups without EU employment)" if missing3 else ""))
    print(f"\n{'employment-weighted mean exposure':<36}{'US direct':>11}{'US via ISCO':>13}{'EU 2-digit':>12}{'EU 3-digit':>12}{'EU / US':>9}")
    labels = {f"{r}_rating_{m}": f"{'GPT-4' if r == 'dv' else 'human'} ratings, {m}" for r in RATERS for m in MEASURES}
    labels["anthropic_observed"] = "Anthropic observed exposure (2026)"
    for c, label in labels.items():
        print(f"{label:<36}{us_direct[c]:>11.3f}{us_via_groups3[c]:>13.3f}{eu_value2[c]:>12.3f}{eu_value[c]:>12.3f}{eu_value[c] / us_via_groups3[c]:>9.3f}")
    print("(US via ISCO and EU / US use the 3-digit run; the 2-digit column is the earlier public-data result)")
    print("\nAntropic m_2030 (modest / substantial / extreme): 0.2 / 0.3 / 0.5, read off the human alpha / beta / gamma means;")
    print("Antropic m_anchor: 0.14, the observed exposure averaged over occupations.")
    print("\nISCO 2-digit groups, human beta rating and employment shares (US via crosswalk, EU-27 2025):")
    g = groups.copy()
    g["us_share"] = g["us_emp"] / g["us_emp"].sum()
    g["eu_share"] = g["eu_emp"] / g["eu_emp"].sum()
    print(g[["human_rating_beta", "us_share", "eu_share"]].round(3).to_string())


if __name__ == "__main__":
    main()
