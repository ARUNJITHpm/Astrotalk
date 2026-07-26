"""Suite-wide fixtures.

The admin token used to be the hardcoded literal ``"chargemod"``, accepted
unconditionally by ``app/platform/admin_auth.py`` whether or not anything was
configured. That backdoor is gone (console plan Part 4), so the suite now does
what production does: it *configures* a token.

Setting it here rather than editing the eight test files that send
``X-Admin-Token: chargemod`` keeps those tests as they were — they assert the
gate's behaviour, not the secret's value.
"""

import pytest

from app.platform.config import get_settings

TEST_ADMIN_TOKEN = "chargemod"


@pytest.fixture(autouse=True)
def _configured_admin_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", TEST_ADMIN_TOKEN)
