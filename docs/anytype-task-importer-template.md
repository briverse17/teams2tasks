---
name: anytype-task-importer
description: Import tasks from JSON files to Anytype using MCP server. Use when user asks to add tasks to Anytype, import tasks from JSON, or bulk create tasks in Anytype.
license: MIT
compatibility: opencode
---

# Anytype Task Importer

Import tasks from JSON files to Anytype workspace using the MCP server.

## What I do

- Read task data from JSON files
- Identify target Anytype space and task type
- Find or create tags in Anytype
- Batch create tasks with proper property mapping

## Default Parameters

When not specified by user, use these defaults:

| Parameter | Default | Notes |
|-----------|---------|-------|
| JSON file | `outputs/tasks_inferred_*.json` | Use `glob("outputs/tasks_inferred_*.json")` to find the latest |
| Task Type ID | `<TASK_TYPE_ID>` | From list-types API |
| Template ID | `<TEMPLATE_ID>` | From list-templates API |
| Tag name | "BridgeVerse" | |
| Tag ID | `<TAG_ID>` | From list-tags API |
| Space name | "briverse" | |
| Space ID | `<SPACE_ID>` | From list-spaces API |
| Task status | null | Do not set Status select field |

## Required MCP Tools

- anytype_API-list-spaces
- anytype_API-list-types
- anytype_API-list-properties
- anytype_API-list-tags
- anytype_API-create-object
- anytype_API-create-tag
- anytype_API-get-property

## Step 1: Find the JSON File

1. If user specified a path, use that
2. Otherwise, glob `outputs/tasks_inferred_*.json` and use the most recent file (sorted by name)

## Step 2: Read the JSON File

Read the JSON file containing tasks. Expected fields:
- `title` - Task name
- `description` - Task description
- `chat_name` - Source chat/channel
- `assignee` - Assigned person
- `priority` - High/Medium/Low
- `status` - Pending/In Progress/Completed/etc. (ignore this - set to null)
- `due_date` - Due date (nullable)

## Step 3: Identify Target Space and Type

1. Call `anytype_API-list-spaces` to find the space ID
2. Call `anytype_API-list-types` with space_id to find the "task" type (key: `task`)

## Step 4: Find/Create the Tag

1. Call `anytype_API-list-tags` with:
   - `space_id`: The space ID
   - `property_id`: The Tag property ID (from list-properties)

2. If the tag doesn't exist, create it with `anytype_API-create-tag`:
   - `space_id`: The space ID
   - `property_id`: The Tag property ID
   - `name`: The tag name (e.g., "BridgeVerse")
   - `color`: One of: grey, yellow, orange, red, pink, purple, blue, ice, teal, lime

## Step 5: Create Tasks

For each task, call `anytype_API-create-object`:

### Required Parameters
- `space_id`: The space ID
- `type_key`: "task"
- `template_id`: The template ID
- `name`: Task title

### Property Mapping

| Field | Property Key | Format | Notes |
|-------|--------------|--------|-------|
| Tag | `tag` | multi_select | Array of tag IDs |
| Priority | `priority` | number | High=3, Medium=2, Low=1 |
| Due Date | `due_date` | date | ISO format (YYYY-MM-DD) |
| Done | `done` | checkbox | Do not set - leave null |

### Example Task Creation

```json
{
  "space_id": "<SPACE_ID>",
  "name": "Example Task",
  "type_key": "task",
  "template_id": "<TEMPLATE_ID>",
  "body": "**Source Chat:** Test Chat\n\nTask description here.",
  "properties": [
    {"key": "tag", "multi_select": ["<TAG_ID>"]},
    {"key": "priority", "number": 3},
    {"key": "due_date", "date": "2026-04-10"}
  ]
}
```

## Important Notes

1. **Status Field**: Do NOT set the Status select field. Leave it null/default. Status info can be mentioned in the body.

2. **Done Checkbox**: Do NOT set the `done` checkbox. Leave it null.

3. **Batch Operations**: Create tasks in batches. If more than 25 tasks, split into multiple batches.

4. **Body Template**:
```
**Source Chat:** [chat_name]

[description]
```

5. **Priority Mapping**:
   - High = 3
   - Medium = 2
   - Low = 1

6. **Date Format**: Due dates in ISO format (YYYY-MM-DD).
