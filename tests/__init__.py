"""
Makes 'tests' a package and ensures src/ is on sys.path.

pytest adds src/ automatically via pytest.ini, but the unittest runner has no
equivalent setting — inserting the path here means both runners can import
from models, data_storage, etc. without extra setup.
"""

import sys
from pathlib import Path

_src = Path(__file__).parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
