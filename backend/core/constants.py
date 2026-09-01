from enum import StrEnum

MAX_UPLOAD_SIZE = 20 * 1024 * 1024


class MessageRole(StrEnum):
    AI = "ai"
    HUMAN = "human"


class IntegrationStatus(StrEnum):
    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"
    EXPIRED = "expired"
    DEGRADED = "degraded"
