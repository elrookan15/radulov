"""Model Context Protocol (MCP) Client & Gemini Documentation Tools for RADULOV.

Provides deterministic client communication with MCP servers (HTTP/JSON-RPC 2.0)
and exposes official Gemini API & SDK documentation search and retrieval tools.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_GEMINI_DOCS_URL = os.environ.get(
    "GEMINI_DOCS_MCP_URL", "https://gemini-api-docs-mcp.dev"
)
DEFAULT_TIMEOUT_SEC = 15.0


class MCPClient:
    """Lightweight JSON-RPC 2.0 client for HTTP-based MCP servers."""

    def __init__(self, server_url: str, timeout_sec: float = DEFAULT_TIMEOUT_SEC):
        self.server_url = server_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @staticmethod
    def _parse_response_json(response_text: str) -> dict[str, Any]:
        """Parse direct JSON responses and JSON payloads embedded in SSE frames."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        sse_payloads: list[str] = []
        current_payload_lines: list[str] = []

        def flush_payload() -> None:
            if current_payload_lines:
                sse_payloads.append("\n".join(current_payload_lines))
                current_payload_lines.clear()

        for line in response_text.splitlines():
            if line == "":
                flush_payload()
                continue

            if line.startswith("data:"):
                payload = line[5:]
                if payload.startswith(" "):
                    payload = payload[1:]
                if payload:
                    current_payload_lines.append(payload)

        flush_payload()

        for payload in sse_payloads:
            if payload == "[DONE]":
                continue
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("Unable to parse response JSON", response_text, 0)

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a remote MCP tool using standard JSON-RPC 2.0 payload."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=self.server_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream, */*",
                "User-Agent": "RADULOV-Aegis/0.3.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                resp_bytes = response.read()
                resp_str = resp_bytes.decode("utf-8", errors="replace")

                result_json = self._parse_response_json(resp_str)
                if "error" in result_json:
                    return {"error": result_json["error"]}
                return result_json.get("result", {})
        except urllib.error.HTTPError as http_err:
            return {"error": f"HTTP {http_err.code}: {http_err.reason}"}
        except urllib.error.URLError as url_err:
            return {"error": f"Network connection failed: {url_err.reason}"}
        except Exception as err:
            return {"error": f"MCP execution error: {err}"}

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools on the remote MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=self.server_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "RADULOV-Aegis/0.3.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                result_json = json.loads(response.read().decode("utf-8", errors="replace"))
                return result_json.get("result", {}).get("tools", [])
        except Exception:
            return []


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
