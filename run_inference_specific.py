#!/usr/bin/env python3
"""Run task inference for specific chats."""

import json
from pathlib import Path
from src.inference.engine import infer_tasks_from_chat

# Load the scraped data
data_path = Path("outputs/scrape_default_20260330_232642.json")
with open(data_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Target chats
target_chats = [
    "David Kuan",
    "In-house AI Devs",
    "Risk transformation to AI/ML",
    "Report for Genesis",
    "[SFI + Pan Asia] ATP Accounts Automation",
]

# Your user name
user_name = "Nguyen Minh Vu"

# Results accumulator
all_tasks = []

print(f"Running task inference for user: {user_name}")
print(f"Target chats: {target_chats}\n")

# Find and process matching chats
found_chats = []
for chat in data["chats"]:
    chat_name = chat.get("name", "")
    if chat_name in target_chats:
        found_chats.append(chat_name)
        messages = chat.get("messages", [])
        
        print(f"Processing: {chat_name} ({len(messages)} messages)")
        try:
            tasks = infer_tasks_from_chat(
                chat_name=chat_name,
                messages=messages,
                user_name=user_name
            )
            print(f"  → Found {len(tasks)} tasks")
            all_tasks.extend(tasks)
        except Exception as e:
            print(f"  ✗ Error: {e}")

# Report results
print(f"\n{'='*60}")
print(f"Total tasks found: {len(all_tasks)}")
print(f"Chats processed: {len(found_chats)}")
if len(found_chats) < len(target_chats):
    missing = [c for c in target_chats if c not in found_chats]
    print(f"Chats not found: {missing}")

# Save results
output_path = Path("outputs/tasks_inferred_specific.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"tasks": all_tasks}, f, indent=2)
print(f"Results saved to: {output_path}")

# Display tasks
if all_tasks:
    print(f"\n{'='*60}")
    print("Inferred Tasks:")
    for i, task in enumerate(all_tasks, 1):
        print(f"\n{i}. {task.get('title', 'N/A')}")
        print(f"   Chat: {task.get('chat_name', 'N/A')}")
        print(f"   Description: {task.get('description', 'N/A')[:100]}...")
        print(f"   Assignee: {task.get('assignee', 'N/A')}")
        print(f"   Priority: {task.get('priority', 'N/A')}")
        print(f"   Due Date: {task.get('due_date', 'N/A')}")
        print(f"   Tags: {', '.join(task.get('context_tags', []))}")
