from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from sunbeam.core.deployment import NETWORK_ISOLATION_KEY
from sunbeam.core.questions import save_answers

SNAP_JSON = Path("/var/snap/openstack/common/network-isolation.json")

def import_network_isolation_answers(client, console) -> Dict[str, Any]:
    """Import /var/snap/openstack/common/network-isolation.json into answers."""
    if not SNAP_JSON.exists():
        return {}
    try:
        data = json.loads(SNAP_JSON.read_text())
    except Exception as e:
        console.print(f"[red]Invalid network-isolation.json: {e}[/red]")
        return {}
    if not data.get("enable_isolation"):
        return {}
    save_answers(client, NETWORK_ISOLATION_KEY, {"network_isolation": data})
    console.print("[green]Imported network isolation config into answers.[/green]")
    return data
