"""Import pure functions without the heavy Home Assistant runtime locally."""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "trybatec"
for module_name, module_dir in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.trybatec", MODULE),
):
    if module_name not in sys.modules:
        package = types.ModuleType(module_name)
        package.__path__ = [str(module_dir)]
        sys.modules[module_name] = package
