ueue---
description: Repository Information Overview
alwaysApply: true
---

# Claude Remote Client Information

## Summary
Claude Remote Client is a Python application that provides a bridge between Slack and Claude CLI, enabling remote development workflows with session management, task queuing, and automated maintenance. It allows users to interact with Claude AI through Slack.

## Structure
- **claude_remote_client/**: Main package containing the application code
- **tests/**: Unit and integration tests
- **.kiro/**: Configuration for Kiro
- **.github/**: GitHub workflows and CI/CD configuration
- **.zencoder/**: Zencoder configuration and rules

## Language & Runtime
**Language**: Python
**Version**: 3.9+
**Build System**: setuptools
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- slack-sdk (>=3.21.0): Slack API client
- PyYAML (>=6.0): YAML parsing and configuration
- asyncio-mqtt (>=0.11.0): MQTT client for async operations

**Development Dependencies**:
- pytest (>=7.0.0): Testing framework
- pytest-asyncio (>=0.21.0): Async testing support
- pytest-mock (>=3.10.0): Mocking for tests
- pytest-cov (>=4.0.0): Test coverage

**Optional Dependencies**:
- croniter (>=1.3.0): Advanced cron parsing
- psutil (>=5.9.0): Process monitoring
- aiofiles (>=23.0.0): Async file operations

## Build & Installation
```bash
# Install from source
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"

# Install with enhanced functionality
pip install -e ".[enhanced]"
```

## Main Entry Points
**CLI Entry Point**: `claude-remote-client`
**Main Module**: `claude_remote_client.cli`
**Configuration**: Uses YAML configuration files (default: `~/.claude-remote-client/config.yaml`)

## Testing
**Framework**: pytest
**Test Location**: `tests/` directory
**Naming Convention**: `test_*.py`
**Run Command**:
```bash
pytest
pytest tests/test_cli.py  # Run specific test file
pytest -v                 # Verbose output
pytest --cov=claude_remote_client  # With coverage
```

## Usage
```bash
# Run with default config
claude-remote-client

# Run setup wizard
claude-remote-client --setup

# Use custom config file
claude-remote-client --config my.yaml

# Validate configuration only
claude-remote-client --validate
```