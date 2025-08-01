# Claude Code CLI Integration

This document describes the integration between the Claude Remote Client and the Claude Code CLI, enabling advanced features like JSON output, session management, and non-interactive execution.

## Overview

The Claude Remote Client has been enhanced to support Claude Code CLI specific features:

- **Multiple Output Formats**: Support for text, JSON, and stream-JSON output formats
- **Session Management**: Resume Claude Code sessions using `--resume` flag
- **Non-Interactive Execution**: Execute single commands using `-p/--print` flag
- **Model Selection**: Specify models using `--model` flag
- **Session Continuity**: Continue previous sessions using `--continue` flag

## Key Components

### 1. Enhanced Subprocess Handler

The `SubprocessClaudeHandler` now supports Claude Code CLI specific features:

```python
from claude_remote_client.claude_client.subprocess_handler import SubprocessClaudeHandler

# Create handler with JSON output
handler = SubprocessClaudeHandler(config)
handler.output_format = "json"
handler.model = "claude-3-opus"

# Start process with session resumption
await handler.start_process(session, resume_claude_session="previous-session-id")

# Execute non-interactive command
result = await handler.execute_command("Explain the code", timeout=30)
```

### 2. Session Manager Integration

The `SessionManager` provides high-level methods for Claude Code operations:

```python
from claude_remote_client.session_manager.session_manager import SessionManager

# Execute non-interactive command
result = await session_manager.execute_non_interactive(
    command="Analyze the project structure",
    project_path="/path/to/project",
    output_format="json"
)

# Continue a Claude session
session = await session_manager.continue_claude_session("session-id")

# Get Claude session mapping
mapping = session_manager.get_claude_session_mapping()
```

### 3. Enhanced Session Model

The `ClaudeSession` model now tracks Claude Code's internal session ID:

```python
from claude_remote_client.models import ClaudeSession

session = ClaudeSession(
    session_id="internal-id",
    project_path="/path/to/project",
    claude_session_id="claude-code-session-id"  # New field
)
```

## Usage Examples

### 1. Non-Interactive Execution with JSON Output

```python
# Execute a single command and get JSON response
result = await session_manager.execute_non_interactive(
    command="List all Python files and their purposes",
    project_path="/my/project",
    output_format="json",
    timeout=30
)

if result["success"]:
    data = result["data"]  # Parsed JSON response
    print(json.dumps(data, indent=2))
```

### 2. Resume a Previous Claude Session

```python
# Create a session that resumes a previous Claude Code session
session = ClaudeSession(
    session_id="new-session",
    project_path="/my/project",
    claude_session_id="claude-abc123"  # Previous Claude session ID
)

# The subprocess handler will use --resume flag
session = await session_manager.create_session(
    project_path="/my/project"
)
```

### 3. Continue the Most Recent Session

```python
# Continue the most recent Claude Code session
await session_manager.continue_claude_session("session-id")

# This uses the --continue flag internally
```

### 4. Stream JSON Output

```python
# Configure for streaming JSON output
handler.output_format = "stream-json"

# JSON responses will be parsed and stored in handler.json_responses
# Each line is a separate JSON object
```

## Configuration

### Claude Config

```yaml
claude:
  cli_path: "claude"  # Path to Claude Code CLI
  default_args:
    - "--dangerously-skip-permissions"
  timeout: 300  # Default timeout in seconds
```

### Setting Output Format

```python
# During handler creation
handler = SubprocessClaudeHandler(config)
handler.output_format = "json"  # or "text", "stream-json"

# For non-interactive execution
result = await session_manager.execute_non_interactive(
    command="...",
    project_path="...",
    output_format="json"
)
```

## Error Handling

The integration includes robust error handling:

```python
try:
    result = await handler.execute_command("command", timeout=10)
except ClaudeProcessError as e:
    if "timed out" in str(e):
        print("Command execution timed out")
    else:
        print(f"Error: {e}")
```

## Session ID Mapping

Track the relationship between internal sessions and Claude Code sessions:

```python
# Get all session mappings
mapping = session_manager.get_claude_session_mapping()
# Returns: {"internal-id-1": "claude-id-1", "internal-id-2": None, ...}

# Access Claude session ID from a session
claude_id = session.claude_session_id

# Get from handler
claude_id = handler.get_claude_session_id()
```

## Best Practices

1. **Use JSON Output for Programmatic Access**: When you need to parse Claude's responses programmatically, use JSON output format.

2. **Session Continuity**: Store Claude session IDs to resume conversations later using the `--resume` flag.

3. **Non-Interactive for One-Shot Commands**: Use `execute_non_interactive()` for single commands that don't require conversation context.

4. **Error Handling**: Always handle `ClaudeProcessError` exceptions, especially for timeout scenarios.

5. **Resource Cleanup**: The session manager handles cleanup automatically, but ensure you call `stop()` when done.

## Testing

Run the integration tests:

```bash
pytest tests/test_claude_code_integration.py -v
```

Run the example script:

```bash
python examples/claude_code_integration_example.py
```

## Limitations

1. The integration requires Claude Code CLI to be installed and accessible in the system PATH.
2. JSON parsing errors are handled gracefully but may result in text output instead.
3. Session IDs are only available when Claude Code CLI provides them in the output.

## Future Enhancements

- Support for additional Claude Code CLI flags
- Integration with Claude Code's file handling capabilities  
- Support for custom prompt templates
- Advanced session search and filtering based on Claude session IDs