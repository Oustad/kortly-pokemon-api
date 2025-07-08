#!/usr/bin/env python3
"""
Fake Slack Webhook Server for Testing Pokemon Card Scanner Error Notifications

This script creates a local HTTP server that mimics Slack's webhook endpoint,
allowing you to test the webhook functionality without external dependencies.

Usage:
    python fake_slack_webhook.py
    
Then update .env with:
    ERROR_WEBHOOK_URL=http://localhost:3000/webhook
    ERROR_WEBHOOK_ENABLED=true
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class WebhookCounter:
    """Simple counter for received webhooks."""
    def __init__(self):
        self.count = 0
        self.by_level = {}
    
    def increment(self, level: str):
        self.count += 1
        self.by_level[level] = self.by_level.get(level, 0) + 1


# Global counter
counter = WebhookCounter()

# Create FastAPI app
app = FastAPI(title="Fake Slack Webhook Server", version="1.0.0")


def get_level_color(level: str) -> str:
    """Get color for log level."""
    level_colors = {
        "DEBUG": Colors.CYAN,
        "INFO": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "CRITICAL": Colors.RED + Colors.BOLD,
    }
    return level_colors.get(level.upper(), Colors.WHITE)


def format_webhook_payload(payload: Dict[str, Any]) -> str:
    """Format webhook payload for display."""
    level = payload.get('level', 'UNKNOWN')
    message = payload.get('message', 'No message')
    timestamp = payload.get('timestamp', 'No timestamp')
    environment = payload.get('environment', 'unknown')
    service = payload.get('service', 'unknown')
    endpoint = payload.get('endpoint', 'N/A')
    request_id = payload.get('request_id', 'N/A')
    
    color = get_level_color(level)
    
    header = f"{color}{Colors.BOLD}[{level}]{Colors.END} {timestamp}"
    
    lines = [
        f"🚨 {header}",
        f"📦 Service: {service} ({environment})",
        f"🔗 Endpoint: {endpoint}",
        f"🆔 Request ID: {request_id}",
        f"💬 Message: {message}",
    ]
    
    # Add context if present
    if 'context' in payload:
        lines.append(f"📊 Context: {json.dumps(payload['context'], indent=2)}")
    
    # Add user agent if present
    if 'user_agent' in payload:
        lines.append(f"🌐 User Agent: {payload['user_agent']}")
    
    # Add traceback if present (truncated for readability)
    if 'traceback' in payload:
        traceback = payload['traceback']
        if len(traceback) > 200:
            traceback = traceback[:200] + "... (truncated)"
        lines.append(f"🔍 Traceback: {traceback}")
    
    return "\n".join(lines)


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "service": "Fake Slack Webhook Server",
        "status": "running",
        "webhooks_received": counter.count,
        "by_level": counter.by_level,
        "endpoints": {
            "webhook": "/webhook",
            "stats": "/stats",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "webhooks_received": counter.count}


@app.get("/stats")
async def stats():
    """Statistics endpoint."""
    return {
        "total_webhooks": counter.count,
        "by_level": counter.by_level,
        "uptime": "running"
    }


@app.post("/webhook")
async def webhook_endpoint(request: Request):
    """
    Main webhook endpoint that receives error notifications.
    
    This mimics Slack's webhook behavior by:
    1. Accepting POST requests with JSON payload
    2. Returning 200 OK on success
    3. Logging the received payload for inspection
    """
    try:
        # Get the JSON payload
        payload = await request.json()
        
        # Update counter
        level = payload.get('level', 'UNKNOWN')
        counter.increment(level)
        
        # Format and display the webhook
        formatted_output = format_webhook_payload(payload)
        
        # Print to console with separator
        print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}📥 WEBHOOK #{counter.count} RECEIVED{Colors.END}")
        print(f"{Colors.BLUE}{'='*80}{Colors.END}")
        print(formatted_output)
        print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")
        
        # Log the full payload for debugging (optional)
        logger.debug(f"Full payload: {json.dumps(payload, indent=2)}")
        
        # Return success response (like Slack would)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "Webhook received successfully"}
        )
        
    except json.JSONDecodeError:
        print(f"{Colors.RED}❌ ERROR: Invalid JSON payload{Colors.END}")
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON payload"}
        )
    
    except Exception as e:
        print(f"{Colors.RED}❌ ERROR: {str(e)}{Colors.END}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"}
        )


def print_startup_banner():
    """Print startup banner with instructions."""
    print(f"\n{Colors.GREEN}{Colors.BOLD}🚀 Fake Slack Webhook Server Starting...{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.WHITE}📡 Server URL: {Colors.BOLD}http://localhost:3000{Colors.END}")
    print(f"{Colors.WHITE}🎯 Webhook URL: {Colors.BOLD}http://localhost:3000/webhook{Colors.END}")
    print(f"{Colors.WHITE}📊 Stats URL: {Colors.BOLD}http://localhost:3000/stats{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.YELLOW}📝 To test with Pokemon Card Scanner:{Colors.END}")
    print(f"   1. Update .env file:")
    print(f"      {Colors.WHITE}ERROR_WEBHOOK_URL=http://localhost:3000/webhook{Colors.END}")
    print(f"      {Colors.WHITE}ERROR_WEBHOOK_ENABLED=true{Colors.END}")
    print(f"   2. Run the scanner and trigger some errors")
    print(f"   3. Watch webhooks appear here in real-time!")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.GREEN}✅ Ready to receive webhooks!{Colors.END}\n")


async def main():
    """Main function to run the webhook server."""
    print_startup_banner()
    
    # Configure uvicorn server
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=3000,
        log_level="warning",  # Reduce uvicorn noise
        access_log=False      # Disable access logs
    )
    
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Shutting down webhook server...{Colors.END}")
        print(f"{Colors.GREEN}📊 Final stats: {counter.count} webhooks received{Colors.END}")
        if counter.by_level:
            for level, count in counter.by_level.items():
                color = get_level_color(level)
                print(f"   {color}{level}: {count}{Colors.END}")
        print(f"{Colors.GREEN}✅ Server stopped.{Colors.END}")


if __name__ == "__main__":
    # Check for required dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError as e:
        print(f"{Colors.RED}❌ Missing dependency: {e}{Colors.END}")
        print(f"{Colors.YELLOW}💡 Install with: pip install fastapi uvicorn{Colors.END}")
        sys.exit(1)
    
    # Run the server
    asyncio.run(main())