"""API route routers."""

from storyplanner.api.routes import (
    assistant,
    connector,
    events,
    export,
    notes,
    outline,
    plot,
    projects,
    psyke,
    scenes,
    timeline,
)

# Ordered list of every router mounted under the /api prefix.
ALL_ROUTERS = [
    projects.router,
    scenes.router,
    outline.router,
    plot.router,
    timeline.router,
    psyke.router,
    notes.router,
    assistant.router,
    connector.router,
    export.router,
    events.router,
]

__all__ = ["ALL_ROUTERS"]
