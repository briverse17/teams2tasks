"""Engine to extract tasks from a Teams chat."""

import json
from typing import Any, cast

import dspy

from src.inference.models.task import MessageRef, Task, TaskInferenceOutput

# Configuration for OpenAI
lm = dspy.LM("openai/gpt-4o")
dspy.configure(lm=lm)


class TeamsChatToTasks(dspy.Signature):  # type: ignore[misc]
    """Analyze carefully the Teams chat history provided.

    Identify ONLY tasks assigned to or owned by the specified user.
    Extract actionable tasks, requests, or commitments made TO this user or BY this user.
    For each task assigned to the user, infer priority and any mentioned deadlines.
    Extract the specific messages (sender, text, time) that document the task.
    Ignore tasks assigned to other team members.
    Return a structured JSON-formatted list of tasks for this user only, with each task matching the
    Task schema.
    """

    chat_name = dspy.InputField(desc="The name of the Teams chat")
    user_name = dspy.InputField(desc="The name of the user whose tasks to extract")
    history = dspy.InputField(
        desc="The formatted string of recent chat messages for analysis"
    )
    tasks = dspy.OutputField(
        desc="""A JSON-formatted list of tasks assigned to the user, matching the Task model schema
with fields: id, chat_name, title, description, assignee, priority, status, due_date, 
context_tags, source_messages"""
    )


class TaskExtractor(dspy.Module):  # type: ignore[misc]
    """Extract tasks from a Teams chat."""

    def __init__(self, user_name: str) -> None:
        """Initialize the TaskExtractor."""
        super().__init__()
        self.user_name = user_name
        # Use dspy.Predict with the defined signature
        self.extractor = dspy.Predict(TeamsChatToTasks)

    def forward(
        self,
        chat_name: str,
        messages: list[dict[str, Any]],
        window_size: int = 30,
        custom_instructions: str | None = None,
    ) -> list[dict[str, Any]]:
        """Forward pass to extract tasks from a Teams chat."""
        # Use a window of the most recent messages instead of a specific date
        recent_messages = messages[-window_size:] if len(messages) > window_size else messages
        
        if not recent_messages:
            return []

        # Pre-process messages into a readable format for the LLM
        formatted_history = []
        for msg in recent_messages:
            timestamp = msg.get("timestamp", msg.get("time", ""))
            sender = msg.get("sender_name", msg.get("sender", "Unknown"))
            text = msg.get("text", "")
            formatted_history.append(f"[{timestamp}] {sender}: {text}")

        history_str = "\n".join(formatted_history)
        if custom_instructions:
            history_str += f"\n\n[CUSTOM DIRECTIVES FOR THIS CHAT]: {custom_instructions}"

        # Run extraction with user context
        response = self.extractor(
            chat_name=chat_name, user_name=self.user_name, history=history_str
        )

        # Parse the JSON output from the LLM
        try:
            # Clean up potential markdown formatting if LLM includes it
            cleaned_tasks = response.tasks.strip()
            if cleaned_tasks.startswith("```"):
                # Remove code blocks
                lines = cleaned_tasks.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_tasks = "\n".join(lines).strip()

            task_list_data = json.loads(cleaned_tasks)
            # Handle both list of tasks and {tasks: [...]} formats
            if isinstance(task_list_data, dict) and "tasks" in task_list_data:
                task_list_data = task_list_data["tasks"]

            # Validate that tasks match the Task model schema using TaskInferenceOutput
            if isinstance(task_list_data, list):
                try:
                    # Explicitly construct MessageRef objects and validate complete Task structure
                    validated_tasks = []
                    for task_data in task_list_data:
                        # Explicitly construct MessageRef objects for source_messages
                        if "source_messages" in task_data and task_data["source_messages"]:
                            task_data["source_messages"] = [
                                MessageRef(**msg) for msg in task_data["source_messages"]
                            ]
                        # Create Task with validated MessageRef objects
                        task = Task(**task_data)
                        validated_tasks.append(task)

                    # Wrap in TaskInferenceOutput for final collection validation
                    inference_output = TaskInferenceOutput(tasks=validated_tasks)
                    return [task.model_dump() for task in inference_output.tasks]
                except Exception as e:
                    print(f"Error: Task validation failed for chat '{chat_name}': {e}")
                    print(f"Task data: {task_list_data}")
                    return []
            elif isinstance(task_list_data, dict) and "tasks" in task_list_data:
                try:
                    tasks_data = task_list_data["tasks"]
                    # Explicitly construct MessageRef objects
                    for task_data in tasks_data:
                        if "source_messages" in task_data and task_data["source_messages"]:
                            task_data["source_messages"] = [
                                MessageRef(**msg) for msg in task_data["source_messages"]
                            ]
                    inference_output = TaskInferenceOutput(tasks=[Task(**t) for t in tasks_data])
                    return [task.model_dump() for task in inference_output.tasks]
                except Exception as e:
                    print(
                        f"Error: TaskInferenceOutput validation failed for chat '{chat_name}': {e}"
                    )
                    return []
            return []
        except Exception as e:
            print(f"Error parsing task output for chat '{chat_name}': {e}")
            print(f"Raw output: {response.tasks}")
            return []


def infer_tasks_from_chat(
    chat_name: str,
    messages: list[dict[str, Any]],
    user_name: str,
    window_size: int = 30,
    custom_instructions: str | None = None,
) -> list[dict[str, Any]]:
    """Run the inference engine on a sliding window of recent messages."""
    engine = TaskExtractor(user_name=user_name)
    return cast(
        list[dict[str, Any]],
        engine(
            chat_name=chat_name,
            messages=messages,
            window_size=window_size,
            custom_instructions=custom_instructions,
        ),
    )

