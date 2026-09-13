"""Unit tests for RADULOV MCP Client and Gemini Docs tools."""

import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from radulov.mcp import (
    MCPClient,
    get_gemini_doc,
    search_gemini_docs,
)


class TestRadulovMCP(unittest.TestCase):
    """Test suite for MCP client and Gemini Docs integration."""

    def test_mcp_client_init_and_next_id(self):
        """Ensure MCPClient initializes correctly and increments request ID."""
        client = MCPClient("https://gemini-api-docs-mcp.dev/")
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

        client = MCPClient("https://gemini-api-docs-mcp.dev")
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

        client = MCPClient("https://gemini-api-docs-mcp.dev")
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

        client = MCPClient("https://gemini-api-docs-mcp.dev")
        res = client.call_tool("gemini_get_doc", {"chunk_id": "chunk_01"})
        self.assertEqual(res.get("text"), "SSE Document Content")

    @patch("urllib.request.urlopen")
    def test_call_tool_multiple_sse_events(self, mock_urlopen):
        """Ensure call_tool does not merge separate SSE events into one payload."""
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

        client = MCPClient("https://gemini-api-docs-mcp.dev")
        res = client.call_tool("gemini_get_doc", {"chunk_id": "chunk_01"})
        self.assertEqual(res.get("text"), "First")

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
        client = MCPClient("https://gemini-api-docs-mcp.dev")
        res = client.call_tool("gemini_search_docs", {"query": "fail"})
        self.assertIn("error", res)
        self.assertIn("HTTP 500", res["error"])

    @patch("urllib.request.urlopen")
    def test_call_tool_network_error(self, mock_urlopen):
        """Ensure call_tool gracefully formats network connection failures."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        client = MCPClient("https://gemini-api-docs-mcp.dev")
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


if __name__ == "__main__":
    unittest.main()
