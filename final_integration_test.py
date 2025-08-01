#!/usr/bin/env python3
"""Final integration test for Slack-Claude system."""

import os
import asyncio
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient

load_dotenv()

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
CLAUDE_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
PROJECT_PATH = os.getenv("PROJECT_PATH", ".")


async def run_integration_test():
    """Run complete integration test."""
    slack = AsyncWebClient(token=SLACK_TOKEN)
    
    print("🚀 FINAL INTEGRATION TEST")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Channel: {SLACK_CHANNEL}")
    print(f"Claude: {CLAUDE_PATH}")
    print("=" * 60)
    
    # Test message
    test_id = datetime.now().strftime('%H%M%S')
    
    # 1. Send test start message
    await slack.chat_postMessage(
        channel=SLACK_CHANNEL,
        text=f"🧪 **Integration Test {test_id} Started**\nTesting bidirectional Slack-Claude communication..."
    )
    
    # 2. Test queries
    queries = [
        ("What programming language is this project written in?", "language_check"),
        ("List the main directories in this project", "directory_list"),
        ("What is the purpose of the session_manager module?", "module_purpose")
    ]
    
    results = []
    
    for query, test_name in queries:
        print(f"\n📤 Test: {test_name}")
        print(f"   Query: {query}")
        
        # Send query to Slack
        await slack.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"**Test {test_name}:** {query}"
        )
        
        # Process with Claude
        try:
            result = subprocess.run(
                [CLAUDE_PATH, '--print', query],
                cwd=PROJECT_PATH,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"   ✅ Claude responded ({len(response)} chars)")
                
                # Send response to Slack
                await slack.chat_postMessage(
                    channel=SLACK_CHANNEL,
                    text=f"**Claude says:**\n{response[:500]}..."  # Truncate long responses
                )
                
                results.append((test_name, True, None))
            else:
                error = result.stderr.strip()
                print(f"   ❌ Claude error: {error}")
                results.append((test_name, False, error))
                
        except subprocess.TimeoutExpired:
            print(f"   ⚠️  Timeout")
            results.append((test_name, False, "Timeout"))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((test_name, False, str(e)))
        
        await asyncio.sleep(1)  # Brief pause
    
    # 3. Send summary
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    summary = f"""
🏁 **Integration Test {test_id} Complete**

Results: {passed}/{total} tests passed

"""
    
    for test_name, success, error in results:
        if success:
            summary += f"✅ {test_name}\n"
        else:
            summary += f"❌ {test_name}: {error}\n"
    
    summary += f"\n✨ Overall Status: {'PASSED' if passed == total else 'FAILED'}"
    
    await slack.chat_postMessage(
        channel=SLACK_CHANNEL,
        text=summary
    )
    
    # Print final result
    print("\n" + "=" * 60)
    print(f"✅ Integration test complete: {passed}/{total} passed")
    print(f"Check #{SLACK_CHANNEL} in Slack for details")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_integration_test())
    exit(0 if success else 1)