"""
Open-dataset replay for the virtual plant (SIM-01).

Replays real/benchmark sensor data through the existing canonical metrics instead of the
synthetic generators. Opt-in: `python -m simulator.cli --replay-dir data/datasets`.
Fetch the files first:  `python -m simulator.datasets fetch`

Only datasets cleared for commercial use are wired in (see docs/DATASETS.md for credits).
Signals whose physical range differs from our asset (test-rig pressure, metro compressor
current) are scaled to the asset's nominal value; temperatures and vibration are used as-is.
"""

import csv
import itertools
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from services.common.canonical import AssetOperationalStatus as St

Row = tuple[dict[str, float], St | None]  # (metric overrides, status override)

UCI = "https://archive.ics.uci.edu/static/public"
DATASETS: dict[str, dict[str, str]] = {
    "ai4i": {
        "title": "AI4I 2020 Predictive Maintenance Dataset",
        "url": f"{UCI}/601/ai4i+2020+predictive+maintenance+dataset.zip",
        "licence": "CC BY 4.0",
        "credit": "S. Matzka (2020), UCI Machine Learning Repository. DOI 10.24432/C5HS5C",
        "used_for": "CNC machines",
    },
    "metropt3": {
        "title": "MetroPT-3 Dataset",
        "url": f"{UCI}/791/metropt+3+dataset.zip",
        "licence": "CC BY 4.0",
        "credit": "Davari, Veloso, Ribeiro & Gama (2021), UCI Machine Learning Repository. "
        "DOI 10.24432/C5VW3R",
        "used_for": "Air compressors",
    },
    "hydraulic": {
        "title": "Condition Monitoring of Hydraulic Systems",
        "url": f"{UCI}/447/condition+monitoring+of+hydraulic+systems.zip",
        "licence": "CC BY 4.0",
        "credit": "Helwig, Pignanelli & Schuetze (2015), UCI Machine Learning Repository. "
        "DOI 10.24432/C5CW21",
        "used_for": "Coolant pumps",
    },
}


def fetch(root: Path) -> None:
    """Download and extract every dataset into root/<name>/ (skips ones already present)."""
    for name, meta in DATASETS.items():
        dest = root / name
        if dest.exists() and any(dest.iterdir()):
            print(f"{name}: already present")
            continue
        dest.mkdir(parents=True, exist_ok=True)
        zpath = dest / "download.zip"
        print(f"{name}: downloading {meta['url']}")
        urllib.request.urlretrieve(meta["url"], zpath)
        with zipfile.ZipFile(zpath) as z:
            for member in z.namelist():
                # flat archives only: refuse anything that would escape dest
                if Path(member).name != member:
                    raise ValueError(f"unexpected path in {name} archive: {member}")
            z.extractall(dest)
        zpath.unlink()


def _forever(make: Callable[[], Iterator[Row]], offset: int) -> Iterator[Row]:
    """Loop a finite reader endlessly, starting `offset` rows in (so assets differ)."""
    yield from itertools.islice(make(), offset, None)
    while True:
        yield from make()


# --------------------------------------------------------------------------- AI4I -> CNC
def ai4i_rows(root: Path, nominal: dict[str, Any]) -> Iterator[Row]:
    """One row per machined part. Dataset means: 1539 rpm, 40 Nm; max torque 76.6 Nm."""
    rpm_nom = float(nominal.get("spindle_rpm", 8000))
    kw_nom = float(nominal.get("power_kw", 12.0))
    with open(root / "ai4i" / "ai4i2020.csv", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rpm, torque = float(r["Rotational speed [rpm]"]), float(r["Torque [Nm]"])
            yield (
                {
                    "spindle_rpm": round(rpm * rpm_nom / 1539.0, 1),
                    "spindle_load_pct": round(torque / 76.6 * 100.0, 1),
                    "power_kw": round(kw_nom * (rpm * torque) / (1539.0 * 40.0), 2),
                    "spindle_temp_c": round(float(r["Process temperature [K]"]) - 273.15, 2),
                    "tool_wear_min": float(r["Tool wear [min]"]),
                },
                St.FAULT if r["Machine failure"] == "1" else None,
            )


# ------------------------------------------------------------------ MetroPT-3 -> compressor
def metropt3_rows(root: Path, nominal: dict[str, Any]) -> Iterator[Row]:
    """One row per 10 s. Typical loaded values in the dataset: ~9 bar, ~6 A."""
    bar_nom = float(nominal.get("discharge_pressure_bar", 7.4))
    kw_nom = float(nominal.get("motor_power_kw", 30.0))
    path = root / "metropt3" / "MetroPT3(AirCompressor).csv"
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            power = round(kw_nom * float(r["Motor_current"]) / 6.0, 2)
            yield (
                {
                    "discharge_pressure_bar": round(float(r["TP3"]) * bar_nom / 9.0, 2),
                    "discharge_temp_c": round(float(r["Oil_temperature"]), 2),
                    "motor_power_kw": power,
                },
                St.RUNNING if power > 5.0 else St.IDLE,
            )


# ------------------------------------------------------------------- Hydraulic -> pumps
def hydraulic_rows(root: Path, nominal: dict[str, Any]) -> Iterator[Row]:
    """One row per second (60 per load cycle). Rig typicals: 160 bar, 8 l/min, 2500 W."""
    bar_nom = float(nominal.get("discharge_bar", 5.5))
    flow_nom = float(nominal.get("flow_m3h", 40.0))
    kw_nom = float(nominal.get("power_kw", 9.0))
    d = root / "hydraulic"
    names = ("TS1", "VS1", "PS1", "FS1", "EPS1")
    files = [open(d / f"{n}.txt", encoding="ascii") for n in names]  # noqa: SIM115
    try:
        for lines in zip(*files, strict=False):
            ts1, vs1, ps1, fs1, eps1 = ([float(x) for x in ln.split()] for ln in lines)
            for s in range(60):
                yield (
                    {
                        "motor_temp_c": ts1[s],
                        "vibration_mm_s": vs1[s],
                        "discharge_bar": round(ps1[s * 100] * bar_nom / 160.0, 2),
                        "flow_m3h": round(fs1[s * 10] * flow_nom / 8.0, 2),
                        "power_kw": round(eps1[s * 100] * kw_nom / 2500.0, 2),
                    },
                    None,
                )
    finally:
        for f in files:
            f.close()


# asset type -> (reader, seconds each row is held, rows between consecutive assets)
SOURCES: dict[str, tuple[Callable[[Path, dict[str, Any]], Iterator[Row]], float, int]] = {
    "cnc_machine": (ai4i_rows, 60.0, 1500),
    "air_compressor": (metropt3_rows, 10.0, 50_000),
    "centrifugal_pump": (hydraulic_rows, 1.0, 400 * 60),
}


class Replay:
    """Holds each dataset row for its sampling period of simulated time."""

    def __init__(self, rows: Iterator[Row], period_s: float):
        self._rows, self._period = rows, period_s
        self._age, self._cur = period_s, None

    def next(self, dt: float) -> Row:
        self._age += dt
        if self._age >= self._period:
            self._cur, self._age = next(self._rows), 0.0
        return self._cur


def make_replay(type_id: str, root: Path, nominal: dict[str, Any], index: int) -> Replay | None:
    """Replay for the index-th asset of this type, or None if the type has no dataset."""
    if type_id not in SOURCES:
        return None
    reader, period, stride = SOURCES[type_id]
    return Replay(_forever(lambda: reader(root, nominal), index * stride), period)


if __name__ == "__main__":
    if sys.argv[1:2] != ["fetch"]:
        sys.exit("usage: python -m simulator.datasets fetch [dir]")
    fetch(Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/datasets"))
