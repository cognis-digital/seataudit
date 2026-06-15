"""SEATAUDIT MCP server — exposes audit() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

import json
import sys

from seataudit.core import audit, load_inventory


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
    def seataudit_scan(inventory_path: str) -> str:
        """SaaS license, seat-usage and shadow-IT auditor.

        Args:
            inventory_path: Path to a JSON inventory file.

        Returns:
            JSON string with full audit findings.
        """
        try:
            inv = load_inventory(inventory_path)
        except FileNotFoundError:
            return json.dumps({"error": f"inventory file not found: {inventory_path}"})
        except (ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": f"invalid inventory: {exc}"})
        result = audit(inv)
        return json.dumps(result.to_dict(), indent=2)

    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
