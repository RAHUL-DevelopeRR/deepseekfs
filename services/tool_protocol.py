"""Qwen's Hermes tool prompt and OpenAI-compatible response conversion."""
import json
import re


def tool_messages(messages, tools):
    schemas = "\n".join(json.dumps(tool["function"], ensure_ascii=False) for tool in tools)
    instruction = '\n# Tools\nYou may call the following functions:\n<tools>\n' + schemas + '\n</tools>\n'
    if len(tools) == 1:
        instruction += (
            'When an operation is needed, call the listed function. Output only its JSON arguments inside one '
            '<tool_call></tool_call> block; omit the function name and wrapper. '
            'Example: <tool_call>{"path":"/absolute/path"}</tool_call>. '
        )
    else:
        instruction += (
            'For each function call return a JSON object inside <tool_call></tool_call> tags: '
            '<tool_call>{"name":"function_name","arguments":{"argument":"value"}}</tool_call>. '
        )
    instruction += (
        'Use only listed functions. Never claim success without a successful tool result. '
        'After the requested operations succeed, answer in plain text using the tool results. '
        'Do not repeat completed operations.'
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
    payloads = [json.loads(match.group(1)) for match in matches]
    compact_arguments = False
    if not matches and len(allowed) == 1:
        fenced = re.fullmatch(r"\s*```(?:json)?\s*(\{.*?\})\s*```\s*", content, re.DOTALL | re.IGNORECASE)
        raw = fenced.group(1) if fenced else content.strip()
        if raw.startswith("{") and raw.endswith("}"):
            try:
                payloads = [json.loads(raw)]
                compact_arguments = True
            except json.JSONDecodeError:
                pass
    for payload in payloads:
        name, arguments = payload.get("name"), payload.get("arguments", {})
        if name is None and len(allowed) == 1:
            name = next(iter(allowed))
            arguments = payload.get("arguments", payload)
        if name not in allowed or not isinstance(arguments, dict):
            raise ValueError("Model selected an unavailable tool or invalid arguments")
        calls.append({"id": f"call_{len(calls)}", "type": "function", "function": {
            "name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}})
    cleaned = "" if compact_arguments and calls else re.sub(
        r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL
    ).strip()
    return {"role": "assistant", "content": cleaned, "tool_calls": calls}
