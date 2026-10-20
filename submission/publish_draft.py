import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mcp_client import Mcp

body = pathlib.Path("DEV_POST.md").read_text(encoding="utf-8")

mcp = Mcp()
try:
    mcp.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "sloth-fridge", "version": "0.1.0"},
        },
    )
    mcp.notify("notifications/initialized")
    result = mcp.call(
        "update_article",
        {
            "id": 4881227,
            "title": "Sloth Fridge: A Fridge Photo Turns Into a Shopping List",
            "body_markdown": body,
            "tags": ["hf26challenge", "ai", "python", "opensource"],
            "description": "A fridge photo becomes a shopping list. It runs fully on your own laptop with open-weight models, so your photos never leave your machine and it costs nothing to run.",
            "published": False,
        },
    )
    text = ""
    for item in result.get("content", []):
        text += item.get("text", "")
    print(text[:2000])
finally:
    mcp.close()
