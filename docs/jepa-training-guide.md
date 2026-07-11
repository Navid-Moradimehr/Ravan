# JEPA Preparation Guide

JEPA-style training can start from passive, synchronized industrial
observations. Connect sensors and PLC read values, map them to stable assets
and tags, enable the normalized lakehouse sink, and create a manifest with
`purpose: jepa`.

Use multi-sensor windows rather than independent scalar rows. Include quality
and missingness masks, source timestamps, units, operating regime, asset
identity, and topology context. Split by time or site, not random individual
rows, to prevent future information leaking into training.

Actions and rewards are not required for initial representation pretraining,
but maintenance, recipe, operator, and process-context events improve the
meaning of the learned representation.
