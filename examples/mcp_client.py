"""Minimal MCP client for a DCC host — stdlib only.

Speaks JSON-RPC 2.0 over HTTP to a DCC's MCP endpoint (streamable HTTP or plain JSON).
No SDK, no第三方依赖, so it can run on any machine that has Python 3.9+.

Usage:
    client = DccMcp("http://127.0.0.1:52796/mcp")
    client.load_skill("3dsmax-scripting")
    out = client.call("3dsmax_scripting__execute_python",
                      {"code": "print(1)", "confirm_execution": True})
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class DccMcp:
    def __init__(self, url: str, timeout: float = 300.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._rid = 0
        self._initialized = False

    # --- transport ---------------------------------------------------------
    def _post(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **({"Mcp-Session-Id": self.session_id} if self.session_id else {}),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = resp.read().decode("utf-8", "replace")
        return self._decode(raw)

    @staticmethod
    def _decode(raw: str) -> Dict[str, Any]:
        """Servers answer either plain JSON or SSE (`data: {...}` lines)."""
        raw = raw.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    try:
                        return json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
        return {"raw": raw}

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None,
             notify: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notify:
            self._rid += 1
            payload["id"] = self._rid
        return self._post(payload)

    # --- protocol ----------------------------------------------------------
    def initialize(self) -> Dict[str, Any]:
        """Handshake once per process. A second initialize on the same session can 400."""
        if self._initialized:
            return {}
        res = self._rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mcp-dcc-automation", "version": "1.0"},
        })
        self._rpc("notifications/initialized", {}, notify=True)
        self._initialized = True
        return res

    def list_tools(self) -> List[Dict[str, Any]]:
        self.initialize()
        tools: List[Dict[str, Any]] = []
        cursor = None
        while True:
            res = self._rpc("tools/list", {"cursor": cursor} if cursor else {})
            result = res.get("result", {}) or {}
            tools.extend(result.get("tools", []) or [])
            cursor = result.get("nextCursor")
            if not cursor:
                return tools

    def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool and return its parsed JSON payload when it is JSON text."""
        self.initialize()
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in res:
            raise RuntimeError(f"MCP error: {res['error']}")
        texts = [c.get("text", "") for c in (res.get("result", {}) or {}).get("content", []) or []
                 if c.get("type") == "text"]
        payload: Any = "\n".join(texts)
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            pass
        return payload if isinstance(payload, dict) else {"text": payload}

    def load_skill(self, name: str) -> Dict[str, Any]:
        return self.call("load_skill", {"skill_name": name})
