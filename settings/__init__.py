# queen/settings/__init__.py
"""Lean settings package initializer.

Intentionally avoids eager re-exports to prevent circular imports and heavy
import-time side effects. Import submodules directly:

  from queen.settings import settings as SETTINGS_MOD
  from queen.settings import indicators as IND
  from queen.settings import timeframes as TF
"""

__all__ = ()  # no eager exports on purpose
