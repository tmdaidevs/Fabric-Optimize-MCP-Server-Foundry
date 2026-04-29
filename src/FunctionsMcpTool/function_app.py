import logging
import os
import re

import azure.functions as func
import azure.durable_functions as df
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity

from auth.fabric_auth import init_server_auth, require_auth
from tools import all_tools, AUTH_TOOL_NAMES
from clients.fabric_client import list_workspaces
from bot.teams_bot import FabricOptimizerBot

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

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

    def _make_handler(tool, required_params):
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

        # Build proper function signature with explicit params
        # The MCP extension requires named params, not **kwargs
        import types
        params = ", ".join(required_params) if required_params else ""
        if params:
            code = f"def {tool['name']}({params}) -> str:\n    return _inner({', '.join(f'{p}={p}' for p in required_params)})"
        else:
            code = f"def {tool['name']}() -> str:\n    return _inner()"
        local_ns = {"_inner": handler}
        exec(code, local_ns)
        fn = local_ns[tool["name"]]
        fn.__doc__ = tool["description"]
        return fn

    _handler = _make_handler(_tool, list(_required))

    for _pname, _pdesc in reversed(_req_props):
        _handler = app.mcp_tool_property(arg_name=_pname, description=_pdesc)(_handler)

    app.mcp_tool()(_handler)


# --- Teams Bot endpoint ---
_bot_settings = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MicrosoftAppId", ""),
    app_password=os.environ.get("MicrosoftAppPassword", ""),
)
_adapter = BotFrameworkAdapter(_bot_settings)
_bot = FabricOptimizerBot()


@app.route(route="messages", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def messages(req: func.HttpRequest) -> func.HttpResponse:
    """Teams bot messages endpoint."""
    if "application/json" not in (req.headers.get("Content-Type") or ""):
        return func.HttpResponse(status_code=415)

    body = req.get_json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def _turn_callback(turn_context):
        await _bot.on_turn(turn_context)

    await _adapter.process_activity(activity, auth_header, _turn_callback)
    return func.HttpResponse(status_code=200)


# Import orchestration to register durable functions
from orchestration.daily_scan import register_durable_functions
register_durable_functions(app)
