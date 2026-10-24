"""Let the pure modules import without Home Assistant installed.

Registers `bambu_x2d` as a namespace package pointing at custom_components/bambu_x2d
WITHOUT executing its __init__.py (which imports homeassistant). Submodules like
models/commands/soak/threemf/derived/discovery are HA-free and import normally.
"""
import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).parent.parent / "custom_components" / "bambu_x2d"

if "bambu_x2d" not in sys.modules:
    pkg = types.ModuleType("bambu_x2d")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["bambu_x2d"] = pkg
