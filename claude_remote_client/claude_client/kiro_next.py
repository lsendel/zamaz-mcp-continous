#!/usr/bin/env python3
"""
Kiro Next - Claude Code command to process specs and complete pending tasks.

This command goes through all specs in the .kiro/specs/claude-remote-client directory
and continues with all pending tasks, marking them as complete.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import sys
sys.path.append('/Users/lsendel/IdeaProjects/zamaz-mcp-continous')


from claude_remote_client.config import Config, ClaudeConfig
from claude_remote_client.models import ClaudeSession
from claude_remote_client.exceptions import SessionError, ClaudeProcessError
from claude_remote_client.session_manager.session_manager import SessionManager


class KiroNext:
    """Process Kiro specs and complete pending tasks using Claude Code."""
    
    def __init__(self, base_path: str = "/Users/lsendel/IdeaProjects/zamaz-mcp-continous"):
        self.base_path = Path(base_path)
        self.specs_path = self.base_path / ".kiro" / "specs" / "claude-remote-client"
        self.session_manager = None
        self.processed_specs = []
        self.pending_tasks = []
        
    async def initialize(self):
        """Initialize the session manager and Claude configuration."""
        config = Config(
            claude=ClaudeConfig(
                cli_path="claude",
                default_args=["--dangerously-skip-permissions"],
                timeout=300
            ),
            data_dir=str(self.base_path / ".claude-remote-client")
        )
        
        self.session_manager = SessionManager(config)
        await self.session_manager.start()
        
    async def find_spec_files(self) -> List[Path]:
        """Find all spec files in the kiro specs directory."""
        spec_files = []
        
        if not self.specs_path.exists():
            print(f"Specs directory not found: {self.specs_path}")
            return spec_files
            
        # Find all .md, .json, and .yaml files
        for ext in ['*.md', '*.json', '*.yaml', '*.yml']:
            spec_files.extend(self.specs_path.rglob(ext))
            
        return sorted(spec_files)
    
    async def parse_spec_file(self, spec_file: Path) -> Dict[str, Any]:
        """Parse a spec file and extract tasks."""
        content = spec_file.read_text()
        
        spec_data = {
            'file': str(spec_file),
            'name': spec_file.stem,
            'tasks': [],
            'completed': False
        }
        
        # Simple task extraction from markdown files
        if spec_file.suffix == '.md':
            lines = content.split('\n')
            current_task = None
            
            for line in lines:
                # Look for task indicators
                if line.strip().startswith('- [ ]'):
                    task_text = line.strip()[5:].strip()
                    current_task = {
                        'description': task_text,
                        'status': 'pending',
                        'line': line
                    }
                    spec_data['tasks'].append(current_task)
                elif line.strip().startswith('- [x]'):
                    task_text = line.strip()[5:].strip()
                    current_task = {
                        'description': task_text,
                        'status': 'completed',
                        'line': line
                    }
                    spec_data['tasks'].append(current_task)
                elif line.strip().startswith('TODO:') or line.strip().startswith('TASK:'):
                    task_text = line.strip().split(':', 1)[1].strip()
                    current_task = {
                        'description': task_text,
                        'status': 'pending',
                        'line': line
                    }
                    spec_data['tasks'].append(current_task)
        
        # For JSON files
        elif spec_file.suffix == '.json':
            try:
                data = json.loads(content)
                if 'tasks' in data:
                    spec_data['tasks'] = data['tasks']
                elif 'todos' in data:
                    spec_data['tasks'] = data['todos']
            except json.JSONDecodeError:
                print(f"Error parsing JSON file: {spec_file}")
        
        return spec_data
    
    async def process_spec(self, spec: Dict[str, Any]) -> bool:
        """Process a single spec using Claude Code."""
        print(f"\n{'='*60}")
        print(f"Processing spec: {spec['name']}")
        print(f"File: {spec['file']}")
        print(f"{'='*60}")
        
        pending_tasks = [t for t in spec['tasks'] if t['status'] == 'pending']
        
        if not pending_tasks:
            print("No pending tasks found in this spec.")
            return True
            
        print(f"Found {len(pending_tasks)} pending tasks:")
        for i, task in enumerate(pending_tasks, 1):
            print(f"  {i}. {task['description']}")
        
        # Create or get session for this spec
        try:
            session = await self.session_manager.create_session(str(self.base_path))
            
            # Build command for Claude
            command = self._build_claude_command(spec, pending_tasks)
            
            print(f"\nExecuting command via Claude Code...")
            result = await self.session_manager.execute_non_interactive(
                command=command,
                project_path=str(self.base_path),
                output_format="json",
                timeout=300
            )
            
            if result['success']:
                print("✅ Tasks processed successfully!")
                await self._update_spec_file(spec, pending_tasks, 'completed')
                return True
            else:
                print(f"❌ Error processing tasks: {result.get('error', 'Unknown error')}")
                return False
                
        except (SessionError, ClaudeProcessError) as e:
            print(f"❌ Session error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    def _build_claude_command(self, spec: Dict[str, Any], tasks: List[Dict[str, Any]]) -> str:
        """Build a command for Claude to process the tasks."""
        task_list = "\n".join([f"- {task['description']}" for task in tasks])
        
        command = f"""
Process the following tasks from the spec file '{spec['name']}':

{task_list}

For each task:
1. Analyze what needs to be done
2. Implement the necessary changes
3. Verify the implementation
4. Mark the task as complete

Project context: This is part of the claude-remote-client in {self.base_path}

Please complete all tasks systematically and provide a summary of what was done.
"""
        return command.strip()
    
    async def _update_spec_file(self, spec: Dict[str, Any], completed_tasks: List[Dict[str, Any]], new_status: str):
        """Update the spec file to mark tasks as completed."""
        spec_path = Path(spec['file'])
        
        if not spec_path.exists():
            return
            
        content = spec_path.read_text()
        
        # Update markdown checkboxes
        if spec_path.suffix == '.md':
            for task in completed_tasks:
                if 'line' in task:
                    old_line = task['line']
                    new_line = old_line.replace('- [ ]', '- [x]')
                    content = content.replace(old_line, new_line)
            
            # Add completion timestamp
            if '\n## Completion Status\n' not in content:
                content += f"\n\n## Completion Status\n\nLast processed: {datetime.now().isoformat()}\n"
            
            spec_path.write_text(content)
            print(f"✅ Updated spec file: {spec_path}")
    
    async def generate_report(self):
        """Generate a summary report of all processed specs."""
        report_path = self.base_path / ".kiro" / "reports" / f"kiro_next_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = f"""# Kiro Next Processing Report

Generated: {datetime.now().isoformat()}

## Summary

- Total specs found: {len(self.processed_specs)}
- Successfully processed: {sum(1 for s in self.processed_specs if s.get('success', False))}
- Failed: {sum(1 for s in self.processed_specs if not s.get('success', False))}

## Processed Specs

"""
        
        for spec in self.processed_specs:
            status = "✅" if spec.get('success', False) else "❌"
            report += f"\n### {status} {spec['name']}\n"
            report += f"- File: `{spec['file']}`\n"
            report += f"- Tasks: {len(spec.get('tasks', []))}\n"
            report += f"- Pending before: {len([t for t in spec.get('tasks', []) if t['status'] == 'pending'])}\n"
            
            if spec.get('error'):
                report += f"- Error: {spec['error']}\n"
        
        report_path.write_text(report)
        print(f"\n📄 Report saved to: {report_path}")
        return report_path
    
    async def run(self):
        """Main execution method."""
        print("🚀 Starting Kiro Next processor...")
        print(f"Base path: {self.base_path}")
        print(f"Specs path: {self.specs_path}")
        
        try:
            # Initialize
            await self.initialize()
            
            # Find all spec files
            spec_files = await self.find_spec_files()
            print(f"\nFound {len(spec_files)} spec files")
            
            if not spec_files:
                print("No spec files found. Exiting.")
                return
            
            # Process each spec
            for spec_file in spec_files:
                spec_data = await self.parse_spec_file(spec_file)
                
                # Process the spec
                success = await self.process_spec(spec_data)
                
                # Record result
                spec_data['success'] = success
                spec_data['processed_at'] = datetime.now().isoformat()
                self.processed_specs.append(spec_data)
                
                # Brief pause between specs
                await asyncio.sleep(2)
            
            # Generate report
            await self.generate_report()
            
            print("\n✅ Kiro Next processing complete!")
            
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            raise
        finally:
            if self.session_manager:
                await self.session_manager.stop()


async def main():
    """Main entry point for the kiro_next command."""
    kiro = KiroNext()
    await kiro.run()


if __name__ == "__main__":
    # Run the command
    asyncio.run(main())