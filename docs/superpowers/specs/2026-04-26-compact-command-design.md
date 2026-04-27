# `/compact` Command Design

**Date:** 2026-04-26
**Scope:** Add `/compact` command to agentic mode in `src/bot/orchestrator.py`.

## Background

Session continuity already works — `claude_session_id` is persisted in SQLite and auto-resumed between messages and bot restarts. `/new` already exists and clears the session. `/compact` is the only new feature needed.

## Goal

Give users a way to shrink an active session's context window usage without losing the thread. `/compact` summarises the current session, resets the Claude session, and injects the summary into the next message so the conversation continues seamlessly.

## Architecture

No changes to `ClaudeIntegration`, `SessionManager`, or the database schema. All state lives in `context.user_data` (Telegram's per-user in-memory dict). The feature is purely orchestrator-level.

## Components

### 1. `agentic_compact` handler

Location: `src/bot/orchestrator.py`, alongside `agentic_new`.

Steps:
1. Read `claude_session_id` from `context.user_data`. If absent, reply "No active session to compact." and return.
2. Send a "Working..." progress message.
3. Call `claude_integration.run_command()` with the active session ID and this fixed prompt:
   > "Summarise our entire conversation so far. Include: all decisions made, key facts, work completed, and what we were working towards. Be concise but complete enough to continue effectively."
4. On success:
   - Store `claude_response.result` in `context.user_data["compact_summary"]`.
   - Clear `context.user_data["claude_session_id"]` (set to `None`).
   - Set `context.user_data["force_new_session"] = True`.
   - Edit progress message to "Session compacted ✓".
5. On failure (exception or `claude_response.is_error`):
   - Edit progress message to "Compact failed — session unchanged."
   - Leave `claude_session_id` and session state untouched.

### 2. Summary injection in `agentic_text`

After building `prompt = location_prefix + message_text`, check:

```python
compact_summary = context.user_data.get("compact_summary")
if compact_summary and context.user_data.get("force_new_session"):
    prompt = f"[Previous session summary: {compact_summary}]\n\n{prompt}"
```

`compact_summary` is cleared from `user_data` in the same place `force_new_session` is cleared (after the first successful `run_command` call), so it is only prepended once.

### 3. Registration

In `_register_agentic_handlers`:
```python
app.add_handler(CommandHandler("compact", self._inject_deps(self.agentic_compact)))
```

In `get_bot_commands()` (agentic branch):
```python
BotCommand("compact", "Compact current session to save context")
```

## Data flow

```
User: /compact
  → agentic_compact: run_command(session_id, summarise_prompt)
  → on success: user_data["compact_summary"] = summary
                user_data["claude_session_id"] = None
                user_data["force_new_session"] = True
  → reply: "Session compacted ✓"

User: <next message>
  → agentic_text: prompt = "[Previous session summary: ...]" + message
                  force_new=True → new Claude session
  → on success: user_data["force_new_session"] = False   ← cleared here
                user_data["compact_summary"] = deleted   ← cleared here
                user_data["claude_session_id"] = new_id
```

## Error handling

- No active session: immediate reply, no API call.
- `run_command` raises exception: caught, progress message updated, session state unchanged.
- `claude_response.is_error`: treated same as exception.

## Out of scope

- Showing the summary to the user (kept internal to reduce noise).
- Persisting `compact_summary` to SQLite (lost on bot restart; acceptable since it's a transient compaction aid).
- Any changes to `/new`, session storage, or the Claude integration layer.
