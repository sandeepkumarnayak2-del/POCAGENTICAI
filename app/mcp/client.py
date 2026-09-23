"""MCP client helpers for Streamable HTTP servers.

The LangGraph application is synchronous at the graph boundary, while the
MCP Python SDK is asynchronous. ``call_tool_sync`` bridges that boundary in a
safe way, including when called from an already-running FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings
from app.observability.logging import logger


@asynccontextmanager
async def session():
    """Open, initialize and close one MCP Streamable HTTP session."""
    logger.info("mcp_connecting", server_url=settings.mcp_server_url)
    async with streamable_http_client(settings.mcp_server_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as client:
            await client.initialize()
            logger.info("mcp_connected", server_url=settings.mcp_server_url)
            yield client


async def _list_tools_async():
    async with session() as client:
        result = await client.list_tools()
        names = [tool.name for tool in result.tools]
        logger.info("mcp_tools_discovered", tools=names)
        return names


async def _call_tool_async(tool_name: str, arguments: dict):
    async with session() as client:
        logger.info("mcp_tool_call", tool=tool_name, arguments=arguments)
        result = await client.call_tool(tool_name, arguments=arguments)
        if result.isError:
            logger.error("mcp_tool_error", tool=tool_name, result=str(result.content))
            raise RuntimeError(str(result.content))

        value = _extract_tool_result(result)
        logger.info(
            "mcp_tool_result",
            tool=tool_name,
            result_type=type(value).__name__,
        )
        return value


def _extract_tool_result(result):
    """Return the application payload from an MCP ``CallToolResult``.

    Depending on the MCP SDK/FastMCP version, a tool's return value can arrive
    directly in ``structuredContent`` or as JSON text inside ``content``.
    FastMCP can also wrap structured output in a ``result`` envelope. Normalize
    those representations before returning to the application layer.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return _unwrap_result(structured)

    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if not text:
            continue
        try:
            return _unwrap_result(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            return text

    return None


def _unwrap_result(value):
    """Unwrap the common FastMCP ``{"result": ...}`` envelope."""
    if isinstance(value, dict) and set(value.keys()) == {"result"}:
        return value["result"]
    return value


def _run_async(coro):
    """Run an async MCP operation from synchronous LangGraph nodes."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # FastAPI may already have an event loop. Run the MCP coroutine in a
    # short-lived worker thread so the synchronous graph can safely block.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def list_tools():
    return _run_async(_list_tools_async())


def call_tool(tool_name: str, arguments: dict):
    return _run_async(_call_tool_async(tool_name, arguments))


def call_tool_sync(tool_name: str, arguments: dict):
    """Synchronous API used by LangChain tools inside the agent graph."""
    return call_tool(tool_name, arguments)
