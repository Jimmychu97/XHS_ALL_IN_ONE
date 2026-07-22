from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

# 全局工具注册表  name -> ToolEntry
TOOL_REGISTRY: Dict[str, "ToolEntry"] = {}


@dataclass
class ToolEntry:
    name: str
    description: str
    param_model: type[BaseModel]
    func: Callable


def agent_tool(name: str, description: str, param_model: type[BaseModel]) -> Callable:
    """装饰器：注册工具到全局注册表"""
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = ToolEntry(name=name, description=description, param_model=param_model, func=func)
        return func
    return decorator


def get_tools_schema() -> List[Dict[str, Any]]:
    """返回 OpenAI function calling 格式的工具列表"""
    result = []
    for entry in TOOL_REGISTRY.values():
        schema = entry.param_model.model_json_schema()
        result.append({
            "type": "function",
            "function": {
                "name": entry.name,
                "description": entry.description,
                "parameters": {
                    "type": schema.get("type", "object"),
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        })
    return result


def execute_tool(name: str, arguments: str, dependencies: Dict[str, Any]) -> str:
    """执行工具，dependencies 作为缺省参数补充"""
    entry = TOOL_REGISTRY.get(name)
    if not entry:
        return f"[工具不存在: {name}]"
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        params: Dict[str, Any] = {}
        for field_name in entry.param_model.model_fields:
            if field_name in args:
                params[field_name] = args[field_name]
            elif field_name in dependencies:
                params[field_name] = dependencies[field_name]
        validated = entry.param_model(**params)
        result = entry.func(validated)
        return str(result) if result is not None else "[工具无返回]"
    except Exception as e:
        return f"[工具执行错误: {e}]"
