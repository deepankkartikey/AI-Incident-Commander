"""
Slack Integration Module

This module handles all Slack-related operations:
- Real-time message streaming from a specific channel using Socket Mode
- Slash command handling (/declare-incident)
- Publishing messages to incident channels
- Managing Slack client connections
- Agent tools for Slack operations

Requirements:
- SLACK_BOT_TOKEN: Bot User OAuth Token (xoxb-...) for API calls
- SLACK_APP_TOKEN: App-Level Token (xapp-...) for Socket Mode
- SLACK_MONITOR_CHANNEL: Channel ID (starts with C) to monitor

Slash Commands:
- /declare-incident sev1 - Declare a critical (SEV-1) incident
- /declare-incident sev2 - Declare a major (SEV-2) incident
"""

import asyncio
import os
import ssl
import certifi
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, field

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from pydantic_ai import RunContext


# ============================================================================
# Configuration
# ============================================================================
INCIDENT_CONTEXT_MESSAGE_COUNT = int(os.getenv("INCIDENT_CONTEXT_MESSAGE_COUNT", "10"))

# ============================================================================
# Global Slack Clients
# ============================================================================
slack_client: Optional[WebClient] = None
socket_mode_client: Optional[SocketModeClient] = None

# Global variable to store last incident context (channel name, messages, etc.)
_last_incident_context: Optional[dict] = None

# Global reference to the main incident state (set by main.py)
_global_incident_state = None


def set_global_incident_state(state):
    """
    Set the global incident state reference.
    This allows the slash command handler to update the agent's state directly.

    Args:
        state: The IncidentState instance from main.py
    """
    global _global_incident_state
    _global_incident_state = state


def get_global_incident_state():
    """Get the global incident state reference."""
    return _global_incident_state


def get_slack_client() -> WebClient:
    """Get the global Slack client instance"""
    if slack_client is None:
        raise RuntimeError("Slack client not initialized. Call initialize_slack_client() first.")
    return slack_client


def get_socket_mode_client() -> SocketModeClient:
    """
    Get the global Socket Mode client instance.
    Raises RuntimeError if Socket Mode is not initialized.
    """
    if socket_mode_client is None:
        raise RuntimeError(
            "Socket Mode client not initialized. "
            "Make sure SLACK_APP_TOKEN is set and initialize_slack_client() was called successfully."
        )
    return socket_mode_client


def get_last_incident_context() -> Optional[dict]:
    """
    Get the last incident context (channel name, messages, etc.) set by /declare-incident command.
    This is used by the AI agent to access the suggested channel name and conversation context.

    Returns:
        Dictionary with 'channel_name', 'severity', 'messages', 'timestamp' or None
    """
    global _last_incident_context
    return _last_incident_context


def clear_incident_context():
    """Clear the stored incident context after it has been used."""
    global _last_incident_context
    _last_incident_context = None


async def initialize_slack_client() -> bool:
    """
    Initialize and test the Slack client connection.
    Also initializes Socket Mode client if SLACK_APP_TOKEN is provided.

    Returns:
        True if successful, False otherwise.
    """
    global slack_client, socket_mode_client

    print("\n🔌 Initializing Slack client...")

    # Step 1: Validate Bot Token
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        print("   ❌ ERROR: SLACK_BOT_TOKEN environment variable not set")
        return False

    print(f"   ✓ Slack bot token found (length: {len(slack_token)})")

    if not slack_token.startswith("xoxb-"):
        print(f"   ⚠️  WARNING: SLACK_BOT_TOKEN should start with 'xoxb-'")
        print(f"   Current token starts with: {slack_token[:10]}...")

    try:
        # Step 2: Initialize Web Client with SSL
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        slack_client = WebClient(token=slack_token, ssl=ssl_context)
        print("   ✓ WebClient initialized with SSL context")

        # Step 3: Test connection
        print("   📡 Testing Slack API connection (auth.test)...")
        response = slack_client.auth_test()

        if not response["ok"]:
            error = response.get("error", "Unknown error")
            print(f"   ❌ Slack auth.test failed: {error}")
            return False

        bot_id = response.get("user_id", "unknown")
        team = response.get("team", "unknown")
        bot_name = response.get("user", "unknown")
        print(f"   ✅ Slack connection successful!")
        print(f"      Bot: {bot_name} (ID: {bot_id})")
        print(f"      Team: {team}")

        # Step 4: Initialize Socket Mode (required)
        if not _initialize_socket_mode():
            return False

        return True

    except SlackApiError as e:
        error_msg = e.response.get("error", "Unknown error")
        print(f"   ❌ SlackApiError during auth.test: {error_msg}")
        return False
    except Exception as e:
        print(f"   ❌ {type(e).__name__} during Slack initialization: {str(e)}")
        _print_ssl_help_if_needed(e)
        import traceback
        traceback.print_exc()
        return False


def _initialize_socket_mode() -> bool:
    """
    Initialize Socket Mode client (required for real-time messaging).

    Returns:
        True if successful, False otherwise.
    """
    global socket_mode_client

    app_token = os.getenv("SLACK_APP_TOKEN")
    if not app_token:
        print(f"\n   ❌ ERROR: SLACK_APP_TOKEN environment variable not set")
        print("   Socket Mode is required for this application.")
        print("   💡 To enable Socket Mode:")
        print("      1. Go to https://api.slack.com/apps")
        print("      2. Enable Socket Mode and generate an app-level token")
        print("      3. Add 'connections:write' scope")
        print("      4. Set SLACK_APP_TOKEN environment variable")
        return False

    print(f"\n🔌 Initializing Socket Mode for real-time messaging...")
    print(f"   ✓ App token found (length: {len(app_token)})")

    # Validate token format
    if not app_token.startswith("xapp-"):
        print(f"\n   ❌ ERROR: SLACK_APP_TOKEN has wrong format!")
        print(f"   Current token starts with: {app_token[:10]}...")
        print(f"\n   ⚠️  Socket Mode requires an APP-LEVEL TOKEN (xapp-...)")
        print(f"   ⚠️  You appear to be using a BOT TOKEN (xoxb-...)")
        print(f"\n   These are TWO DIFFERENT tokens:")
        print(f"   • SLACK_BOT_TOKEN  = Bot User OAuth Token (xoxb-...) ← API calls")
        print(f"   • SLACK_APP_TOKEN  = App-Level Token (xapp-...)     ← Socket Mode")
        print(f"\n   📋 To get the correct token:")
        print(f"   1. Go to https://api.slack.com/apps → Your App")
        print(f"   2. Navigate to 'Socket Mode' → Enable if needed")
        print(f"   3. Generate an app-level token with 'connections:write'")
        print(f"   4. Set: export SLACK_APP_TOKEN='xapp-...'\n")
        return False

    try:
        socket_mode_client = SocketModeClient(
            app_token=app_token,
            web_client=slack_client
        )
        print("   ✅ Socket Mode client initialized successfully")
        print("   📡 Socket Mode ready for real-time message streaming")
        return True
    except Exception as e:
        print(f"   ❌ Failed to initialize Socket Mode: {e}")
        import traceback
        traceback.print_exc()
        return False


def _print_ssl_help_if_needed(error: Exception) -> None:
    """Print helpful SSL certificate error messages for macOS users."""
    if "CERTIFICATE_VERIFY_FAILED" in str(error):
        print(f"\n   💡 macOS SSL Certificate Fix:")
        print(f"      1. Run: /Applications/Python\\ 3.*/Install\\ Certificates.command")
        print(f"      2. Or: pip install --upgrade certifi")
        print(f"      3. Or: brew install ca-certificates")
        print(f"      Note: Using certifi bundle: {certifi.where()}")


# ============================================================================
# Slack Helper Functions
# ============================================================================

def fetch_recent_messages(client: WebClient, channel_id: str, limit: int = None, include_bot_messages: bool = False) -> list:
    """
    Fetch recent messages from a Slack channel.

    Args:
        client: Slack WebClient instance
        channel_id: Channel ID to fetch messages from
        limit: Number of messages to fetch (defaults to INCIDENT_CONTEXT_MESSAGE_COUNT)
        include_bot_messages: Whether to include bot messages (default: False)

    Returns:
        List of message dictionaries with 'user', 'text', 'timestamp', and 'is_bot' fields
    """
    if limit is None:
        limit = INCIDENT_CONTEXT_MESSAGE_COUNT

    try:
        response = client.conversations_history(
            channel=channel_id,
            limit=limit
        )

        if not response["ok"]:
            return []

        raw_messages = response.get("messages", [])
        messages = []

        for msg in reversed(raw_messages):
            is_bot = msg.get("bot_id") is not None
            has_subtype = msg.get("subtype") is not None

            if not include_bot_messages and (has_subtype or is_bot):
                continue

            user_id = msg.get("user", "unknown")
            text = msg.get("text", "")
            ts = msg.get("ts", "")

            username = user_id
            if not is_bot:
                try:
                    user_info = client.users_info(user=user_id)
                    if user_info["ok"]:
                        profile = user_info["user"]["profile"]
                        username = profile.get("display_name") or user_info["user"]["real_name"]
                except:
                    pass
            elif msg.get("username"):
                username = msg.get("username")
            elif msg.get("bot_id"):
                username = f"bot:{msg.get('bot_id')}"

            messages.append({
                "user": username,
                "text": text,
                "timestamp": ts,
                "is_bot": is_bot
            })

        return messages

    except Exception as e:
        print(f"   ⚠️  Exception while fetching messages: {e}")
        return []


def generate_incident_name_and_summary(messages: list, severity: str) -> dict:
    """
    Generate an incident channel name and one-line summary based on recent conversation context using AI.
    Falls back to timestamp-based naming and generic summary if AI generation fails.

    Args:
        messages: List of recent messages with 'user' and 'text' fields
        severity: Severity level ('sev1' or 'sev2')

    Returns:
        Dictionary with 'channel_name' and 'summary' keys
        - channel_name: incident-YYYYMMDD-HHMM-description
        - summary: One-line description of the incident
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    default_name = f"incident-{timestamp}-{severity}"
    default_summary = f"{severity.upper()} incident declared based on recent conversation"

    if not messages:
        return {
            "channel_name": default_name,
            "summary": default_summary
        }

    conversation = "\n".join([f"{msg['user']}: {msg['text']}" for msg in messages])

    try:
        import boto3
        import json

        bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

        prompt = f"""Based on this recent Slack conversation, analyze the incident and provide:
1. A concise 2-4 word description for the incident channel name
2. A one-line summary of the incident

Conversation:
{conversation}

Requirements for channel name:
- Maximum 4 words
- Lowercase with hyphens
- Describe the technical issue
- Be specific and clear
- Examples: "api-gateway-down", "database-connection-timeout", "payment-service-error"

Requirements for summary:
- Single sentence (maximum 150 characters)
- Clear and actionable
- Describe what is happening and the impact
- Example: "Payment API experiencing 500 errors affecting customer checkout flow"

Return your response in this exact JSON format:
{{"channel_name": "your-channel-name", "summary": "Your one-line summary here"}}"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3
        }

        # Use cross-region inference profile for better availability
        response = bedrock_runtime.invoke_model(
            modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        ai_response = response_body['content'][0]['text'].strip()

        # Try to parse JSON response
        try:
            result = json.loads(ai_response)
            channel_desc = result.get('channel_name', '').lower().strip()
            summary = result.get('summary', '').strip()
        except json.JSONDecodeError:
            # If not valid JSON, try to extract from text
            channel_desc = ai_response.split('\n')[0].strip().lower()
            summary = default_summary

        # Clean up channel name
        channel_desc = channel_desc.replace(" ", "-")
        channel_desc = "".join(c for c in channel_desc if c.isalnum() or c == "-")
        channel_desc = channel_desc[:50].strip("-")

        if channel_desc and summary:
            return {
                "channel_name": f"incident-{timestamp}-{channel_desc}",
                "summary": summary[:150]  # Enforce max length
            }

        return {
            "channel_name": default_name,
            "summary": default_summary
        }

    except Exception as e:
        print(f"   ⚠️  AI generation failed: {e}")
        return {
            "channel_name": default_name,
            "summary": default_summary
        }


def generate_incident_channel_name(messages: list, severity: str) -> str:
    """
    Generate an incident channel name based on recent conversation context using AI.
    Falls back to timestamp-based naming if AI generation fails.

    This function is kept for backward compatibility but now uses generate_incident_name_and_summary internally.

    Args:
        messages: List of recent messages with 'user' and 'text' fields
        severity: Severity level ('sev1' or 'sev2')

    Returns:
        Channel name in format: incident-YYYYMMDD-HHMM-description
    """
    result = generate_incident_name_and_summary(messages, severity)
    return result["channel_name"]


def add_all_users_to_channel(client: WebClient, channel_id: str) -> None:
    """
    Fetch all users in the workspace and add them to the specified Slack channel.
    Invites users in batches of 100 (Slack API limit).

    Args:
        client: Slack WebClient instance
        channel_id: Channel ID to add users to
    """
    try:
        users_response = client.users_list()
        if not users_response["ok"]:
            return

        user_ids = [
            u["id"]
            for u in users_response["members"]
            if not u.get("is_bot", False) and not u.get("deleted", False)
        ]

        batch_size = 100
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i+batch_size]
            try:
                client.conversations_invite(channel=channel_id, users=batch)
            except SlackApiError:
                pass

    except Exception:
        pass



# ============================================================================
# Slack Slash Command Handling
# ============================================================================

def handle_slash_command(client: SocketModeClient, req: SocketModeRequest):
    """
    Handle incoming slash commands from Slack.

    Processes the /declare-incident command to formally declare incidents with severity levels.

    Command format: /declare-incident <severity>
    Where severity is: sev1 (critical) or sev2 (major)

    Args:
        client: SocketModeClient instance
        req: SocketModeRequest containing the slash command payload

    Note: The socket event handler has already acknowledged this request.
    """
    payload = req.payload
    command = payload.get("command", "")
    text = payload.get("text", "").strip().lower()
    user_id = payload.get("user_id", "")
    channel_id = payload.get("channel_id", "")

    print(f"\n🔧 [SLASH COMMAND] {command} {text} (User: {user_id}, Channel: {channel_id})")

    if command == "/declare-incident":
        if text not in ["sev1", "sev2"]:
            error_msg = (
                "❌ Invalid severity level. Please use:\n"
                "• `/declare-incident sev1` - for critical incidents\n"
                "• `/declare-incident sev2` - for major incidents"
            )
            try:
                web_client = get_slack_client()
                web_client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=error_msg
                )
            except Exception:
                pass
            return

        severity_display = "SEV-1 (Critical)" if text == "sev1" else "SEV-2 (Major)"

        try:
            web_client = get_slack_client()

            recent_messages = fetch_recent_messages(
                web_client,
                channel_id,
                limit=INCIDENT_CONTEXT_MESSAGE_COUNT,
                include_bot_messages=True
            )

            # Generate incident name and summary using AI
            incident_info = generate_incident_name_and_summary(recent_messages, text)
            base_channel_name = incident_info["channel_name"]
            incident_summary = incident_info["summary"]
            suggested_channel_name = f"{base_channel_name}-summary"
            
            print(f"   🤖 AI Generated Incident Name: {base_channel_name}")
            print(f"   📝 AI Generated Summary: {incident_summary}")

            created_channel_id = None
            created_channel_name = None
            sanitized_name = _sanitize_channel_name(suggested_channel_name)

            try:
                create_response = web_client.conversations_create(
                    name=sanitized_name,
                    is_private=False
                )

                if create_response["ok"]:
                    created_channel_id = create_response["channel"]["id"]
                    created_channel_name = create_response["channel"]["name"]
                    print(f"   ✅ Channel created: #{created_channel_name} (ID: {created_channel_id})")

                    topic = f"{severity_display} incident - Declared by <@{user_id}>"
                    web_client.conversations_setTopic(
                        channel=created_channel_id,
                        topic=topic
                    )

                    add_all_users_to_channel(web_client, created_channel_id)

                    welcome_msg = (
                        f"🚨 *Incident Response Channel* 🚨\n\n"
                        f"*Severity:* {severity_display}\n"
                        f"*Declared by:* <@{user_id}>\n"
                        f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"*Summary:* {incident_summary}\n\n"
                        f"_This channel will be used for executive summaries and incident coordination._"
                    )
                    web_client.chat_postMessage(
                        channel=created_channel_id,
                        text=welcome_msg,
                        mrkdwn=True
                    )

            except SlackApiError as e:
                error = e.response.get("error", "Unknown")
                if error == "name_taken":
                    try:
                        channels_response = web_client.conversations_list()
                        for ch in channels_response.get("channels", []):
                            if ch["name"] == sanitized_name:
                                created_channel_id = ch["id"]
                                created_channel_name = ch["name"]
                                print(f"   ✓ Found existing channel: #{created_channel_name}")
                                break
                    except Exception:
                        pass

            context_summary = ""
            if recent_messages:
                context_summary = f"\n\n*Context (last {len(recent_messages)} messages):*\n"
                for msg in recent_messages[-3:]:
                    context_summary += f"• {msg['user']}: {msg['text'][:100]}...\n" if len(msg['text']) > 100 else f"• {msg['user']}: {msg['text']}\n"

            if created_channel_id:
                confirmation_msg = (
                    f"🚨 *Incident Declared* 🚨\n"
                    f"Severity: *{severity_display}*\n"
                    f"Summary: _{incident_summary}_\n"
                    f"Declared by: <@{user_id}>\n"
                    f"Incident Channel: <#{created_channel_id}|{created_channel_name}>"
                    f"_AI monitoring will post executive summaries to above channel"
                )
            else:
                confirmation_msg = (
                    f"🚨 *Incident Declared* 🚨\n"
                    f"Severity: *{severity_display}*\n"
                    f"Summary: _{incident_summary}_\n"
                    f"Declared by: <@{user_id}>\n"
                    f"Suggested Channel: `{suggested_channel_name}`"
                    f"{context_summary}\n"
                    f"_⚠️ Channel creation failed. Please create manually._"
                )

            web_client.chat_postMessage(
                channel=channel_id,
                text=confirmation_msg,
                mrkdwn=True
            )
            print(f"   ✅ Incident declared: {severity_display}")

            global _last_incident_context
            _last_incident_context = {
                "channel_name": suggested_channel_name,
                "channel_id": created_channel_id,
                "severity": text,
                "summary": incident_summary,
                "messages": recent_messages,
                "timestamp": datetime.now().isoformat()
            }

            global_state = get_global_incident_state()
            if global_state and created_channel_id:
                print(f"   📝 Current state before update - channel_id: {global_state.slack_channel_id}")
                global_state.slack_channel_id = created_channel_id
                print(f"   ✅ Updated global incident state with channel_id: {created_channel_id}")
                print(f"   ✓ Verification - state.slack_channel_id is now: {global_state.slack_channel_id}")
            elif not global_state:
                print(f"   ⚠️  WARNING: Global incident state is None - cannot update channel_id!")
            elif not created_channel_id:
                print(f"   ⚠️  WARNING: Channel was not created successfully - cannot update state")

        except Exception as e:
            print(f"   ❌ Error handling incident declaration: {e}")
            import traceback
            traceback.print_exc()


# ============================================================================
# Slack Message Streaming
# ============================================================================

@dataclass
class SlackMessageStreamer:
    """
    Handles streaming messages from a specific Slack channel using Socket Mode.

    This class filters messages to ONLY process messages from the configured channel.
    All messages from other channels are ignored.
    """
    channel_identifier: str  # Channel ID (must start with C) to monitor
    on_message_callback: Callable  # Callback function: callback(timestamp, message)
    channel_id: Optional[str] = None  # Resolved channel ID
    _socket_client: Optional[SocketModeClient] = None
    _seen_messages: set = field(default_factory=set)  # Track message timestamps
    _user_cache: dict = field(default_factory=dict)  # Cache user info to reduce API calls

    async def stream_messages(self):
        """Stream messages from the configured Slack channel using Socket Mode."""
        print(f"\n🔗 Setting up Slack channel monitoring: {self.channel_identifier}")

        try:
            # Get the Slack clients
            client = get_slack_client()
            self._socket_client = get_socket_mode_client()

            # Resolve and validate channel ID
            self.channel_id = self._resolve_channel_id(client, self.channel_identifier)
            if not self.channel_id:
                print(f"❌ Could not resolve channel: {self.channel_identifier}")
                return

            # Start Socket Mode streaming
            print(f"✅ Using Socket Mode for real-time monitoring of channel: {self.channel_id}")
            await self._stream_with_socket_mode()

        except Exception as e:
            print(f"❌ Error setting up Slack streaming: {e}")
            import traceback
            traceback.print_exc()

    def _resolve_channel_id(self, client: WebClient, channel_identifier: str) -> Optional[str]:
        """
        Resolve a channel name or ID to a channel ID.

        Args:
            client: Slack WebClient instance
            channel_identifier: Channel name (e.g., "#my-channel") or channel ID (e.g., "C12345")

        Returns:
            Channel ID if found, None otherwise
        """
        if channel_identifier.startswith("C"):
            return channel_identifier

        channel_name = channel_identifier.lstrip("#")

        try:
            response = client.conversations_list(types="public_channel,private_channel")
            if response["ok"]:
                for channel in response["channels"]:
                    if channel["name"] == channel_name:
                        channel_id = channel["id"]
                        print(f"   ✅ Resolved '{channel_name}' to channel ID: {channel_id}")
                        return channel_id
        except Exception as e:
            print(f"   ❌ Exception while resolving channel: {e}")

        return None

    async def _stream_with_socket_mode(self):
        """Stream messages using Socket Mode (real-time WebSocket connection)."""
        web_client = get_slack_client()

        def handle_socket_event(client: SocketModeClient, req: SocketModeRequest):
            """Handle incoming Socket Mode events - process slash commands and channel messages."""
            response = SocketModeResponse(envelope_id=req.envelope_id)
            try:
                client.send_socket_mode_response(response)
            except Exception as e:
                print(f"   ⚠️  Failed to acknowledge socket event: {e}")
                return

            if req.type == "slash_commands":
                try:
                    handle_slash_command(client, req)
                except Exception as e:
                    print(f"   ⚠️  Error handling slash command: {e}")
                return

            if req.type != "events_api":
                return

            try:
                event = req.payload.get("event", {})
                event_type = event.get("type")

                if event_type != "message":
                    return

                channel = event.get("channel")
                if channel != self.channel_id:
                    return

                subtype = event.get("subtype")
                if subtype and subtype != "bot_message":
                    return

                msg_ts = event.get("ts")
                if msg_ts in self._seen_messages:
                    return
                self._seen_messages.add(msg_ts)

                text = event.get("text", "")
                if not text:
                    return

                is_bot = subtype == "bot_message"

                if is_bot:
                    username = event.get("username", event.get("bot_id", "bot"))
                else:
                    user = event.get("user", "unknown")
                    try:
                        username = self._get_username(web_client, user)
                    except Exception:
                        username = user

                timestamp = datetime.now().strftime("%H:%M:%S")
                message = f"{username}: {text}"

                try:
                    self.on_message_callback(timestamp, message)
                    print(f"🎯 [Slack] [{timestamp}] {message}")
                except Exception as e:
                    print(f"   ⚠️  Error processing message callback: {e}")

            except Exception as e:
                print(f"   ⚠️  Error in event handler: {e}")

        # Register the event handler
        self._socket_client.socket_mode_request_listeners.append(handle_socket_event)

        # Connect and maintain Socket Mode connection
        try:
            print("   🔌 Connecting to Slack Socket Mode...")
            self._socket_client.connect()
            print("   ✅ Socket Mode connection established")
            print(f"   📡 Real-time message streaming active")
            print(f"\n{'='*70}")
            print("🎧 LISTENING FOR SLACK MESSAGES")
            print(f"📍 Channel ID: {self.channel_id}")
            print(f"⚡ Messages acknowledged immediately upon receipt")
            print(f"{'='*70}\n")

            # Keep the connection alive with health checks
            reconnect_attempts = 0
            max_reconnect_attempts = 5
            loop_counter = 0

            while True:
                await asyncio.sleep(1)
                loop_counter += 1

                # Periodic cleanup of seen messages (every 1 hour = 3600 seconds)
                if loop_counter % 3600 == 0:
                    old_size = len(self._seen_messages)
                    # Keep only the last 1000 message timestamps to prevent memory growth
                    if old_size > 1000:
                        self._seen_messages = set(list(self._seen_messages)[-1000:])
                        print(f"   🧹 Cleaned up message cache ({old_size} -> {len(self._seen_messages)} entries)")

                # Check connection health
                if not self._socket_client.is_connected():
                    reconnect_attempts += 1
                    print(f"   ⚠️  Socket Mode disconnected. Reconnecting... (attempt {reconnect_attempts}/{max_reconnect_attempts})")

                    if reconnect_attempts >= max_reconnect_attempts:
                        print(f"   ❌ Max reconnection attempts reached. Giving up.")
                        raise ConnectionError("Socket Mode connection lost after multiple reconnection attempts")

                    try:
                        self._socket_client.connect()
                        print(f"   ✅ Socket Mode reconnected successfully")
                        reconnect_attempts = 0  # Reset counter on successful reconnection
                    except Exception as e:
                        print(f"   ❌ Reconnection failed: {e}")
                        await asyncio.sleep(2 ** reconnect_attempts)  # Exponential backoff
                else:
                    # Connection is healthy, reset reconnection counter
                    if reconnect_attempts > 0:
                        reconnect_attempts = 0

        except KeyboardInterrupt:
            print("\n   🛑 Stopping Socket Mode connection...")
            self._socket_client.disconnect()
        except SlackApiError as e:
            error_msg = e.response.get("error", "Unknown error")
            print(f"   ❌ Socket Mode error: {error_msg}")

            if error_msg == "not_allowed_token_type":
                self._print_token_error_help()

            if self._socket_client.is_connected():
                self._socket_client.disconnect()
            raise
        except Exception as e:
            print(f"   ❌ Socket Mode error: {e}")
            import traceback
            traceback.print_exc()
            if self._socket_client.is_connected():
                self._socket_client.disconnect()
            raise

    def _get_username(self, client: WebClient, user_id: str) -> str:
        """Get user's display name from user ID with caching to prevent API delays."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            user_info = client.users_info(user=user_id)
            if user_info["ok"]:
                profile = user_info["user"]["profile"]
                username = profile.get("display_name") or user_info["user"]["real_name"]
                self._user_cache[user_id] = username
                return username
        except Exception:
            pass

        return user_id

    def _print_token_error_help(self):
        """Print helpful error message for token type issues."""
        print(f"\n   ⚠️  CONFIGURATION ERROR: Wrong token type for Socket Mode")
        print(f"   SLACK_APP_TOKEN must be an App-Level Token (xapp-...), not a Bot Token!")
        print(f"\n   📋 To fix this:")
        print(f"   1. Go to https://api.slack.com/apps")
        print(f"   2. Select your app")
        print(f"   3. Navigate to 'Socket Mode' → Enable if needed")
        print(f"   4. Generate an app-level token with 'connections:write' scope")
        print(f"   5. Set: export SLACK_APP_TOKEN='xapp-...'\n")





# ============================================================================
# Agent Tools for Slack Operations
# ============================================================================

def create_agent_tool_create_incident_channel(agent, incident_state_type):
    """
    Create and register the create_incident_channel_with_state agent tool.

    Args:
        agent: The pydantic_ai Agent instance
        incident_state_type: The IncidentState type for typing

    Returns:
        The decorated tool function
    """
    @agent.tool()
    async def create_incident_channel_with_state(
        ctx: RunContext[incident_state_type],
        channel_name: str,
        topic: str = "",
        purpose: str = ""
    ) -> str:
        """
        Create a new Slack channel for incident communication and store the channel_id in state.
        This tool automatically updates the incident state so future summaries use the same channel.

        Args:
            ctx: The run context with access to incident state
            channel_name: Name for the channel (lowercase, no spaces, use hyphens)
            topic: Optional topic/description for the channel
            purpose: Optional purpose statement for the channel

        Returns:
            Success message with channel details, or error message
        """
        print(f"\n🔧 [AGENT TOOL] create_incident_channel_with_state: {channel_name}")

        if ctx.deps.slack_channel_id:
            existing_id = ctx.deps.slack_channel_id
            return f"✅ Incident channel already exists (ID: {existing_id}). Using existing channel."

        incident_context = get_last_incident_context()
        if incident_context and incident_context.get("channel_id"):
            created_channel_id = incident_context.get("channel_id")
            created_channel_name = incident_context.get("channel_name", "incident-channel")
            ctx.deps.slack_channel_id = created_channel_id
            clear_incident_context()
            return (
                f"✅ Using incident channel created during declaration: #{created_channel_name}\n"
                f"Channel ID: {created_channel_id}\n"
                f"All future summaries will be posted here."
            )

        if incident_context and incident_context.get("channel_name"):
            suggested_name = incident_context.get("channel_name")
            channel_name = suggested_name

        try:
            client = get_slack_client()
        except Exception as e:
            return f"❌ Slack client not initialized: {e}"

        sanitized_name = _sanitize_channel_name(channel_name)

        try:
            channels_response = client.conversations_list()
            if channels_response["ok"]:
                existing_channel = next(
                    (ch for ch in channels_response["channels"] if ch["name"] == sanitized_name),
                    None
                )
                if existing_channel:
                    channel_id = existing_channel["id"]
                    ctx.deps.slack_channel_id = channel_id
                    add_all_users_to_channel(client, channel_id)
                    return f"✅ Incident channel already exists: #{sanitized_name} (ID: {channel_id}). All users invited."
        except Exception:
            pass

        try:
            response = client.conversations_create(name=sanitized_name, is_private=False)

            if not response["ok"]:
                error = response.get("error", "Unknown error")
                return f"❌ Failed to create channel: {error}"

            channel_id = response["channel"]["id"]
            channel_name_created = response["channel"]["name"]
            print(f"   ✅ Channel created: #{channel_name_created} ({channel_id})")

            ctx.deps.slack_channel_id = channel_id
            _set_channel_metadata(client, channel_id, topic, purpose)
            add_all_users_to_channel(client, channel_id)

            return f"✅ Created channel #{channel_name_created} (ID: {channel_id}). All users invited. Future summaries will be posted here."

        except SlackApiError as e:
            error_msg = e.response.get("error", "Unknown error")
            if error_msg == "name_taken":
                return _handle_existing_channel(client, ctx, sanitized_name)
            return f"❌ Slack API error: {error_msg}"

        except Exception as e:
            return f"❌ Unexpected error: {e}"


    return create_incident_channel_with_state


def _sanitize_channel_name(channel_name: str) -> str:
    """Sanitize channel name to meet Slack requirements (lowercase, alphanumeric + hyphens)."""
    sanitized = channel_name.lower().replace(" ", "-")
    return "".join(c for c in sanitized if c.isalnum() or c == "-")


def _set_channel_metadata(client: WebClient, channel_id: str, topic: str, purpose: str) -> None:
    """Set topic and purpose for a channel if provided."""
    if topic:
        try:
            client.conversations_setTopic(channel=channel_id, topic=topic)
        except SlackApiError:
            pass

    if purpose:
        try:
            client.conversations_setPurpose(channel=channel_id, purpose=purpose)
        except SlackApiError:
            pass


def _handle_existing_channel(client: WebClient, ctx, sanitized_name: str) -> str:
    """Handle the case where a channel already exists with the given name."""
    try:
        channels_response = client.conversations_list()

        if not channels_response["ok"]:
            return f"❌ Channel '{sanitized_name}' exists but could not be found."

        channel_info = next(
            (ch for ch in channels_response["channels"] if ch["name"] == sanitized_name),
            None
        )

        if channel_info:
            channel_id = channel_info["id"]
            ctx.deps.slack_channel_id = channel_id
            add_all_users_to_channel(client, channel_id)
            return f"✅ Channel '{sanitized_name}' already exists. All users invited and channel ID stored."
        else:
            return f"❌ Channel '{sanitized_name}' exists but could not be found."

    except Exception as ex:
        return f"❌ Channel '{sanitized_name}' exists. Exception: {ex}"


def create_agent_tool_publish_to_slack(agent, incident_state_type):
    """
    Create and register the publish_exec_summary_to_slack agent tool.

    Args:
        agent: The pydantic_ai Agent instance
        incident_state_type: The IncidentState type for typing

    Returns:
        The decorated tool function
    """
    @agent.tool()
    async def publish_exec_summary_to_slack(
        ctx: RunContext[incident_state_type],
        markdown_content: str,
        channel_id: str
    ) -> str:
        """
        Publish an executive summary to a Slack channel.

        Args:
            ctx: The run context with access to incident state
            markdown_content: Multi-line markdown string containing the executive summary
            channel_id: The Slack channel ID (e.g., 'C1234567890')

        Returns:
            Success message with the posted message timestamp, or error message
        """
        print(f"\n🔧 [AGENT TOOL] publish_exec_summary_to_slack to channel: {channel_id}")

        if not channel_id or channel_id.startswith("$") or "PREV" in channel_id or "CHANNEL" in channel_id.upper():
            error_msg = (
                f"❌ Invalid channel_id: '{channel_id}'. "
                "You must pass ctx.deps.slack_channel_id (the actual channel ID value), "
                f"Current state channel_id: {ctx.deps.slack_channel_id}"
            )
            return error_msg

        try:
            client = get_slack_client()
        except RuntimeError as e:
            return f"❌ Slack client not initialized: {e}"

        try:
            response = client.chat_postMessage(
                channel=channel_id,
                text=markdown_content,
                mrkdwn=True,
                unfurl_links=False,
                unfurl_media=False
            )

            if not response["ok"]:
                error = response.get('error', 'Unknown error')
                return f"❌ Failed to post message: {error}"

            timestamp = response["ts"]
            channel = response["channel"]
            print(f"   ✅ Message posted to {channel} (ts: {timestamp})")
            return f"✅ Successfully posted executive summary to channel {channel} (ts: {timestamp})"

        except SlackApiError as e:
            error_msg = e.response.get("error", "Unknown error")
            return f"❌ Slack API error: {error_msg}"

        except Exception as e:
            error_type = type(e).__name__
            return f"❌ Unexpected error ({error_type}): {str(e)}"

    return publish_exec_summary_to_slack


def create_agent_tool_request_team_feedback(agent, incident_state_type):
    """
    Create and register the request_team_feedback agent tool.

    Args:
        agent: The pydantic_ai Agent instance
        incident_state_type: The IncidentState type for typing

    Returns:
        The decorated tool function
    """
    @agent.tool()
    async def request_team_feedback(
        ctx: RunContext[incident_state_type],
        summary: str,
        specific_questions: list[str]
    ) -> str:
        """
        Request updates and feedback from team members in the incident channel.
        Automatically fetches channel members and tags them with specific questions.

        Args:
            ctx: The run context with access to incident state
            summary: Brief context about the current incident status
            specific_questions: List of specific questions to ask team members

        Returns:
            Success message with confirmation of posted questions, or error message
        """
        print(f"\n🔧 [AGENT TOOL] request_team_feedback with {len(specific_questions)} questions")

        # Validate we have a channel ID
        channel_id = ctx.deps.slack_channel_id
        if not channel_id:
            return "❌ Cannot request feedback: No incident channel created yet. Wait for incident declaration."

        try:
            client = get_slack_client()
        except RuntimeError as e:
            return f"❌ Slack client not initialized: {e}"

        try:
            # Get channel members (excluding bots)
            members_response = client.conversations_members(channel=channel_id)
            if not members_response["ok"]:
                return f"❌ Failed to fetch channel members: {members_response.get('error', 'Unknown error')}"

            member_ids = members_response.get("members", [])

            # Filter out bots
            human_members = []
            for member_id in member_ids:
                try:
                    user_info = client.users_info(user=member_id)
                    if user_info["ok"] and not user_info["user"].get("is_bot", False):
                        human_members.append(member_id)
                except Exception:
                    continue

            if not human_members:
                return "⚠️ No human team members found in the incident channel to request feedback from."

            # Build the feedback request message
            message_lines = [
                f"*🔔 Team Update Requested*",
                f"",
                f"📊 *Current Status:* {summary}",
                f"",
                f"*Questions for the team:*"
            ]

            # Distribute questions among team members
            # If more questions than members, cycle through members
            for i, question in enumerate(specific_questions):
                member_index = i % len(human_members)
                member_id = human_members[member_index]
                # Use the special >>> prefix format for tagging
                message_lines.append(f">>> <@{member_id}> : {question}")

            message = "\n".join(message_lines)

            # Post the feedback request
            response = client.chat_postMessage(
                channel=channel_id,
                text=message,
                mrkdwn=True,
                unfurl_links=False,
                unfurl_media=False
            )

            if not response["ok"]:
                error = response.get('error', 'Unknown error')
                return f"❌ Failed to post feedback request: {error}"

            timestamp = response["ts"]
            tagged_count = len(human_members) if len(specific_questions) >= len(human_members) else len(specific_questions)
            print(f"   ✅ Feedback request posted - tagged {tagged_count} team members with {len(specific_questions)} questions")

            # Update state to record when feedback was requested
            ctx.deps.last_feedback_request_summary = ctx.deps.summary_count
            print(f"   📝 Updated last_feedback_request_summary to: {ctx.deps.summary_count}")

            return (
                f"✅ Successfully requested team feedback in channel {channel_id}\n"
                f"   Tagged {tagged_count} team members with {len(specific_questions)} specific questions\n"
                f"   Message timestamp: {timestamp}"
            )

        except SlackApiError as e:
            error_msg = e.response.get("error", "Unknown error")
            return f"❌ Slack API error: {error_msg}"

        except Exception as e:
            error_type = type(e).__name__
            return f"❌ Unexpected error ({error_type}): {str(e)}"

    return request_team_feedback

