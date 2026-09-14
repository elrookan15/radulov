"""Unit tests for RADULOV MCP Client and Gemini Docs tools."""

import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from radulov.mcp import (
    MCPClient,
    MCP_PROTOCOL_VERSION,
    get_gemini_doc,
    search_gemini_docs,
)


def _stateless_client(url: str = "https://gemini-api-docs-mcp.dev") -> MCPClient:
    """Client that skips initialize so existing transport tests stay single-POST."""
    return MCPClient(url, perform_handshake=False)


def _json_response(payload: dict, headers: dict | None = None) -> MagicMock:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(payload).encode("utf-8")
    mock_response.headers = headers or {}
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_response
    return ctx


def _bytes_response(body: bytes, headers: dict | None = None) -> MagicMock:
    mock_response = MagicMock()
    mock_response.read.return_value = body
    mock_response.headers = headers or {}
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_response
    return ctx


INIT_OK = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "gemini-docs", "version": "0.19.1"},
        "instructions": "Use gemini_search_docs first.",
    },
}


class TestRadulovMCP(unittest.TestCase):
    """Test suite for MCP client and Gemini Docs integration."""

    def test_mcp_client_init_and_next_id(self):
        """Ensure MCPClient initializes correctly and increments request ID."""
        client = _stateless_client("https://gemini-api-docs-mcp.dev/")
        self.assertEqual(client.server_url, "https://gemini-api-docs-mcp.dev")
        self.assertEqual(client._next_id(), 1)
        self.assertEqual(client._next_id(), 2)

    @patch("urllib.request.urlopen")
    def test_call_tool_json_response(self, mock_urlopen):
        """Ensure call_tool sends JSON-RPC 2.0 request and parses JSON response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "Google GenAI SDK Documentation"}]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = _stateless_client()
        res = client.call_tool("gemini_search_docs", {"query": "interactions"})
        self.assertIn("content", res)
        self.assertEqual(res["content"][0]["text"], "Google GenAI SDK Documentation")

    @patch("urllib.request.urlopen")
    def test_call_tool_sse_response(self, mock_urlopen):
        """Ensure call_tool handles SSE formatted payloads."""
        mock_response = MagicMock()
        sse_payload = (
            "event: message\n"
            'data: {"jsonrpc": "2.0", "id": 1, "result": {"text": "SSE Document Content"}}\n\n'
        )
        mock_response.read.return_value = sse_payload.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = _stateless_client()
        res = client.call_tool("gemini_get_doc", {"chunk_id": "chunk_01"})
        self.assertEqual(res.get("text"), "SSE Document Content")

    @patch("urllib.request.urlopen")
    def test_call_tool_multiline_sse_response(self, mock_urlopen):
        """Ensure call_tool joins multi-line SSE data frames before parsing JSON."""
        mock_response = MagicMock()
        sse_payload = (
            "event: message\n"
            'data: {"jsonrpc": "2.0",\n'
            'data: "id": 1,\n'
            'data: "result": {"text": "SSE Document Content"}}\n\n'
        )
        mock_response.read.return_value = sse_payload.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = _stateless_client()
        res = client.call_tool("gemini_get_doc", {"chunk_id": "chunk_01"})
        self.assertEqual(res.get("text"), "SSE Document Content")

    @patch("urllib.request.urlopen")
    def test_call_tool_multiple_sse_events(self, mock_urlopen):
        """Ensure call_tool uses the first complete SSE JSON event, not a merged payload."""
        mock_response = MagicMock()
        sse_payload = (
            "event: message\n"
            'data: {"jsonrpc": "2.0", "id": 1, "result": {"text": "First"}}\n'
            "\n"
            "event: message\n"
            'data: {"jsonrpc": "2.0", "id": 2, "result": {"text": "Second"}}\n\n'
        )
        mock_response.read.return_value = sse_payload.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = _stateless_client()
        res = client.call_tool("gemini_get_doc", {"chunk_id": "chunk_01"})
        self.assertEqual(res.get("text"), "First")

    @patch("urllib.request.urlopen")
    def test_list_tools_sse_response(self, mock_urlopen):
        """Ensure list_tools parses SSE JSON-RPC the same way call_tool does."""
        mock_response = MagicMock()
        sse_payload = (
            "event: message\n"
            'data: {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "gemini_search_docs"}]}}\n\n'
        )
        mock_response.read.return_value = sse_payload.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = _stateless_client()
        tools = client.list_tools()
        self.assertEqual(tools, [{"name": "gemini_search_docs"}])

    def test_sse_data_strips_only_one_leading_space(self):
        """SSE data fields drop one leading space and keep remaining whitespace."""
        payloads = list(
            MCPClient._iter_sse_data_payloads(
                "event: message\ndata:  leading-space-kept\n\n"
            )
        )
        self.assertEqual(payloads, [" leading-space-kept"])

    def test_sse_data_keeps_empty_fields(self):
        """Empty data: lines are preserved as blank lines inside the payload."""
        payloads = list(
            MCPClient._iter_sse_data_payloads("data: a\ndata:\ndata: b\n\n")
        )
        self.assertEqual(payloads, ["a\n\nb"])

    @patch("urllib.request.urlopen")
    def test_call_tool_http_error(self, mock_urlopen):
        """Ensure call_tool gracefully formats HTTP error."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://gemini-api-docs-mcp.dev",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        client = _stateless_client()
        res = client.call_tool("gemini_search_docs", {"query": "fail"})
        self.assertIn("error", res)
        self.assertIn("HTTP 500", res["error"])

    @patch("urllib.request.urlopen")
    def test_call_tool_network_error(self, mock_urlopen):
        """Ensure call_tool gracefully formats network connection failures."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        client = _stateless_client()
        res = client.call_tool("gemini_search_docs", {"query": "fail"})
        self.assertIn("error", res)
        self.assertIn("Network connection failed", res["error"])

    @patch("radulov.mcp._gemini_mcp_client.call_tool")
    def test_search_gemini_docs_success(self, mock_call_tool):
        """Ensure search_gemini_docs extracts and joins text chunks."""
        mock_call_tool.return_value = {
            "content": [
                {"type": "text", "text": "## Overview of google-genai SDK"},
                {"type": "text", "text": "## Interactions API Usage"},
            ]
        }
        output = search_gemini_docs("interactions api")
        self.assertIn("Overview of google-genai SDK", output)
        self.assertIn("Interactions API Usage", output)

    @patch("radulov.mcp._gemini_mcp_client.call_tool")
    def test_search_gemini_docs_error(self, mock_call_tool):
        """Ensure search_gemini_docs returns structured error string."""
        mock_call_tool.return_value = {"error": "Endpoint unavailable"}
        output = search_gemini_docs("interactions api")
        self.assertIn("Gemini Docs Search Error: Endpoint unavailable", output)

    @patch("radulov.mcp._gemini_mcp_client.call_tool")
    def test_get_gemini_doc_success(self, mock_call_tool):
        """Ensure get_gemini_doc extracts content for given chunk ID."""
        mock_call_tool.return_value = {
            "content": [{"type": "text", "text": "Complete documentation for chunk"}]
        }
        output = get_gemini_doc("guides/streaming.md#delta")
        self.assertIn("Complete documentation for chunk", output)

    @patch("radulov.mcp._gemini_mcp_client.call_tool")
    def test_get_gemini_doc_error(self, mock_call_tool):
        """Ensure get_gemini_doc handles errors."""
        mock_call_tool.return_value = {"error": "Chunk not found"}
        output = get_gemini_doc("invalid_chunk_id")
        self.assertIn("Gemini Doc Retrieval Error: Chunk not found", output)

    @patch("urllib.request.urlopen")
    def test_call_tool_sends_protocol_version_header(self, mock_urlopen):
        """Streamable HTTP requests always declare MCP-Protocol-Version."""
        mock_urlopen.return_value = _json_response(
            {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        )
        client = _stateless_client()
        client.call_tool("gemini_search_docs", {"query": "x"})
        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.get_header("Mcp-protocol-version"), MCP_PROTOCOL_VERSION)
        self.assertIn("text/event-stream", req.get_header("Accept"))

    @patch("urllib.request.urlopen")
    def test_handshake_then_tool_call(self, mock_urlopen):
        """First tool call runs initialize, notifications/initialized, then tools/call."""
        mock_urlopen.side_effect = [
            _json_response(INIT_OK),
            _bytes_response(b""),
            _json_response(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                }
            ),
        ]
        client = MCPClient("https://gemini-api-docs-mcp.dev")
        res = client.call_tool("gemini_search_docs", {"query": "x"})
        self.assertEqual(res["content"][0]["text"], "ok")
        self.assertEqual(client.server_info, {"name": "gemini-docs", "version": "0.19.1"})
        self.assertEqual(client.server_instructions, "Use gemini_search_docs first.")
        methods = [
            json.loads(call.args[0].data.decode("utf-8"))["method"]
            for call in mock_urlopen.call_args_list
        ]
        self.assertEqual(
            methods,
            ["initialize", "notifications/initialized", "tools/call"],
        )
        notify = json.loads(mock_urlopen.call_args_list[1].args[0].data.decode("utf-8"))
        self.assertNotIn("id", notify)

    @patch("urllib.request.urlopen")
    def test_session_id_forwarded_after_initialize(self, mock_urlopen):
        """Mcp-Session-Id from initialize is sent on later requests."""
        mock_urlopen.side_effect = [
            _json_response(INIT_OK, headers={"Mcp-Session-Id": "sess-abc"}),
            _bytes_response(b"", headers={"Mcp-Session-Id": "sess-abc"}),
            _json_response(
                {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
                headers={"Mcp-Session-Id": "sess-abc"},
            ),
        ]
        client = MCPClient("https://gemini-api-docs-mcp.dev")
        client.list_tools()
        self.assertEqual(client._session_id, "sess-abc")
        later_req = mock_urlopen.call_args_list[2].args[0]
        self.assertEqual(later_req.get_header("Mcp-session-id"), "sess-abc")
        notify_req = mock_urlopen.call_args_list[1].args[0]
        self.assertEqual(notify_req.get_header("Mcp-session-id"), "sess-abc")

    @patch("urllib.request.urlopen")
    def test_initialize_failure_still_calls_tool(self, mock_urlopen):
        """Handshake errors fail open so docs tools still attempt tools/call."""
        mock_urlopen.side_effect = [
            urllib.error.HTTPError(
                url="https://gemini-api-docs-mcp.dev",
                code=500,
                msg="Internal Server Error",
                hdrs={},
                fp=None,
            ),
            _json_response(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"content": [{"type": "text", "text": "still works"}]},
                }
            ),
        ]
        client = MCPClient("https://gemini-api-docs-mcp.dev")
        with patch("sys.stderr"):
            res = client.call_tool("gemini_search_docs", {"query": "x"})
        self.assertEqual(res["content"][0]["text"], "still works")
        methods = [
            json.loads(call.args[0].data.decode("utf-8"))["method"]
            for call in mock_urlopen.call_args_list
        ]
        self.assertEqual(methods, ["initialize", "tools/call"])

    @patch("urllib.request.urlopen")
    def test_list_tools_uses_sse_accept_header(self, mock_urlopen):
        """list_tools shares the Streamable HTTP Accept header with call_tool."""
        mock_urlopen.return_value = _json_response(
            {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        )
        client = _stateless_client()
        client.list_tools()
        req = mock_urlopen.call_args.args[0]
        self.assertIn("text/event-stream", req.get_header("Accept"))
        self.assertEqual(req.get_header("Mcp-protocol-version"), MCP_PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
