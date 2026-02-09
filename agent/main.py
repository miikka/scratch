import json
import os
import subprocess
import sys

import httpx

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = "anthropic/claude-opus-4-6"
URL = "https://openrouter.ai/api/v1/chat/completions"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write content to a file (creates or overwrites).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace old_text with new_text in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command and return stdout+stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def execute_tool(name, args):
    try:
        if name == "read":
            return open(args["path"]).read()
        elif name == "write":
            with open(args["path"], "w") as f:
                f.write(args["content"])
            return f"Wrote {len(args['content'])} bytes to {args['path']}"
        elif name == "edit":
            text = open(args["path"]).read()
            if args["old_text"] not in text:
                return "Error: old_text not found in file"
            text = text.replace(args["old_text"], args["new_text"], 1)
            with open(args["path"], "w") as f:
                f.write(text)
            return "OK"
        elif name == "bash":
            r = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True, timeout=120
            )
            out = r.stdout + r.stderr
            return out if out else "(no output)"
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


def chat(messages):
    resp = httpx.post(
        URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": messages, "tools": TOOLS},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


def main():
    if not API_KEY:
        print("Set OPENROUTER_API_KEY env var")
        sys.exit(1)

    messages = [{"role": "system", "content": "You are a helpful assistant with access to tools for reading, writing, and editing files, and running shell commands."}]

    while True:
        try:
            user_input = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.strip().lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            msg = chat(messages)
            messages.append(msg)

            if msg.get("content"):
                print(f"\n{msg['content']}")

            if not msg.get("tool_calls"):
                break

            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                print(f"\n[{name}] {json.dumps(args, indent=2)[:200]}")
                result = execute_tool(name, args)
                print(f"  → {result[:200]}")
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )


if __name__ == "__main__":
    main()
