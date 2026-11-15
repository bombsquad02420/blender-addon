"""Load the addon folder as a package without Blender.

The folder name has a hyphen, so it can't be imported normally.
"""

import importlib.util
import pathlib
import sys

ADDON_DIR = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = "ballistica_cloud_tools"


def load(module):
	if PACKAGE not in sys.modules:
		spec = importlib.util.spec_from_file_location(
			PACKAGE, ADDON_DIR / "__init__.py", submodule_search_locations=[str(ADDON_DIR)])
		package = importlib.util.module_from_spec(spec)
		sys.modules[PACKAGE] = package
		spec.loader.exec_module(package)
	return importlib.import_module(f"{PACKAGE}.{module}")
