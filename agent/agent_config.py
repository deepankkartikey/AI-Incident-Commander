# ============================================================================
# AI Agent Configuration
# ============================================================================
import os
from pydantic_ai import Agent

from agent.models import IncidentState
from agent.system_prompts import load_system_prompt

# Choose AI model based on environment
# Option 1: Groq (Free & Fast - Recommended!)
# Option 2: OpenAI (Free $5 credits, then pay-per-use)  
# Option 3: Keep Bedrock (requires AWS setup)
MODEL_TYPE = os.getenv('AI_MODEL_TYPE', 'groq')  # Default to Groq

if MODEL_TYPE == 'groq':
    # Groq - Free and super fast Llama 3.1 (updated model)
    model = 'groq:llama-3.1-8b-instant'
elif MODEL_TYPE == 'openai':
    # OpenAI GPT-3.5 Turbo - Free $5 credits
    model = 'openai:gpt-3.5-turbo'
elif MODEL_TYPE == 'bedrock':
    # AWS Bedrock Claude (original)
    model = 'bedrock:us.anthropic.claude-3-5-sonnet-20241022-v2:0'
else:
    # Fallback to Groq
    model = 'groq:llama-3.1-70b-versatile'

# Initialize the AI agent
agent = Agent(
    model,
    deps_type=IncidentState,
    system_prompt=load_system_prompt("incident_monitor")
)
