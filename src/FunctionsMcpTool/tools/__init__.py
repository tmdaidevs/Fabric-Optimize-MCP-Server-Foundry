from .rule_engine import RuleResult, RuleSeverity, RuleStatus, render_rule_report
from .auth_tools import auth_tools
from .workspace import workspace_tools
from .lakehouse import lakehouse_tools
from .warehouse import warehouse_tools
from .eventhouse import eventhouse_tools
from .semantic_model import semantic_model_tools
from .gateway import gateway_tools

AUTH_TOOL_NAMES = {t["name"] for t in auth_tools}
all_tools = (
    auth_tools
    + workspace_tools
    + lakehouse_tools
    + warehouse_tools
    + eventhouse_tools
    + semantic_model_tools
    + gateway_tools
)


def get_tool_by_name(name):
    return next((t for t in all_tools if t["name"] == name), None)
