#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export Claude Code and Codex session logs for a project into "
            "GitHub Flavored Markdown files, one file per session."
        )
    )
    parser.add_argument(
        "project",
        help="Absolute or relative project path used by Claude Code and Codex.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="session-markdown",
        help="Directory where Markdown files will be written.",
    )
    parser.add_argument(
        "--claude-root",
        default="~/.claude",
        help="Claude Code state directory. Default: ~/.claude",
    )
    parser.add_argument(
        "--codex-root",
        default="~/.codex",
        help="Codex state directory. Default: ~/.codex",
    )
    parser.add_argument(
        "--max-tool-output-chars",
        type=int,
        default=12000,
        help="Maximum characters to keep for a single tool output block.",
    )
    return parser.parse_args()


@dataclass
class Event:
    timestamp: str | None
    role: str
    body: str
    collapsed: bool = False
    summary: str | None = None


@dataclass
class SessionDoc:
    source: str
    session_id: str
    started_at: str | None
    project: str
    title: str | None = None
    model: str | None = None
    cwd: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)


def iso_from_unix_seconds(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def normalize_iso(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value


def normalize_project_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def claude_project_dirname(project_path: str) -> str:
    project = project_path.replace("\\", "/")
    return project.replace("/", "-")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return slug.strip("-") or "session"


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "session"


def trim_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    omitted = len(value) - limit
    return f"{value[:limit].rstrip()}\n\n[truncated {omitted} characters]"


def fence_code(text: str, language: str = "") -> str:
    if not text.endswith("\n"):
        text = text + "\n"
    return f"```{language}\n{text}```"


def wrap_details(summary: str, body: str) -> str:
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"


def maybe_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    return json.dumps(value, indent=2, ensure_ascii=False)


def extract_claude_text_block(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return maybe_json(content).strip()

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            parts.append(str(item))
            continue

        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text", "").strip()
            if text:
                parts.append(text)
        elif item_type == "tool_use":
            tool_name = item.get("name", "tool")
            tool_input = maybe_json(item.get("input", {}))
            parts.append(
                f"Tool call: `{tool_name}`\n\n{fence_code(tool_input, 'json')}"
            )
        elif item_type == "tool_result":
            result_text = item.get("content", "")
            if isinstance(result_text, list):
                result_text = maybe_json(result_text)
            parts.append(f"Tool result\n\n{fence_code(str(result_text).strip())}")
        elif item_type == "thinking":
            thinking = item.get("thinking", "").strip()
            if thinking:
                parts.append(f"_Thinking_\n\n{thinking}")
        else:
            parts.append(f"{item_type or 'content'}\n\n{fence_code(maybe_json(item))}")

    return "\n\n".join(part for part in parts if part).strip()


def is_collapsible_tool_text(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("Tool call: `") or stripped.startswith("Tool result")


def claude_summary_for_text(text: str) -> str | None:
    stripped = text.lstrip()
    match = re.match(r"Tool call: `([^`]+)`", stripped)
    if match:
        return f"Tool call: {match.group(1)}"
    if stripped.startswith("Tool result"):
        return "Tool result"
    return None


def is_contextual_user_text(text: str) -> bool:
    stripped = text.lstrip()
    return (
        stripped.startswith("<environment_context>")
        or stripped.startswith("<turn_aborted>")
        or stripped.startswith("<local-command-caveat>")
    )


def load_claude_sessions(
    project_path: str, claude_root: Path, max_tool_output_chars: int
) -> list[SessionDoc]:
    project_dir = claude_root / "projects" / claude_project_dirname(project_path)
    if not project_dir.exists():
        return []

    sessions: list[SessionDoc] = []
    for session_file in sorted(project_dir.glob("*.jsonl")):
        session_id = session_file.stem
        doc = SessionDoc(
            source="claude",
            session_id=session_id,
            started_at=None,
            project=project_path,
            cwd=project_path,
        )

        for raw_line in session_file.open():
            entry = json.loads(raw_line)
            entry_type = entry.get("type")
            timestamp = normalize_iso(entry.get("timestamp"))
            doc.started_at = doc.started_at or timestamp
            doc.cwd = entry.get("cwd") or doc.cwd
            doc.model = (
                entry.get("message", {}).get("model")
                or doc.model
            )

            if entry_type == "user":
                if entry.get("isMeta"):
                    continue
                text = extract_claude_text_block(entry.get("message", {}).get("content"))
                if text:
                    text = trim_text(text, max_tool_output_chars)
                    doc.events.append(Event(
                        timestamp=timestamp,
                        role="user",
                        body=text,
                        collapsed=is_collapsible_tool_text(text) or is_contextual_user_text(text),
                        summary=claude_summary_for_text(text) or (
                            "Session context" if is_contextual_user_text(text) else None
                        ),
                    ))
            elif entry_type == "assistant":
                text = extract_claude_text_block(entry.get("message", {}).get("content"))
                if text:
                    text = trim_text(text, max_tool_output_chars)
                    doc.events.append(
                        Event(
                            timestamp=timestamp,
                            role="assistant",
                            body=text,
                            collapsed=is_collapsible_tool_text(text),
                            summary=claude_summary_for_text(text),
                        )
                    )
            elif entry_type == "summary":
                summary = extract_claude_text_block(entry.get("summary"))
                if summary:
                    doc.events.append(
                        Event(timestamp=timestamp, role="summary", body=summary)
                    )

        if doc.events:
            doc.title = first_user_line(doc.events) or session_id
            sessions.append(doc)

    return sessions


def first_user_line(events: list[Event]) -> str | None:
    for event in events:
        if event.role == "user":
            line = event.body.splitlines()[0].strip()
            if line:
                return line
    return None


def load_codex_threads(codex_root: Path, project_path: str) -> list[sqlite3.Row]:
    db_path = codex_root / "state_5.sqlite"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM threads
            WHERE cwd = ?
            ORDER BY created_at ASC
            """,
            (project_path,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def render_codex_message_content(parts: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for part in parts:
        part_type = part.get("type")
        if part_type in {"input_text", "output_text"}:
            text = part.get("text", "").strip()
            if text:
                blocks.append(text)
        else:
            blocks.append(f"{part_type or 'content'}\n\n{fence_code(maybe_json(part))}")
    return "\n\n".join(blocks).strip()


def load_codex_sessions(
    project_path: str, codex_root: Path, max_tool_output_chars: int
) -> list[SessionDoc]:
    sessions: list[SessionDoc] = []

    for thread in load_codex_threads(codex_root, project_path):
        rollout_path = Path(thread["rollout_path"])
        if not rollout_path.exists():
            continue

        doc = SessionDoc(
            source="codex",
            session_id=thread["id"],
            started_at=iso_from_unix_seconds(thread["created_at"]),
            project=project_path,
            title=thread["title"] or thread["first_user_message"] or thread["id"],
            model=thread["model"],
            cwd=thread["cwd"],
            metadata={
                "git_branch": thread["git_branch"],
                "git_sha": thread["git_sha"],
                "approval_mode": thread["approval_mode"],
                "cli_version": thread["cli_version"],
                "rollout_path": str(rollout_path),
            },
        )

        for raw_line in rollout_path.open():
            entry = json.loads(raw_line)
            timestamp = normalize_iso(entry.get("timestamp"))
            entry_type = entry.get("type")
            payload = entry.get("payload", {})

            if entry_type == "session_meta":
                meta = payload
                doc.started_at = normalize_iso(meta.get("timestamp")) or doc.started_at
                doc.cwd = meta.get("cwd") or doc.cwd
                doc.model = meta.get("model") or doc.model
                continue

            if entry_type == "turn_context":
                continue

            if entry_type != "response_item":
                continue

            payload_type = payload.get("type")
            if payload_type == "message":
                role = payload.get("role")
                if role not in {"user", "assistant", "system", "developer"}:
                    continue
                if role in {"system", "developer"}:
                    continue
                text = render_codex_message_content(payload.get("content", []))
                if text:
                    doc.events.append(
                        Event(
                            timestamp=timestamp,
                            role=role,
                            body=text,
                            collapsed=role == "user" and is_contextual_user_text(text),
                            summary="Session context"
                            if role == "user" and is_contextual_user_text(text)
                            else None,
                        )
                    )
            elif payload_type == "function_call":
                tool_name = payload.get("name", "tool")
                arguments = maybe_json(payload.get("arguments", ""))
                doc.events.append(
                    Event(
                        timestamp=timestamp,
                        role="tool",
                        body=f"Tool call: `{tool_name}`\n\n{fence_code(arguments, 'json')}",
                        collapsed=True,
                        summary=f"Tool call: {tool_name}",
                    )
                )
            elif payload_type == "function_call_output":
                output = trim_text(str(payload.get("output", "")).strip(), max_tool_output_chars)
                doc.events.append(
                    Event(
                        timestamp=timestamp,
                        role="tool_output",
                        body=f"Tool output\n\n{fence_code(output)}",
                        collapsed=True,
                        summary="Tool result",
                    )
                )

        if doc.events:
            sessions.append(doc)

    return sessions


def format_metadata(doc: SessionDoc) -> str:
    lines = [
        f"- Source: `{doc.source}`",
        f"- Session ID: `{doc.session_id}`",
        f"- Project: `{doc.project}`",
    ]
    if doc.cwd:
        lines.append(f"- Working directory: `{doc.cwd}`")
    if doc.started_at:
        lines.append(f"- Started: `{doc.started_at}`")
    if doc.model:
        lines.append(f"- Model: `{doc.model}`")
    for key, value in doc.metadata.items():
        if value is None or value == "":
            continue
        label = key.replace("_", " ").title()
        lines.append(f"- {label}: `{value}`")
    return "\n".join(lines)


def render_session_markdown(doc: SessionDoc) -> str:
    heading = doc.title or doc.session_id
    lines = [f"# {heading}", "", format_metadata(doc), ""]

    for index, event in enumerate(doc.events, start=1):
        if index > 1:
            lines.append("---")
            lines.append("")

        role = event.role.replace("_", " ").title()
        heading_text = role
        body = event.body

        if event.role == "user" and not event.collapsed:
            heading_text = "🧑 Human Prompt"
        elif event.role == "assistant":
            heading_text = "Assistant Reply"
        elif event.role == "summary":
            heading_text = "Summary"
        elif event.role == "tool":
            heading_text = "Tool Call"
        elif event.role == "tool_output":
            heading_text = "Tool Result"

        if event.collapsed:
            label = event.summary or heading_text
            if event.timestamp:
                lines.append(f"**{label}** · `{event.timestamp}`")
            else:
                lines.append(f"**{label}**")
            lines.append("")
            lines.append(wrap_details(event.summary or heading_text, event.body))
        else:
            if event.timestamp:
                lines.append(f"## {index}. {heading_text} ({event.timestamp})")
            else:
                lines.append(f"## {index}. {heading_text}")
            lines.append("")
            lines.append(body)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_sessions(output_dir: Path, sessions: list[SessionDoc]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for doc in sessions:
        started = doc.started_at or "unknown-time"
        started_slug = sanitize_filename(started.replace(":", "-"))
        session_slug = sanitize_filename(doc.session_id)
        filename = f"{doc.source}-{started_slug}-{session_slug}.md"
        (output_dir / filename).write_text(render_session_markdown(doc))


def main() -> int:
    args = parse_args()

    project_path = normalize_project_path(args.project)
    output_dir = Path(args.output_dir).expanduser().resolve()
    claude_root = Path(args.claude_root).expanduser().resolve()
    codex_root = Path(args.codex_root).expanduser().resolve()

    sessions = []
    sessions.extend(load_claude_sessions(project_path, claude_root, args.max_tool_output_chars))
    sessions.extend(load_codex_sessions(project_path, codex_root, args.max_tool_output_chars))
    sessions.sort(key=lambda doc: (doc.started_at or "", doc.source, doc.session_id))

    write_sessions(output_dir, sessions)

    print(
        f"Wrote {len(sessions)} session markdown file(s) for {project_path} to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
