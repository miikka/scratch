import functools
import inspect
import json
import os
import urllib.request


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-sonnet-4"


def _extract_func_body(source):
    """Split decorated source into (decorator_lines, func_def) at the 'def' keyword."""
    lines = source.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("def "):
            return "".join(lines[:i]), "".join(lines[i:])
    return "", source


def _ask_llm(func_source, error, args, kwargs):
    prompt = (
        f"This Python function raised an error when called with "
        f"args={args!r}, kwargs={kwargs!r}:\n\n"
        f"```python\n{func_source}```\n\n"
        f"Error: {error}\n\n"
        f"Return ONLY the fixed function. No markdown fences, no explanation."
    )
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    reply = data["choices"][0]["message"]["content"].strip()
    if reply.startswith("```"):
        lines = reply.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        reply = "\n".join(lines)
    return reply


def selfrepair(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            source_file = inspect.getfile(func)
            with open(source_file) as f:
                full_source = f.read()

            raw_source = inspect.getsource(func)
            _decorators, func_body = _extract_func_body(raw_source)

            print(f"[selfrepair] {func.__name__} raised {type(e).__name__}: {e}")
            print(f"[selfrepair] Asking LLM for a fix...")

            fixed_body = _ask_llm(func_body, e, args, kwargs)
            if not fixed_body.endswith("\n"):
                fixed_body += "\n"

            new_source = full_source.replace(func_body, fixed_body, 1)
            with open(source_file, "w") as f:
                f.write(new_source)
            print(f"[selfrepair] Patched {source_file}")

            ns = {}
            exec(compile(fixed_body, source_file, "exec"), func.__globals__, ns)
            return ns[func.__name__](*args, **kwargs)

    return wrapper
