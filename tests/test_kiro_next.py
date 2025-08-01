"""
Test version of Kiro Next - demonstrates functionality without executing real Claude commands.
"""

import asyncio
from pathlib import Path
from claude_remote_client.claude_client.kiro_next import KiroNext


class SimulatedKiroNext(KiroNext):
    """Test version that simulates task processing."""
    
    async def process_spec(self, spec):
        """Override to simulate processing without real Claude execution."""
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
        
        print("\n[SIMULATION MODE] Would execute the following command:")
        command = self._build_claude_command(spec, pending_tasks)
        print("-" * 40)
        print(command)
        print("-" * 40)
        
        # Simulate success
        print("\n✅ [SIMULATED] Tasks processed successfully!")
        return True


async def main():
    """Run the test version."""
    print("🧪 Running Kiro Next in TEST MODE (no actual Claude execution)")
    
    kiro = SimulatedKiroNext()
    
    # Find and parse specs without full initialization
    spec_files = await kiro.find_spec_files()
    print(f"\nFound {len(spec_files)} spec files:")
    for f in spec_files:
        print(f"  - {f.name}")
    
    # Process first spec as demonstration
    if spec_files:
        print("\n📋 Processing first spec as demonstration...")
        first_spec = await kiro.parse_spec_file(spec_files[0])
        await kiro.process_spec(first_spec)
        
        # Show task summary
        print("\n📊 Task Summary for all specs:")
        total_tasks = 0
        total_pending = 0
        
        for spec_file in spec_files:
            spec = await kiro.parse_spec_file(spec_file)
            tasks = len(spec['tasks'])
            pending = len([t for t in spec['tasks'] if t['status'] == 'pending'])
            total_tasks += tasks
            total_pending += pending
            
            print(f"\n  {spec['name']}:")
            print(f"    Total tasks: {tasks}")
            print(f"    Pending: {pending}")
            print(f"    Completed: {tasks - pending}")
    
        print(f"\n📈 Overall Summary:")
        print(f"  Total tasks across all specs: {total_tasks}")
        print(f"  Total pending: {total_pending}")
        print(f"  Total completed: {total_tasks - total_pending}")
        print(f"  Completion rate: {((total_tasks - total_pending) / total_tasks * 100):.1f}%")


if __name__ == "__main__":
    asyncio.run(main())