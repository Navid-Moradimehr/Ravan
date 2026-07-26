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
2. Explain where each value comes from. Site IDs may be looked up from the
   registry; endpoints, certificates, broker topics, Modbus maps, and API
   paths must come from the external system or its administrator.
3. Validate protocol-specific endpoint syntax and credential-reference syntax.
4. Present a draft and hand it to `Integrations -> Source connections` without
   saving or enabling it.
5. Require the operator to complete protocol mappings in the typed editor.
6. Direct the operator through Validate, Test, Preview, Save, and Enable.
7. Never send or display secret values.

# Safety

This skill may prepare a draft and explain actions. It may not control PLCs,
actuators, robots, or safety systems. Existing source lifecycle actions require
an explicit expiring confirmation preview.
