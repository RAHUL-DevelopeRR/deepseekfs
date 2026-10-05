"""Qwen's Hermes tool prompt and OpenAI-compatible response conversion."""
import json
import re


def tool_messages(messages, tools):
    schemas = "\n".join(json.dumps(tool["function"], ensure_ascii=False) for tool in tools)
    instruction = (
        '\n# Tools\nYou may call the following functions:\n<tools>\n' + schemas
        + '\n</tools>\nFor each function call return a JSON object inside '
        '<tool_call></tool_call> tags: '
        '<tool_call>{"name":"function_name","arguments":{"argument":"value"}}</tool_call>. '
        'Use only listed functions. Never claim an operation succeeded without its tool result.'
    )
    fitted = [dict(message) for message in messages]
    if fitted and fitted[0].get("role") == "system":
        fitted[0]["content"] = (fitted[0].get("content") or "") + instruction
    else:
        fitted.insert(0, {"role": "system", "content": instruction})
    for message in fitted:
        if message.get("role") == "tool":
            message["role"] = "user"
            message["content"] = '<tool_response>\n' + (message.get("content") or "") + '\n</tool_response>'
        if message.get("tool_calls"):
            message["content"] = (message.get("content") or "") + "\n" + "\n".join(
                '<tool_call>' + json.dumps({"name": call["function"]["name"],
                    "arguments": json.loads(call["function"]["arguments"])}) + '</tool_call>'
                for call in message.pop("tool_calls")
            )
    return fitted


def tool_response(content, tools):
    allowed = {tool["function"]["name"] for tool in tools}
    calls = []
    matches = list(re.finditer(r'<tool_call>\s*(.*?)\s*</tool_call>', content, re.DOTALL))
    if '<tool_call>' in content and not matches:
        raise ValueError("Incomplete model tool call")
    for match in matches:
        payload = json.loads(match.group(1))
        name, arguments = payload.get("name"), payload.get("arguments", {})
        if name not in allowed or not isinstance(arguments, dict):
            raise ValueError("Model selected an unavailable tool or invalid arguments")
        calls.append({"id": f"call_{len(calls)}", "type": "function", "function": {
            "name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}})
    return {"role": "assistant", "content": re.sub(r'<tool_call>.*?</tool_call>', '', content,
        flags=re.DOTALL).strip(), "tool_calls": calls}
