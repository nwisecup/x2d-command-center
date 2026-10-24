"""Minimal test runner for environments without pytest (CI uses real pytest)."""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import conftest  # noqa: F401  (registers the namespace package)

failed = passed = 0
for mod_path in sorted(Path(__file__).parent.glob("test_*.py")):
    mod = importlib.import_module(mod_path.stem)
    for name in dir(mod):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                passed += 1
            except Exception:  # noqa: BLE001
                failed += 1
                print(f"FAIL {mod_path.stem}::{name}")
                traceback.print_exc()
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
