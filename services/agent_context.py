"""
Neuron -- Agent Context Builder (v2)
=====================================
Minimal context per mode. No tool descriptions in system prompts.

Tools are now passed via native function calling (tools= parameter),
not as text in the system prompt. This is how Claude/GPT work.

Context tiers:
  CHAT:   ~80 tokens  (env facts + role)
  QUERY:  ~120 tokens (env facts + search instructions)
  ACTION: ~100 tokens (env facts + role — tools are separate)
"""
from __future__ import annotations

import os
import platform
from datetime import datetime
from pathlib import Path


def _env() -> str:
    """One-line environment facts."""
    now = datetime.now()
    return (
        f"{now.strftime('%A, %B %d, %Y')} | "
        f"{now.strftime('%I:%M %p')} | "
        f"{platform.system()} {platform.release()} | "
        f"User: {os.getenv('USERNAME', os.getenv('USER', 'user'))} | "
        f"Home: {Path.home()}"
    )


def build_chat_context() -> str:
    """Minimal context for conversational mode. No tools."""
    if os.getenv("NEURON_CHAT_INCLUDE_ENV", "").lower() in {"1", "true", "yes", "on"}:
        return (
            f"You are Neuron, a helpful local AI assistant. "
            f"Respond concisely. {_env()}"
        )
    now = datetime.now()
    return (
        "You are Neuron. Reply in one short sentence. "
        f"Today is {now.strftime('%A, %B %d, %Y')}."
    )


def build_query_context() -> str:
    """Context for file search + summarization."""
    return (
        f"You are Neuron, a file intelligence assistant. "
        f"List the search results concisely with file names and paths. "
        f"{_env()}"
    )


def build_action_context(tool_descriptions: str = "") -> str:
    """Context for agent mode. Tools are passed separately via schemas."""
    return (
        f"You are Neuron, a local AI assistant that can manage files and run commands. "
        f"Use the provided tools when the user asks you to do something. "
        f"Action mode follows a coding-agent tool surface inspired by claw-code: "
        f"BashTool and PowerShellTool map to powershell_session or shell, FileReadTool maps to file_read, "
        f"FileWriteTool maps to file_write, FileEditTool maps to file_edit, "
        f"and GlobTool maps to glob. "
        f"For code-generation tasks in Action mode, create or edit files with "
        f"file_write/file_edit instead of only chatting. Use powershell_session "
        f"when the user asks to run, compile, test, inspect terminal output, or "
        f"continue a multi-step command session. "
        f"Use only real Windows paths from the user's request or search results. "
        f"Never invent placeholder paths such as C:/path/file.txt or /path/to/file. "
        f"If no real path is available for a new coding artifact, write under "
        f"the user's home directory in a NeuronWorkspace folder with a sensible filename. "
        f"If function-calling is unavailable, emit strict JSON only, for example "
        f'{{"tool":"file_write","args":{{"path":"C:/Users/.../NeuronWorkspace/App.java","content":"..."}}}}. '
        f"{_env()}"
    )
