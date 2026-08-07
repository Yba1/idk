from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-endpoint limits are real production behaviour (10/min on query routes,
# 20/min on atlas) and stay on by default. The e2e suite drives several full
# queries per spec from a single IP and legitimately exceeds that, so it is
# switchable -- but only by an explicit opt-out, never inferred from
# NEULIT_PROFILE. A fake-profile deployment is still a deployment.
#
# Set NEULIT_RATE_LIMIT=off to disable. Anything else (including unset) leaves
# limiting on.
_ENABLED = os.environ.get("NEULIT_RATE_LIMIT", "on").strip().lower() != "off"

limiter = Limiter(key_func=get_remote_address, enabled=_ENABLED)
