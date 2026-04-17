# AGENTS.md

## Commands

```bash
uv sync              # Install dependencies
uv run playwright install chromium  # Install browser deps
uv run ruff check .   # Lint
uv run mypy .         # Type check
```

## CLI Apps

### MS Teams Scraper (`main.py`)

```bash
uv run python main.py <command>
```

| Command | Description |
|---------|-------------|
| `default` | Scrape all active chats from today |
| `by-chats "Chat1" "Chat2"` | Scrape specific chat names |
| `by-dates "2026-03-30" "2026-03-29"` | Scrape dates (ISO or DD/MM format) |
| `by-range <from> [to]` | Scrape date range (to defaults to today) |

Options:
- `--stop-early`: Stop scanning sidebar when a chat is before from-date

### Task Inference (`run_inference.py`)

```bash
uv run python run_inference.py <scraped_messages_json_path>
```

- Reads scraped JSON, infers tasks using AI (last 30 messages per chat)
- User name: `Nguyen Minh Vu` (hardcoded)
- Output: `outputs/tasks_inferred_<timestamp>.json`

### Task Inference Specific (`run_inference_specific.py`)

```bash
uv run python run_inference_specific.py
```

- Hardcoded: data path, target chats, user name
- Edit the script to change targets
- Output: `outputs/tasks_inferred_specific.json`

## Key Conventions

- **Python 3.13+** required
- **uv** is the package manager (not pip)
- Lint → Typecheck order matters before committing

## Anytype Task Importer Skill

When user asks to add tasks to Anytype or import from JSON:

1. Load skill: `anytype-task-importer`
2. Default JSON: `outputs/tasks_inferred_*.json` (latest)
3. Default tag: "BridgeVerse"
4. Default space: "briverse"

Skill location: `.opencode/skills/anytype-task-importer/`

If skill doesn't exist, use the prompting guide below to generate it.

### Prompting Guide to Generate the Skill

When the skill doesn't exist, use this prompt to generate it:

```
Create an OpenCode skill called "anytype-task-importer" at `.opencode/skills/anytype-task-importer/SKILL.md`.

The skill imports tasks from JSON files to Anytype using the MCP server.

## Frontmatter
- name: anytype-task-importer
- description: Import tasks from JSON files to Anytype using MCP server. Use when user asks to add tasks to Anytype, import tasks from JSON, or bulk create tasks in Anytype.
- license: MIT
- compatibility: opencode

## Default Parameters Table
| Parameter | Default | Notes |
|-----------|---------|-------|
| JSON file | `outputs/tasks_inferred_*.json` | Use glob to find the latest |
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

## Workflow Steps

1. Find the JSON file (glob `outputs/tasks_inferred_*.json` or use user-specified path)
2. Read the JSON file
3. Identify target space and type (use defaults or query APIs)
4. Find/create the tag (use defaults or query APIs)
5. Create tasks using create-object API

## Property Mapping
- Tag: `tag` key, multi_select format
- Priority: `priority` key, number format (High=3, Medium=2, Low=1)
- Due Date: `due_date` key, date format (YYYY-MM-DD)
- Done: `done` key, checkbox format (do NOT set - leave null)

## Important Notes
- Do NOT set Status select field - leave it null
- Do NOT set done checkbox - leave it null
- Body template: `**Source Chat:** [chat_name]\n\n[description]`
- Use template_id parameter when creating objects

Save the template to `docs/anytype-task-importer-template.md`.
```

### Fixed IDs (discovered via Anytype MCP)

| ID | Purpose |
|----|---------|
| `bafyreier3cjtrgg2b3z4oli5cjs6kgf3uysv2bfcga6ojcg3c3m6x3u7y4.4t1v1kyxckvy` | Space ID |
| `bafyreictooewbq3q7rq4rtcaojrz7p7au2phrf3u5znavhaz4dmnw6aq3m` | Task Type ID |
| `bafyreiausneaasv3577yhbtmpbtgdd43mfgnl5jawxqifj5imyfki4onlm` | Template ID |
| `bafyreigfjpmwp4huvflf2op5opcuakto2vekicsexsgtt6zjuzxursycxa` | BridgeVerse Tag ID |
| `bafyreig2t7qwggkufghg5sosn4qtpzuy6nywu2bo4muaqrj6l5w4bcqaam` | Tag Property ID |
