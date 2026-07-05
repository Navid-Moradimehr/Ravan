# Real-World PLC And Sensor Simulation Sources

This project does not need access to customer PLCs to build useful benchmark traffic.
We can combine real industrial datasets, protocol simulators, and process models to create realistic site-local replay packs.

## What We Can Use

### High-fidelity ICS datasets

- [SWaT](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/swat/)
- [WaDi](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/wadi/)
- [EPIC](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/epic/)
- [BATADAL](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/batadal/)
- [iTrust IoT honeypot traffic](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/iot/)
- [CISS](https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/ciss/)

These are the closest public sources to real PLC/sensor plus network traffic. Several include historian-style time series and PCAP/NetFlow artifacts. iTrust also requests dataset access rather than redistributing the raw files.

### Process and machine fault datasets

- [AI4I 2020 Predictive Maintenance](https://archive.ics.uci.edu/ml/datasets/AI4I%2B2020%2BPredictive%2BMaintenance%2BDataset)
- [NASA C-MAPSS](https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data)
- [Tennessee Eastman Process](https://kilthub.cmu.edu/articles/dataset/Dataset_of_Manipulations_on_the_Tennessee_Eastman_Process/23805552)
- [Paderborn bearing data](https://mb.uni-paderborn.de/kat/forschung/bearing-datacenter/data-sets-and-download)
- [MIMII sound dataset](https://zenodo.org/records/3384388)

These are not PLC protocols themselves, but they are useful for shaping realistic sensor curves, drift patterns, fault progression, and anomaly distributions.

### Protocol and device simulators

- [open62541 OPC UA stack](https://github.com/open62541/open62541)
- [OPC UA sensor simulator](https://developer.cisco.com/codeexchange/github/repo/flopach/opc-ua-sensor-simulator/)
- [pymodbus modbus simulator](https://github.com/pymodbus-dev/modbus-simulator)
- [OpenModSim](https://sanny32.github.io/OpenModSim/)
- [modbusua gateway](https://github.com/serhmarch/modbusua)
- [MQTT simulators](https://github.com/InfluxCommunity/MQTT_Simulators)
- [MQTT simulator](https://github.com/DamascenoRafael/mqtt-simulator)

These are the easiest way to generate live traffic that looks like PLC and sensor data without needing physical hardware.

### Repository-defined benchmark scenarios

- `mock-normal`: stable baseline with no injected faults.
- `mock-drift`: gradual sensor offset for drift validation.
- `mock-spike`: intermittent spikes for anomaly-path validation.
- `multi-plc-line`: one asset observed by multiple PLC/source identities on the same line.
- `burst-load`: short-lived spike-heavy traffic for backpressure and peak-load checks.
- `dropout-reconnect`: signal loss followed by recovery for reconnect and resilience checks.
- `industrial-benchmark`: replay of the checked-in mixed industrial baseline CSV.

## Recommended Simulation Stack

1. Use `open62541`, `modbus-simulator`, and MQTT simulators to generate protocol-native traffic.
2. Calibrate payload values and fault curves with SWaT, WaDi, EPIC, BATADAL, AI4I, C-MAPSS, TEP, Paderborn, and MIMII.
3. Replay network traces when available, especially SWaT/WaDi/CISS PCAP and historian exports.
4. Feed the resulting events into `industrial_mixed_benchmark.csv`-style replay packs.
5. Preserve site boundaries, source IDs, and line IDs so multi-site isolation stays testable.
6. Compare benchmark sessions using repeated runs and record median/variance, not a single sample.

## Mapping Rules For This Platform

- `site_id` should represent a plant, branch, or subnet boundary.
- `source_id` should represent a PLC, RTU, sensor gateway, or protocol simulator instance.
- `asset_id` should represent the physical asset or line being monitored.
- `tag` should remain stable across repeated runs so correlations and baselines are meaningful.
- `scenario_id` should encode the process story, such as `normal`, `drift`, `burst`, `attack`, or `maintenance`.

## Access Notes

- iTrust datasets are request-based and should not be redistributed in this repository.
- Some datasets are huge, so the practical approach is to extract representative slices and preserve the schema plus timing patterns.
- For open-source releases, keep only generated subsets, transformations, and benchmark metadata in-repo.

## Recommended Next Step

Use `datastream-import convert` to normalize selected dataset slices into the repo's benchmark CSV format, then run the same benchmark/calibration commands against those slices to create a realistic baseline.

Suggested order:

1. Convert AI4I slices first because they are small and easy to validate.
2. Convert C-MAPSS next for degradation-heavy runs.
3. Convert generic SWaT/WADI-like CSV exports after the preset mapping is stable.
4. Feed the normalized CSVs into `benchmark real-world-simulator`, `site-profile-matrix`, and `site-profile-calibration`.

## Current Repo Status

- AI4I is now fetched from the public UCI archive, normalized, and benchmarked through the end-to-end pipeline.
- NASA C-MAPSS is now fetched from the official NASA ZIP, normalized, and benchmarked through the end-to-end pipeline.
- SWaT workbook and CSV normalization now exist in the repo, and the adapter has been benchmarked with a synthetic workbook fixture.
- The public SWaT download still needs one more verification pass against the exact upstream file we ship users to make sure the staged workbook path matches the upstream format in every environment.
