"""Replays: record a game's inputs, and re-simulate them exactly.

See docs/decisions/003-replay-over-multi-window.md. Import from the
modules (format, recorder, replayer) directly: the env uses the recorder
without importing this package, which keeps imports free of cycles.
"""
