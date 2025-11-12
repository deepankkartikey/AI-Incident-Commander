"""
AI-Powered Incident Response Monitor
Connects to three SSE streams (metrics, Slack, Zoom) and generates executive summaries
for leadership stakeholders during incident response.
"""
import importlib

# Load environment variables first, before any other imports
from dotenv import load_dotenv

# Database functionality disabled (AWS DynamoDB not needed for this demo)
# from persistance.db import create_agent_tool_add_summary_to_db

env_file = load_dotenv()
if env_file:
    print("✅ Successfully loaded .env file")
else:
    print("⚠️  No .env file found, using existing environment variables")

import asyncio
import json
import os
import ssl
import certifi
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import RunContext, UsageLimits

# Import Slack integration module from slack_integration package
from slack_integration.slack_integration import (
    initialize_slack_client,
    SlackMessageStreamer,
    create_agent_tool_create_incident_channel,
    create_agent_tool_publish_to_slack,
    create_agent_tool_request_team_feedback,
    set_global_incident_state
)
import atlassian_integration.integration
# Import agent configuration
from agent.agent_config import agent
from agent.system_prompts import get_generate_summary_prompt


# ============================================================================
# Data Models
# ============================================================================

class StreamEvent(BaseModel):
    """Represents an event from one of the streams"""
    timestamp: str
    channel: str  # "metrics", "slack", or "zoom"
    message: str


class IncidentState(BaseModel):
    """Current state of the incident"""
    metrics_events: List[StreamEvent] = Field(default_factory=list)
    slack_events: List[StreamEvent] = Field(default_factory=list)
    zoom_events: List[StreamEvent] = Field(default_factory=list)
    last_summary_time: Optional[float] = None
    incident_start_time: float = Field(default_factory=lambda: datetime.now().timestamp())
    slack_channel_id: Optional[str] = None  # Track the incident Slack channel ID
    incident_resolved: bool = False  # Track if incident has been resolved
    jira_tickets_created: bool = False  # Track if JIRA tickets have been created
    confluence_postmortem_created: bool = False  # Track if Confluence post-mortem has been created
    last_feedback_request_summary: int = 0  # Track which summary number last requested feedback
    summary_count: int = 0  # Track current summary number

    @property
    def all_events(self) -> List[StreamEvent]:
        """Get all events sorted by timestamp"""
        all_events = self.metrics_events + self.slack_events + self.zoom_events
        return sorted(all_events, key=lambda e: e.timestamp)
    
    @property
    def recent_events(self, seconds: int = 60) -> List[StreamEvent]:
        """Get events from the last N seconds"""
        cutoff_time = datetime.now().timestamp() - seconds
        return [e for e in self.all_events if self._event_timestamp(e) > cutoff_time]
    
    def _event_timestamp(self, event: StreamEvent) -> float:
        """Convert event timestamp to unix timestamp"""
        # Assuming timestamp format is "HH:MM:SS"
        try:
            time_parts = event.timestamp.split(":")
            hours, minutes, seconds = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
            today = datetime.now()
            event_time = today.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
            return event_time.timestamp()
        except:
            return datetime.now().timestamp()


class ExecutiveSummary(BaseModel):
    """Executive summary for leadership"""
    timestamp: str
    incident_duration: str
    current_status: str
    customer_impact: str
    key_actions_taken: List[str]
    root_cause: Optional[str] = None
    eta_to_resolution: Optional[str] = None
    severity: str


# ============================================================================
# AI Agent Configuration
# ============================================================================
# Agent is imported from agent.agent_config to ensure single instance across the application

# Register Slack agent tools (these functions already use @agent.tool() internally)
create_agent_tool_create_incident_channel(agent, IncidentState)
create_agent_tool_publish_to_slack(agent, IncidentState)
create_agent_tool_request_team_feedback(agent, IncidentState)
# Database tool disabled (AWS DynamoDB not needed for this demo)
# create_agent_tool_add_summary_to_db(agent, IncidentState)

@agent.system_prompt
async def add_context(ctx: RunContext[IncidentState]) -> str:
    """Add current incident context to the prompt"""
    state = ctx.deps
    
    # Calculate incident duration
    duration_seconds = datetime.now().timestamp() - state.incident_start_time
    duration_minutes = int(duration_seconds / 60)
    duration_str = f"{duration_minutes}m {int(duration_seconds % 60)}s"
    
    # Calculate summaries since last feedback request
    summaries_since_feedback = state.summary_count - state.last_feedback_request_summary

    # Get recent events from each channel
    recent_metrics = [e for e in state.metrics_events[-10:]]
    recent_slack = [e for e in state.slack_events[-10:]]
    recent_zoom = [e for e in state.zoom_events[-10:]]
    
    context = f"""
Current Incident Context:
- Duration: {duration_str}
- Total events tracked: {len(state.all_events)}
- Current summary: #{state.summary_count}
- Last feedback request: Summary #{state.last_feedback_request_summary} ({summaries_since_feedback} summaries ago)

Recent Events (last 10 from each channel):

METRICS STREAM (Automated monitoring):
{chr(10).join(f"  [{e.timestamp}] {e.message}" for e in recent_metrics) if recent_metrics else "  (no recent events)"}

SLACK CHANNEL (#incident-response):
{chr(10).join(f"  [{e.timestamp}] {e.message}" for e in recent_slack) if recent_slack else "  (no recent events)"}

ZOOM BRIDGE (Voice call transcript):
{chr(10).join(f"  [{e.timestamp}] {e.message}" for e in recent_zoom) if recent_zoom else "  (no recent events)"}
"""
    return context


# ============================================================================
# Stream Monitoring
# ============================================================================

@dataclass
class IncidentMonitor:
    """Main incident monitoring coordinator"""
    base_url: str = "http://localhost:8081"  # Updated to match Go server port
    summary_interval: int = 60  # Generate summary every 60 seconds
    state: IncidentState = field(default_factory=IncidentState)
    slack_monitor_channel: Optional[str] = None  # Slack channel to monitor (e.g., "#incident-response")

    async def connect_to_stream(self, stream_name: str, channel: str):
        """Connect to an SSE stream and process events"""
        url = f"{self.base_url}/stream/{stream_name}"
        print(f"🔗 Connecting to {channel} stream at {url}")
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                print(f"✅ Connected to {channel} stream")
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        message = line[6:]  # Remove "data: " prefix
                        
                        # Extract timestamp if present
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        if message.startswith("["):
                            # Format: [HH:MM:SS] message
                            end_bracket = message.find("]")
                            if end_bracket > 0:
                                timestamp = message[1:end_bracket]
                                message = message[end_bracket+2:]  # Skip "] "
                        
                        event = StreamEvent(
                            timestamp=timestamp,
                            channel=channel,
                            message=message
                        )
                        
                        # Store event in appropriate list
                        if channel == "metrics":
                            self.state.metrics_events.append(event)
                        elif channel == "slack":
                            self.state.slack_events.append(event)
                        elif channel == "zoom":
                            self.state.zoom_events.append(event)
                        
                        # Print event
                        print(f"[{channel.upper():8}] [{timestamp}] {message}")
    
    async def stream_from_slack_channel(self):
        """Stream messages from a Slack channel using Socket Mode"""
        if not self.slack_monitor_channel:
            print("⚠️  No Slack channel configured for monitoring. Skipping Slack stream.")
            return

        # Create a callback to handle incoming messages
        def on_slack_message(timestamp: str, message: str):
            """Handle incoming Slack messages"""
            # Create event
            stream_event = StreamEvent(
                timestamp=timestamp,
                channel="slack",
                message=message
            )

            # Store event in state
            self.state.slack_events.append(stream_event)

        # Create streamer and start streaming
        streamer = SlackMessageStreamer(
            channel_identifier=self.slack_monitor_channel,
            on_message_callback=on_slack_message
        )

        await streamer.stream_messages()


    async def generate_summaries(self):
        """Periodically generate executive summaries"""
        await asyncio.sleep(30)  # Wait for some events to accumulate
        
        previous_channel_id = None  # Track channel ID to detect new creation
        
        while True:
            await asyncio.sleep(self.summary_interval)
            
            # Stop generating summaries if incident is resolved
            if self.state.incident_resolved:
                print("\n" + "="*80)
                print("🛑 Incident resolved - stopping executive summary generation")
                print("📝 Final post-mortem available in Confluence and JIRA")
                print("="*80 + "\n")
                break

            # Stop generating summaries after post-mortem is created
            if self.state.confluence_postmortem_created:
                print("\n" + "="*80)
                print("🛑 Post-mortem created - stopping executive summary generation")
                print("📝 JIRA tickets and Confluence page are the final updates")
                print("="*80 + "\n")
                break
            
            # CRITICAL: Do not generate summaries until incident is declared
            if not self.state.slack_channel_id:
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"⏳ [{current_time}] Waiting for incident declaration... (slack_channel_id: {self.state.slack_channel_id})")
                print("   ℹ️  The /declare-incident command will automatically create and link the incident channel")
                continue

            # Check if we have enough events
            if len(self.state.all_events) < 5:
                print("⏳ Waiting for more events before generating summary...")
                continue
            
            # Increment summary count
            self.state.summary_count += 1

            # 🚨 CHECK FOR RESOLUTION BEFORE GENERATING SUMMARY
            # Look at recent Zoom messages for resolution keywords
            if not self.state.incident_resolved and not self.state.jira_tickets_created:
                recent_zoom = [e.message.lower() for e in self.state.zoom_events[-5:]]
                resolution_keywords = [
                    "marking as resolved", "incident resolved", "let's close it out",
                    "marking this resolved", "close it out"
                ]
                
                if any(keyword in msg for msg in recent_zoom for keyword in resolution_keywords):
                    print("\n" + "🔔"*40)
                    print("   🎯 INCIDENT RESOLUTION DETECTED IN ZOOM MESSAGES!")
                    print("   📋 Creating JIRA tickets and Confluence post-mortem...")
                    print("="*80)
                    
                    try:
                        # Import the tool directly
                        from atlassian_integration.integration import create_jira_and_confluence_postmortem
                        
                        # Create a minimal RunContext-like object
                        class SimpleContext:
                            def __init__(self, state):
                                self.deps = state
                        
                        ctx = SimpleContext(self.state)
                        postmortem_msg = await create_jira_and_confluence_postmortem(ctx)
                        
                        print(f"\n✅ POST-MORTEM CREATION COMPLETED!")
                        print("="*80)
                        print(postmortem_msg)
                        print("="*80)
                        
                        # Post to Slack
                        try:
                            from slack_integration.slack_integration import get_slack_client
                            slack_client = get_slack_client()
                            if slack_client and self.state.slack_channel_id:
                                slack_client.chat_postMessage(
                                    channel=self.state.slack_channel_id,
                                    text=postmortem_msg
                                )
                                print("   ✅ Posted post-mortem links to Slack!")
                        except Exception as slack_error:
                            print(f"   ⚠️  Could not post to Slack: {slack_error}")
                        
                        print("🔔"*40 + "\n")
                        
                        # Stop generating more summaries
                        continue
                        
                    except Exception as pm_error:
                        print(f"\n❌ Error creating post-mortem: {pm_error}")
                        import traceback
                        traceback.print_exc()
            
            print("\n" + "="*80)
            print(f"📊 GENERATING EXECUTIVE SUMMARY #{self.state.summary_count}")
            print("="*80)
            print(f"💬 Incident ACTIVE - Using channel: {self.state.slack_channel_id}")

            try:
                # Generate summary using AI agent
                base_prompt = get_generate_summary_prompt(
                    self.state.summary_count, 
                    self.state.slack_channel_id or "NOT_SET"
                )

                # Add current state context to help the agent
                # Note: We only reach this code when incident is declared (slack_channel_id exists)
                state_context = f"\n\n**CURRENT INCIDENT STATE:**\n"
                state_context += f"- Incident Status: ACTIVE (incident has been declared)\n"
                state_context += f"- Incident Channel ID: {self.state.slack_channel_id}\n"
                state_context += f"- Incident Duration: {int((datetime.now().timestamp() - self.state.incident_start_time) / 60)} minutes\n"
                state_context += f"- Summary Count: {self.state.summary_count}\n"
                state_context += f"- Last Feedback Request: Summary #{self.state.last_feedback_request_summary}\n"
                state_context += f"- Summaries Since Feedback: {self.state.summary_count - self.state.last_feedback_request_summary}\n"
                state_context += f"\n**CRITICAL INSTRUCTIONS:**\n"
                state_context += f"- The incident channel ALREADY EXISTS (ID: {self.state.slack_channel_id})\n"
                state_context += f"- DO NOT create new channels - use the existing channel\n"
                state_context += f"- Your PRIMARY task: Generate summary and post to existing channel\n"
                state_context += f"- ONLY use publish_exec_summary_to_slack tool - no channel creation needed\n"
                state_context += f"- Keep tool calls minimal and focused on summary posting\n"

                prompt = base_prompt + state_context

                # Run agent with retry limit to prevent infinite loops
                print("   🤖 Running AI agent to generate summary...")
                print(f"   📊 Current state - Channel ID: {self.state.slack_channel_id or 'Not created yet'}")

                try:
                    result = await agent.run(
                        prompt,
                        deps=self.state,
                        usage_limits=UsageLimits(request_limit=20)  # Increased from 10 to 20 to handle complex tool calls
                    )
                    print("   ✅ AI agent completed successfully")

                    # Log how many tool calls were made and check for post-mortem creation
                    postmortem_result = None
                    if hasattr(result, 'all_messages'):
                        tool_calls = [msg for msg in result.all_messages() if hasattr(msg, 'tool_calls') and msg.tool_calls]
                        if tool_calls:
                            total_calls = sum(len(msg.tool_calls) for msg in tool_calls)
                            print(f"   📞 Agent made {total_calls} tool call(s)")
                            
                            # Check if post-mortem tool was called
                            for msg in result.all_messages():
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tool_call in msg.tool_calls:
                                        tool_name = tool_call.tool_name if hasattr(tool_call, 'tool_name') else str(tool_call)
                                        print(f"      🔧 Tool called: {tool_name}")
                                        if 'postmortem' in tool_name.lower() or 'jira' in tool_name.lower():
                                            print(f"      🎯 POST-MORTEM TOOL DETECTED!")
                                            # Find the corresponding tool return message
                                            for ret_msg in result.all_messages():
                                                if hasattr(ret_msg, 'tool_return') and ret_msg.tool_return:
                                                    postmortem_result = str(ret_msg.tool_return.content)
                                                    print(f"      📋 Post-mortem result captured: {postmortem_result[:100]}...")

                except Exception as agent_error:
                    # Check if it's a usage limit error
                    error_str = str(agent_error).lower()
                    if "usage" in error_str or "limit" in error_str or "request" in error_str:
                        print(f"   ⚠️  AGENT USAGE LIMIT REACHED!")
                        print(f"   The agent exceeded the maximum number of requests (10 allowed)")
                        print(f"   This usually means:")
                        print(f"   - The agent is stuck in a loop calling tools repeatedly")
                        print(f"   - The agent is trying to create a channel that already exists")
                        print(f"   - Check the Slack channel state: {self.state.slack_channel_id}")
                        print(f"   Error: {agent_error}")
                        print(f"\n   Skipping this summary and continuing...\n")
                        continue
                    else:
                        # Re-raise other exceptions
                        raise

                # Check if channel was just created (state would have been updated by the agent tool)
                if self.state.slack_channel_id and self.state.slack_channel_id != previous_channel_id:
                    print(f"\n🎉 INCIDENT CHANNEL CREATED!")
                    print(f"   Channel ID: {self.state.slack_channel_id}")
                    print(f"   👉 Join this channel in Slack to follow incident updates\n")
                    previous_channel_id = self.state.slack_channel_id
                
                # Parse the response - use .output for pydantic-ai
                response_text = str(result.output)
                
                # Try to extract JSON if present, otherwise display as-is
                try:
                    import re
                    json_match = re.search(r'{.*}', response_text, re.DOTALL)
                    if json_match:
                        summary_dict = json.loads(json_match.group())
                        
                        # Display summary
                        severity = summary_dict.get('severity', 'UNKNOWN')
                        print(f"\n{'🔴' if 'SEV-1' in severity or 'SEV-2' in severity else '🟡'} EXECUTIVE SUMMARY")
                        print(f"Time: {summary_dict.get('timestamp', 'N/A')}")
                        print(f"Duration: {summary_dict.get('incident_duration', 'N/A')}")
                        print(f"Severity: {severity}")
                        print(f"\n📍 Current Status:")
                        print(f"   {summary_dict.get('current_status', 'N/A')}")
                        print(f"\n👥 Customer Impact:")
                        print(f"   {summary_dict.get('customer_impact', 'N/A')}")
                        print(f"\n✅ Key Actions Taken:")
                        for action in summary_dict.get('key_actions_taken', []):
                            print(f"   • {action}")
                        
                        if summary_dict.get('root_cause'):
                            print(f"\n🔍 Root Cause:")
                            print(f"   {summary_dict['root_cause']}")
                        
                        if summary_dict.get('eta_to_resolution'):
                            print(f"\n⏱️  ETA to Resolution:")
                            print(f"   {summary_dict['eta_to_resolution']}")
                    else:
                        # No JSON found, display raw response
                        print(f"\n📊 EXECUTIVE SUMMARY")
                        print(response_text)
                except (json.JSONDecodeError, KeyError) as e:
                    # Fallback to displaying raw response
                    print(f"\n📊 EXECUTIVE SUMMARY")
                    print(response_text)
                
                # If post-mortem was created, display it prominently
                if postmortem_result:
                    print("\n" + "🎉"*40)
                    print("\n📚 POST-MORTEM DOCUMENTATION CREATED")
                    print("="*80)
                    print(postmortem_result)
                    print("="*80)
                    print("\n" + "🎉"*40 + "\n")
                
                # 🚨 NEW: Explicit post-mortem creation when incident is resolved
                # Check if the summary indicates resolution and post-mortem hasn't been created
                if not self.state.incident_resolved and not self.state.jira_tickets_created:
                    response_lower = response_text.lower()
                    resolution_keywords = [
                        "incident resolved", "resolved -", "status: resolved",
                        "all systems operational", "systems have returned to normal",
                        "incident closed", "marking as resolved"
                    ]
                    
                    if any(keyword in response_lower for keyword in resolution_keywords):
                        print("\n" + "🔔"*40)
                        print("   🎯 INCIDENT RESOLUTION DETECTED!")
                        print("   📋 Creating JIRA tickets and Confluence post-mortem...")
                        print("="*80)
                        
                        try:
                            # Import the tool directly
                            from atlassian_integration.integration import create_jira_and_confluence_postmortem
                            
                            # Create a minimal RunContext-like object
                            class SimpleContext:
                                def __init__(self, state):
                                    self.deps = state
                            
                            ctx = SimpleContext(self.state)
                            postmortem_msg = await create_jira_and_confluence_postmortem(ctx)
                            
                            print(f"\n✅ POST-MORTEM CREATION COMPLETED!")
                            print("="*80)
                            print(postmortem_msg)
                            print("="*80)
                            
                            # TODO: Post this message to Slack
                            # For now, just display it
                            
                        except Exception as pm_error:
                            print(f"\n❌ Error creating post-mortem: {pm_error}")
                            import traceback
                            traceback.print_exc()
                        
                        print("🔔"*40 + "\n")
                
                print("\n" + "="*80 + "\n")
                
                self.state.last_summary_time = datetime.now().timestamp()

            except Exception as e:
                print(f"❌ Error generating summary: {e}")
                import traceback
                traceback.print_exc()
    
    async def run(self):
        """Run all monitoring tasks concurrently"""
        print("🚀 Starting AI Incident Response Monitor")
        print(f"📡 Monitoring streams at {self.base_url}")
        if self.slack_monitor_channel:
            print(f"💬 Monitoring Slack channel: {self.slack_monitor_channel}")
        print(f"📊 Executive summaries every {self.summary_interval} seconds\n")
        
        # Create tasks for all streams and summary generation
        tasks = [
            asyncio.create_task(self.connect_to_stream("incidents", "metrics")),
            asyncio.create_task(self.connect_to_stream("zoom", "zoom")),
            asyncio.create_task(self.generate_summaries()),
        ]
        
        # Use real Slack streaming if channel is configured, otherwise use localhost stream
        if self.slack_monitor_channel:
            tasks.append(asyncio.create_task(self.stream_from_slack_channel()))
        else:
            print(f"💬 Monitoring Simulator stream: {self.slack_monitor_channel}")
            tasks.append(asyncio.create_task(self.connect_to_stream("team", "slack")))

        # Run all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

# ============================================================================
# Meeting Decisions Generation Workflow
# ============================================================================

# Import the meeting decisions workflow from separate module
try:
    from meeting_decisions_workflow import generate_decisions_for_task_service_meetings
except ImportError:
    # If the workflow module doesn't exist, define a stub
    async def generate_decisions_for_task_service_meetings():
        print("❌ Meeting decisions workflow not available")
        print("   The meeting_decisions_workflow.py module was not found")
        return


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point"""
    # Check if we should run the meeting decisions workflow instead of incident monitoring
    if os.getenv("GENERATE_MEETING_DECISIONS", "0") == "1":
        print("🎯 Running Meeting Decisions Generation Workflow")
        await generate_decisions_for_task_service_meetings()
        return

    # SSL/Certificate diagnostics
    print("\n🔐 SSL/Certificate Diagnostics:")
    try:
        print(f"   • Python SSL version: {ssl.OPENSSL_VERSION}")
        print(f"   • Default CA bundle: {ssl.get_default_verify_paths().cafile}")
        print(f"   • Certifi CA bundle: {certifi.where()}")
    except Exception as e:
      print(f"   ⚠️  Error during SSL diagnostics: {e}")

    # Check if Slack token is set
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if slack_token:
        print(f"   • SLACK_BOT_TOKEN: ✓ Set (length: {len(slack_token)})")
    else:
        print(f"   • SLACK_BOT_TOKEN: ❌ Not set")



    # Initialize Slack client and test connection
    slack_healthy = await initialize_slack_client()
    if not slack_healthy:
        print("⚠️  Warning: Slack integration will not be available")
        print("   The agent will continue but cannot create channels or post messages\n")

    # Get Slack channel to monitor from environment variable
    slack_monitor_channel = os.getenv("SLACK_MONITOR_CHANNEL","C09QB9P3XST")
    if slack_monitor_channel:
        print(f"\n💬 Slack monitoring enabled for channel: {slack_monitor_channel}")
        print(f"   Messages will be polled using bot token (every 2 seconds)")
    else:
        print(f"\n💬 SLACK_MONITOR_CHANNEL not set - using localhost:8081 for Slack events")
        print(f"   Set SLACK_MONITOR_CHANNEL (e.g., '#incident-response') to poll from real Slack channel")

    monitor = IncidentMonitor(
        base_url="http://localhost:8081",  # Updated to match Go server port
        summary_interval=15,  # Summary every 15 seconds
        slack_monitor_channel=slack_monitor_channel  # Configure Slack channel to monitor
    )

    # Set the global incident state reference so slash command handler can update it
    print(f"\n🔗 Connecting incident state to Slack integration...")
    set_global_incident_state(monitor.state)
    print(f"   ✓ Incident state connected - slash commands can now update channel ID\n")

    try:
        # Run the monitor
        await monitor.run()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
