"""
Top-level pytest config: makes both service codebases importable.

api-fintech/ and mcp-fintech/ contain hyphens, so they are scripts loaded
via sys.path rather than installable packages. We add their roots so
`from domain.entities...` and `import server` work in tests.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api-fintech"))
sys.path.insert(0, str(ROOT / "mcp-fintech"))
