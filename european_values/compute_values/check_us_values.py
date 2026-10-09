"""Check that every US value in calibration_parameters.yaml matches the code's defaults.

Run from the repository root:  uv run python european_values/compute_values/check_us_values.py
Rounded Table 1 entries are compared at their printed precision.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))
from econ_scenarios import SCENARIOS, Calibration  # noqa: E402

HERE = Path(__file__).resolve().parent
spec = yaml.safe_load((HERE.parent / "calibration_parameters.yaml").read_text(encoding="utf-8"))
cal = Calibration()


def decimals(x: float) -> int:
    s = repr(float(x))
    return len(s.split(".")[1]) if "." in s and "e" not in s else 0


def close(printed: float, actual: float) -> bool:
    d = decimals(printed)
    return round(actual, d) == round(float(printed), d)


failures: list[str] = []
checked = 0
for p in spec["parameters"]:
    code = p.get("code")
    if not code:
        continue
    name = code.split()[0].split(".")[1]
    us = p["us_value"]
    if code.startswith("Scenario."):
        for sc, v in us.items():
            actual = getattr(SCENARIOS[sc], name)
            checked += 1
            if not close(v, actual):
                failures.append(f"{p['id']}[{sc}]: yaml {v} vs code {actual}")
    else:
        actual = getattr(cal, name)
        if isinstance(us, dict):  # sep_rel, a (cognitive, other) pair
            for v, a in zip(us.values(), actual):
                checked += 1
                if not close(v, a):
                    failures.append(f"{p['id']}: yaml {v} vs code {a}")
        else:
            checked += 1
            if not close(us, actual):
                failures.append(f"{p['id']}: yaml {us} vs code {actual}")

print(f"{checked} US values checked against the code")
for f in failures:
    print("MISMATCH", f)
sys.exit(1 if failures else 0)
