"""
Claude client module for the Claude Remote Client.

This module handles all Claude CLI integration including subprocess management,
message streaming, and process lifecycle.
"""

from .subprocess_handler import SubprocessClaudeHandler
from .message_streamer import MessageStreamer

__all__ = [
    "SubprocessClaudeHandler",
    "MessageStreamer"
]