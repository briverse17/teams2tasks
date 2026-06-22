"""Data models for MS Teams scraper output."""

from datetime import datetime

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represent a single message in a Teams chat."""

    id: str = Field(..., description="Unique message ID extracted from Teams")
    timestamp: datetime = Field(..., description="Timestamp of the message")
    sender_name: str = Field(..., description="Display name of the sender")
    sender_email: str | None = Field(None, description="Sender email address if available")
    text: str = Field(..., description="The message content")


class Chat(BaseModel):
    """Represent a single chat conversation thread."""

    id: str = Field(..., description="Unique chat/thread ID")
    name: str = Field(..., description="Name of the chat")
    type: str = Field(..., description="Type of chat: personal, one-on-one, or group")
    participants: list[str] = Field(
        default_factory=list,
        description="List of participant IDs parsed from the chat ID"
    )
    messages: list[Message] = Field(default_factory=list)


class ScrapeOutput(BaseModel):
    """Represent the final compiled output of the scraper."""

    generated_at: datetime = Field(default_factory=datetime.now)
    chats: list[Chat]

