from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict, BaseSettings


class Agent(BaseModel):
    is_in_memory: bool = True


class Tools(BaseModel):
    github_pat: str


class LLMs(BaseModel):
    openai_base_url: str = "https://api.openai.com/v1"
    openai_gpt_4o_mini: str = "4o-mini"
    openai_gpt_5_mini: str = "gpt-5-mini"
    openai_gpt_5_4: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
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


class Redis(BaseModel):
    host: str = "localhost"
    port: int = 6379


class DB(BaseModel):
    qdrant: Qdrant
    postgres: Postgres
    redis: Redis = Redis()


class Auth(BaseModel):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30


class Settings(BaseSettings):
    app: App = App()
    agent: Agent = Agent()
    auth: Auth
    db: DB
    llms: LLMs
    tools: Tools

    model_config = SettingsConfigDict(
        env_prefix="BOT__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
