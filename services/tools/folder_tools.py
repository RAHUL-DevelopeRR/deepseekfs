"""Folder-oriented MemoryOS tools."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from .base import BaseTool, PermissionLevel, ToolParam, ToolResult
from .common import format_size


class FolderCreateTool(BaseTool):
    name = "folder_create"
    description = "Create a new folder (and parent directories if needed)."
    permission = PermissionLevel.MODERATE
    parameters = [
        ToolParam("path", "path", "Absolute path of the folder to create"),
    ]

    def execute(self, path: str, **kwargs) -> ToolResult:
        try:
            folder = Path(path)
            if folder.exists():
                return ToolResult(True, f"Folder already exists: {path}")
            folder.mkdir(parents=True, exist_ok=True)
            return ToolResult(True, f"Created folder: {path}")
        except Exception as exc:
            return ToolResult(False, f"Error creating folder: {exc}")


class FolderListTool(BaseTool):
    name = "folder_list"
    description = "List contents of a directory (files and subdirectories). Returns a tree-like structure."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("path", "path", "Absolute path of the directory to list"),
        ToolParam("max_depth", "integer", "Maximum depth to traverse", required=False, default=2),
        ToolParam("max_items", "integer", "Maximum items to return", required=False, default=100),
    ]

    def execute(self, path: str, max_depth: int = 2, max_items: int = 100, **kwargs) -> ToolResult:
        try:
            folder = Path(path)
            if not folder.is_dir():
                return ToolResult(False, f"Not a directory: {path}")

            lines: list[str] = []
            count = 0

            def walk(dir_path: Path, depth: int, prefix: str) -> None:
                nonlocal count
                if depth > max_depth or count >= max_items:
                    return
                try:
                    entries = sorted(dir_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower()))
                except PermissionError:
                    lines.append(f"{prefix}[Permission Denied]")
                    return

                for entry in entries:
                    if count >= max_items:
                        lines.append(f"{prefix}... (truncated)")
                        return
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        lines.append(f"{prefix}[DIR] {entry.name}/")
                        count += 1
                        walk(entry, depth + 1, prefix + "  ")
                    else:
                        lines.append(f"{prefix}[FILE] {entry.name} ({format_size(entry.stat().st_size)})")
                        count += 1

            walk(folder, 0, "")
            output = f"Contents of {path}:\n" + "\n".join(lines) if lines else f"{path} is empty"
            return ToolResult(True, output, {"count": count, "path": path})
        except Exception as exc:
            return ToolResult(False, f"Error listing folder: {exc}")


class FolderSearchTool(BaseTool):
    name = "folder_search"
    description = "Search for folders by name pattern. Supports glob patterns and fuzzy matching."
    permission = PermissionLevel.SAFE
    parameters = [
        ToolParam("query", "string", "Folder name or pattern to search for"),
        ToolParam("search_path", "path", "Root path to search in", required=False, default=""),
        ToolParam("max_results", "integer", "Max results to return", required=False, default=20),
    ]

    def execute(self, query: str, search_path: str = "", max_results: int = 20, **kwargs) -> ToolResult:
        try:
            root = Path(search_path) if search_path else Path.home()
            if not root.is_dir():
                return ToolResult(False, f"Search path not found: {search_path}")

            results = []
            query_lower = query.lower()

            for dirpath, dirnames, _ in os.walk(str(root)):
                dirnames[:] = [
                    dirname
                    for dirname in dirnames
                    if not dirname.startswith(".")
                    and dirname not in {"node_modules", "__pycache__", ".git", "venv", ".venv", "AppData"}
                ]
                for dirname in dirnames:
                    if query_lower in dirname.lower():
                        full_path = os.path.join(dirpath, dirname)
                        try:
                            file_count = sum(1 for _ in Path(full_path).iterdir())
                        except (PermissionError, OSError):
                            file_count = -1
                        results.append({"path": full_path, "name": dirname, "items": file_count})
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(True, f"No folders matching '{query}' found in {root}")

            output_lines = [f"Found {len(results)} folder(s) matching '{query}':"]
            for result in results:
                items = f" ({result['items']} items)" if result["items"] >= 0 else ""
                output_lines.append(f"  [DIR] {result['path']}{items}")
            return ToolResult(True, "\n".join(output_lines), results)
        except Exception as exc:
            return ToolResult(False, f"Error searching folders: {exc}")


class FolderOrganizeTool(BaseTool):
    name = "folder_organize"
    description = "Organize files in a folder by type, date, or custom categories. Moves files into categorized subfolders."
    permission = PermissionLevel.MODERATE
    parameters = [
        ToolParam("path", "path", "Folder to organize"),
        ToolParam("mode", "string", "Organization mode: 'type' (by extension), 'date' (by modified date), 'size' (by size category)"),
        ToolParam("dry_run", "boolean", "If True, only show plan without moving", required=False, default=True),
    ]

    CATEGORIES = {
        "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex"},
        "Spreadsheets": {".xlsx", ".xls", ".csv", ".ods"},
        "Presentations": {".pptx", ".ppt", ".odp"},
        "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"},
        "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
        "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"},
        "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
        "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".rs", ".go", ".rb", ".php"},
        "Executables": {".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh"},
        "Data": {".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".sql", ".db", ".sqlite"},
    }

    def execute(self, path: str, mode: str = "type", dry_run: bool = True, **kwargs) -> ToolResult:
        try:
            folder = Path(path)
            if not folder.is_dir():
                return ToolResult(False, f"Not a directory: {path}")

            files = [entry for entry in folder.iterdir() if entry.is_file() and not entry.name.startswith(".")]
            if not files:
                return ToolResult(True, f"No files to organize in {path}")

            plan: dict[str, list[Path]] = {}

            if mode == "type":
                for entry in files:
                    category = "Other"
                    for name, exts in self.CATEGORIES.items():
                        if entry.suffix.lower() in exts:
                            category = name
                            break
                    plan.setdefault(category, []).append(entry)
            elif mode == "date":
                for entry in files:
                    category = datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m")
                    plan.setdefault(category, []).append(entry)
            elif mode == "size":
                for entry in files:
                    size = entry.stat().st_size
                    if size < 1024 * 100:
                        category = "Small (< 100KB)"
                    elif size < 1024 * 1024 * 10:
                        category = "Medium (100KB - 10MB)"
                    else:
                        category = "Large (> 10MB)"
                    plan.setdefault(category, []).append(entry)
            else:
                return ToolResult(False, f"Unknown organization mode: {mode}")

            output_lines = [f"Organization plan for {path} (mode: {mode}):"]
            for category, category_files in sorted(plan.items()):
                output_lines.append(f"\n  [DIR] {category}/ ({len(category_files)} files)")
                for entry in category_files[:10]:
                    output_lines.append(f"    -> {entry.name}")
                if len(category_files) > 10:
                    output_lines.append(f"    ... and {len(category_files) - 10} more")

            if dry_run:
                output_lines.append("\n[DRY RUN] No files were moved. Set dry_run=False to execute.")
                return ToolResult(
                    True,
                    "\n".join(output_lines),
                    {"plan": {key: [str(item) for item in value] for key, value in plan.items()}, "dry_run": True},
                )

            moved = 0
            for category, category_files in plan.items():
                target_dir = folder / category
                target_dir.mkdir(exist_ok=True)
                for entry in category_files:
                    destination = target_dir / entry.name
                    if destination.exists():
                        stem = entry.stem
                        suffix = entry.suffix
                        counter = 1
                        while destination.exists():
                            destination = target_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                    shutil.move(str(entry), str(destination))
                    moved += 1

            output_lines.append(f"\n[OK] Moved {moved} files into {len(plan)} categories.")
            return ToolResult(True, "\n".join(output_lines), {"moved": moved, "categories": len(plan)})
        except Exception as exc:
            return ToolResult(False, f"Error organizing folder: {exc}")
