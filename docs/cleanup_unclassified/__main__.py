"""Allow running docs.cleanup_unclassified as a module."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cleanup_unclassified import main

if __name__ == "__main__":
    main()
