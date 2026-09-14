"""Model Context Protocol (MCP) Client & Gemini Documentation Tools for RADULOV.

Provides deterministic client communication with MCP servers (HTTP/JSON-RPC 2.0
Streamable HTTP) and exposes official Gemini API & SDK documentation search
and retrieval tools.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from radulov import __version__

DEFAULT_GEMINI_DOCS_URL = os.environ.get(
    "GEMINI_DOCS_MCP_URL", "https://gemini-api-docs-mcp.dev"
)
DEFAULT_TIMEOUT_SEC = 15.0
MCP_PROTOCOL_VERSION = "2025-03-26"
CLIENT_NAME = "RADULOV-Aegis"
ACCEPT_HEADER = "application/json, text/event-stream, */*"


class MCPClient:
    """JSON-RPC 2.0 client for HTTP-based MCP servers (Streamable HTTP)."""

    def __init__(
        self,
        server_url: str,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        *,
        perform_handshake: bool = True,
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self._request_id = 0
        self._perform_handshake = perform_handshake
        self._handshake_done = False
        self._session_id: str | None = None
        self.server_info: dict[str, Any] | None = None
        self.server_instructions: str | None = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": ACCEPT_HEADER,
            "User-Agent": f"{CLIENT_NAME}/{__version__}",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _sse_data_value(line: str) -> str:
        """Return an SSE `data:` field value.

        WHATWG EventSource: if the value starts with U+0020 SPACE, remove
        exactly that one space. Do not strip any other leading or trailing
        whitespace, and keep empty fields so multi-line payloads stay intact.
        """
        value = line[5:]
        if value.startswith(" "):
            return value[1:]
        return value

    @staticmethod
    def _iter_sse_data_payloads(response_text: str):
        """Yield concatenated `data:` fields for each SSE event."""
        current: list[str] = []
        for raw_line in response_text.splitlines():
            line = raw_line.rstrip("\r")
            if line == "":
                if current:
                    yield "\n".join(current)
                    current = []
                continue
            if line.startswith("data:"):
                current.append(MCPClient._sse_data_value(line))
        if current:
            yield "\n".join(current)

    @staticmethod
    def _parse_response_json(response_text: str) -> dict[str, Any]:
        """Parse a direct JSON body or the first valid JSON payload in an SSE stream."""
        if not response_text or not response_text.strip():
            return {}

        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        for payload in MCPClient._iter_sse_data_payloads(response_text):
            if payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        raise json.JSONDecodeError("Unable to parse response JSON", response_text, 0)

    @staticmethod
    def _header_value(headers: Any, name: str) -> str | None:
        if headers is None:
            return None
        getter = getattr(headers, "get", None)
        if getter is None:
            return None
        value = getter(name)
        if value:
            return str(value)
        return None

    def _capture_session(self, headers: Any) -> None:
        value = self._header_value(headers, "Mcp-Session-Id")
        if value:
            self._session_id = value

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        """POST one JSON-RPC message. Returns (parsed body, response headers)."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=self.server_url,
            data=data,
            headers=self._build_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                resp_str = response.read().decode("utf-8", errors="replace")
                parsed = self._parse_response_json(resp_str)
                return parsed, response.headers
        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            if err_body.strip():
                try:
                    parsed = self._parse_response_json(err_body)
                    if parsed:
                        return parsed, http_err.headers
                except json.JSONDecodeError:
                    pass
            return (
                {"error": f"HTTP {http_err.code}: {http_err.reason}"},
                http_err.headers,
            )
        except urllib.error.URLError as url_err:
            return {"error": f"Network connection failed: {url_err.reason}"}, None
        except Exception as err:
            return {"error": f"MCP execution error: {err}"}, None

    def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        is_notification: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            payload["id"] = self._next_id()
        if params is not None:
            payload["params"] = params
        parsed, headers = self._post(payload)
        self._capture_session(headers)
        return parsed

    def ensure_initialized(self) -> None:
        """Run initialize + notifications/initialized once. Fail open on errors."""
        if not self._perform_handshake or self._handshake_done:
            return
        self._handshake_done = True
        try:
            parsed = self._rpc(
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": CLIENT_NAME, "version": __version__},
                },
            )
            if "error" in parsed:
                sys.stderr.write(f"WARNING: MCP initialize error: {parsed['error']}\n")
                return
            result = parsed.get("result", {})
            if isinstance(result, dict):
                info = result.get("serverInfo")
                self.server_info = info if isinstance(info, dict) else None
                instructions = result.get("instructions")
                self.server_instructions = (
                    instructions if isinstance(instructions, str) else None
                )
            self._rpc("notifications/initialized", {}, is_notification=True)
        except Exception as err:
            sys.stderr.write(f"WARNING: MCP initialize failed: {err}\n")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a remote MCP tool using standard JSON-RPC 2.0 payload."""
        self.ensure_initialized()
        parsed = self._rpc(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        if "error" in parsed:
            return {"error": parsed["error"]}
        return parsed.get("result", {})

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools on the remote MCP server."""
        self.ensure_initialized()
        parsed = self._rpc("tools/list", {})
        if "error" in parsed:
            sys.stderr.write(f"WARNING: MCP tools/list error: {parsed['error']}\n")
            return []
        result = parsed.get("result", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return tools if isinstance(tools, list) else []


# Global Gemini Documentation Client
_gemini_mcp_client = MCPClient(DEFAULT_GEMINI_DOCS_URL)


def search_gemini_docs(
    query: str,
    language: str = "python",
    scope: str = "sdk",
    limit: int = 5,
) -> str:
    """Search official Google Gemini API and SDK documentation.

    Args:
        query: Search keywords, method names, or tasks (e.g. 'interactions api streaming', 'GenerateContentConfig').
        language: Language filter ('python', 'javascript', 'go', 'java', 'dotnet').
        scope: Documentation scope ('sdk', 'guide', 'api-reference', 'type-reference').
        limit: Maximum number of documentation results to return (default: 5).

    Returns:
        Formatted summary of relevant Gemini API documentation chunks with chunk IDs.
    """
    args: dict[str, Any] = {
        "query": query,
        "language": language,
        "scope": scope,
        "limit": limit,
    }
    result = _gemini_mcp_client.call_tool("gemini_search_docs", args)

    if "error" in result:
        return f"Gemini Docs Search Error: {result['error']}"

    content = result.get("content", [])
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
        if text_parts:
            return "\n\n".join(text_parts)

    if isinstance(result, dict) and "text" in result:
        return str(result["text"])

    return f"No documentation found for query: '{query}'"


def get_gemini_doc(chunk_id: str, context: int = 0) -> str:
    """Retrieve the full content of a specific Gemini documentation page chunk.

    Args:
        chunk_id: Exact chunk ID returned by search_gemini_docs (e.g. 'guides/retries.md#backoff-strategy').
        context: Number of adjacent chunks to include before and after (default: 0).

    Returns:
        Full content of the documentation chunk.
    """
    args: dict[str, Any] = {
        "chunk_id": chunk_id,
        "context": context,
    }
    result = _gemini_mcp_client.call_tool("gemini_get_doc", args)

    if "error" in result:
        return f"Gemini Doc Retrieval Error: {result['error']}"

    content = result.get("content", [])
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
        if text_parts:
            return "\n\n".join(text_parts)

    if isinstance(result, dict) and "text" in result:
        return str(result["text"])

    return f"No document content found for chunk_id: '{chunk_id}'"
