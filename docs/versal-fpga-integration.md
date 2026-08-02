# AMD Versal and FPGA Integration

Ravan integrates Versal through a gateway protocol. The supported v1 profile is
`amd_versal_v1`, carried over Sparkplug B/MQTT or OPC UA. This keeps board,
register-map, DMA, XRT, and bitstream details at the edge while Ravan owns
normalization, historian storage, lineage, observability, and artifact
references.

## Data flow

```text
Versal PS/PL/AI Engine
  ├─ scalar health, latency, inference and condition metrics
  │    └─ Sparkplug B or OPC UA → edge-ingest → Kafka → historian/AI
  └─ waveforms, images, video, tensors and simulator traces
       └─ file:// or s3:// ObservationArtifactReference → artifact topic
```

Configure an existing Sparkplug B or OPC UA connection with
`config.device_profile: amd_versal_v1` and a `config.versal` object containing
the board and device identifiers. The gateway should also publish firmware,
bitstream, Vitis/XRT, clock, calibration, topology and register-map versions.

Ravan's canonical scalar fields remain the source of truth. High-rate or large
payloads must not be encoded as one historian event per sample; publish an
immutable `ObservationArtifactReference` with checksum, URI, modality, shape,
encoding, sampling rate and lineage instead.

## Simulator and run manifests

Generate a deterministic hardware-free manifest with:

```text
ravan-versal-sim --source-id versal-sim-1 --site-id demo-site
```

The manifest contains scalar metrics and an artifact reference. The same
contract accepts `verilator`, `vitis_sw_emu`, `vitis_hw_emu`, and `hardware` as
run origins. The normal CI boundary is the gateway simulator plus a small
Verilator/cocotb AXI reference design. AMD Vitis hardware emulation is an
optional hardware-team/nightly tier because it combines QEMU, XSim and the AI
Engine simulator and requires the vendor toolchain.

Useful AMD outputs are preserved as artifacts: PLIO CSV, VCD/WDB waveforms,
AXI transaction logs, profile text/XML, `.aierun_summary`, JSON summaries and
throughput logs. Only derived scalar health/performance metrics are normalized
into the historian.

Direct XRT/PCIe/QDMA/XDMA ingestion is a future adapter and should only be
introduced after measured gateway latency or bandwidth is insufficient. Ravan
does not flash bitstreams or control actuators.
