"""Data models for task inference."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def coerce_to_str(v: object) -> str:
    """Coerce int to str for id field."""
    return str(v)



class MessageRef(BaseModel):
    """Reference to the specific message that triggered the task."""

    sender: str
    text: str
    time: str


class Task(BaseModel):
    """Inferred actionable item from Teams chat."""

    id: Annotated[str, BeforeValidator(coerce_to_str)] = Field(
        ..., description="Unique task identifier, e.g., TSK-20240330-001"
    )
    chat_name: str = Field(..., description="Source Teams chat name")
    title: str = Field(..., description="Short, actionable title")
    description: str = Field(..., description="Detailed explanation of what needs to be done")
    assignee: str | None = Field(None, description="Inferred person responsible")
    priority: str = Field("Medium", description="Inferred priority: High, Medium, Low")
    status: str = Field("Pending", description="Initial status: Pending, In Progress, Done")
    due_date: str | None = Field(None, description="Inferred deadline mentions")
    context_tags: list[str] = Field(default_factory=list, description="Extracted keywords")
    source_messages: list[MessageRef] = Field(..., description="Message(s) that led to this task")


class TaskInferenceOutput(BaseModel):
    """The collection of tasks inferred from a specific chat context."""

    tasks: list[Task]

