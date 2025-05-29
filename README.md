# Telegram FAQ Bot

A sophisticated, AI-powered Telegram bot designed to automatically answer student questions using FAQ content. Built with modularity and scalability in mind, featuring comprehensive advisor controls and intelligent content moderation.

## 🚀 Features

### Core Functionality
- **🤖 AI-Powered Responses**: Leverages OpenAI's GPT models to provide contextual, FAQ-based answers
- **📚 Dynamic FAQ Integration**: Automatically processes and learns from your FAQ document
- **🔄 Real-time Processing**: Instant responses to student queries with intelligent context matching

### Administrative Controls
- **👥 Advisor Management**: Role-based access control for bot administration
- **⚡ Bot State Control**: Start, stop, and monitor bot activity with simple commands
- **📊 Status Monitoring**: Real-time bot health and activity status checking

### Moderation & Safety
- **👎 Quick Moderation**: Delete inappropriate bot responses with a simple downvote reaction
<!-- - **🛡️ Content Filtering**: Built-in safeguards for appropriate responses -->
- **📝 Comprehensive Logging**: Detailed activity logs for monitoring and debugging

### Deployment Flexibility
- **🔧 Development Mode**: Polling-based setup for local testing
- **🌐 Production Ready**: Webhook support for scalable server deployment
- **⚙️ Environment-Based Config**: Secure configuration management

## 📋 Prerequisites

- Python 3.11 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- OpenAI API Key (optional for basic testing)
- FAQ content in Markdown format

## 🛠️ Installation

### 1. Clone the Repository

```bash
gh repo clone ab-dauletkhan/aao_bot
cd aao_bot
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
uv venv env -p 3.11

# Activate environment
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional but recommended
OPENAI_API_KEY=your_openai_api_key_here
MODERATOR_CHAT_ID=your_moderator_chat_id
ADVISOR_USER_IDS=123456789,987654321

# Production webhook settings (optional)
WEBHOOK_DOMAIN=https://yourdomain.com
WEBHOOK_URL_PATH=/webhook/your-secret-path
```

### 4. Prepare FAQ Content

Create a `faq.md` file in the project root with your FAQ content:

```markdown
# Frequently Asked Questions

## How do I register for classes?
To register for classes, log into the student portal...

## What are the library hours?
The library is open Monday-Friday 8AM-10PM...
```

### 5. Run the Bot

```bash
# Start the bot
uv run python bot/main.py
```

## 🎯 Usage

### For Students
Simply send any question as a text message to the bot. The AI will analyze your question against the FAQ content and provide a relevant answer.

**Example:**
```
Student: "What are the office hours?"
Bot: "According to our FAQ, office hours are Monday-Friday 9AM-5PM. You can visit the main office or schedule an appointment online."
```

### For Advisors
Advisors have special privileges to control the bot:

| Command | Description | Usage |
|---------|-------------|-------|
| `/start` | Activate the bot | Send in any chat |
| `/stop` | Deactivate the bot | Send in any chat |
| `/status` | Check bot status | Send in any chat |
| 👎 Reaction | Delete bot message | React to any bot message |

## ⚙️ Configuration Options

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | Bot token from BotFather | `1234567890:ABC...` |
| `OPENAI_API_KEY` | ❌ No | OpenAI API key for AI responses | `sk-proj-...` |
| `MODERATOR_CHAT_ID` | ❌ No | Chat ID for moderation alerts | `-1001234567890` |
| `ADVISOR_USER_IDS` | ❌ No | Comma-separated advisor user IDs | `123456,789012` |
| `WEBHOOK_DOMAIN` | ❌ No | Domain for webhook mode | `https://bot.example.com` |
| `WEBHOOK_URL_PATH` | ❌ No | Webhook URL path | `/webhook/secret` |

### Deployment Modes

#### Development (Polling)
```bash
# Simply run without webhook settings
uv run python bot/main.py
```

#### Production (Webhook)
```env
WEBHOOK_DOMAIN=https://yourdomain.com
WEBHOOK_URL_PATH=/webhook/your-secret-path
PORT=you-may-skip-or-set-to-8443
```

## 📁 Project Structure

```
telegram-faq-bot/
├── main.py                 # Application entry point
├── config.py              # Configuration and environment variables
├── logging_config.py      # Logging setup and configuration
├── openai_client.py       # OpenAI API integration
├── utils.py               # Utility functions and helpers
├── webhook.py             # Webhook and health check handlers
├── handlers/              # Telegram bot event handlers
│   ├── __init__.py
│   ├── commands.py        # Command handlers (/start, /stop, etc.)
│   ├── messages.py        # Message processing and AI responses
│   └── reactions.py       # Reaction-based moderation
├── logs/                  # Application logs (auto-created)
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── faq.md                # FAQ content (you create this)
└── README.md             # This file
```

## 🚀 Advanced Features

### Custom FAQ Processing
The bot automatically parses your `faq.md` file and creates a knowledge base. It supports:
- Markdown formatting
- Multiple sections and categories
- Dynamic content updates (restart required)

### Logging and Monitoring
- **Console Logging**: Real-time activity monitoring
- **Error Tracking**: Detailed error reporting and stack traces
- **Performance Metrics**: Response times and API usage tracking

### Security Features
- **Role-based Access**: Only designated advisors can control the bot
- **Input Sanitization**: Markdown injection prevention
- **Rate Limiting**: Built-in protection against spam
- **Secure Configuration**: Environment-based secrets management

## 🐛 Troubleshooting

### Common Issues

**Bot not responding:**
- Check if `TELEGRAM_BOT_TOKEN` is correct
- Verify the bot is activated with `/start`
- Check logs in the `logs/` directory

**AI responses not working:**
- Ensure `OPENAI_API_KEY` is set and valid
- Check your OpenAI account has sufficient credits
- Verify the `faq.md` file exists and has content

**Webhook issues:**
- Ensure your server is accessible via HTTPS
- Check that the webhook URL path is correct
- Verify your domain certificate is valid

### Getting Help

1. Check the logs for error messages
2. Review the [Contributing Guidelines](CONTRIBUTING.md)
3. Open an issue on GitHub with:
   - Error messages from logs
   - Steps to reproduce
   - Your environment details

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before getting started.

### Quick Start for Contributors

1. Fork the repository
2. Create a feature branch: `git switch -c feature/amazing-feature`
3. Make your changes and test thoroughly
4. Commit with clear messages: `git commit -m 'Add amazing feature'`
5. Push to your fork: `git push origin feature/amazing-feature`
6. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔐 Security

For security concerns, please review our [Security Policy](SECURITY.md) and report vulnerabilities responsibly.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [OpenAI](https://openai.com/) - AI-powered response generation
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

---

**You can use this project as your first open-source contribution!**
