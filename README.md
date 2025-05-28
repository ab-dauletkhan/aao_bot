# Telegram FAQ Bot

A modular Telegram bot that answers student questions based on an FAQ document, powered by OpenAI. Designed for easy deployment and extension, with features for advisors to manage the bot's activity and moderate content.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **AI-Powered Responses**: Uses OpenAI to provide concise, FAQ-based answers to student questions.
- **Advisor Controls**: Advisors can activate, deactivate, and check the bot's status using simple commands.
- **Reaction-Based Moderation**: Advisors can delete bot messages with a downvote reaction (👎) for quick moderation.
- **Logging and Monitoring**: Comprehensive logging for easy debugging and performance tracking.
- **Flexible Deployment**: Supports both polling (for local development) and webhook (for production) modes.

---

## Installation

1. **Clone the repository**:

    ```bash
    gh repo clone ab-dauletkhan/aao_bot
    cd telegram-faq-bot
    ```

2. **Install dependencies**:

    ```bash
    uv venv env -p 3.11
    source env/bin/activate
    uv pip install -r requirements.txt
    ```

    > **Note**: Ensure you have Python 3.11+ installed.

3. **Set up environment variables**:

    - Create a `.env` file in the project root (see [Configuration](#configuration) for details).
4. **Prepare the FAQ file**:

    - Place your FAQ content in a file named `faq.md` in the project root.
5. **Run the bot**:

    ```bash
    uv run python main.py
    ```


---

## Usage

### Running the Bot

- **Polling Mode (Local Development)**: Simply run `python main.py` without webhook settings.
- **Webhook Mode (Production)**: Set `WEBHOOK_DOMAIN` and `WEBHOOK_URL_PATH` in your `.env` file for server deployment.

### Commands

- `/start`: Activate the bot (advisors only).
- `/stop`: Deactivate the bot (advisors only).
- `/status`: Check the bot's current status (advisors only).

### Interacting with the Bot

- **Students**: Send a text message with a question, and the bot will respond with an answer from the FAQ.
- **Advisors**: Use reactions (👎) to delete bot messages if needed.

---

## Configuration

To configure the bot, create a `.env` file in the project root with the following variables:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
MODERATOR_CHAT_ID=your_moderator_chat_id
ADVISOR_USER_IDS=comma_separated_advisor_user_ids
```

- **`TELEGRAM_BOT_TOKEN`**: Required. Get this from [BotFather](https://t.me/BotFather).
- **`OPENAI_API_KEY`**: Optional for basic testing. Get this from [OpenAI](https://platform.openai.com/).
- **`MODERATOR_CHAT_ID`**: Optional. The chat ID where moderator notifications are sent.
- **`ADVISOR_USER_IDS`**: Optional. Comma-separated list of Telegram user IDs with advisor privileges (e.g., `123456,789101`).

Additionally:

- Place your FAQ content in `faq.md` in the project root. The bot uses this to generate responses.

---

## Project Structure

Here’s a quick overview of the project’s modular structure:

- **`config.py`**: Environment variables and constants.
- **`logging.py`**: Logging configuration.
- **`openai_client.py`**: OpenAI integration for generating responses.
- **`utils.py`**: Utility functions (e.g., markdown sanitization).
- **`handlers/`**: Telegram bot handlers (commands, messages, reactions).
- **`webhook.py`**: Webhook and health check functions for production.
- **`main.py`**: Entry point to start the bot.

This structure makes it easy to maintain and extend the bot’s functionality.

---

## Contributing

We welcome contributions! To get started:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with clear, descriptive messages.
4. Open a pull request with a detailed description of your changes.

Please follow our [code of conduct](CODE_OF_CONDUCT.md) and [contributing guidelines](CONTRIBUTING.md).

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

### Additional Notes

- **Logging**: The bot logs to both the console and a `logs/` directory for easy debugging.
- **OpenAI**: If no `OPENAI_API_KEY` is provided, the bot will still run but won’t answer questions.
- **Testing**: Use polling mode for local testing and development.
