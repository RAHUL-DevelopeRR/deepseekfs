def test_action_coding_prompt_selects_coding_agent_tools(monkeypatch):
    from services.agent.executor import TaskExecutor

    def schema(name):
        return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}

    executor = TaskExecutor(engine=object())
    executor._tool_schemas = [
        schema("file_write"),
        schema("file_edit"),
        schema("file_read"),
        schema("glob"),
        schema("shell"),
        schema("folder_list"),
    ]

    selected = executor._select_relevant_schemas(
        "give me code for a Java hospital management system"
    )
    names = {item["function"]["name"] for item in selected}

    assert {"file_write", "file_edit", "file_read", "glob", "shell"} <= names
    from services.agent_context import build_action_context
    assert "Save code" in build_action_context(coding=True)
    assert "Save code" not in build_action_context()
    assert "stop calling tools" in build_action_context()


def test_folder_listing_does_not_receive_unrelated_tool_schemas():
    from services.agent.executor import TaskExecutor

    def schema(name):
        return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}

    executor = TaskExecutor(engine=object())
    executor._tool_schemas = [schema(name) for name in (
        "folder_list", "folder_create", "file_read", "glob", "file_delete",
    )]

    names = {item["function"]["name"] for item in executor._select_relevant_schemas(
        "list files in folder: C:/Users/example/Documents"
    )}

    assert names == {"folder_list"}


def test_tool_name_inside_file_content_does_not_match_tool_keyword():
    from services.agent.executor import TaskExecutor

    names = {item["function"]["name"] for item in TaskExecutor(object())._select_relevant_schemas(
        "Create a text file containing exactly TOOL_ACTION_OK"
    )}

    assert names == {"file_write"}
