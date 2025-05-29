# Contributing to Telegram FAQ Bot

Thank you for your interest in contributing to the Telegram FAQ Bot! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

Before contributing, ensure you have:
- Python 3.11 or higher installed
- Git installed and configured
- A GitHub account
- Basic knowledge of Python and async programming
- Familiarity with the Telegram Bot API (helpful but not required)

### First-Time Contributors

Welcome! Here are some good ways to get started:

1. **Explore the codebase**: Read through the README and browse the code structure
2. **Look for beginner-friendly issues**: Check for issues labeled `good first issue` or `help wanted`
3. **Improve documentation**: Documentation improvements are always welcome
4. **Fix small bugs**: Start with minor bug fixes to get familiar with the codebase
5. **Ask questions**: Don't hesitate to ask questions in issues or discussions

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
gh repo clone ab-dauletkhan/aao_bot
cd aao_bot

# Add the upstream repository
git remote add upstream https://github.com/ab-dauletkhan/aao_bot.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
uv venv env -p 3.11
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt

# Install development dependencies (if available)
uv pip install -r requirements-dev.txt  # Create this file if needed
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your development credentials
# Use test bot tokens and API keys for development
```

### 4. Create FAQ Content

```bash
# Create a test FAQ file
echo "# Test FAQ\n\n## Test Question\nTest answer for development." > faq.md
```

### 5. Run Tests

```bash
# Run the bot in development mode
uv run python bot/main.py

# Test basic functionality
# Send messages to your test bot to verify it works
```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

#### Code Contributions
- **Bug fixes**: Fix reported issues
- **Feature development**: Add new functionality
- **Performance improvements**: Optimize existing code
- **Code refactoring**: Improve code structure and readability

#### Documentation
- **README improvements**: Make the README clearer and more helpful
- **Code comments**: Add or improve inline documentation
- **API documentation**: Document functions and classes
- **Tutorials**: Create guides for specific use cases

#### Content
- **FAQ templates**: Create example FAQ content
- **Configuration examples**: Provide deployment examples
- **Use case documentation**: Document different ways to use the bot

#### Testing
- **Unit tests**: Add test coverage for existing code
- **Integration tests**: Test bot functionality end-to-end
- **Performance tests**: Benchmark bot performance

### Contribution Workflow

1. **Check existing issues**: Look for related issues before starting work
2. **Create an issue**: For significant changes, create an issue to discuss first
3. **Create a branch**: Use a descriptive branch name
4. **Make changes**: Follow coding standards and write tests
5. **Test thoroughly**: Ensure your changes work as expected
6. **Submit pull request**: Follow the pull request template
7. **Address feedback**: Respond to review comments promptly

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some specific preferences:

```python
# Use type hints
def process_message(message: str) -> str:
    """Process user message and return response."""
    return response

# Use meaningful variable names
user_question = message.text
ai_response = generate_answer(user_question)

# Use docstrings for functions and classes
async def handle_user_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user question and send AI-generated response."""
    pass
```

### Code Organization

- **Modular design**: Keep functions and classes focused on single responsibilities
- **Clear naming**: Use descriptive names for variables, functions, and classes
- **Error handling**: Include appropriate error handling and logging
- **Async/await**: Use async/await consistently for asynchronous operations

### Import Organization

```python
# Standard library imports
import os
import logging
from typing import Optional, List

# Third-party imports
from telegram import Update
from telegram.ext import ContextTypes

# Local imports
from config import settings
from utils import sanitize_markdown
```

### Logging

Use the project's logging configuration:

```python
from loguru import logger
import sys


def setup_logging() -> None:
    """Set up loguru with rotation and JSON serialization."""
    logger.remove()

    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        colorize=True,
    )
```

## Testing Guidelines

### Manual Testing

Before submitting changes:

1. **Basic functionality**: Test that the bot starts and responds to messages
2. **Admin commands**: Verify `/start`, `/stop`, and `/status` work correctly
3. **Error handling**: Test with invalid inputs and edge cases
4. **Performance**: Ensure changes don't significantly impact response time

### Test Bot Setup

For development and testing:

1. Create a separate test bot with @BotFather
2. Use test API keys (OpenAI offers test credits)
3. Create a test Telegram group for testing advisor features
4. Document your test scenarios

### Writing Tests

If adding automated tests:

```python
import unittest
from unittest.mock import Mock, AsyncMock

class TestMessageHandler(unittest.TestCase):
    def setUp(self):
        self.handler = MessageHandler()

    async def test_process_user_question(self):
        # Test case implementation
        pass
```

## Pull Request Process

### Before Submitting

1. **Update documentation**: Update README or other docs if needed
2. **Test thoroughly**: Ensure all functionality works as expected
3. **Clean commit history**: Use meaningful commit messages
4. **Check compatibility**: Ensure changes work with Python 3.11+

### Pull Request Template

When creating a pull request, include:

```markdown
## Description
Brief description of changes and motivation.

## Changes Made
- List of specific changes
- New features or bug fixes
- Updated documentation

## Testing
- [ ] Manual testing completed
- [ ] No new errors in logs
- [ ] All existing functionality still works
- [ ] New features work as expected

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation has been updated
- [ ] Changes have been tested thoroughly
- [ ] Commit messages are clear and descriptive
```

### Review Process

1. **Automated checks**: Ensure any CI checks pass (first we need ci checks please)
2. **Code review**: Maintainers will review your code
3. **Address feedback**: Make requested changes promptly
4. **Final approval**: Maintainers will merge when ready

## Issue Guidelines

### Reporting Bugs

Use this template for bug reports:

```markdown
## Bug Description
Clear description of what the bug is.

## Steps to Reproduce
1. Go to '...'
2. Send message '...'
3. Observe error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- Python version:
- Operating system:
- Bot version/commit:
- Telegram client used:

## Logs
Include relevant error messages or logs (remove sensitive information).

## Additional Context
Any other context about the problem.
```

### Feature Requests

Use this template for feature requests:

```markdown
## Feature Description
Clear description of the feature you'd like to see.

## Use Case
Explain why this feature would be useful and who would benefit.

## Proposed Implementation
If you have ideas about how to implement this feature.

## Alternatives Considered
Other solutions you've considered.

## Additional Context
Any other context or examples.
```

### Issue Labels

We use these labels to categorize issues:

- `bug`: Something isn't working correctly
- `enhancement`: New feature or improvement
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed
- `question`: Further information requested
- `security`: Security-related issues
- `priority`: High priority issues

## Documentation

### Documentation Standards

- **Clear and concise**: Write for users of all skill levels
- **Examples included**: Provide code examples where helpful
- **Up-to-date**: Keep documentation current with code changes
- **Well-structured**: Use headers, lists, and formatting effectively

### Types of Documentation

#### Code Documentation
```python
def generate_response(question: str, faq_content: str) -> str:
    """
    Generate AI response based on user question and FAQ content.

    Args:
        question: User's question as a string
        faq_content: FAQ content to reference for answers

    Returns:
        AI-generated response string

    Raises:
        OpenAIError: If API request fails
        ValueError: If question or faq_content is empty
    """
    pass
```

#### README Updates
- Keep installation instructions current
- Update feature lists when adding functionality
- Include new configuration options
- Add troubleshooting for common issues

#### API Documentation
Document any new configuration options:

```markdown
### New Configuration Option

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEW_OPTION` | No | Description of what it does | `example_value` |
```

## Community

### Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For general questions and community discussions
- **Pull Request Comments**: For code review discussions

### Getting Help

If you need help while contributing:

1. **Check existing documentation**: README, issues, and pull requests
2. **Search closed issues**: Your question might have been answered before
3. **Create a discussion**: For general questions about contributing
4. **Ask in issues**: Comment on relevant issues if you need clarification

### Mentorship

We're committed to helping new contributors:

- **Code review feedback**: We provide constructive feedback on pull requests
- **Guidance on issues**: We help guide contributors toward good solutions
- **Documentation help**: We assist with documentation improvements
- **Best practices**: We share knowledge about Python and bot development

## Development Tips

### Useful Tools

```bash
# Code linters
uvx ruff check
uvx pyrefly check

# Code formatting
uvx ruff format
```

### Debugging

```python
# Add debug logging
logger.debug("Processing message: %s", message.text)

# Use pdb for debugging
import pdb; pdb.set_trace()

# Test with different inputs
test_messages = [
    "What are the office hours?",
    "How do I register?",
    "",  # Empty message
    "x" * 1000,  # Very long message
]
```

### Working with Telegram Bot API

```python
# Always handle API errors
try:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=response,
        parse_mode="MarkdownV2"
    )
except TelegramError as e:
    logger.error("Failed to send message: %s", e)
```

### OpenAI Integration Best Practices

```python
# Handle API limits and errors
try:
    response = await openai_client.generate_response(question)
except openai.RateLimitError:
    logger.warning("OpenAI rate limit reached")
    return "I'm currently receiving too many requests. Please try again later."
except openai.APIError as e:
    logger.error("OpenAI API error: %s", e)
    return "I'm having trouble processing your question right now."
```

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality in a backward-compatible manner
- **PATCH**: Backward-compatible bug fixes

### Contributing to Releases

- **Feature freeze**: New features stop being merged before releases
- **Bug fixes**: Critical bug fixes may be included in patch releases
- **Testing**: Help test release candidates
- **Documentation**: Ensure documentation is updated for releases

## Recognition

### Contributors

All contributors are recognized in:
- GitHub contributor graphs
- Release notes for significant contributions
- README acknowledgments section

### Types of Recognition

- **Code contributors**: Listed in commit history and GitHub contributors
- **Documentation contributors**: Acknowledged in documentation updates
- **Bug reporters**: Credited in issue resolution
- **Community helpers**: Recognized for helping other contributors

## Questions and Support

### For Contributors

If you have questions about contributing:

1. Check this CONTRIBUTING.md file
2. Look at existing issues and pull requests
3. Create a GitHub discussion
4. Contact maintainers directly if needed

### For Users

If you need help using the bot:

1. Check the README.md file
2. Look at existing issues
3. Create a new issue with the question label

## Thank You

Thank you for contributing to the Telegram FAQ Bot! Your contributions help improve the project for everyone in the educational community.

Every contribution, whether it's code, documentation, bug reports, or community support, is valuable and appreciated.

---

**Happy Contributing!** 🎉

*Last Updated: May 2025*
