from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict, BaseSettings


class App(BaseModel):
    debug: bool = True
    title: str = "AI Workspace Assistant"
    description: str = "Internal AI assistant for engineers"
    version: str = "0.0.1"


class Settings(BaseSettings):
    app: App = App()

    model_config = SettingsConfigDict(
        env_prefix="BOT__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
