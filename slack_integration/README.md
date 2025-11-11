# Slack Integration Module

## Overview

This module provides comprehensive Slack integration functionality for the AI-Powered Incident Response Monitor. It enables real-time message streaming from Slack channels, automated incident channel creation, and executive summary publishing capabilities.

## Features

- ✅ **Real-time Message Streaming**: Monitor Slack channels using Socket Mode (WebSocket)
- ✅ **Incident Channel Management**: Automatically create and configure incident channels
- ✅ **Executive Summary Publishing**: Post formatted updates to Slack channels
- ✅ **User Management**: Automatically invite all workspace users to incident channels
- ✅ **SSL/TLS Support**: Secure connections with certificate validation
- ✅ **Agent Tools**: Integrated with pydantic_ai for AI-powered operations

## Architecture

```
slack_integration/
├── __init__.py                    # Package exports
├── slack_integration.py           # Core implementation
├── cleanup_incident_channels.py   # Utility for cleaning up test channels
└── README.md                      # This file
```

## Requirements

### Python Dependencies

Install the required packages:

```bash
pip install slack-sdk certifi pydantic-ai
```

Required packages:
- `slack-sdk`: Official Slack SDK for Python
- `certifi`: SSL certificate bundle for secure connections
- `pydantic-ai`: AI agent framework with tool integration

### Slack App Configuration

You need to create a Slack App with the following configuration:

#### 1. Create a Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Enter app name (e.g., "AI Incident Monitor")
4. Select your workspace

#### 2. Bot Token Scopes (OAuth & Permissions)

Navigate to **OAuth & Permissions** and add these Bot Token Scopes:

**Required Scopes:**
- `channels:read` - View basic channel info
- `channels:manage` - Create and manage channels
- `channels:history` - View messages in public channels
- `chat:write` - Post messages
- `users:read` - View users in workspace
- `groups:read` - View private channel info
- `groups:write` - Manage private channels
- `im:read` - View direct messages
- `mpim:read` - View group direct messages

#### 3. Add the Slash Command

Navigate to **Features** → **Slash Commands**:

1. Click **"Create New Command"**
2. Fill in the command details:
   - **Command**: `/declare-incident`
   - **Request URL**: Leave blank (Socket Mode handles this)
   - **Short Description**: `Declare an incident with severity level`
   - **Usage Hint**: `sev1 or sev2`
   - **Escape channels, users, and links**: Leave unchecked
3. Click **"Save"**

This enables users to type `/declare-incident sev1` or `/declare-incident sev2` in any Slack channel to create incident response channels automatically.

#### 4. Enable Socket Mode

Navigate to **Socket Mode**:

1. Enable Socket Mode
2. Generate an **App-Level Token** with the scope:
   - `connections:write` - Connect to Slack with Socket Mode

**Important:** This creates an `xapp-...` token (different from the bot token)

#### 5. Enable Event Subscriptions

Navigate to **Features** → **Event Subscriptions**:

1. **Toggle "Enable Events" to ON**
2. **Request URL**: Leave blank (Socket Mode doesn't need this)
3. **Subscribe to Bot Events** - Add these events:
   - `message.channels` - Listen to messages in public channels
   - `message.groups` - Listen to messages in private channels
   - `app_mention` - When bot is mentioned (@botname)
4. Click **"Save Changes"**

These events allow the bot to monitor channel conversations for incident context and respond when mentioned.

#### 6. Install App to Workspace

1. Navigate to **Settings** → **Install App**
2. Click **"Reinstall to Workspace"** (this is important to activate the new slash command)
3. Authorize the app with all requested permissions
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

**Note:** You must reinstall the app after adding the slash command and event subscriptions to activate these features.

## Environment Variables

Set the following environment variables:

```bash
# Required: Bot User OAuth Token (from OAuth & Permissions)
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"

# Required: App-Level Token (from Socket Mode)
export SLACK_APP_TOKEN="xapp-your-app-level-token-here"

# Required: Channel ID to monitor (starts with C)
export SLACK_MONITOR_CHANNEL="C1234567890"
```

### Finding Your Channel ID

**Method 1: From Slack URL**
- Open the channel in Slack
- The URL will contain the channel ID: `https://app.slack.com/client/T.../C1234567890`

**Method 2: Using the API**
```python
from slack_sdk import WebClient
client = WebClient(token="xoxb-...")
response = client.conversations_list()
for channel in response["channels"]:
    print(f"{channel['name']}: {channel['id']}")
```

## Usage

### Basic Setup

```python
import asyncio
from slack_integration import initialize_slack_client, SlackMessageStreamer

async def main():
    # Initialize Slack client
    success = await initialize_slack_client()
    if not success:
        print("Failed to initialize Slack")
        return
    
    # Your application logic here
    print("Slack client ready!")

asyncio.run(main())
```

### Real-time Message Streaming

```python
from slack_integration import SlackMessageStreamer

def handle_message(timestamp: str, message: str):
    """Callback function for processing messages"""
    print(f"[{timestamp}] {message}")

# Create streamer with channel ID
streamer = SlackMessageStreamer(
    channel_identifier="C1234567890",  # or "#channel-name"
    on_message_callback=handle_message
)

# Start streaming (runs continuously)
await streamer.stream_messages()
```

### Creating Incident Channels

```python
from slack_integration import get_slack_client, add_all_users_to_channel

client = get_slack_client()

# Create a new channel
response = client.conversations_create(
    name="incident-2025-11-05",
    is_private=False
)

channel_id = response["channel"]["id"]

# Set channel metadata
client.conversations_setTopic(
    channel=channel_id,
    topic="Production incident - API Gateway down"
)

client.conversations_setPurpose(
    channel=channel_id,
    purpose="Coordinate response to API Gateway outage"
)

# Invite all users
add_all_users_to_channel(client, channel_id)
```

### Publishing Messages

```python
from slack_integration import get_slack_client

client = get_slack_client()

# Post a formatted message
response = client.chat_postMessage(
    channel="C1234567890",
    text="*Incident Summary*\n\nStatus: Resolved\nDuration: 45 minutes",
    mrkdwn=True
)

print(f"Message posted at: {response['ts']}")
```

## Agent Tools

This module provides two agent tools for pydantic_ai integration:

### 1. Create Incident Channel Tool

```python
from slack_integration import create_agent_tool_create_incident_channel
from pydantic_ai import Agent

agent = Agent("openai:gpt-4")

# Register the tool
create_incident_channel = create_agent_tool_create_incident_channel(
    agent, 
    IncidentState
)
```

The tool enables the agent to:
- Create new Slack channels with sanitized names
- Set channel topic and purpose
- Automatically invite all workspace users
- Store channel ID in incident state for future use
- Handle duplicate channel names gracefully

### 2. Publish to Slack Tool

```python
from slack_integration import create_agent_tool_publish_to_slack

# Register the tool
publish_to_slack = create_agent_tool_publish_to_slack(
    agent,
    IncidentState
)
```

The tool enables the agent to:
- Post formatted markdown content to Slack channels
- Support rich text formatting (bold, italic, lists, etc.)
- Return message timestamp for tracking

## API Reference

### Core Functions

#### `initialize_slack_client() -> bool`
Initialize and test Slack client connections (both WebClient and Socket Mode).

**Returns:** `True` if successful, `False` otherwise

**Side Effects:** Sets global `slack_client` and `socket_mode_client` variables

---

#### `get_slack_client() -> WebClient`
Get the initialized Slack WebClient instance.

**Returns:** Slack WebClient instance

**Raises:** `RuntimeError` if client not initialized

---

#### `get_socket_mode_client() -> SocketModeClient`
Get the initialized Socket Mode client instance.

**Returns:** SocketModeClient instance

**Raises:** `RuntimeError` if Socket Mode not initialized

---

#### `add_all_users_to_channel(client: WebClient, channel_id: str) -> None`
Fetch all workspace users and add them to a channel (in batches of 100).

**Parameters:**
- `client`: Slack WebClient instance
- `channel_id`: Channel ID to add users to

---

### SlackMessageStreamer Class

```python
@dataclass
class SlackMessageStreamer:
    channel_identifier: str       # Channel ID or name
    on_message_callback: Callable # Callback function(timestamp, message)
    
    async def stream_messages(self):
        """Stream messages from the configured channel"""
```

**Features:**
- Filters messages to only process the configured channel
- Deduplicates messages using timestamp tracking
- Includes bot messages (to capture AI responses and automated messages)
- Ignores message edits, deletions, and other subtypes
- Automatically reconnects on disconnection
- Resolves channel names to IDs

---

## Troubleshooting

### Common Issues

#### 1. SSL Certificate Errors (macOS)

```
ERROR: CERTIFICATE_VERIFY_FAILED
```

**Fix:**
```bash
# Method 1: Run Python's certificate installer
/Applications/Python\ 3.*/Install\ Certificates.command

# Method 2: Update certifi
pip install --upgrade certifi

# Method 3: Install certificates via Homebrew
brew install ca-certificates
```

---

#### 2. Token Type Errors

```
ERROR: not_allowed_token_type
```

**Cause:** Using bot token (`xoxb-...`) instead of app-level token (`xapp-...`) for Socket Mode

**Fix:**
- `SLACK_BOT_TOKEN` should be `xoxb-...` (from OAuth & Permissions)
- `SLACK_APP_TOKEN` should be `xapp-...` (from Socket Mode)

These are **two different tokens**!

---

#### 3. Missing Scopes

```
ERROR: missing_scope
```

**Fix:** Add the required scopes in **OAuth & Permissions** → **Bot Token Scopes**, then reinstall the app to workspace.

---

#### 4. Channel Not Found

```
ERROR: channel_not_found
```

**Possible causes:**
- Channel ID is incorrect
- Bot not invited to private channel
- Channel was deleted

**Fix:**
- Verify channel ID starts with `C`
- For private channels, manually invite the bot
- Use `conversations_list` to verify channel exists

---

#### 5. Socket Mode Connection Issues

```
ERROR: Socket Mode disconnected
```

**Possible causes:**
- Network connectivity issues
- Socket Mode not enabled in app settings
- Invalid app-level token

**Fix:**
- Check internet connection
- Verify Socket Mode is enabled in app settings
- Regenerate app-level token if needed
- The streamer will attempt to reconnect automatically

---

## Testing

### Test Slack Connection

```python
import asyncio
from slack_integration import initialize_slack_client

async def test():
    if await initialize_slack_client():
        print("✅ Slack integration working!")
    else:
        print("❌ Slack integration failed")

asyncio.run(test())
```

### Test Message Streaming

```python
import asyncio
from slack_integration import initialize_slack_client, SlackMessageStreamer

async def test_streaming():
    await initialize_slack_client()
    
    def on_message(ts, msg):
        print(f"📨 [{ts}] {msg}")
    
    streamer = SlackMessageStreamer(
        channel_identifier="C1234567890",
        on_message_callback=on_message
    )
    
    await streamer.stream_messages()

asyncio.run(test_streaming())
```

### Cleanup Test Channels

Use the provided utility script to clean up incident channels:

```bash
python slack_integration/cleanup_incident_channels.py
```

This will list all channels starting with "incident-" and offer to archive them.

---

## Security Best Practices

1. **Never commit tokens to version control**
   - Use environment variables
   - Add `.env` to `.gitignore`

2. **Use minimal required scopes**
   - Only request necessary OAuth scopes
   - Review scopes periodically

3. **Rotate tokens regularly**
   - Regenerate tokens every 90 days
   - Revoke unused tokens immediately

4. **Monitor bot activity**
   - Check app analytics in Slack
   - Set up alerts for unusual activity

5. **Use private channels for sensitive data**
   - Set `is_private=True` when creating channels
   - Manually manage user access for sensitive incidents

---

## Architecture Decisions

### Why Socket Mode?

**Socket Mode** was chosen over **Events API (HTTP endpoints)** because:

1. **No public endpoint required** - Works behind firewalls/NAT
2. **Real-time bidirectional communication** - WebSocket connection
3. **Simpler deployment** - No need for webhook server setup
4. **Better for development** - Works on localhost

### Message Filtering

The `SlackMessageStreamer` implements strict channel filtering:
- Only processes messages from the configured channel
- Silently ignores all other channels
- Prevents cross-channel message leakage
- Ensures incident isolation

### Global Client Pattern

The module uses global `slack_client` and `socket_mode_client` variables because:
- Slack SDK clients are thread-safe and reusable
- Avoids redundant authentication calls
- Simplifies dependency injection in agent tools
- Reduces connection overhead

---

## Examples

### Complete Incident Monitor

```python
import asyncio
import os
from slack_integration import (
    initialize_slack_client,
    SlackMessageStreamer,
    get_slack_client,
    add_all_users_to_channel
)

async def main():
    # 1. Initialize Slack
    if not await initialize_slack_client():
        print("Failed to initialize Slack")
        return
    
    # 2. Create incident channel
    client = get_slack_client()
    response = client.conversations_create(
        name="incident-api-outage",
        is_private=False
    )
    incident_channel = response["channel"]["id"]
    
    # 3. Configure channel
    client.conversations_setTopic(
        channel=incident_channel,
        topic="🚨 API Gateway Outage - High Priority"
    )
    
    # 4. Add all users
    add_all_users_to_channel(client, incident_channel)
    
    # 5. Monitor source channel
    def handle_slack_message(timestamp, message):
        # Forward to incident channel
        client.chat_postMessage(
            channel=incident_channel,
            text=f"[{timestamp}] {message}"
        )
    
    streamer = SlackMessageStreamer(
        channel_identifier=os.getenv("SLACK_MONITOR_CHANNEL"),
        on_message_callback=handle_slack_message
    )
    
    # 6. Start streaming
    await streamer.stream_messages()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Contributing

When contributing to this module:

1. Maintain backward compatibility
2. Add type hints to all functions
3. Update this README with new features
4. Test with multiple Slack workspaces
5. Handle errors gracefully with helpful messages

---

## License

This module is part of the AI-Powered Incident Response Monitor project.

---

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review Slack API documentation: https://api.slack.com/docs
3. Check Slack SDK documentation: https://slack.dev/python-slack-sdk/

---

## Changelog

### Version 1.0.0 (2025-11-05)
- Initial release
- Real-time message streaming via Socket Mode
- Incident channel creation and management
- Agent tools for pydantic_ai integration
- Comprehensive error handling and SSL support

