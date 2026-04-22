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
    return (
        f"You are Neuron, a helpful local AI assistant. "
        f"Respond concisely. {_env()}"
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
        f"Use real Windows paths. {_env()}"
    )
