"""Allow ``python -m synthase`` as well as ``synthase``."""

import sys

from synthase.app import main

sys.exit(main())
