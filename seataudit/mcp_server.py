"""SEATAUDIT MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from seataudit.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-seataudit[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-seataudit[mcp]'")
        return 1
    app = FastMCP("seataudit")

    @app.tool()
    def seataudit_scan(target: str) -> str:
        """SaaS license, seat-usage and shadow-IT auditor. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
