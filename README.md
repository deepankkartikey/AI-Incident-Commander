# AI Communication Monitor

A personal AI-powered incident response system that monitors real-time communication streams and automatically creates intelligent summaries with integrated JIRA tickets and Confluence documentation.

## ✨ Features

- 🤖 **AI-Powered Analysis** - Uses Groq's Llama 3.1 for fast, real-time incident analysis
- 💬 **Slack Integration** - Real-time monitoring of channels with Socket Mode
- 📊 **Multi-Stream Monitoring** - Tracks metrics, status updates, and chat messages via SSE
- 🎫 **JIRA Integration** - Creates tickets and epics for action items and tracking
- 📄 **Confluence Integration** - Generates professional post-mortem documentation
- 🔗 **Smart Cross-Linking** - Links tickets, pages, and Slack messages automatically
- ⚙️ **Event-Driven Architecture** - Responds to incident lifecycle changes in real-time

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Go 1.23+
- Free accounts: Slack, Atlassian, Groq

### Setup

1. **Clone and setup environment:**
   ```bash
   git clone <your-repo>
   cd AI\ Comm
   ./run.sh  # Starts both Go and Python services
   ```

2. **Configure your credentials:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (see Configuration section)
   ```

3. **That's it!** The `run.sh` script handles everything:
   - Loads environment variables securely
   - Starts Go content generator (port 8081)
   - Starts Python AI monitor
   - Provides graceful shutdown with Ctrl+C

## 🔄 System Architecture

### Personal Setup Flow

```
Go SSE Server (8081) → Python AI Monitor → Slack Socket Mode
        ↓                      ↓                    ↓
   Incident Streams     Groq AI Analysis    Real-time Messages
        ↓                      ↓                    ↓
   Timeline Events      Smart Summaries       Channel Updates
        ↓                      ↓                    ↓
    JIRA Tickets ←← Confluence Pages ←← Slack Notifications
```

### What It Does

1. **Real-Time Monitoring**: 
   - Go server simulates incident data streams
   - Python monitor listens to Slack channels
   - AI analyzes patterns and generates insights

2. **Smart Integration**: 
   - Detects incident lifecycle events
   - Creates organized documentation in Confluence
   - Tracks action items in JIRA
   - Posts summaries to Slack channels

3. **Personal Workflow**: Perfect for:
   - Learning AI/ML integration
   - Practicing DevOps incident response
   - Building portfolio projects
   - Experimenting with modern APIs

## ⚙️ Configuration

Create your `.env` file with these free-tier credentials:

```bash
# Slack (Free)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Atlassian (Free)
ATLASSIAN_API_EMAIL=your-email@gmail.com
ATLASSIAN_API_TOKEN=your-api-token
ATLASSIAN_URL=https://your-site.atlassian.net
ATLASSIAN_CLOUD_ID=your-cloud-id
JIRA_PROJECT_KEY=YOUR_KEY
CONFLUENCE_SPACE_ID=YOUR_SPACE

# Groq AI (Free)
AI_MODEL_TYPE=groq
GROQ_API_KEY=gsk_your-groq-api-key

# Optional
STATUSPAGE_API_KEY=your-statuspage-key
```

### Getting Free API Keys

- **🆓 Slack**: Create bot at https://api.slack.com/apps
- **🆓 Atlassian**: Sign up at https://atlassian.com (10 users free)
- **🆓 Groq**: Get API key at https://console.groq.com (fast & free)

## 🎯 Personal Learning Outcomes

This project demonstrates:

- **Modern AI Integration**: Using latest LLMs for real-world tasks
- **Microservices Architecture**: Go + Python services working together
- **Real-Time Systems**: Socket Mode, SSE streams, event-driven design
- **API Integration**: REST APIs, webhooks, third-party services
- **DevOps Practices**: Environment management, security, automation
- **Documentation**: Automated documentation generation with AI

## 📊 What Gets Created

### Live Demo Output
- **Web Interface**: http://localhost:8081 (incident timeline)
- **Slack Channel**: Real-time monitoring with AI summaries
- **JIRA Epic**: Tracks all related action items
- **Confluence Page**: Professional post-mortem documentation

### Example Workflow
```
Incident Detected → AI Analysis → Slack Summary → JIRA Tickets → Confluence Docs
      ↓                 ↓              ↓              ↓              ↓
"API Gateway      "Root cause:     "Executive     "APB-123:      "Complete
 outage started"   Memory leak"     summary        Fix memory     post-mortem
                                   posted"        leak"          generated"
```

## 🏗️ Project Structure

```
AI Comm/
├── 🚀 run.sh                          # One-command startup script
├── 🐍 main.py                         # Python AI monitor
├── 📁 contentgen/
│   └── 🔧 main.go                     # Go SSE server
├── 🤖 agent/
│   ├── agent_config.py                # AI model configuration
│   └── system_prompts.py              # AI behavior instructions
├── 💬 slack_integration/
│   └── slack_integration.py           # Real-time Slack monitoring
├── 🏢 atlassian_integration/
│   └── integration.py                 # JIRA/Confluence automation
├── 🔧 .env.example                    # Configuration template
└── 📋 requirements.txt                # Python dependencies
```

## 🧪 Testing Your Setup

```bash
# Start everything
./run.sh

# Expected output:
🚀 Starting AI Communication System...
📄 Loading environment variables from .env file...
✅ Environment variables loaded
1️⃣ Starting Content Generator (Go) on port 8081...
2️⃣ Starting AI Communication Monitor (Python)...
🎯 Both services started successfully!
```

Visit http://localhost:8081 to see the incident simulation interface.

## 🛠️ Technology Stack

- **AI**: Groq Llama 3.1 (free tier, lightning fast)
- **Backend**: Python 3.12 with Pydantic AI
- **Streaming**: Go with Server-Sent Events
- **Integrations**: Slack SDK, Atlassian REST APIs
- **Security**: Environment-based configuration
- **Deployment**: Simple bash scripting for local development

## 📚 Learning Resources

Built while learning:
- Real-time AI applications
- Modern Python async programming
- Go concurrent programming  
- REST API integration patterns
- Event-driven architectures
- DevOps automation practices

## 📝 Personal Project

This is a personal learning project by **Deepank Kartikey**. Built to explore:
- Modern AI/LLM integration patterns
- Real-time communication systems
- DevOps incident response automation
- Multi-language service architectures

Feel free to fork, modify, and learn from this codebase! 🚀

