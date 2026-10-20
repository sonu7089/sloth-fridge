import json
import pathlib
import subprocess
import sys
import threading

EXE = r"C:\Users\PC\.devrelay\bin\dev_mlh_mcp_server.exe"


class Mcp:
    def __init__(self):
        self.proc = subprocess.Popen(
            [EXE, "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.next_id = 0

    def send(self, payload):
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def read(self):
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()
            raise RuntimeError(f"MCP server closed: {err[:500]}")
        return json.loads(line)

    def request(self, method, params=None, timeout_note=""):
        self.next_id += 1
        request_id = self.next_id
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        while True:
            message = self.read()
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"])[:800])
                return message.get("result", {})

    def notify(self, method, params=None):
        self.send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def call(self, tool, arguments):
        return self.request("tools/call", {"name": tool, "arguments": arguments})

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


def main():
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
        tools = mcp.request("tools/list")
        names = [t["name"] for t in tools.get("tools", [])]
        print("tools:", ", ".join(names))
        return names
    finally:
        mcp.close()


if __name__ == "__main__":
    names = main()
    if "--call" in sys.argv:
        tool = sys.argv[sys.argv.index("--call") + 1]
        args = json.loads(pathlib.Path(sys.argv[sys.argv.index("--args") + 1]).read_text(encoding="utf-8"))
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
            result = mcp.call(tool, args)
            print(json.dumps(result, indent=2)[:3000])
        finally:
            mcp.close()
