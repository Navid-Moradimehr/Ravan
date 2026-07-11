# Dreamer Preparation Guide

Dreamer-style training requires ordered transitions. A user must provide
observation/state at time `t`, the action applied at `t`, the resulting
observation/state at `t+1`, an outcome/reward signal, and an episode boundary.

Use `industrial.operational` for PLC command audits, operator overrides,
recipe transitions, maintenance mode, and batch/changeover boundaries. Use
MES, quality, energy, and downtime records for outcomes. Define the reward in
user-owned training code; the platform does not guess business or safety
objectives.

Train offline on held-out time periods and sites first. Keep the resulting
policy recommendation-only until the company has a validated simulator,
safety envelope, approval process, and independent operational evaluation.
