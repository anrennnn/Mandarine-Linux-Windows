"""PyInstaller entry point (the package __main__ uses relative imports)."""
import sys

from mandarine.cli import main

sys.exit(main())
