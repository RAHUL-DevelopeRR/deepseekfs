"""Cross-platform system tools."""
from __future__ import annotations

from .base import BaseTool, PermissionLevel, ToolResult


class SystemProfileTool(BaseTool):
    name = "system_profile"
    description = "Return OS, storage, hotkey, and packaging profile for this device."
    permission = PermissionLevel.SAFE
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        from services.platform_support import get_platform_profile, is_windows_10_or_newer

        profile = get_platform_profile().to_dict()
        profile["windows_10_or_newer"] = is_windows_10_or_newer()
        lines = [
            f"OS: {profile['system']} {profile['machine']}",
            f"Data: {profile['data_dir']}",
            f"Cache: {profile['cache_dir']}",
            f"Hotkeys: {profile['hotkeys']}",
            f"Desktop bundle: {profile['desktop_bundle']}",
            f"Mobile bundle: {profile['mobile_bundle']}",
        ]
        return ToolResult(True, "\n".join(lines), profile)
