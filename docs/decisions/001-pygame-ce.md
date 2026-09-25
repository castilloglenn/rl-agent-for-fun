# 001: Use pygame-ce instead of pygame

**Date:** 2026-09-25. **Status:** Accepted.

## Context

The project moved from Windows to macOS, with Python 3.14. pygame 2.6.1, the latest release, has no prebuilt wheel for Python 3.14 on macOS, so pip compiled it locally. The build shipped without the compiled font module, and pygame fell back to `font.py`, which crashed with a circular import on the first `pygame.font.SysFont` call.

## Decision

Replace `pygame` with `pygame-ce` (Community Edition), which has a prebuilt 3.14 macOS wheel. It's a drop-in replacement: the code still does `import pygame`, and no source changes were needed.

## Alternative rejected

Rebuilding the venv with Python 3.13, where pygame 2.6.1 has a wheel. The owner chose to stay on 3.14.
