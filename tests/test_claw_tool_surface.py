import json


def test_claw_tool_index_maps_snapshot_to_neuron_tools(tmp_path, monkeypatch):
    from services.tools import claw_tools
    from services.tools.claw_tools import ClawToolIndexTool

    snapshot = tmp_path / "tools_snapshot.json"
    snapshot.write_text(
        json.dumps(
            [
                {
                    "name": "BashTool",
                    "source_hint": "tools/BashTool/BashTool.tsx",
                    "responsibility": "Run shell commands",
                },
                {
                    "name": "FileWriteTool",
                    "source_hint": "tools/FileWriteTool/FileWriteTool.ts",
                    "responsibility": "Write files",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(claw_tools, "CLAW_TOOL_SNAPSHOT", snapshot)

    result = ClawToolIndexTool().execute("BashTool")

    assert result.success
    assert "BashTool -> Neuron: shell" in result.output


def test_claw_powershell_maps_to_persistent_session(tmp_path, monkeypatch):
    from services.tools import claw_tools
    from services.tools.claw_tools import ClawToolIndexTool

    snapshot = tmp_path / "tools_snapshot.json"
    snapshot.write_text(
        json.dumps(
            [
                {
                    "name": "PowerShellTool",
                    "source_hint": "tools/PowerShellTool/PowerShellTool.tsx",
                    "responsibility": "Run PowerShell commands",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(claw_tools, "CLAW_TOOL_SNAPSHOT", snapshot)

    result = ClawToolIndexTool().execute("PowerShellTool")

    assert result.success
    assert "PowerShellTool -> Neuron: powershell_session" in result.output
