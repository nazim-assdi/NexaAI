from __future__ import annotations

import json
import re
from typing import Any


N8N_SYSTEM_PROMPT = """You are Nexa AI's n8n workflow engineer.
Create practical, importable n8n workflow JSON from the user's requirements.
Return exactly one JSON object, with no Markdown fences and no commentary.
The object must use the standard n8n workflow export shape:
{
  "name": "Descriptive workflow name",
  "nodes": [
    {
      "id": "stable-unique-id",
      "name": "Readable node name",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [240, 300],
      "parameters": {}
    }
  ],
  "connections": {},
  "active": false,
  "settings": {"executionOrder": "v1"}
}
Use valid standard n8n node type names and realistic parameters. Connect nodes by their exact display names.
Use a Manual Trigger for workflows intended to be run manually; use a Webhook trigger only when requested.
Use Code nodes only when necessary and provide valid JavaScript in parameters.jsCode.
Never invent or embed API keys, passwords, cookies, or private tokens. Use credential placeholders and explain which credentials the user must configure.
For workflows that depend on external websites or APIs, mark those nodes as requiring internet when applicable. Prefer local file, schedule, manual, webhook and local service nodes when the user requests offline automation.
Do not claim a workflow has been executed or tested. The app only generates and validates the JSON structure.
Keep node positions spaced out and use unique IDs and node names.
"""


def build_n8n_messages(requirement: str) -> list[dict[str, str]]:
    text = str(requirement).strip()
    if not text:
        raise ValueError("Describe the workflow you want to build.")
    if len(text) > 12000:
        raise ValueError("The workflow description is too long (maximum 12,000 characters).")
    return [
        {"role": "system", "content": N8N_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]


def _strip_thinking_and_fences(text: str) -> str:
    value = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"^\s*```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```\s*$", "", value)
    return value.strip()


def extract_n8n_json(text: str) -> dict[str, Any]:
    value = _strip_thinking_and_fences(text)
    decoder = json.JSONDecoder()
    candidates = [index for index, char in enumerate(value) if char == "{"]
    for start in candidates:
        try:
            data, _ = decoder.raw_decode(value[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            validate_n8n_workflow(data)
            return data
    raise ValueError("The model did not return a valid n8n JSON object. Try a shorter or more specific description.")


def validate_n8n_workflow(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("Workflow must be a JSON object.")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError("Workflow JSON is missing its name.")
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Workflow must contain at least one node.")

    names: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"Node {index + 1} is not an object.")
        for field in ("name", "type", "typeVersion", "position", "parameters"):
            if field not in node:
                raise ValueError(f"Node {index + 1} is missing '{field}'.")
        name = str(node["name"]).strip()
        if not name or name in names:
            raise ValueError(f"Node {index + 1} has an empty or duplicate name.")
        names.add(name)
        if not isinstance(node["type"], str) or not node["type"].strip():
            raise ValueError(f"Node '{name}' has an invalid type.")
        if not isinstance(node["position"], list) or len(node["position"]) != 2:
            raise ValueError(f"Node '{name}' must have a two-number position.")
        if not all(isinstance(point, (int, float)) for point in node["position"]):
            raise ValueError(f"Node '{name}' position must contain numbers.")
        if not isinstance(node["parameters"], dict):
            raise ValueError(f"Node '{name}' parameters must be an object.")

    connections = data.get("connections", {})
    if not isinstance(connections, dict):
        raise ValueError("Workflow connections must be a JSON object.")
    for source_name, connection in connections.items():
        if source_name not in names:
            raise ValueError(f"Connection refers to an unknown source node: {source_name}")
        if not isinstance(connection, dict):
            raise ValueError(f"Connections for '{source_name}' must be an object.")
        main = connection.get("main", [])
        if not isinstance(main, list):
            raise ValueError(f"Main connections for '{source_name}' must be a list.")
        for output_group in main:
            if not isinstance(output_group, list):
                raise ValueError(f"Main connection outputs for '{source_name}' must be lists.")
            for link in output_group:
                if not isinstance(link, dict) or link.get("node") not in names:
                    raise ValueError(f"Connection from '{source_name}' points to an unknown node.")

    if "settings" in data and not isinstance(data["settings"], dict):
        raise ValueError("Workflow settings must be a JSON object.")


def workflow_json_text(data: dict[str, Any]) -> str:
    validate_n8n_workflow(data)
    return json.dumps(data, ensure_ascii=False, indent=2)
