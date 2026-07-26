---
name: ravan-source-onboarding
label: Ravan source onboarding
version: 1
mode: guided
approval_required: true
---

# Purpose

Guide an operator through registering an OPC UA, MQTT, Modbus, REST, or HTTP
Push source without inventing credentials or enabling ingestion implicitly.

# Required sequence

1. Ask for protocol, source name, site ID, endpoint, and credential reference.
2. Validate protocol-specific endpoint syntax and credential-reference syntax.
3. Present a draft and link to `Integrations -> Source connections`.
4. Require the operator to complete protocol mappings in the typed editor.
5. Direct the operator through Validate, Test, and Enable.
6. Never send or display secret values.

# Safety

This skill may prepare a draft and explain actions. It may not control PLCs,
actuators, robots, or safety systems. Existing source lifecycle actions require
an explicit expiring confirmation preview.
