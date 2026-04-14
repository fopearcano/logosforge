"""Entry point for StoryPlanner."""

import sys

from storyplanner.app import create_app


def main() -> int:
    app, window = create_app()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
