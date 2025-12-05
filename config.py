"""
Configuration management for the AI Communication Workflow.
Uses environment variables with pydantic-settings for validation.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Cisco Bridge API Configuration (Primary LLM)
    cisco_client_id: str = Field(..., description="Cisco OAuth2 client ID")
    cisco_client_secret: str = Field(..., description="Cisco OAuth2 client secret")
    cisco_app_key: str = Field(..., description="Cisco Bridge API app key")
    cisco_token_url: str = Field(
        default="https://id.cisco.com/oauth2/default/v1/token",
        description="Cisco OAuth2 token endpoint",
    )
    cisco_api_url: str = Field(
        default="https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions",
        description="Cisco Bridge API chat completions endpoint",
    )

    # LLM Parameters
    llm_temperature: float = Field(default=0.7, description="LLM sampling temperature")
    llm_max_tokens: Optional[int] = Field(default=None, description="Max tokens to generate")

    # Email Configuration
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(..., description="SMTP username")
    smtp_password: str = Field(..., description="SMTP password/app password")
    email_from: str = Field(..., description="Sender email address")
    email_to: str = Field(..., description="Comma-separated recipient emails")

    # Webex Configuration
    webex_access_token: str = Field(..., description="Webex Bot access token")
    webex_room_id: str = Field(..., description="Webex room/space ID to post to")
    webex_mention_emails: str = Field(
        default="", description="Comma-separated emails of people to mention"
    )

    @property
    def email_recipients(self) -> List[str]:
        """Parse comma-separated email recipients into a list."""
        return [email.strip() for email in self.email_to.split(",") if email.strip()]

    @property
    def webex_mentions(self) -> List[str]:
        """Parse comma-separated Webex mention emails into a list."""
        if not self.webex_mention_emails:
            return []
        return [
            email.strip()
            for email in self.webex_mention_emails.split(",")
            if email.strip()
        ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    """Get application settings, loading from .env file if present."""
    return Settings()

