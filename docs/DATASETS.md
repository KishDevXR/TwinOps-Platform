# Open datasets used by the simulator

The simulator can replay these datasets through the canonical telemetry metrics
(`python -m simulator.cli --replay-dir data/datasets`). Files are downloaded by
`python -m simulator.datasets fetch` into `data/datasets/`, which is not committed.

| Dataset | Drives | Licence | Credit |
|---|---|---|---|
| AI4I 2020 Predictive Maintenance Dataset | CNC machines | CC BY 4.0 | S. Matzka (2020), UCI Machine Learning Repository. DOI 10.24432/C5HS5C |
| MetroPT-3 Dataset | Air compressors | CC BY 4.0 | Davari, Veloso, Ribeiro & Gama (2021), UCI Machine Learning Repository. DOI 10.24432/C5VW3R |
| Condition Monitoring of Hydraulic Systems | Coolant pumps | CC BY 4.0 | Helwig, Pignanelli & Schütze (2015), UCI Machine Learning Repository. DOI 10.24432/C5CW21 |

## Changes made to the data

CC BY 4.0 requires saying whether the material was changed. It is:

- Values are mapped onto TwinOps metric names and replayed in a loop, each asset starting at a different row.
- Signals whose range differs from the simulated asset are scaled linearly to the asset's nominal rating:
  AI4I speed and power; MetroPT-3 pressure and motor current (converted to power); Hydraulic pressure, flow and power.
- Temperatures and vibration are used as recorded (AI4I temperatures converted from K to °C).
- AI4I is synthetic data modelled on industry data, with one row per part, so each row is held for a 60 s machining cycle.

## Not used

- **NASA IMS Bearings** (public domain): planned for bearing remaining-life models; not wired in yet.
- **MIMII 1.0** (CC BY-SA 4.0): share-alike, so derived data would have to carry the same licence. Left out.
- **NASA Milling**: no explicit licence found. Do not ship until NASA PCoE confirms.
- Robots, conveyors, AHUs, the chiller, energy meters, docks and forklifts have no dataset and use the simulator's own models.

Licence terms were taken from the project's dataset sheet
(`Documents/Commercial-Use Datasets for Digital Twin Simulator.xlsx`); confirm them on the source pages before a commercial release.
