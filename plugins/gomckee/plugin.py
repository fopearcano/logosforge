"""Go McKee plugin for Storyplanner."""

from pathlib import Path

from gomckee.integration import GoMcKeePlugin


def register(api):
    plugin = GoMcKeePlugin(api, Path(__file__).resolve().parent)
    plugin.register()
