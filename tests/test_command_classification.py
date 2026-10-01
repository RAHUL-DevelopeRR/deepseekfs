from services.tools.base import PermissionLevel
from services.tools.execution_tools import ShellTool


def test_compound_commands_cannot_bypass_confirmation():
    classify = ShellTool()._classify_command
    assert classify("Get-Date") == PermissionLevel.SAFE
    assert classify("Get-Date\nRemove-Item notes.txt") == PermissionLevel.DANGEROUS
    assert classify("Get-Date; Set-Content notes.txt x") == PermissionLevel.MODERATE
    assert classify("Get-Date $(Set-Content notes.txt x)") == PermissionLevel.MODERATE
