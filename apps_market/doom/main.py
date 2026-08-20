"""DOOM 3D — entry shim. Implementation lives under src/.

The launcher loads this module and reads `App` off it.
"""

from .src.app import App

__all__ = ["App"]
