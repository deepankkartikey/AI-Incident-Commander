"""
Slack Integration Package

This package provides Slack integration functionality including:
- Real-time message streaming from Slack channels
- Publishing messages to incident channels
- Managing Slack client connections
- Agent tools for Slack operations
"""

from .slack_integration import (
    # Client management
    initialize_slack_client,
    get_slack_client,
    get_socket_mode_client,

    # Message streaming
    SlackMessageStreamer,

    # Agent tools
    create_agent_tool_create_incident_channel,
    create_agent_tool_publish_to_slack,

    # Utility functions
    add_all_users_to_channel,
)

__all__ = [
    'initialize_slack_client',
    'get_slack_client',
    'get_socket_mode_client',
    'SlackMessageStreamer',
    'create_agent_tool_create_incident_channel',
    'create_agent_tool_publish_to_slack',
    'add_all_users_to_channel',
]
