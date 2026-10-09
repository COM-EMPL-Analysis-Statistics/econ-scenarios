"""EU diffusion share d from the JRC AIM-WORK survey: adoption x task hand-off x frequency.

The model's d_t is the share of the affected task instances that are performed with AI. AIM-WORK
(JRC, fielded late 2024 to early 2025, ~70,000 respondents, all EU-27 member states, 4-digit
ISCO) asks each worker whether they used an AI tool in their main job in the last 12 months
(B20), how often (B21), and, for eight AI-feasible task types (writing, data and numbers,
brainstorming, customer advice, images, translation, planning, transcription), whether they hand
that task off to the tool. That is an instance measure of d in concept, measured for the EU
directly rather than scaled from the US:

    d  =  sum_i w_i * adopt_i * handoff_i * f_i  /  sum_i w_i

over workers in cognitive occupations (ISCO 1-4 and 52, where the affected tasks sit), with
  handoff_i  the share of the eight task types the adopter hands off (an upper bound where a
             job lacks some of the eight; the "present tasks" variant counts only task types in
             which the occupation is above the median intensity)
  f_i        the share of a handed-off task's instances done with AI, read off the frequency
             answer. Three readings are reported: headcount (f = 1 for every adopter), weekly
             (f = 1 if used at least weekly, else 0) and graded (several times a day 1.0, about
             once a day 0.6, several times a week 0.35, about once a week 0.15, a few times a
             month 0.05, less often 0.02). The graded weights are a judgement.

Inputs: the cleaned estimation sample of De Schouwer, "Hard to Start? Task-Level Evidence on
Generative AI Adoption" (AI_Tasks/data/clean/workers.csv and tasks.csv: employed respondents
aged 16-65 with valid occupation, weights w1_pop adjusted to Eurostat employment by sex, age and
education within country) and the frequency answer B21 from the raw file. The microdata stay
outside the repository; only the aggregates below are written to data/.

Run with a Python that has pandas and pyreadstat (the AI_Tasks conda environment), from the
repository root:
    python european_values/compute_values/compute_d_anchor_aimwork.py [path to AI_Tasks]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

AI_TASKS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\desch\Dropbox\AI_Tasks")
OUT = Path(__file__).resolve().parent.parent / "data" / "aimwork_d_anchor_aggregates.csv"
TASKS = ["text", "data", "brainstorm", "customer", "image", "translation", "planning", "transcription"]
GRADED = {
    "Several times a day": 1.0,
    "About once a day": 0.6,
    "Several times a week": 0.35,
    "About once a week": 0.15,
    "A few times a month": 0.05,
    "Less often": 0.02,
}
WEEKLY = {k: 1.0 if v >= 0.15 else 0.0 for k, v in GRADED.items()}


def cognitive(isco: pd.Series) -> pd.Series:
    s = isco.astype(str).str.zfill(4)
    return s.str[0].isin(list("1234")) | s.str.startswith("52")


def main() -> None:
    import pyreadstat

    workers = pd.read_csv(AI_TASKS / "data/clean/workers.csv", dtype={"isco": str})
    tasks = pd.read_csv(AI_TASKS / "data/clean/tasks.csv", dtype={"isco": str})
    raw, _ = pyreadstat.read_sav(str(AI_TASKS / "data/AIMWORK/aimwork_EMPL.sav"), apply_value_formats=True,
                                 usecols=["Respondent_Serial", "B21"])
    raw["B21"] = raw["B21"].astype(str)
    workers = workers.merge(raw, on="Respondent_Serial", how="left")

    # hand-off share over the eight task types, and over the task types present in the job
    # (occupation above the median standardised intensity, z > 0, in that task)
    wide = tasks.pivot_table(index="Respondent_Serial", columns="task", values="use", aggfunc="first")
    wide = wide.reindex(columns=TASKS)
    workers = workers.merge(wide, left_on="Respondent_Serial", right_index=True, how="left")
    handed = workers[TASKS].sum(axis=1, min_count=1)
    answered = workers[TASKS].notna().sum(axis=1)
    workers["handoff_all"] = handed / 8.0
    present = pd.DataFrame({t: (workers["z_" + t] > 0).astype(float) for t in TASKS})
    handed_present = (workers[TASKS].fillna(0.0) * present).sum(axis=1)
    n_present = present.sum(axis=1).clip(lower=1)
    workers["handoff_present"] = handed_present / n_present
    adopters_no_items = (workers["adopt"] == 1) & (answered == 0)
    for col in ("handoff_all", "handoff_present"):
        # adopters who skipped the task items get the mean hand-off of adopters who answered
        fill = (workers.loc[(workers["adopt"] == 1) & (answered > 0), col] * workers.loc[(workers["adopt"] == 1) & (answered > 0), "w1_pop"]).sum() / workers.loc[(workers["adopt"] == 1) & (answered > 0), "w1_pop"].sum()
        workers.loc[adopters_no_items, col] = fill
        workers.loc[workers["adopt"] == 0, col] = 0.0

    workers["f_head"] = 1.0
    workers["f_weekly"] = workers["B21"].map(WEEKLY).fillna(0.0)
    workers["f_graded"] = workers["B21"].map(GRADED).fillna(0.0)
    workers["cog"] = cognitive(workers["isco"])

    def d(df: pd.DataFrame, handoff: str, f: str) -> float:
        return float((df["w1_pop"] * df["adopt"] * df[handoff] * df[f]).sum() / df["w1_pop"].sum())

    rows = []
    for pop, df in (("cognitive occupations (ISCO 1-4, 52)", workers[workers["cog"]]), ("all workers", workers)):
        adoption = float((df["w1_pop"] * df["adopt"]).sum() / df["w1_pop"].sum())
        for handoff in ("handoff_all", "handoff_present"):
            for f in ("f_head", "f_weekly", "f_graded"):
                rows.append({"population": pop, "handoff": handoff, "frequency": f, "adoption": adoption, "d": d(df, handoff, f)})
    res = pd.DataFrame(rows)
    by_cc = workers[workers["cog"]].groupby("cc").apply(
        lambda g: pd.Series({"adoption": (g["w1_pop"] * g["adopt"]).sum() / g["w1_pop"].sum(),
                             "d_graded_present": d(g, "handoff_present", "f_graded"),
                             "d_head_all": d(g, "handoff_all", "f_head")}), include_groups=False)
    OUT.parent.mkdir(exist_ok=True)
    pd.concat([res.assign(cc="EU27"), by_cc.reset_index().assign(population="cognitive occupations", handoff="", frequency="")]).to_csv(OUT, index=False)

    n_cog = int(workers["cog"].sum())
    print(f"AIM-WORK estimation sample: {len(workers):,} workers, {n_cog:,} in cognitive occupations; weights w1_pop")
    print(f"\n{'population':<38}{'hand-off share':<18}{'frequency':<10}{'adoption':>10}{'d':>8}")
    for r in rows:
        print(f"{r['population']:<38}{r['handoff'].replace('handoff_', 'over '):<18}{r['frequency'].replace('f_', ''):<10}{r['adoption']:>10.3f}{r['d']:>8.3f}")
    print("\nBy member state, cognitive occupations: adoption, d (graded, present tasks), d (headcount, all eight)")
    print(by_cc.sort_values("adoption", ascending=False).round(3).to_string())
    print(f"\nwrote {OUT.name}")


if __name__ == "__main__":
    main()
