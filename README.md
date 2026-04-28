# Fabric Optimize MCP Server

MCP (Model Context Protocol) server for Microsoft Fabric optimization. Provides 30 tools to scan, analyze, and fix Lakehouses, Warehouses, Eventhouses, Semantic Models, and Gateways.

Deployed on Azure Functions (Flex Consumption) with the Azure Functions MCP extension. Compatible with Azure AI Foundry Agent Service, VS Code Copilot, and any MCP client.

## Architecture

```
MCP Client (Foundry / VS Code / CLI)
        │
        ▼  MCP Protocol (Streamable HTTP)
┌─────────────────────────┐
│  MCP Server             │
│  Azure Functions (Python)│
│  /runtime/webhooks/mcp  │
└────────┬────────────────┘
         │  REST API
         ▼
┌─────────────────────────┐
│  Backend API             │
│  Azure Functions (Node)  │
│  /api/tools/{toolName}   │
│  - Fabric REST API       │
│  - SQL Analytics (TDS)   │
│  - KQL Queries           │
│  - Livy Spark Sessions   │
│  - XMLA/TMSL             │
└─────────────────────────┘
```

## Tools (30)

### Workspace
| Tool | Description |
|------|-------------|
| `workspace_list` | List all Fabric workspaces |
| `workspace_list_items` | List items in a workspace |
| `workspace_capacity_info` | Show capacity SKU and state |
| `fabric_optimization_report` | Full optimization report |

### Lakehouse
| Tool | Description |
|------|-------------|
| `lakehouse_list` | List lakehouses |
| `lakehouse_list_tables` | List tables (Delta/Parquet) |
| `lakehouse_optimization_recommendations` | Scan for issues |
| `lakehouse_fix` | Apply fixes to a table |
| `lakehouse_auto_optimize` | Auto-optimize all tables |
| `lakehouse_run_table_maintenance` | OPTIMIZE + VACUUM |
| `lakehouse_get_job_status` | Check maintenance job |

### Warehouse
| Tool | Description |
|------|-------------|
| `warehouse_list` | List warehouses |
| `warehouse_optimization_recommendations` | Scan for issues |
| `warehouse_analyze_query_patterns` | Query performance analysis |
| `warehouse_fix` | Apply fixes |
| `warehouse_auto_optimize` | Auto-optimize |

### Eventhouse
| Tool | Description |
|------|-------------|
| `eventhouse_list` | List eventhouses |
| `eventhouse_list_kql_databases` | List KQL databases |
| `eventhouse_optimization_recommendations` | Scan for issues |
| `eventhouse_fix` | Apply fixes |
| `eventhouse_auto_optimize` | Auto-optimize |
| `eventhouse_fix_materialized_views` | Repair broken views |

### Semantic Model
| Tool | Description |
|------|-------------|
| `semantic_model_list` | List semantic models |
| `semantic_model_optimization_recommendations` | Scan for issues |
| `semantic_model_fix` | Apply fixes |
| `semantic_model_auto_optimize` | Auto-optimize |

### Gateway
| Tool | Description |
|------|-------------|
| `gateway_list` | List gateways |
| `gateway_list_connections` | List connections |
| `gateway_optimization_recommendations` | Scan for issues |
| `gateway_fix` | Apply fixes |

## Setup

### Prerequisites
- Azure subscription
- [Azure Developer CLI (azd)](https://aka.ms/azd)
- Python 3.11+

### Deploy
```bash
azd init --template <this-repo>
azd env set AZURE_SUBSCRIPTION_ID <your-sub-id>
azd env set AZURE_LOCATION swedencentral
azd env set VNET_ENABLED false
azd up
```

### Connect to Foundry Agent Service
1. Get the MCP system key:
   ```bash
   az functionapp keys list --name <func-name> --resource-group <rg> --query "systemKeys.mcp_extension" -o tsv
   ```
2. In Foundry portal → Agent → Add Tool → Custom → MCP
3. Enter endpoint: `https://<func-name>.azurewebsites.net/runtime/webhooks/mcp`
4. Auth: Key-based, header `x-functions-key` with the system key

### Connect to VS Code Copilot
Add to `.vscode/mcp.json` (included in repo) and provide the system key when prompted.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `BACKEND_URL` | Backend API base URL | `https://func-ygp7lcleawheu.azurewebsites.net/api/tools` |

## CI/CD

The repo includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) that deploys on push to `master`.

### Required Secrets
| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_ENV_NAME` | azd environment name |
| `AZURE_LOCATION` | Azure region (e.g. `swedencentral`) |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

## License
MIT
