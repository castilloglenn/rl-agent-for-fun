"""Drivers: everything that decides a car's actions, behind one interface.

Keyboard (you), baselines (random, heuristic), and later RL and imitation
agents all implement `Driver` (src/drivers/base.py), so the demo, runner,
replays, and evaluation treat them the same. See
docs/decisions/012-agent-training-modes.md.
"""
