#!/usr/bin/env python3
"""
Example demonstrating Claude Code CLI integration features.

This example shows how to use the enhanced subprocess handler with
Claude Code CLI specific features like JSON output, session resumption,
and non-interactive execution.
"""

import asyncio
import json
from pathlib import Path

from claude_remote_client.config import Config, ClaudeConfig
from claude_remote_client.session_manager.session_manager import SessionManager
from claude_remote_client.models import ClaudeSession


async def demonstrate_claude_code_features():
    """Demonstrate various Claude Code CLI integration features."""
    
    # Configure Claude Code CLI
    config = Config(
        claude=ClaudeConfig(
            cli_path="claude",  # Assumes 'claude' is in PATH
            default_args=["--dangerously-skip-permissions"],
            timeout=60
        ),
        data_dir="~/.claude-remote-client"
    )
    
    # Create session manager
    session_manager = SessionManager(config)
    await session_manager.start()
    
    try:
        # 1. Create a session for a project
        print("=== Creating a new Claude session ===")
        project_path = str(Path.cwd())  # Use current directory as example
        session = await session_manager.create_session(project_path)
        print(f"Created session: {session.session_id}")
        print(f"Project: {session.project_path}")
        
        # Get the subprocess handler to demonstrate features
        handler = await session_manager.get_session_handler(session.session_id)
        
        # 2. Execute a non-interactive command with JSON output
        print("\n=== Non-interactive execution with JSON output ===")
        result = await session_manager.execute_non_interactive(
            command="List the main files in this directory",
            project_path=project_path,
            output_format="json",
            timeout=30
        )
        
        if result["success"]:
            print("Command executed successfully!")
            if isinstance(result["data"], dict):
                print("Response:", json.dumps(result["data"], indent=2))
            else:
                print("Response:", result["data"])
        else:
            print("Command failed:", result["error"])
        
        # 3. Send interactive messages
        print("\n=== Interactive session ===")
        if handler:
            # Send a message to Claude
            await handler.send_message("Hello! Can you see the project structure?")
            
            # Wait a bit for response
            await asyncio.sleep(2)
            
            # Get recent output
            recent_output = handler.get_recent_output(lines=20)
            print("Claude's response:")
            print(recent_output)
            
            # Check if we got a Claude session ID
            claude_session_id = handler.get_claude_session_id()
            if claude_session_id:
                print(f"\nClaude session ID: {claude_session_id}")
                session.claude_session_id = claude_session_id
        
        # 4. Demonstrate session continuation
        print("\n=== Session continuation ===")
        if session.claude_session_id:
            print(f"Continuing Claude session: {session.claude_session_id}")
            await session_manager.continue_claude_session(session.session_id)
            print("Session continued successfully!")
        
        # 5. List all sessions with Claude session mapping
        print("\n=== Session mapping ===")
        sessions = await session_manager.list_sessions()
        claude_mapping = session_manager.get_claude_session_mapping()
        
        for session_info in sessions:
            sid = session_info["session_id"]
            claude_id = claude_mapping.get(sid, "None")
            print(f"Session {sid} -> Claude session: {claude_id}")
        
        # 6. Get process information
        print("\n=== Process information ===")
        if handler:
            process_info = handler.get_process_info()
            print(f"Process PID: {process_info['pid']}")
            print(f"Output format: {process_info['output_format']}")
            print(f"Claude session ID: {process_info['claude_session_id']}")
            print(f"Is running: {process_info['is_running']}")
        
        # 7. Demonstrate JSON output format
        print("\n=== JSON output format ===")
        if handler:
            handler.output_format = "json"
            print("Switched to JSON output format")
            
            # Send another message
            await handler.send_message("Return a JSON object with project summary")
            await asyncio.sleep(2)
            
            # Check if we have JSON response
            if hasattr(handler, 'json_response'):
                print("JSON Response received:")
                print(json.dumps(handler.json_response, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        await session_manager.stop()
        print("Session manager stopped")


async def demonstrate_error_handling():
    """Demonstrate error handling in Claude Code integration."""
    print("\n=== Error Handling Examples ===")
    
    config = Config(
        claude=ClaudeConfig(
            cli_path="claude",
            timeout=5  # Short timeout for demonstration
        )
    )
    
    session_manager = SessionManager(config)
    await session_manager.start()
    
    try:
        # 1. Non-existent project path
        print("\n1. Attempting to create session with invalid path:")
        try:
            await session_manager.create_session("/non/existent/path")
        except Exception as e:
            print(f"   Error caught: {e}")
        
        # 2. Command timeout
        print("\n2. Demonstrating command timeout:")
        try:
            result = await session_manager.execute_non_interactive(
                command="This might timeout",
                project_path=".",
                timeout=0.1  # Very short timeout
            )
        except Exception as e:
            print(f"   Error caught: {e}")
        
        # 3. Invalid session continuation
        print("\n3. Attempting to continue non-existent session:")
        try:
            await session_manager.continue_claude_session("non-existent-session")
        except Exception as e:
            print(f"   Error caught: {e}")
    
    finally:
        await session_manager.stop()


def main():
    """Main entry point."""
    print("Claude Code CLI Integration Example")
    print("===================================\n")
    
    # Run the demonstrations
    asyncio.run(demonstrate_claude_code_features())
    asyncio.run(demonstrate_error_handling())
    
    print("\nExample completed!")


if __name__ == "__main__":
    main()