import json
from typing import List
from datetime import datetime

import dspy

from src.inference.models.task import MessageRef, Task, TaskInferenceOutput

# Configuration for OpenAI
lm = dspy.LM(
    "openai/gpt-4o",
)
dspy.configure(lm=lm)


class TeamsChatToTasks(dspy.Signature):
    """
    Carefully analyze the Teams chat history provided.
    Identify ONLY tasks assigned to or owned by the specified user.
    Extract actionable tasks, requests, or commitments made TO this user or BY this user.
    For each task assigned to the user, infer priority and any mentioned deadlines.
    Extract the specific messages (sender, text, time) that document the task.
    Ignore tasks assigned to other team members.
    Return a structured JSON-formatted list of tasks for this user only, with each task matching the Task schema.
    """

    chat_name = dspy.InputField(desc="The name of the Teams chat")
    user_name = dspy.InputField(desc="The name of the user whose tasks to extract")
    history = dspy.InputField(desc="The formatted string of chat messages for analysis from the target date")
    tasks = dspy.OutputField(desc="A JSON-formatted list of tasks assigned to the user, matching the Task model schema with fields: id, chat_name, title, description, assignee, priority, status, due_date, context_tags, source_messages")


class TaskExtractor(dspy.Module):
    def __init__(self, user_name: str):
        super().__init__()
        self.user_name = user_name
        # Use dspy.Predict with the defined signature
        self.extractor = dspy.Predict(TeamsChatToTasks)

    def forward(self, chat_name: str, messages: List[dict]):
        # Target date: yesterday (Mar 30, 2026)
        target_date = "2026-03-30"
        user_messages_on_date = False
        all_messages_on_date = []

        # First pass: check if user has any messages on target date and collect messages from that date
        for msg in messages:
            timestamp = msg.get("timestamp", msg.get("time", ""))
            sender = msg.get("sender_name", msg.get("sender", "Unknown"))
            text = msg.get("text", "")

            # Extract date from timestamp (assuming ISO format or similar)
            try:
                msg_date = timestamp.split("T")[0] if "T" in timestamp else timestamp.split(" ")[0]
            except:
                msg_date = ""

            if msg_date == target_date:
                all_messages_on_date.append((timestamp, sender, text))
                if sender.lower() == self.user_name.lower():
                    user_messages_on_date = True

        # Skip chat if user didn't send any messages on target date (saves tokens)
        if not user_messages_on_date:
            return []

        # Pre-process messages into a readable format for the LLM
        formatted_history = []
        for timestamp, sender, text in all_messages_on_date:
            formatted_history.append(f"[{timestamp}] {sender}: {text}")

        history_str = "\n".join(formatted_history)

        # Run extraction with user context
        response = self.extractor(chat_name=chat_name, user_name=self.user_name, history=history_str)

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
                    print(f"Error: TaskInferenceOutput validation failed for chat '{chat_name}': {e}")
                    return []
            return []
        except Exception as e:
            print(f"Error parsing task output for chat '{chat_name}': {e}")
            print(f"Raw output: {response.tasks}")
            return []


def infer_tasks_from_chat(chat_name: str, messages: List[dict], user_name: str) -> List[dict]:
    """Helper function to run the inference engine on a single chat's messages."""
    engine = TaskExtractor(user_name=user_name)
    return engine(chat_name=chat_name, messages=messages)
