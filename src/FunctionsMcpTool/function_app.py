import logging
import os
import re

import azure.functions as func

from auth.fabric_auth import init_server_auth, require_auth
from tools import all_tools, AUTH_TOOL_NAMES
from clients.fabric_client import list_workspaces

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

_auth_initialized = False


def _ensure_auth():
    global _auth_initialized
    if not _auth_initialized:
        init_server_auth()
        _auth_initialized = True


def _resolve_workspace_id(value: str) -> str:
    if GUID_RE.match(value):
        return value
    workspaces = list_workspaces()
    clean = value.lower().replace("-", "")
    for ws in workspaces:
        if ws["displayName"].lower() == clean or ws["displayName"].lower() == value.lower():
            return ws["id"]
    raise ValueError(f'Workspace "{value}" not found.')


# Register all tools as MCP tool triggers
for _tool in all_tools:
    if _tool["name"] in AUTH_TOOL_NAMES:
        continue

    _props = _tool["input_schema"].get("properties", {})
    _required = _tool["input_schema"].get("required", [])

    # Collect required properties for decorators
    _req_props = [(k, _props[k].get("description", k)) for k in _required if k in _props]

    def _make_handler(tool):
        def handler(**kwargs) -> str:
            try:
                _ensure_auth()
                require_auth()
                args = {k: v for k, v in kwargs.items() if v is not None}
                if "workspaceId" in args and not GUID_RE.match(str(args["workspaceId"])):
                    args["workspaceId"] = _resolve_workspace_id(str(args["workspaceId"]))
                return tool["handler"](args)
            except Exception as e:
                logging.error(f"Tool {tool['name']} error: {e}")
                return f"Error: {str(e)}"
        handler.__name__ = tool["name"]
        handler.__doc__ = tool["description"]
        return handler

    _handler = _make_handler(_tool)

    for _pname, _pdesc in reversed(_req_props):
        _handler = app.mcp_tool_property(arg_name=_pname, description=_pdesc)(_handler)

    app.mcp_tool()(_handler)
