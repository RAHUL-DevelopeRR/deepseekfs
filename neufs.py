"""Headless Neuron filesystem assistant CLI.

Usage examples:
    python neufs.py status
    python neufs.py search "python files" --limit 5
    python neufs.py index "C:/Users/me/Documents" --recursive
    python neufs.py summarize "C:/Users/me/Documents"
    python neufs.py chat "hello"
    python neufs.py action --tool folder_list --arg path=.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _print_json(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if payload.get("ok", False) else 1


def _cmd_status(_args: argparse.Namespace) -> int:
    import app.config as config
    from services.model_manager import get_llm_model_path, get_model_search_dirs

    index_count = None
    try:
        from core.indexing.index_builder import get_index
        idx = get_index()
        index_count = idx._db.count()
    except Exception as exc:
        index_error = str(exc)
    else:
        index_error = None

    model_path = get_llm_model_path()
    return _print_json(
        {
            "ok": True,
            "storage_dir": str(config.STORAGE_DIR),
            "base_dir": str(config.BASE_DIR),
            "runtime_dir": str(config.RUNTIME_DIR),
            "model_path": str(model_path) if model_path else None,
            "model_search_dirs": [str(p) for p in get_model_search_dirs()],
            "index_count": index_count,
            "index_error": index_error,
            "internet_enabled": bool(config.UserConfig.load().get("internet_enabled", False)),
            "watch_paths": config.WATCH_PATHS,
        }
    )


def _cmd_search(args: argparse.Namespace) -> int:
    from core.search.semantic_search import SemanticSearch

    results = SemanticSearch().search(args.query, top_k=args.limit, use_llm_rerank=False)
    return _print_json(
        {
            "ok": True,
            "query": args.query,
            "count": len(results),
            "results": results,
        }
    )


def _cmd_index(args: argparse.Namespace) -> int:
    import app.config as config
    from core.indexing.index_builder import get_index

    path = Path(args.path).expanduser()
    if not path.exists() or not path.is_dir():
        return _print_json({"ok": False, "error": f"Folder not found: {path}"})

    if args.add_watch:
        config.UserConfig.add_watch_path(str(path))

    idx = get_index()
    added = idx.index_directory(str(path), recursive=args.recursive)
    idx.save()

    return _print_json(
        {
            "ok": True,
            "path": str(path.resolve()),
            "recursive": args.recursive,
            "added": added,
            "index_count": idx._db.count(),
            "added_to_watch_paths": bool(args.add_watch),
        }
    )


def _cmd_summarize(args: argparse.Namespace) -> int:
    from services.tools.search_tools import SummarizeTool

    path = Path(args.path).expanduser()
    if not path.exists():
        return _print_json({"ok": False, "error": f"Path not found: {path}"})

    result = SummarizeTool().execute(str(path))
    return _print_json(
        {
            "ok": result.success,
            "path": str(path.resolve()),
            "summary": result.output,
            "data": result.data,
        }
    )


def _cmd_chat(args: argparse.Namespace) -> int:
    from services.memory_os import get_memory_os
    from services.internet_search import internet_enabled_for_request

    override = True if args.internet else False if args.offline else None
    agent = get_memory_os()
    with internet_enabled_for_request(override):
        response = agent.chat(args.message, mode=args.mode)
    return _print_json({"ok": True, "mode": args.mode, "response": response})


def _cmd_action(args: argparse.Namespace) -> int:
    from services.agent.executor import TaskExecutor
    from services.agent.task import Task

    try:
        tool_args = _parse_tool_args(args.args, args.arg or [])
    except json.JSONDecodeError as exc:
        return _print_json({"ok": False, "error": f"Invalid --args JSON: {exc}"})
    except ValueError as exc:
        return _print_json({"ok": False, "error": str(exc)})

    if not isinstance(tool_args, dict):
        return _print_json({"ok": False, "error": "--args must decode to a JSON object"})

    executor = TaskExecutor(engine=None)
    if args.yes:
        executor.on_confirmation = lambda *_: True

    task = Task(goal=args.goal or f"run {args.tool}")
    output = executor._execute_tool_step(task, args.tool, tool_args)
    ok = output.startswith("[OK]")
    return _print_json(
        {
            "ok": ok,
            "tool": args.tool,
            "output": output,
            "task": task.to_dict(),
        }
    )


def _parse_tool_args(json_arg: str, pairs: list[str]) -> dict[str, Any]:
    if json_arg and json_arg.startswith("@"):
        json_text = Path(json_arg[1:]).read_text(encoding="utf-8")
    else:
        json_text = json_arg or "{}"

    parsed = json.loads(json_text)
    if not isinstance(parsed, dict):
        raise ValueError("--args must decode to a JSON object")

    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--arg must be key=value, got: {pair}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--arg key cannot be empty")
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError:
            parsed[key] = value
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neufs", description="Headless Neuron filesystem assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show storage, model, and index status")
    status.set_defaults(func=_cmd_status)

    search = sub.add_parser("search", help="Run offline semantic search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.set_defaults(func=_cmd_search)

    index = sub.add_parser("index", help="Index a folder into the offline semantic index")
    index.add_argument("path")
    index.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    index.add_argument("--add-watch", action="store_true", help="Persist this folder as a watched folder")
    index.set_defaults(func=_cmd_index)

    summarize = sub.add_parser("summarize", help="Summarize a file or folder")
    summarize.add_argument("path")
    summarize.set_defaults(func=_cmd_summarize)

    chat = sub.add_parser("chat", help="Run headless MemoryOS chat")
    chat.add_argument("message")
    chat.add_argument("--mode", choices=["auto", "chat", "query", "action"], default="chat")
    live = chat.add_mutually_exclusive_group()
    live.add_argument("--internet", action="store_true", help="Opt in to live public web retrieval for this request")
    live.add_argument("--offline", action="store_true", help="Force offline-only mode for this request")
    chat.set_defaults(func=_cmd_chat)

    action = sub.add_parser("action", help="Run a direct tool action")
    action.add_argument("--tool", required=True)
    action.add_argument("--args", default="{}")
    action.add_argument("--arg", action="append", help="Tool argument as key=value; repeatable")
    action.add_argument("--goal", default="")
    action.add_argument("--yes", action="store_true", help="Approve moderate tools")
    action.set_defaults(func=_cmd_action)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        return _print_json({"ok": False, "error": str(exc), "type": type(exc).__name__})


if __name__ == "__main__":
    raise SystemExit(main())
