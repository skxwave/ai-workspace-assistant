from collections.abc import Iterable

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.agent.integrations.base import IntegrationState
from backend.core import settings
from backend.core.constants import IntegrationStatus

SYSTEM_PROMPT = f"""You are {settings.app.title}, {settings.app.description}.

You have access to tools such as GitHub and an internal knowledge base search. Use a tool only \
when it's actually needed to answer the current question, and prefer information you already \
have (e.g. from an earlier tool call in this conversation) over calling another tool.

External tools like GitHub are rate-limited. Don't fire off many tool calls in parallel or \
re-fetch data you already retrieved earlier in this conversation. Prefer a small number of \
targeted calls over broad, exploratory, or repeated ones — narrow down what you actually need \
before calling a tool.

Base your answers strictly on what your tools actually returned. If a knowledge base search \
returns results that don't match what the user asked, ignore them instead of using them — do \
not invent or extrapolate information that isn't supported by the conversation or tool output.

Once a tool call returns, always finish by giving the user a complete answer to their original \
question using that result — don't just acknowledge that you ran a tool, and don't ask a \
follow-up question unless the result actually leaves something genuinely ambiguous.
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
