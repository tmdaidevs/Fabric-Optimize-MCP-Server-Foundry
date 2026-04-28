import logging
import json
import os
import time

import azure.functions as func
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

BACKEND_URL = os.environ.get("BACKEND_URL", "https://func-ygp7lcleawheu.azurewebsites.net/api/tools")


def call_backend(tool_name: str, args: dict = None) -> str:
    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/{tool_name}", json=args or {}, timeout=120
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < max_retries:
                    delay = min(2 ** attempt, 16)
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        delay = int(retry_after)
                    logging.warning(f"Retrying {tool_name} in {delay}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", json.dumps(data))
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logging.warning(f"Timeout calling {tool_name}, retrying (attempt {attempt + 1})")
                continue
            return f"Error: {tool_name} timed out after {max_retries} retries"
        except Exception as e:
            logging.error(f"Error calling {tool_name}: {e}")
            return f"Error calling {tool_name}: {str(e)}"
    return f"Error: {tool_name} failed after {max_retries} retries"


# ---------------------------------------------------------------------------
# WORKSPACE TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
def workspace_list() -> str:
    """List all Fabric workspaces."""
    return call_backend("workspace_list")


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def workspace_list_items(workspaceId: str, itemType: str = None) -> str:
    """List all items in a workspace."""
    args = {"workspaceId": workspaceId}
    if itemType is not None and itemType.lower() not in ("all", "", "none"):
        args["itemType"] = itemType
    return call_backend("workspace_list_items", args)


@app.mcp_tool()
def workspace_capacity_info() -> str:
    """List Fabric capacities with SKU and state."""
    return call_backend("workspace_capacity_info")


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace to analyze")
def fabric_optimization_report(workspaceId: str) -> str:
    """Generate optimization report for a workspace."""
    return call_backend("fabric_optimization_report", {"workspaceId": workspaceId})


# ---------------------------------------------------------------------------
# LAKEHOUSE TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def lakehouse_list(workspaceId: str) -> str:
    """List all lakehouses in a workspace."""
    return call_backend("lakehouse_list", {"workspaceId": workspaceId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
def lakehouse_list_tables(workspaceId: str, lakehouseId: str) -> str:
    """List all tables in a lakehouse."""
    return call_backend("lakehouse_list_tables", {"workspaceId": workspaceId, "lakehouseId": lakehouseId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
def lakehouse_run_table_maintenance(workspaceId: str, lakehouseId: str, tableName: str = None) -> str:
    """Run OPTIMIZE and VACUUM on lakehouse tables."""
    args = {"workspaceId": workspaceId, "lakehouseId": lakehouseId}
    if tableName is not None:
        args["tableName"] = tableName
    return call_backend("lakehouse_run_table_maintenance", args)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
@app.mcp_tool_property(arg_name="jobInstanceId", description="The ID of the job instance to check")
def lakehouse_get_job_status(workspaceId: str, lakehouseId: str, jobInstanceId: str) -> str:
    """Check table maintenance job status."""
    return call_backend("lakehouse_get_job_status", {
        "workspaceId": workspaceId, "lakehouseId": lakehouseId, "jobInstanceId": jobInstanceId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
def lakehouse_optimization_recommendations(workspaceId: str, lakehouseId: str) -> str:
    """Scan a lakehouse for optimization issues."""
    return call_backend("lakehouse_optimization_recommendations", {
        "workspaceId": workspaceId, "lakehouseId": lakehouseId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
@app.mcp_tool_property(arg_name="tableName", description="The table to fix")
def lakehouse_fix(workspaceId: str, lakehouseId: str, tableName: str, dryRun: bool = False) -> str:
    """Apply fixes to a lakehouse table."""
    args = {"workspaceId": workspaceId, "lakehouseId": lakehouseId, "tableName": tableName}
    if dryRun:
        args["dryRun"] = True
    return call_backend("lakehouse_fix", args)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="lakehouseId", description="The ID of the lakehouse")
def lakehouse_auto_optimize(workspaceId: str, lakehouseId: str, dryRun: bool = False) -> str:
    """Auto-optimize all tables in a lakehouse."""
    args = {"workspaceId": workspaceId, "lakehouseId": lakehouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("lakehouse_auto_optimize", args)


# ---------------------------------------------------------------------------
# WAREHOUSE TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def warehouse_list(workspaceId: str) -> str:
    """List all warehouses in a workspace."""
    return call_backend("warehouse_list", {"workspaceId": workspaceId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="warehouseId", description="The ID of the warehouse")
def warehouse_optimization_recommendations(workspaceId: str, warehouseId: str) -> str:
    """Scan a warehouse for issues."""
    return call_backend("warehouse_optimization_recommendations", {
        "workspaceId": workspaceId, "warehouseId": warehouseId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="warehouseId", description="The ID of the warehouse")
def warehouse_analyze_query_patterns(workspaceId: str, warehouseId: str) -> str:
    """Analyze warehouse query patterns."""
    return call_backend("warehouse_analyze_query_patterns", {
        "workspaceId": workspaceId, "warehouseId": warehouseId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="warehouseId", description="The ID of the warehouse")
def warehouse_fix(workspaceId: str, warehouseId: str, dryRun: bool = False) -> str:
    """Apply fixes to a warehouse."""
    args = {"workspaceId": workspaceId, "warehouseId": warehouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("warehouse_fix", args)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="warehouseId", description="The ID of the warehouse")
def warehouse_auto_optimize(workspaceId: str, warehouseId: str, dryRun: bool = False) -> str:
    """Auto-optimize a warehouse."""
    args = {"workspaceId": workspaceId, "warehouseId": warehouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("warehouse_auto_optimize", args)


# ---------------------------------------------------------------------------
# EVENTHOUSE TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def eventhouse_list(workspaceId: str) -> str:
    """List all eventhouses in a workspace."""
    return call_backend("eventhouse_list", {"workspaceId": workspaceId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def eventhouse_list_kql_databases(workspaceId: str) -> str:
    """List KQL databases in a workspace."""
    return call_backend("eventhouse_list_kql_databases", {"workspaceId": workspaceId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="eventhouseId", description="The ID of the eventhouse")
def eventhouse_optimization_recommendations(workspaceId: str, eventhouseId: str) -> str:
    """Scan an eventhouse for issues."""
    return call_backend("eventhouse_optimization_recommendations", {
        "workspaceId": workspaceId, "eventhouseId": eventhouseId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="eventhouseId", description="The ID of the eventhouse")
def eventhouse_fix(workspaceId: str, eventhouseId: str, dryRun: bool = False) -> str:
    """Apply fixes to an eventhouse."""
    args = {"workspaceId": workspaceId, "eventhouseId": eventhouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("eventhouse_fix", args)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="eventhouseId", description="The ID of the eventhouse")
def eventhouse_auto_optimize(workspaceId: str, eventhouseId: str, dryRun: bool = False) -> str:
    """Auto-optimize an eventhouse."""
    args = {"workspaceId": workspaceId, "eventhouseId": eventhouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("eventhouse_auto_optimize", args)


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="eventhouseId", description="The ID of the eventhouse")
def eventhouse_fix_materialized_views(workspaceId: str, eventhouseId: str, dryRun: bool = False) -> str:
    """Fix broken materialized views."""
    args = {"workspaceId": workspaceId, "eventhouseId": eventhouseId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("eventhouse_fix_materialized_views", args)


# ---------------------------------------------------------------------------
# SEMANTIC MODEL TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
def semantic_model_list(workspaceId: str) -> str:
    """List semantic models in a workspace."""
    return call_backend("semantic_model_list", {"workspaceId": workspaceId})


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="semanticModelId", description="The ID of the semantic model")
def semantic_model_optimization_recommendations(workspaceId: str, semanticModelId: str) -> str:
    """Scan a semantic model for issues."""
    return call_backend("semantic_model_optimization_recommendations", {
        "workspaceId": workspaceId, "semanticModelId": semanticModelId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="semanticModelId", description="The ID of the semantic model")
def semantic_model_fix(workspaceId: str, semanticModelId: str) -> str:
    """Apply fixes to a semantic model."""
    return call_backend("semantic_model_fix", {
        "workspaceId": workspaceId, "semanticModelId": semanticModelId
    })


@app.mcp_tool()
@app.mcp_tool_property(arg_name="workspaceId", description="The ID of the Fabric workspace")
@app.mcp_tool_property(arg_name="semanticModelId", description="The ID of the semantic model")
def semantic_model_auto_optimize(workspaceId: str, semanticModelId: str, dryRun: bool = False) -> str:
    """Auto-optimize a semantic model."""
    args = {"workspaceId": workspaceId, "semanticModelId": semanticModelId}
    if dryRun:
        args["dryRun"] = True
    return call_backend("semantic_model_auto_optimize", args)


# ---------------------------------------------------------------------------
# GATEWAY TOOLS
# ---------------------------------------------------------------------------

@app.mcp_tool()
def gateway_list() -> str:
    """List all gateways."""
    return call_backend("gateway_list")


@app.mcp_tool()
def gateway_list_connections() -> str:
    """List all gateway connections."""
    return call_backend("gateway_list_connections")


@app.mcp_tool()
def gateway_optimization_recommendations() -> str:
    """Scan gateways for issues."""
    return call_backend("gateway_optimization_recommendations")


@app.mcp_tool()
def gateway_fix(dryRun: bool = False) -> str:
    """Apply fixes to gateways."""
    args = {}
    if dryRun:
        args["dryRun"] = True
    return call_backend("gateway_fix", args)
