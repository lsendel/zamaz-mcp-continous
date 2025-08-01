#!/usr/bin/env python3
"""
Kiro Next Instructions - Generate instructions for completing pending tasks.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from claude_remote_client.claude_client.kiro_next import KiroNext


class InstructionGenerator(KiroNext):
    """Generate instructions for completing pending tasks."""
    
    async def run(self):
        """Generate instructions instead of executing tasks."""
        print("📋 Kiro Next - Task Analysis and Instructions")
        print("=" * 60)
        print(f"Base path: {self.base_path}")
        print(f"Specs path: {self.specs_path}\n")
        
        # Find all spec files
        spec_files = await self.find_spec_files()
        if not spec_files:
            print("No spec files found.")
            return
        
        all_pending_tasks = []
        
        # Analyze all specs
        for spec_file in spec_files:
            spec = await self.parse_spec_file(spec_file)
            pending = [t for t in spec['tasks'] if t['status'] == 'pending']
            
            if pending:
                all_pending_tasks.append({
                    'spec': spec,
                    'tasks': pending
                })
        
        if not all_pending_tasks:
            print("✅ No pending tasks found! All tasks are complete.")
            return
        
        # Generate instructions
        print("📝 INSTRUCTIONS FOR COMPLETING PENDING TASKS")
        print("=" * 60)
        
        print("\n1. To execute all pending tasks automatically, run:")
        print("   python /Users/lsendel/IdeaProjects/zamaz-mcp-continous/kiro_next")
        
        print("\n2. To complete tasks manually, here are the pending items:\n")
        
        task_number = 1
        for spec_group in all_pending_tasks:
            spec = spec_group['spec']
            tasks = spec_group['tasks']
            
            print(f"\n📄 {spec['name']} ({len(tasks)} pending tasks):")
            print(f"   File: {spec['file']}")
            print("   Tasks:")
            
            for task in tasks:
                print(f"   {task_number}. [ ] {task['description']}")
                task_number += 1
        
        print("\n3. Example Claude Code command to process specific tasks:")
        print("   claude --dangerously-skip-permissions")
        print('   > "Complete the following tasks from the spec files:"')
        print("   > [paste the task list above]")
        
        print("\n4. To mark tasks as complete manually:")
        print("   - Edit the spec files and change '- [ ]' to '- [x]'")
        print(f"   - Files are in: {self.specs_path}")
        
        # Generate a command file
        command_file = self.base_path / "kiro_pending_tasks.md"
        with open(command_file, 'w') as f:
            f.write(f"# Pending Tasks - Generated {datetime.now().isoformat()}\n\n")
            f.write("## Instructions\n\n")
            f.write("Copy and paste the following into Claude Code to complete all pending tasks:\n\n")
            f.write("```\n")
            f.write("Please complete the following pending tasks from the kiro specs:\n\n")
            
            for spec_group in all_pending_tasks:
                spec = spec_group['spec']
                tasks = spec_group['tasks']
                f.write(f"\nFrom {spec['name']}:\n")
                for task in tasks:
                    f.write(f"- {task['description']}\n")
            
            f.write("\nFor each task:\n")
            f.write("1. Analyze what needs to be done\n")
            f.write("2. Implement the necessary changes\n")
            f.write("3. Verify the implementation\n")
            f.write("4. Update the spec file to mark the task as complete\n")
            f.write("```\n")
        
        print(f"\n📄 Task list saved to: {command_file}")
        print("\n✨ Ready to complete tasks!")


async def main():
    """Generate instructions for completing tasks."""
    generator = InstructionGenerator()
    await generator.run()


if __name__ == "__main__":
    asyncio.run(main())