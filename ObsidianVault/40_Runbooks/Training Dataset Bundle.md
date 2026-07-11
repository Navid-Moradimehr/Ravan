# Training Dataset Bundle

Use `datastreamctl training-dataset validate` to check a versioned manifest and
`datastreamctl training-dataset compile` to produce portable Parquet tables
plus manifest, semantic context, lineage, and quality reports.

JEPA manifests may use passive normalized observations. Dreamer and MuZero
manifests must declare operational action sources, outcome sources, and episode
boundaries. Reward formulas, safety semantics, and model training remain
company-owned.
