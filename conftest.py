import os
import sys
import pytest

# Test ortamını izole et: canlı GitHub state dalına veya borsaya yanlışlıkla yazılmasını önle
os.environ["UNITTEST_MODE"] = "1"
os.environ["TEST_MODE"] = "1"
os.environ["GITHUB_TOKEN"] = ""

@pytest.fixture(autouse=True)
def reset_macro_guard_state():
    yield
    try:
        from macro_strategy_guard import macro_guard
        macro_guard.set_override_regime(None)
        if hasattr(macro_guard, "quorum") and hasattr(macro_guard.quorum, "audit_history"):
            macro_guard.quorum.audit_history.clear()
    except Exception:
        pass
