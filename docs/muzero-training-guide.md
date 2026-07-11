# MuZero Preparation Guide

MuZero-style planning needs observations, actions, rewards, and value/episode
targets. Configure a control-oriented training manifest with
`action_sources`, `outcome_sources`, and an explicit episode boundary.

For the reference workflow, define a finite, auditable action vocabulary such
as `speed_minus`, `speed_hold`, and `speed_plus`. The platform records the
actual command and result; it does not decide whether continuous-control
MuZero adaptations are appropriate for a site.

Evaluate planning against replayed historical episodes or a user-provided
simulator. Do not connect a newly trained planner directly to PLC writes.
