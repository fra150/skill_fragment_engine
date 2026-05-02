#!/usr/bin/env python3
"""MCP Server entry point for Skill Fragment Engine."""

import asyncio
import json
import sys
import os
from typing import Any
from aiohttp import web

from skill_fragment_engine.mcp_server import TOOL_DEFINITIONS, handle_tool_call, API_KEY


async def handle_stdio():
    """Handle stdio communication for MCP."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        
        try:
            message = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        
        method = message.get("method")
        params = message.get("params", {})
        
        if method == "initialize":
            response = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "skill-fragment-engine",
                    "version": "1.0.0",
                },
                "capabilities": {
                    "tools": {},
                },
            }
            print(json.dumps(response), flush=True)
        
        elif method == "tools/list":
            response = {
                "tools": [
                    {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
                    for t in TOOL_DEFINITIONS
                ]
            }
            print(json.dumps(response), flush=True)
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            api_key = params.get("_api_key", "")
            
            result = await handle_tool_call(tool_name, arguments, api_key)
            
            response = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result),
                    }
                ]
            }
            print(json.dumps(response), flush=True)


async def http_initialize(request):
    """Handle initialize via HTTP."""
    return web.json_response({
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": "skill-fragment-engine",
            "version": "1.0.0",
        },
        "capabilities": {
            "tools": {},
        },
    })


async def http_tools_list(request):
    """Handle tools/list via HTTP."""
    return web.json_response({
        "tools": [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in TOOL_DEFINITIONS
        ]
    })


async def http_tools_call(request):
    """Handle tools/call via HTTP."""
    if API_KEY:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response({"error": "API key required"}, status=401)
        api_key = auth_header[7:]
    else:
        api_key = ""
    
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    
    tool_name = data.get("name")
    arguments = data.get("arguments", {})
    
    if not tool_name:
        return web.json_response({"error": "Missing tool name"}, status=400)
    
    result = await handle_tool_call(tool_name, arguments, api_key)
    return web.json_response(result)


async def http_sse(request):
    """Handle SSE for notifications."""
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)
    
    await response.write(b"data: {\"event\":\"initialized\"}\n\n")
    return response


def create_http_app():
    """Create aiohttp application."""
    app = web.Application()
    
    app.router.add_post("/mcp/initialize", http_initialize)
    app.router.add_get("/mcp/tools", http_tools_list)
    app.router.add_post("/mcp/tools/call", http_tools_call)
    app.router.add_get("/mcp/events", http_sse)
    
    return app


async def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stdio":
            await handle_stdio()
        elif sys.argv[1] == "--http":
            host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
            port = int(sys.argv[3]) if len(sys.argv) > 3 else 8000
            app = create_http_app()
            print(f"Starting MCP HTTP server on {host}:{port}")
            web.run_app(app, host=host, port=port)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage: mcp_main.py [--stdio|--http [host] [port]]")
    else:
        print("Skill Fragment Engine MCP Server")
        print("Usage: mcp_main.py [--stdio|--http [host] [port]]")
        print(f"Available tools: {len(TOOL_DEFINITIONS)}")


if __name__ == "__main__":
    asyncio.run(main())