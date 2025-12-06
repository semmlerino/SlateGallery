#!/usr/bin/env python3
"""
SlateGallery - Photo Gallery Generator
Entry point for the modular SlateGallery application.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    try:
        from main import main
    except ImportError:
        # Fallback for when running from different directory
        import sys
        from pathlib import Path
        src_path = Path(__file__).parent / 'src'
        sys.path.insert(0, str(src_path))
        from main import main
    main()
