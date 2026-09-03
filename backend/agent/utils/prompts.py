from collections.abc import Iterable, Sequence

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.agent.integrations.base import IntegrationState
from backend.core import settings
from backend.core.constants import IntegrationStatus

SYSTEM_PROMPT = f"""You are {settings.app.title}, {settings.app.description}.

You have access to tools such as GitHub and an internal knowledge base search. Use a tool \
only when it's actually needed, and prefer information already in this conversation over \
calling a tool again.

Tool usage:
- Batch independent read-only calls into a single step; avoid exploratory or repeated \
calls, and decide what you need before calling.
- Don't call identity or "who am I" tools when the user's message or an earlier result \
already gives you the identifier (e.g. a repository owner).
- Assume conventional paths and casing (e.g. `README.md`). If a lookup 404s, list the \
directory once instead of guessing again.
- When editing a file, make the smallest change that satisfies the request and preserve \
the surrounding structure.

Base your answers strictly on what your tools actually returned. If a knowledge base \
search returns results that don't match what the user asked, ignore them — do not invent \
or extrapolate information that isn't supported by the conversation or tool output.

Once a tool call returns, finish by giving the user a complete answer to their original \
question using that result — don't just acknowledge that you ran a tool, and don't ask a \
follow-up unless the result leaves something genuinely ambiguous.
"""

system_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

_STATUS_NOTICES = {
    IntegrationStatus.NOT_CONNECTED: (
        "The user has not connected these integrations: {names}. If their request "
        "needs one, tell them to connect it instead of guessing or refusing silently."
    ),
    IntegrationStatus.EXPIRED: (
        "These integrations rejected the user's stored credentials and must be "
        "reconnected: {names}. Say so plainly if their request needs one."
    ),
    IntegrationStatus.DEGRADED: (
        "These integrations are temporarily unreachable: {names}. Tell the user to "
        "retry shortly rather than guessing at an answer."
    ),
}


def integration_notice(integrations: Iterable[IntegrationState]) -> str | None:
    grouped: dict[IntegrationStatus, list[str]] = {}
    for state in integrations:
        if state.status is not IntegrationStatus.CONNECTED:
            grouped.setdefault(state.status, []).append(state.name)

    lines = [
        template.format(names=", ".join(sorted(grouped[status])))
        for status, template in _STATUS_NOTICES.items()
        if status in grouped
    ]
    return "\n".join(lines) if lines else None


def turn_context_message(
    *,
    summary: str,
    attached_file_ids: Sequence[str] | None,
    integrations: Iterable[IntegrationState],
) -> SystemMessage | None:
    """Per-turn context, appended after the history so the prompt prefix stays cacheable."""
    parts: list[str] = []
    if summary:
        parts.append(f"Summary of earlier conversation:\n{summary}")
    if notice := integration_notice(integrations):
        parts.append(notice)
    if attached_file_ids:
        ids = list(attached_file_ids)
        parts.append(
            f"User uploaded new files (ids: {ids}); use `search_user_files` with "
            f"file_ids={ids} to look them up."
        )
    return SystemMessage("\n\n".join(parts)) if parts else None
