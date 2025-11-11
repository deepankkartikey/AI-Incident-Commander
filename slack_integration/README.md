# Slack Integration Setup Guide

This guide covers the complete setup of Slack integration for the AI Incident Response system, including bot permissions, Socket Mode configuration, and troubleshooting.

## 🤖 Slack Bot Setup

### Step 1: Create Slack App

1. **Go to**: https://api.slack.com/apps
2. **Click**: "Create New App" → "From scratch"
3. **Enter**: App name (e.g., "AI Incident Commander")
4. **Select**: Your workspace
5. **Click**: "Create App"

### Step 2: Configure Bot Token Scopes

Navigate to **OAuth & Permissions** in the sidebar and add these Bot Token Scopes:

```
✅ Required Bot Token Scopes:
┌─────────────────────┬─────────────────────────────────────────┐
│ Scope               │ Purpose                                 │
├─────────────────────┼─────────────────────────────────────────┤
│ app_mentions:read   │ Detect when bot is mentioned (@bot)    │
│ channels:history    │ Read messages from public channels     │
│ channels:manage     │ Create new incident channels           │
│ channels:read       │ List and access channel information    │
│ channels:join       │ Join public channels automatically     │
│ chat:write          │ Send messages as the bot               │
│ chat:write.public   │ Send messages to channels bot isn't in │
│ commands            │ Handle slash commands (/declare-...)   │
│ groups:history      │ Read private channel messages          │
│ im:history          │ Read direct message history            │
│ im:read             │ Access direct message information      │
│ im:write            │ Send direct messages to users          │
│ users:read          │ Read user profile information          │
└─────────────────────┴─────────────────────────────────────────┘
```

### Step 3: Enable Socket Mode

1. **Navigate to**: "Socket Mode" in the sidebar
2. **Toggle**: "Enable Socket Mode" ✅
3. **Click**: "Generate" to create App-Level Token
4. **Add scope**: `connections:write`
5. **Name**: "Socket Token" (or any name)
6. **Copy**: The App-Level Token (starts with `xapp-`)

### Step 4: Configure Slash Commands

1. **Navigate to**: "Slash Commands" in the sidebar
2. **Click**: "Create New Command"
3. **Command**: `/declare-incident`
4. **Request URL**: Leave blank (using Socket Mode)
5. **Short Description**: "Declare a new incident (sev1 or sev2)"
6. **Usage Hint**: `[sev1|sev2]`
7. **Click**: "Save"

### Step 5: Install App to Workspace

1. **Navigate to**: "OAuth & Permissions"
2. **Click**: "Install App to Workspace"
3. **Review permissions** and click "Allow"
4. **Copy**: Bot User OAuth Token (starts with `xoxb-`)

## 🔑 Environment Configuration

Add these tokens to your `.env` file:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-level-token-here
```

## 🧪 Testing Your Setup

### Quick Verification Commands

```bash
# 1. Start the application
cd "AI Comm" && ./run.sh

# 2. Expected startup output:
✅ Slack connection successful!
   Bot: your_bot_name (ID: B123...)
   Team: Your Workspace Name

✅ Socket Mode connection established
📡 Real-time message streaming active
```

### In-Slack Testing

1. **Add bot to channel**: `/invite @your_bot_name`
2. **Test slash command**: `/declare-incident sev2`
3. **Test mentions**: `@your_bot_name hello`

### Expected Slash Command Flow

```
User: /declare-incident sev2
Bot Response:
🔧 [SLASH COMMAND] /declare-incident sev2 detected
🤖 AI Generated Incident Name: incident-20251110-1234-api-timeout
📝 AI Generated Summary: SEV2 incident - API gateway timeout affecting users
🏗️ Attempting to create channel: incident-20251110-1234-api-timeout-summary
✅ Channel created: #incident-20251110-1234-api-timeout-summary
✅ Incident declared: SEV-2 (Major)
```

## 🔧 Troubleshooting

### Common Permission Errors

#### ❌ `missing_scope - needed: 'channels:manage'`

**Problem**: Bot can't create channels
**Solution**: 
1. Go to OAuth & Permissions in your Slack app
2. Add `channels:manage` scope
3. Click "Reinstall App to Workspace"
4. Authorize new permissions

#### ❌ `channel_not_found` or `not_in_channel`

**Problem**: Bot not in the target channel
**Solution**: Add bot to channel: `/invite @your_bot_name`

#### ❌ `invalid_auth`

**Problem**: Wrong or expired tokens
**Solution**: 
- Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
- Verify `SLACK_APP_TOKEN` starts with `xapp-`
- Check tokens aren't expired in Slack app settings

### Socket Mode Issues

#### ❌ Socket connection fails

**Problem**: App-Level Token issues
**Solution**:
1. Verify Socket Mode is enabled
2. Check App-Level Token has `connections:write` scope
3. Regenerate token if needed

#### ❌ Slash commands not working

**Problem**: Socket Mode configuration
**Solution**:
1. Ensure Socket Mode is enabled
2. Verify `/declare-incident` command exists
3. Check bot is added to channel where command is used

### AI Generation Issues

#### ⚠️ AI generation fallback mode

**Expected behavior**: When AI fails, system uses fallback:
```
⚠️ AI generation failed: [error details]
🤖 AI Generated Incident Name: incident-20251110-1234-sev2
📝 AI Generated Summary: SEV2 incident declared based on recent conversation
```

This is normal and doesn't break functionality.

## 🔄 Permission Update Process

If you need to add permissions later:

1. **Add scopes** in OAuth & Permissions
2. **Reinstall app** (button appears after adding scopes)
3. **Restart application** to pick up new permissions
4. **Test functionality** with slash commands

## 📊 Bot Capabilities

Once properly configured, your bot can:

- ✅ **Monitor channels** in real-time via Socket Mode
- ✅ **Create incident channels** automatically
- ✅ **Handle slash commands** (`/declare-incident`)
- ✅ **Generate AI summaries** of incidents
- ✅ **Post status updates** to channels
- ✅ **Cross-link** with JIRA tickets and Confluence pages

## 🏗️ Architecture Notes

### Why Socket Mode?

- **Real-time**: Instant message processing without polling
- **Secure**: No need to expose public endpoints
- **Simple**: No webhook URL management required
- **Development-friendly**: Works locally without tunneling

### Message Flow

```
Slack Channel → Socket Mode → Python Application → AI Analysis → Response
      ↑                                                              ↓
   User Input ←←←←←←←←←←←←←←← Bot Messages/Reactions ←←←←←←←←←←←←←←←←
```

## 🔒 Security Best Practices

1. **Environment Variables**: Never commit tokens to git
2. **Token Rotation**: Regenerate tokens periodically
3. **Minimal Permissions**: Only add required scopes
4. **Monitoring**: Check app usage in Slack admin panel

## 💡 Pro Tips

1. **Testing**: Use a dedicated test workspace first
2. **Naming**: Use descriptive bot and app names
3. **Documentation**: Keep track of which channels the bot monitors
4. **Updates**: Test permission changes in dev before production

---

## 🔗 Related Documentation

- [Main Project README](../README.md)
- [Agent Configuration](../agent/README.md)
- [Atlassian Integration](../atlassian_integration/README.md)

## 🆘 Need Help?

Common issues and solutions are documented above. For Slack-specific API questions, refer to:
- [Slack API Documentation](https://api.slack.com/docs)
- [Socket Mode Guide](https://api.slack.com/apis/connections/socket)
- [Bot User Guide](https://api.slack.com/bot-users)

