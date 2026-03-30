from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MessageRef(BaseModel):
    """Reference to the specific message that triggered the task"""
    sender: str
    text: str
    time: str  # ISO timestamp from Teams

class Task(BaseModel):
    """Inferred actionable item from Teams chat"""
    id: str = Field(..., description="Unique task identifier, e.g., TSK-20240330-001")
    chat_name: str = Field(..., description="Source Teams chat name")
    title: str = Field(..., description="Short, actionable title")
    description: str = Field(..., description="Detailed explanation of what needs to be done")
    assignee: Optional[str] = Field(None, description="Inferred person responsible (e.g., 'Richie', 'Fuga')")
    priority: str = Field("Medium", description="Inferred priority: High, Medium, Low")
    status: str = Field("Pending", description="Initial status: Pending, In Progress, Done")
    due_date: Optional[str] = Field(None, description="Inferred deadline mentions (e.g., 'tmr morning')")
    context_tags: List[str] = Field(default_factory=list, description="Extracted keywords (e.g., 'SFID', 'UAT', 'Deployment')")
    source_messages: List[MessageRef] = Field(..., description="Message(s) that led to this task")

class TaskInferenceOutput(BaseModel):
    """The collection of tasks inferred from a specific chat context"""
    tasks: List[Task]
