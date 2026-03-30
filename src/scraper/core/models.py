from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Message(BaseModel):
    id: str = Field(..., description="Unique message ID extracted from Teams")
    timestamp: datetime = Field(..., description="Timestamp of the message")
    sender_name: str = Field(..., description="Display name of the sender")
    sender_email: Optional[str] = Field(None, description="Sender email address if available")
    text: str = Field(..., description="The message content")

class Chat(BaseModel):
    id: str = Field(..., description="Unique chat/thread ID")
    name: str = Field(..., description="Name of the chat")
    messages: List[Message] = Field(default_factory=list)

class ScrapeOutput(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.now)
    chats: List[Chat]
