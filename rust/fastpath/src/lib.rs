use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBytes, PyDict, PyList, PyTuple};
use serde_json::{Map, Value};

fn string_field(dict: &Bound<'_, PyDict>, keys: &[&str], default: &str) -> PyResult<String> {
    for key in keys {
        if let Some(value) = dict.get_item(*key)? {
            if !value.is_none() {
                let text = value.str()?.to_str()?.trim().to_string();
                if !text.is_empty() {
                    return Ok(text);
                }
            }
        }
    }
    Ok(default.to_string())
}

fn float_field(dict: &Bound<'_, PyDict>, key: &str, default: f64) -> f64 {
    dict.get_item(key)
        .ok()
        .flatten()
        .and_then(|value| value.extract::<f64>().ok())
        .unwrap_or(default)
}

fn tag_to_legacy_field(tag: &str) -> Option<&'static str> {
    match tag.trim().to_ascii_lowercase().as_str() {
        "temperature" | "temp" | "temperature_c" | "temperature_celsius" | "temp_c" => Some("temperature_c"),
        "vibration" | "vibration_mm_s" | "vibration_mm_per_s" => Some("vibration_mm_s"),
        "pressure" | "pressure_bar" => Some("pressure_bar"),
        _ => None,
    }
}

fn any_to_value(value: &Bound<'_, PyAny>) -> PyResult<Value> {
    if value.is_none() {
        return Ok(Value::Null);
    }
    if let Ok(dict) = value.downcast::<PyDict>() {
        let mut map = Map::new();
        for (key, item) in dict.iter() {
            map.insert(key.extract::<String>()?, any_to_value(&item)?);
        }
        return Ok(Value::Object(map));
    }
    if let Ok(list) = value.downcast::<PyList>() {
        let mut items = Vec::with_capacity(list.len());
        for item in list.iter() {
            items.push(any_to_value(&item)?);
        }
        return Ok(Value::Array(items));
    }
    if let Ok(tuple) = value.downcast::<PyTuple>() {
        let mut items = Vec::with_capacity(tuple.len());
        for item in tuple.iter() {
            items.push(any_to_value(&item)?);
        }
        return Ok(Value::Array(items));
    }
    if let Ok(v) = value.extract::<bool>() {
        return Ok(Value::Bool(v));
    }
    if let Ok(v) = value.extract::<i64>() {
        return Ok(Value::from(v));
    }
    if let Ok(v) = value.extract::<f64>() {
        return Ok(Value::from(v));
    }
    if let Ok(v) = value.extract::<String>() {
        return Ok(Value::String(v));
    }
    Ok(Value::String(value.str()?.to_str()?.to_string()))
}

fn dict_to_value(dict: &Bound<'_, PyDict>) -> PyResult<Value> {
    let mut map = Map::new();
    for (key, value) in dict.iter() {
        map.insert(key.extract::<String>()?, any_to_value(&value)?);
    }
    Ok(Value::Object(map))
}

fn build_partition_key(dict: &Bound<'_, PyDict>) -> PyResult<Vec<u8>> {
    let parts = [
        string_field(dict, &["project_id", "site", "site_id"], "")?,
        string_field(dict, &["site", "site_id"], "demo-site")?,
        string_field(dict, &["line", "line_id"], "line-01")?,
        string_field(dict, &["source_protocol"], "unknown")?,
        string_field(dict, &["source_id", "plc_id", "device_id", "asset_id"], "unknown-source")?,
        string_field(dict, &["asset_id", "device_id"], "unknown-asset")?,
        string_field(dict, &["tag"], "unknown")?,
    ];
    Ok(parts.join("|").into_bytes())
}

fn build_legacy_event(dict: &Bound<'_, PyDict>) -> PyResult<Value> {
    let tag = string_field(dict, &["tag"], "")?;
    let value = float_field(dict, "value", 0.0);
    let mut payload = Map::new();
        payload.insert(
            "event_id".to_string(),
            dict.get_item("event_id")?
                .map(|v| any_to_value(&v))
                .transpose()?
                .unwrap_or(Value::Null),
        );
    payload.insert(
        "device_id".to_string(),
        Value::String(string_field(dict, &["asset_id"], "unknown-asset")?),
    );
    payload.insert(
        "site_id".to_string(),
        Value::String(string_field(dict, &["site", "site_id"], "demo-site")?),
    );
    payload.insert(
        "timestamp".to_string(),
        dict.get_item("ts_source")?
            .map(|v| any_to_value(&v))
            .transpose()?
            .unwrap_or(Value::Null),
    );
    payload.insert(
        "source_protocol".to_string(),
        Value::String(string_field(dict, &["source_protocol"], "unknown")?),
    );
    payload.insert(
        "quality".to_string(),
        Value::String(string_field(dict, &["quality"], "unknown")?),
    );
    payload.insert(
        "schema_version".to_string(),
        dict.get_item("schema_version")?
            .map(|v| any_to_value(&v))
            .transpose()?
            .unwrap_or(Value::from(1)),
    );
    payload.insert("temperature_c".to_string(), Value::from(0.0));
    payload.insert("vibration_mm_s".to_string(), Value::from(0.0));
    payload.insert("pressure_bar".to_string(), Value::from(0.0));
    if let Some(field) = tag_to_legacy_field(&tag) {
        payload.insert(field.to_string(), Value::from(value));
    }
    Ok(Value::Object(payload))
}

#[pyfunction]
fn json_bytes(py: Python<'_>, value: Py<PyAny>) -> PyResult<Py<PyBytes>> {
    let bound = value.bind(py);
    let extracted = if let Ok(dict) = bound.downcast::<PyDict>() {
        dict_to_value(dict)?
    } else {
        any_to_value(bound)?
    };
    let bytes = serde_json::to_vec(&extracted).map_err(|err| PyValueError::new_err(err.to_string()))?;
    Ok(PyBytes::new_bound(py, &bytes).into())
}

#[pyfunction]
fn stream_partition_key(py: Python<'_>, value: Py<PyAny>) -> PyResult<Py<PyBytes>> {
    let bound = value.bind(py);
    let dict = bound.downcast::<PyDict>()?;
    let bytes = build_partition_key(dict)?;
    Ok(PyBytes::new_bound(py, &bytes).into())
}

#[pyfunction]
fn encode_event_bundle(py: Python<'_>, value: Py<PyAny>) -> PyResult<(Py<PyBytes>, Py<PyBytes>, Py<PyBytes>)> {
    let bound = value.bind(py);
    let dict = bound.downcast::<PyDict>()?;
    let normalized = dict_to_value(dict)?;
    let key = build_partition_key(dict)?;
    let legacy = build_legacy_event(dict)?;
    let normalized_bytes = serde_json::to_vec(&normalized).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let legacy_bytes = serde_json::to_vec(&legacy).map_err(|err| PyValueError::new_err(err.to_string()))?;
    Ok((
        PyBytes::new_bound(py, &key).into(),
        PyBytes::new_bound(py, &normalized_bytes).into(),
        PyBytes::new_bound(py, &legacy_bytes).into(),
    ))
}

#[pymodule]
fn fastpath(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(json_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(stream_partition_key, m)?)?;
    m.add_function(wrap_pyfunction!(encode_event_bundle, m)?)?;
    Ok(())
}
