"""Settings for every test, before any test file imports pygame.

No sound in the tests: the app plays none, and pygame.init() starting
macOS's audio can stall for half a minute or fail (CoreAudio error -66681,
seen 2026-10-01). Windows run headless (dummy video) as each file already
asks.
"""

import os

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
