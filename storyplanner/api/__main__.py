"""``python -m storyplanner.api`` -> start the API server."""

import sys

from storyplanner.api.server import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
