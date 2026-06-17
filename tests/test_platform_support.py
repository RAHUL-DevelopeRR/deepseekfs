def test_platform_profile_has_runtime_dirs():
    from services.platform_support import get_platform_profile

    profile = get_platform_profile()

    assert profile.system
    assert profile.data_dir
    assert profile.cache_dir
    assert profile.desktop_bundle


def test_system_profile_tool_registered():
    from services.tools import get_tool

    tool = get_tool("system_profile")
    result = tool.execute()

    assert result.success
    assert "OS:" in result.output
    assert "Desktop bundle:" in result.output
