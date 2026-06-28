# Industrial Data Sources for Testing

## Mock Data Generator (Built-in)

The fastest way to test without downloading anything:

```bash
# Generate CSV with pump data, normal scenario
python services/datasets/mock_generator.py --preset pump --scenario normal --csv data/pump_normal.csv --csv-rows 1000

# Generate with drift scenario
python services/datasets/mock_generator.py --preset motor --scenario drift --csv data/motor_drift.csv

# Stream directly to Kafka/Redpanda
python services/datasets/mock_generator.py --preset all --scenario spike --rate 25 --topic industrial.normalized
```

### Presets
- `pump` — 9 tags (3 pumps × temperature/vibration/pressure)
- `motor` — 8 tags (2 motors × current/voltage/RPM/temperature)
- `turbine` — 5 tags (power/RPM/inlet temp/outlet temp/vibration)
- `all` — 22 tags combined

### Scenarios
- `normal` — Baseline noise only
- `drift` — Gradual sensor offset
- `spike` — Random large deviations
- `stuck` — Frozen sensor value
- `dropout` — Intermittent NaN values
- `noisy` — High Gaussian noise
- `degradation` — Progressive wear
- `maintenance_reset` — Post-maintenance baseline

## Real Datasets Catalog

| Dataset | Size | Type | License | Best For |
|---------|------|------|---------|----------|
| **AI4I 2020** | 1.5 MB | CSV | CC BY 4.0 | Predictive maintenance, failure classification |
| **NASA Bearing (IMS)** | 120 MB | ZIP | Public Domain | Bearing fault detection, run-to-failure |
| **NASA C-MAPSS** | 45 MB | ZIP | Public Domain | Turbofan degradation, RUL prediction |
| **SKAB** | 15 MB | CSV | MIT | Multivariate anomaly detection benchmark |
| **NAB** | 25 MB | CSV | AGPL-3.0 | Streaming anomaly detection evaluation |
| **SWaT** | 350 MB | ZIP | Research Use | Cyber-physical attack detection |

### Download and Use

```python
from services.datasets.data_sources_catalog import download_source, AI4I_SOURCE

# Download AI4I dataset
path = download_source(AI4I_SOURCE)

# Replay into pipeline
python services/datasets/ai4i_adapter.py --csv data/ai4i2020.csv --topic industrial.normalized --rate 25
```

### List Available Sources

```bash
python services/datasets/data_sources_catalog.py --list
```

## Using with Scenarios

Combine real datasets with scenario injection:

```bash
# Set scenario environment variables
export SCENARIO_TYPE=drift
export SCENARIO_PARAMS=drift_rate=0.05

# Replay with scenario applied
python services/datasets/ai4i_adapter.py --csv data/ai4i2020.csv --loop
```

## Data Format

All data sources produce `IndustrialEvent`-shaped records:

```json
{
  "event_id": "evt-123456",
  "source_protocol": "mock|dataset|opcua|mqtt|modbus",
  "asset_id": "Pump-01",
  "tag": "Temperature",
  "value": 55.2,
  "quality": "good|uncertain|bad",
  "unit": "c",
  "fault_type": "normal|drift|spike|...",
  "ground_truth_severity": "normal|warning|critical",
  "scenario_id": "sc-001",
  "ts_source": "2024-01-01T00:00:00Z"
}
```
