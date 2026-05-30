"""Assistant (chat + actions + settings) endpoints.

Chat reuses the existing :func:`storyplanner.assistant.chat_completion`; actions
are routed through the safe connector action layer so the API never performs raw
DB mutations on the assistant's behalf.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from storyplanner.api import schemas
from storyplanner.api.deps import get_broker, get_db, get_project
from storyplanner.api.errors import ApiError
from storyplanner.api.events import ApiEventBroker
from storyplanner.db import Database

router = APIRouter(tags=["assistant"])

# Settings keys this endpoint exposes (api_key is write-only).
_AI_KEYS = {
    "provider": "ai_provider",
    "model": "ai_model",
    "base_url": "ai_base_url",
    "timeout": "assistant_api_timeout",
}


def _build_provider():
    from storyplanner.providers import ProviderConfig
    from storyplanner.settings import get_manager

    settings = get_manager()
    return ProviderConfig(
        name=str(settings.get("ai_provider") or "LM Studio"),
        base_url=str(settings.get("ai_base_url") or "http://localhost:1234/v1"),
        model=str(settings.get("ai_model") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
    )


@router.post(
    "/projects/{project_id}/assistant/chat",
    response_model=schemas.AssistantResponseDTO,
)
def assistant_chat(
    body: schemas.AssistantRequestDTO,
    project=Depends(get_project),
):
    from storyplanner import assistant

    messages: list[dict] = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    for m in body.history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": body.message})

    try:
        reply, cached = assistant.chat_completion(
            messages, provider=_build_provider(),
        )
    except Exception as exc:  # network / provider errors
        raise ApiError(502, f"Assistant request failed: {exc}", code="assistant_error")
    return schemas.AssistantResponseDTO(reply=reply, cached=cached)


@router.post(
    "/projects/{project_id}/assistant/action",
    response_model=schemas.ConnectorResultDTO,
)
def assistant_action(
    body: schemas.AssistantActionRequestDTO,
    project=Depends(get_project),
    db: Database = Depends(get_db),
    broker: ApiEventBroker = Depends(get_broker),
):
    from storyplanner.api.actions import run_action

    result = run_action(db, project.id, body.action, body.args)
    if result.get("ok"):
        broker.publish(
            "assistant_action_completed", project_id=project.id,
            action=body.action,
        )
        broker.publish("project_data_changed", project_id=project.id)
    return schemas.ConnectorResultDTO(
        ok=bool(result.get("ok")),
        action=result.get("action", body.action),
        result=result.get("result"),
        error=result.get("error", ""),
    )


@router.get(
    "/projects/{project_id}/assistant/settings",
    response_model=schemas.AssistantSettingsDTO,
)
def get_assistant_settings(project=Depends(get_project)):
    from storyplanner.settings import get_manager

    settings = get_manager()
    return schemas.AssistantSettingsDTO(
        provider=str(settings.get("ai_provider") or ""),
        model=str(settings.get("ai_model") or ""),
        base_url=str(settings.get("ai_base_url") or ""),
        timeout=int(settings.get("assistant_api_timeout") or 0),
        api_key=None,  # never returned
    )


@router.patch(
    "/projects/{project_id}/assistant/settings",
    response_model=schemas.AssistantSettingsDTO,
)
def patch_assistant_settings(
    body: schemas.AssistantSettingsDTO,
    project=Depends(get_project),
):
    from storyplanner.settings import get_manager

    settings = get_manager()
    patch = body.model_dump(exclude_unset=True)
    if "provider" in patch:
        settings.set("ai_provider", patch["provider"])
    if "model" in patch:
        settings.set("ai_model", patch["model"])
    if "base_url" in patch:
        settings.set("ai_base_url", patch["base_url"])
    if "timeout" in patch:
        settings.set("assistant_api_timeout", patch["timeout"])
    if patch.get("api_key"):  # write-only; only set when non-empty
        settings.set("ai_api_key", patch["api_key"])
    return get_assistant_settings(project=project)
