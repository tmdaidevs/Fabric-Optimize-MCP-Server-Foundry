import logging
import os

import azure.functions as func

from auth.fabric_auth import init_server_auth, require_auth
from tools import all_tools, AUTH_TOOL_NAMES, get_tool_by_name
from clients.fabric_client import list_workspaces

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

GUID_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

_auth_initialized = False


def _ensure_auth():
    global _auth_initialized
    if not _auth_initialized:
        init_server_auth()
        _auth_initialized = True


def _resolve_workspace_id(value: str) -> str:
    import re
    if re.match(GUID_RE, value, re.IGNORECASE):
        return value
    workspaces = list_workspaces()
    clean = value.lower().replace("-", "")
    match = next(
        (ws for ws in workspaces
         if ws["displayName"].lower() == clean or ws["displayName"].lower() == value.lower()),
        None,
    )
    if match:
        return match["id"]
    raise ValueError(f'Workspace "{value}" not found. Use a valid GUID or exact name.')


# Register all tools as MCP tool triggers (native, no proxy)
for _tool in all_tools:
    if _tool["name"] in AUTH_TOOL_NAMES:
        continue

    _props = _tool["input_schema"].get("properties", {})
    _required = _tool["input_schema"].get("required", [])

    # Build decorator stack dynamically
    _decorators = []
    for _pname, _pdef in _props.items():
        if _pname in _required:
            _decorators.append((_pname, _pdef.get("description", _pname)))

    # We need a closure to capture the tool reference
    def _make_handler(tool):
        def handler(**kwargs) -> str:
            try:
                _ensure_auth()
                require_auth()
                args = {k: v for k, v in kwargs.items() if v is not None}
                # Resolve workspace names to GUIDs
                if "workspaceId" in args and not __import__("re").match(GUID_RE, str(args["workspaceId"]), __import__("re").IGNORECASE):
                    args["workspaceId"] = _resolve_workspace_id(str(args["workspaceId"]))
                return tool["handler"](args)
            except Exception as e:
                logging.error(f"Tool {tool['name']} error: {e}")
                return f"Error: {str(e)}"
        handler.__name__ = tool["name"]
        handler.__doc__ = tool["description"]
        return handler

    _handler = _make_handler(_tool)

    # Apply mcp_tool_property decorators for required params only
    for _pname, _pdesc in reversed(_decorators):
        _handler = app.mcp_tool_property(arg_name=_pname, description=_pdesc)(_handler)

    # Apply mcp_tool decorator
    app.mcp_tool()(_handler)
