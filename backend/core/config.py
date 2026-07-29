from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict, BaseSettings


class Agent(BaseModel):
    is_in_memory: bool = True


class LLMs(BaseModel):
    openai_base_url: str = "https://api.openai.com/v1"
    openai_gpt_4o_mini: str = "openai/gpt-4o-mini"
    openai_gpt_5_mini: str = "gpt-5-mini"
    openai_api_key: str


class App(BaseModel):
    debug: bool = True
    title: str = "AI Workspace Assistant"
    description: str = "Internal AI assistant for engineers"
    version: str = "0.0.1"


class Qdrant(BaseModel):
    url: str = "http://localhost:6333"
    host: str = "localhost"
    port: int = 6333
    key: str
    collection_name: str = "test-collection"


class Postgres(BaseModel):
    db: str = "ai-assistant"
    user: str = "root"
    password: str = "root"
    host: str = "localhost"
    port: int = 5432


class DB(BaseModel):
    qdrant: Qdrant
    postgres: Postgres


class Settings(BaseSettings):
    app: App = App()
    agent: Agent = Agent()
    db: DB
    llms: LLMs

    model_config = SettingsConfigDict(
        env_prefix="BOT__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
