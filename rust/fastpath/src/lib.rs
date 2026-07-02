use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBytes, PyDict};
use serde::Serialize;

#[derive(Debug, Serialize)]
struct WireEvent {
    event_id: String,
    source_protocol: String,
    source_id: String,
    asset_id: String,
    tag: String,
    value: f64,
    quality: String,
    unit: Option<String>,
    site: String,
    line: String,
    ts_source: String,
    ts_ingest: Option<String>,
    schema_version: i64,
    device_id: String,
    project_id: String,
    temperature_c: f64,
    vibration_mm_s: f64,
    pressure_bar: f64,
    fault_type: String,
    scenario_id: String,
    ground_truth_severity: String,
    processed_at: String,
    window_size: i64,
    temperature_avg_c: f64,
    vibration_avg_mm_s: f64,
    anomaly_score: f64,
    severity: String,
}

fn lookup_value<'py>(obj: &'py Bound<'py, PyAny>, name: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    if let Ok(dict) = obj.downcast::<PyDict>() {
        return dict.get_item(name);
    }
    match obj.getattr(name) {
        Ok(value) => Ok(Some(value)),
        Err(_) => Ok(None),
    }
}

fn get_string(obj: &Bound<'_, PyAny>, name: &str, default: &str) -> PyResult<String> {
    match lookup_value(obj, name)? {
        Some(value) => Ok(value.extract::<Option<String>>()?.unwrap_or_else(|| default.to_string())),
        None => Ok(default.to_string()),
    }
}

fn get_opt_string(obj: &Bound<'_, PyAny>, name: &str) -> PyResult<Option<String>> {
    match lookup_value(obj, name)? {
        Some(value) => Ok(value.extract::<Option<String>>()?),
        None => Ok(None),
    }
}

fn get_f64(obj: &Bound<'_, PyAny>, name: &str, default: f64) -> PyResult<f64> {
    match lookup_value(obj, name)? {
        Some(value) => value.extract::<f64>().or(Ok(default)),
        None => Ok(default),
    }
}

fn get_i64(obj: &Bound<'_, PyAny>, name: &str, default: i64) -> PyResult<i64> {
    match lookup_value(obj, name)? {
        Some(value) => value.extract::<i64>().or(Ok(default)),
        None => Ok(default),
    }
}

fn extract_wire_event(event: &Bound<'_, PyAny>) -> PyResult<WireEvent> {
    Ok(WireEvent {
        event_id: get_string(event, "event_id", "")?,
        source_protocol: get_string(event, "source_protocol", "unknown")?,
        source_id: get_string(event, "source_id", "unknown-source")?,
        asset_id: get_string(event, "asset_id", "unknown-asset")?,
        tag: get_string(event, "tag", "unknown")?,
        value: get_f64(event, "value", 0.0)?,
        quality: get_string(event, "quality", "good")?,
        unit: get_opt_string(event, "unit")?,
        site: get_string(event, "site", "demo-site")?,
        line: get_string(event, "line", "line-01")?,
        ts_source: get_string(event, "ts_source", "")?,
        ts_ingest: get_opt_string(event, "ts_ingest")?,
        schema_version: get_i64(event, "schema_version", 1)?,
        device_id: get_string(event, "device_id", "unknown-asset")?,
        project_id: get_string(event, "project_id", "")?,
        temperature_c: get_f64(event, "temperature_c", 0.0)?,
        vibration_mm_s: get_f64(event, "vibration_mm_s", 0.0)?,
        pressure_bar: get_f64(event, "pressure_bar", 0.0)?,
        fault_type: get_string(event, "fault_type", "normal")?,
        scenario_id: get_string(event, "scenario_id", "sc-000")?,
        ground_truth_severity: get_string(event, "ground_truth_severity", "normal")?,
        processed_at: get_string(event, "processed_at", "")?,
        window_size: get_i64(event, "window_size", 0)?,
        temperature_avg_c: get_f64(event, "temperature_avg_c", 0.0)?,
        vibration_avg_mm_s: get_f64(event, "vibration_avg_mm_s", 0.0)?,
        anomaly_score: get_f64(event, "anomaly_score", 0.0)?,
        severity: get_string(event, "severity", "normal")?,
    })
}

#[pyfunction]
#[pyo3(signature = (project_id=None, site=None, line=None, source_protocol=None, source_id=None, asset_id=None, tag=None))]
fn stream_partition_key(
    py: Python<'_>,
    project_id: Option<&str>,
    site: Option<&str>,
    line: Option<&str>,
    source_protocol: Option<&str>,
    source_id: Option<&str>,
    asset_id: Option<&str>,
    tag: Option<&str>,
) -> PyResult<Py<PyBytes>> {
    let key = format!(
        "{}|{}|{}|{}|{}|{}|{}",
        project_id.unwrap_or(""),
        site.unwrap_or("demo-site"),
        line.unwrap_or("line-01"),
        source_protocol.unwrap_or("unknown"),
        source_id.unwrap_or("unknown-source"),
        asset_id.unwrap_or("unknown-asset"),
        tag.unwrap_or("unknown"),
    );
    Ok(PyBytes::new_bound(py, key.as_bytes()).unbind())
}

#[pyfunction]
fn stream_partition_key_from_event(py: Python<'_>, event: &Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
    let key = format!(
        "{}|{}|{}|{}|{}|{}|{}",
        get_string(event, "project_id", "")?,
        get_string(event, "site", "demo-site")?,
        get_string(event, "line", "line-01")?,
        get_string(event, "source_protocol", "unknown")?,
        get_string(event, "source_id", "unknown-source")?,
        get_string(event, "asset_id", "unknown-asset")?,
        get_string(event, "tag", "unknown")?,
    );
    Ok(PyBytes::new_bound(py, key.as_bytes()).unbind())
}

#[pyfunction]
#[pyo3(signature = (event, wire_format=None))]
fn encode_wire_event(py: Python<'_>, event: &Bound<'_, PyAny>, wire_format: Option<&str>) -> PyResult<Py<PyBytes>> {
    let record = extract_wire_event(event)?;
    let bytes = match wire_format.unwrap_or("json").to_ascii_lowercase().as_str() {
        "msgpack" => rmp_serde::to_vec_named(&record)
            .map_err(|err| PyValueError::new_err(format!("msgpack encode failed: {err}")))?,
        _ => serde_json::to_vec(&record)
            .map_err(|err| PyValueError::new_err(format!("json encode failed: {err}")))?,
    };
    Ok(PyBytes::new_bound(py, &bytes).into())
}

#[pyfunction]
#[pyo3(signature = (event, wire_format=None))]
fn wire_roundtrip_size(event: &Bound<'_, PyAny>, wire_format: Option<&str>) -> PyResult<usize> {
    Python::with_gil(|py| {
        let bytes = encode_wire_event(py, event, wire_format)?;
        Ok(bytes.bind(py).as_bytes().len())
    })
}

#[pymodule]
fn datastream_fastpath(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(stream_partition_key, m)?)?;
    m.add_function(wrap_pyfunction!(stream_partition_key_from_event, m)?)?;
    m.add_function(wrap_pyfunction!(encode_wire_event, m)?)?;
    m.add_function(wrap_pyfunction!(wire_roundtrip_size, m)?)?;
    Ok(())
}
