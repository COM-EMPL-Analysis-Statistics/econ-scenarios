"""Build the model's Calibration and Scenarios from calibration_parameters.yaml.

    from load_params import load, load_experiment
    cal, scenarios = load("eu")                       # the EU baseline
    cal, scenarios = load("eu", {"eps": 6})           # the baseline with one change
    for run in load_experiment("experiments/eps_table5.yaml"):
        sim = simulate(run.scenarios["substantial"], run.calibration)

Semantics: the code's defaults are the US calibration (compute_values/check_us_values.py proves
they match the YAML's `us_value` entries, which are Table 1's rounded prints). `load("eu")` starts
from those defaults and overrides every parameter whose `eu.value` is filled in, whatever its
`status`. `load("us")` returns the defaults untouched. An EU calibration with no EU values filled
in is therefore the paper's, to the last digit.

calibration_parameters.yaml is the baseline and is never edited to run a variant. A variant is an
experiment file in experiments/, listing only what changes:

    name: eps table 5
    description: capital-supply elasticity over Antropic's Table 5 range
    base: eu                    # or us
    overrides: {m_2030: {modest: 0.15, substantial: 0.25, extreme: 0.45}}   # fixed changes
    sweep: {eps: [1, 3, 6, .inf]}                                          # one run per value

Keys of `overrides` and `sweep` are parameter ids from the YAML. Several sweep keys give the full
grid. Derived parameters (g, one_minus_phi_R) cannot be set; change their inputs.

Run as a script to see which EU overrides are in effect and the 2030 readout they give:

    uv run python european_values/load_params.py
"""

from __future__ import annotations

import dataclasses
import itertools
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from econ_scenarios import SCENARIOS, Calibration, Scenario  # noqa: E402

HERE = Path(__file__).resolve().parent
YAML = HERE / "calibration_parameters.yaml"
EXPERIMENTS = HERE / "experiments"
SCENARIO_NAMES = ("modest", "substantial", "extreme")

# Parameters the dataclass does not take directly but derives; the YAML sets them through these.
CALIBRATION_FIELD = {
    "share_C": "share_C_override",
    "sep_rel": "sep_rel_override",
}

Kwargs = dict[str, object]
ScenarioKwargs = dict[str, dict[str, object]]
_NOTED: set[str] = set()  # parameters already reported as unused by the model


def _spec() -> dict[str, dict]:
    """The YAML's parameters, by id."""
    spec = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    return {p["id"]: p for p in spec["parameters"]}


def _field_name(code: str) -> str:
    """'Calibration.share_C (property; ...)' -> 'share_C'."""
    return code.split()[0].split(".", 1)[1]


def _apply(pid: str, value: object, params: dict[str, dict], cal_kw: Kwargs, sc_kw: ScenarioKwargs, strict: bool) -> None:
    """Put one parameter's value into the calibration or scenario kwargs."""
    if pid not in params:
        msg = f"unknown parameter id {pid!r}; ids are those of calibration_parameters.yaml"
        raise KeyError(msg)
    p = params[pid]
    code = p.get("code")
    if not code:
        if strict:
            msg = f"{pid} has no code field: the model does not use it"
            raise ValueError(msg)
        if pid not in _NOTED:
            _NOTED.add(pid)
            print(f"note: {pid} has an EU value but no code field; ignored", file=sys.stderr)
        return
    if p.get("derived") and pid != "m_ceiling":
        msg = f"{pid} is derived ({p.get('formula')}); set its inputs, not its value"
        raise ValueError(msg)
    name = _field_name(code)
    if code.startswith("Scenario."):
        for s in SCENARIO_NAMES:
            sc_kw[s][name] = value[s] if isinstance(value, dict) else value
    else:
        name = CALIBRATION_FIELD.get(name, name)
        if isinstance(value, dict):  # sep_rel {cognitive, other}
            value = (float(value["cognitive"]), float(value["other"]))
        cal_kw[name] = value


def overrides(region: str = "eu", extra: dict[str, object] | None = None) -> tuple[Kwargs, ScenarioKwargs]:
    """The (calibration kwargs, {scenario: kwargs}) for ``region``, plus ``extra`` {id: value}."""
    if region not in ("us", "eu"):
        msg = f"region must be 'us' or 'eu', got {region!r}"
        raise ValueError(msg)
    params = _spec()
    cal_kw: Kwargs = {}
    sc_kw: ScenarioKwargs = {s: {} for s in SCENARIO_NAMES}
    if region == "eu":
        for pid, p in params.items():
            value = p["eu"].get("value")
            if value is not None:
                _apply(pid, value, params, cal_kw, sc_kw, strict=False)
    for pid, value in (extra or {}).items():
        _apply(pid, value, params, cal_kw, sc_kw, strict=True)
    return cal_kw, sc_kw


def load(region: str = "eu", extra: dict[str, object] | None = None) -> tuple[Calibration, dict[str, Scenario]]:
    """The Calibration and the three Scenarios for ``region``, with ``extra`` {id: value} on top."""
    cal_kw, sc_kw = overrides(region, extra)
    cal = Calibration(**cal_kw)
    scenarios = {s: dataclasses.replace(SCENARIOS[s], **sc_kw[s]) for s in SCENARIO_NAMES}
    return cal, scenarios


@dataclasses.dataclass(frozen=True)
class Run:
    """One point of an experiment: its label, the parameter values that define it, and the model inputs."""

    experiment: str
    label: str
    base: str
    point: dict[str, object]
    calibration: Calibration
    scenarios: dict[str, Scenario]


def _fmt(v: object) -> str:
    if isinstance(v, dict):
        return "/".join(str(x) for x in v.values())
    return str(v)


def load_experiment(path: str | Path) -> list[Run]:
    """Every run an experiment file defines: its fixed overrides, times each point of its sweep."""
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = EXPERIMENTS / path
    exp = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = exp.get("name") or path.stem
    base = exp.get("base", "eu")
    fixed: dict[str, object] = dict(exp.get("overrides") or {})
    sweep: dict[str, list] = dict(exp.get("sweep") or {})
    for k, v in sweep.items():
        if not isinstance(v, list):
            msg = f"{path.name}: sweep {k!r} must be a list of values"
            raise ValueError(msg)
    keys = list(sweep)
    runs: list[Run] = []
    for combo in itertools.product(*(sweep[k] for k in keys)) if keys else [()]:
        point = {**fixed, **dict(zip(keys, combo))}
        label = name if not keys else name + " [" + ", ".join(f"{k}={_fmt(v)}" for k, v in zip(keys, combo)) + "]"
        cal, scenarios = load(base, point)
        runs.append(Run(name, label, base, point, cal, scenarios))
    return runs


def main() -> None:
    from econ_scenarios import readout, simulate

    cal_kw, sc_kw = overrides("eu")
    base = Calibration()
    print("EU overrides on the calibration:")
    if not cal_kw:
        print("  none")
    for k, v in cal_kw.items():
        print(f"  {k:<18} {v!r:<12} (US {getattr(base, k)!r})")
    print("EU overrides on the scenarios:")
    if not any(sc_kw.values()):
        print("  none")
    for s, kw in sc_kw.items():
        for k, v in kw.items():
            print(f"  {s:<12} {k:<12} {v!r:<10} (US {getattr(SCENARIOS[s], k)!r})")

    rows = ["gdp", "wage_avg", "wage_C", "wage_N", "labor_share", "employment_C", "unemployment"]
    out = {}
    for region in ("us", "eu"):
        cal, scenarios = load(region)
        out[region] = {s: readout(simulate(scenarios[s], cal)) for s in SCENARIO_NAMES}
    print(f"\n{'2030 readout':<16}" + "".join(f"{s[:3] + ' US':>10}{s[:3] + ' EU':>10}" for s in SCENARIO_NAMES))
    for r in rows:
        line = f"{r:<16}"
        for s in SCENARIO_NAMES:
            line += f"{out['us'][s][r]:>10.2f}{out['eu'][s][r]:>10.2f}"
        print(line)


if __name__ == "__main__":
    main()
