"""Allow ``python -m synthase`` as well as ``syn``."""

import sys

from synthase.cli import main

sys.exit(main())
