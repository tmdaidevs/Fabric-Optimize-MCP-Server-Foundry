import os
import logging
import azure.functions as func
import azure.durable_functions as df

from auth.fabric_auth import init_server_auth
from clients.fabric_client import (
    list_workspaces,
    list_workspace_items,
    get_workspace_admins,
)
from clients.graph_client import send_proactive_message
from tools.lakehouse import lakehouse_optimization_recommendations
from tools.warehouse import warehouse_optimization_recommendations
from tools.eventhouse import eventhouse_optimization_recommendations
from tools.semantic_model import semantic_model_optimization_recommendations

logger = logging.getLogger(__name__)

# Excluded workspaces (configured via app setting, comma-separated)
EXCLUDED = set(
    os.environ.get("SCAN_EXCLUDED_WORKSPACES", "").split(",")
)

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Timer trigger — runs daily at 07:00 UTC
@app.schedule(schedule="0 0 7 * * *", arg_name="timer", run_on_startup=False)
@app.durable_client_input(client_name="client")
async def daily_scan_timer(timer: func.TimerRequest, client):
    instance_id = await client.start_new("scan_orchestrator")
    logger.info(f"Started scan orchestration: {instance_id}")


# Orchestrator — fans out per workspace
@app.orchestration_trigger(context_name="context")
def scan_orchestrator(context: df.DurableOrchestrationContext):
    # Get all workspaces
    workspaces = yield context.call_activity("get_workspaces_activity")

    # Fan out — scan each workspace
    tasks = []
    for ws in workspaces:
        if ws["id"] in EXCLUDED or ws.get("displayName", "") in EXCLUDED:
            continue
        if ws.get("type") == "Personal":
            continue
        tasks.append(context.call_activity("scan_and_notify_activity", ws))

    # Wait for all scans
    if tasks:
        results = yield context.task_all(tasks)
        return {
            "scanned": len(results),
            "timestamp": str(context.current_utc_datetime),
        }
    return {"scanned": 0, "timestamp": str(context.current_utc_datetime)}


# Activity: list workspaces
@app.activity_trigger(input_name="input")
def get_workspaces_activity(input):
    init_server_auth()
    return list_workspaces()


# Activity: scan a workspace and notify admins if issues found
@app.activity_trigger(input_name="workspace")
def scan_and_notify_activity(workspace: dict):
    init_server_auth()
    ws_id = workspace["id"]
    ws_name = workspace.get("displayName", ws_id)

    logger.info(f"Scanning workspace: {ws_name}")

    # Get all items in workspace
    items = list_workspace_items(ws_id)

    # Run scans per item type
    findings = []
    for item in items:
        item_type = item.get("type", "")
        item_id = item["id"]
        item_name = item.get("displayName", item_id)

        try:
            result = None
            if item_type == "Lakehouse":
                result = lakehouse_optimization_recommendations(
                    {"workspaceId": ws_id, "lakehouseId": item_id}
                )
            elif item_type == "Warehouse":
                result = warehouse_optimization_recommendations(
                    {"workspaceId": ws_id, "warehouseId": item_id}
                )
            elif item_type == "Eventhouse":
                result = eventhouse_optimization_recommendations(
                    {"workspaceId": ws_id, "eventhouseId": item_id}
                )
            elif item_type == "SemanticModel":
                result = semantic_model_optimization_recommendations(
                    {"workspaceId": ws_id, "semanticModelId": item_id}
                )

            if result and ("\U0001f534" in result or "\U0001f7e1" in result):
                findings.append(
                    {
                        "item_name": item_name,
                        "item_type": item_type,
                        "result": result,
                    }
                )
        except Exception as e:
            logger.warning(f"Scan failed for {item_name}: {e}")

    # If no issues, skip notification
    if not findings:
        logger.info(f"No issues in {ws_name}")
        return {"workspace": ws_name, "issues": 0}

    # Get workspace admins
    admins = get_workspace_admins(ws_id)
    if not admins:
        logger.warning(f"No admins found for {ws_name}")
        return {"workspace": ws_name, "issues": len(findings), "notified": 0}

    # Format message
    message = format_scan_message(ws_name, ws_id, findings)

    # Send to each admin
    notified = 0
    for admin in admins:
        principal = admin.get("principal", {})
        principal_id = principal.get("id")
        if principal_id and principal.get("type") in ("User", "user"):
            try:
                send_proactive_message(principal_id, message)
                notified += 1
                logger.info(
                    f"Notified {principal.get('displayName', principal_id)} for {ws_name}"
                )
            except Exception as e:
                logger.warning(f"Failed to notify {principal_id}: {e}")

    return {"workspace": ws_name, "issues": len(findings), "notified": notified}


def format_scan_message(ws_name: str, ws_id: str, findings: list) -> str:
    """Format an HTML message with scan findings."""
    portal_url = f"https://app.fabric.microsoft.com/groups/{ws_id}"

    html = (
        f'<h2>\U0001f50d Fabric Optimizer \u2014 Daily Scan</h2>'
        f'<p><strong>Workspace:</strong> <a href="{portal_url}">{ws_name}</a></p>'
        f'<p><strong>Issues found:</strong> {len(findings)} item(s) need attention</p>'
        f"<hr/>"
    )

    for f in findings:
        red = f["result"].count("\U0001f534")
        yellow = f["result"].count("\U0001f7e1")
        red_dots = "\U0001f534 " * min(red, 3)
        yellow_dots = "\U0001f7e1 " * min(yellow, 3)
        severity = f"{red_dots}{yellow_dots}"

        html += (
            f"<p><strong>{f['item_type']}: {f['item_name']}</strong> {severity}</p>"
        )

    html += (
        "<hr/>"
        "<p>Reply to this message to discuss findings with the Fabric Optimizer agent.</p>"
        '<p>Say <strong>"approve"</strong> to preview and apply fixes (dry run first).</p>'
    )

    return html
