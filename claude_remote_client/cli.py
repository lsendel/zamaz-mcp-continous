"""
Command-line interface for Claude Remote Client.

This module provides the main entry point for the Claude Remote Client application,
including setup wizard, configuration management, and bot startup.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .config import Config, load_config, create_default_config_file
from .exceptions import ConfigurationError


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration."""
    # Ensure log directory exists
    log_dir = os.path.expanduser("~/.claude-remote-client")
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(log_dir, "claude-remote-client.log")
            )
        ]
    )


def create_data_directory(data_dir: str) -> None:
    """Create the data directory if it doesn't exist."""
    Path(data_dir).mkdir(parents=True, exist_ok=True)


def setup_wizard() -> str:
    """
    Interactive setup wizard for first-time configuration.
    
    Returns:
        str: Path to the created configuration file.
    """
    print("🤖 Welcome to Claude Remote Client Setup!")
    print("=" * 50)
    print()
    
    # Determine config file location
    config_dir = os.path.expanduser("~/.claude-remote-client")
    config_file = os.path.join(config_dir, "config.yaml")
    
    # Create data directory
    create_data_directory(config_dir)
    
    print(f"Configuration will be saved to: {config_file}")
    print()
    
    # Collect Slack configuration
    print("📱 Slack Configuration")
    print("-" * 20)
    
    slack_bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
    while not slack_bot_token.startswith("xoxb-"):
        print("❌ Invalid bot token. Bot tokens should start with 'xoxb-'")
        slack_bot_token = input("Enter your Slack Bot Token (xoxb-...): ").strip()
    
    slack_channel_id = input("Enter your Slack Channel ID (C...): ").strip()
    while not slack_channel_id.startswith("C"):
        print("❌ Invalid channel ID. Channel IDs should start with 'C'")
        slack_channel_id = input("Enter your Slack Channel ID (C...): ").strip()
    
    signing_secret = input("Enter your Slack Signing Secret (optional): ").strip()
    
    print()
    
    # Collect Claude configuration
    print("🧠 Claude Configuration")
    print("-" * 20)
    
    claude_path = input("Enter Claude CLI path (default: claude): ").strip()
    if not claude_path:
        claude_path = "claude"
    
    print()
    
    # Collect project configuration
    print("📁 Project Configuration")
    print("-" * 25)
    
    projects = []
    while True:
        project_name = input("Enter project name (or press Enter to finish): ").strip()
        if not project_name:
            break
        
        project_path = input(f"Enter path for '{project_name}': ").strip()
        expanded_path = os.path.expanduser(project_path)
        
        if not os.path.exists(expanded_path):
            print(f"⚠️  Warning: Path '{expanded_path}' does not exist")
            continue_anyway = input("Continue anyway? (y/N): ").strip().lower()
            if continue_anyway != 'y':
                continue
        
        project_desc = input(f"Enter description for '{project_name}' (optional): ").strip()
        
        projects.append({
            'name': project_name,
            'path': project_path,
            'description': project_desc
        })
        
        print(f"✅ Added project '{project_name}'")
        print()
    
    if not projects:
        print("⚠️  No projects configured. You can add them later in the config file.")
    
    print()
    
    # Create configuration file
    config_data = {
        'slack': {
            'bot_token': slack_bot_token,
            'channel_id': slack_channel_id,
        },
        'claude': {
            'cli_path': claude_path,
            'default_args': ['--dangerously-skip-permissions'],
            'timeout': 300
        },
        'projects': projects,
        'log_level': 'INFO',
        'data_dir': config_dir,
        'max_sessions': 10,
        'task_queue_size': 100
    }
    
    if signing_secret:
        config_data['slack']['signing_secret'] = signing_secret
    
    # Write configuration file
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    print(f"✅ Configuration saved to {config_file}")
    print()
    print("🎉 Setup complete! You can now start the Claude Remote Client.")
    print(f"   Run: claude-remote-client --config {config_file}")
    print()
    
    return config_file


async def start_bot(config: Config) -> None:
    """
    Start the Claude Remote Client bot.
    
    Args:
        config: Application configuration.
    """
    # Import here to avoid circular imports
    from .slack_client.client import SlackBotClient
    from .session_manager.session_manager import SessionManager
    from .task_queue.queue_manager import QueueManager
    
    logger = logging.getLogger(__name__)
    
    try:
        # Validate Claude CLI
        logger.info("Validating Claude CLI...")
        config.validate_claude_cli()
        logger.info("✅ Claude CLI validation successful")
        
        # Initialize components
        logger.info("Initializing components...")
        
        session_manager = SessionManager(config)
        queue_manager = QueueManager(config)
        slack_client = SlackBotClient(config, session_manager, queue_manager)
        
        # Start the bot
        logger.info("🚀 Starting Claude Remote Client...")
        await slack_client.start()
        
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Shutting down Claude Remote Client...")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Claude Remote Client - Remote Claude AI interaction through Slack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-remote-client                    # Run with default config
  claude-remote-client --setup           # Run setup wizard
  claude-remote-client --config my.yaml  # Use custom config file
  claude-remote-client --validate        # Validate configuration only
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Run interactive setup wizard"
    )
    
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Claude Remote Client 0.1.0"
    )
    
    args = parser.parse_args()
    
    # Run setup wizard if requested
    if args.setup:
        config_file = setup_wizard()
        if not args.validate:
            print("To start the bot, run:")
            print(f"  claude-remote-client --config {config_file}")
        return
    
    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config(args.config)
        logger.info(f"✅ Configuration loaded successfully")
        
        # Create data directory
        create_data_directory(config.data_dir)
        
        # If validate only, exit after validation
        if args.validate:
            config.validate_claude_cli()
            print("✅ Configuration is valid!")
            return
        
        # Start the bot
        asyncio.run(start_bot(config))
        
    except ConfigurationError as e:
        logger.error(f"❌ Configuration error: {e}")
        print()
        print("💡 Tip: Run 'claude-remote-client --setup' to create a new configuration.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()