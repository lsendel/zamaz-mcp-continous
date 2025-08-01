#!/usr/bin/env python3
"""Fix unused imports in Python files."""

import ast
import os
import sys
from pathlib import Path


def find_unused_imports(file_path):
    """Find unused imports in a Python file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Collect all imports
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = f"{node.module}.{alias.name}" if node.module else alias.name
        
        # Find all name usages
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # Find unused imports
        unused = []
        for name, full_name in imports.items():
            if name not in used_names:
                # Special cases - keep these even if apparently unused
                keep_patterns = [
                    '__future__',
                    'typing',  # Type hints might be in strings
                    'annotations',
                    '__all__',
                ]
                if not any(pattern in full_name for pattern in keep_patterns):
                    unused.append((name, full_name))
        
        return unused
    
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


def main():
    """Main function to check all Python files."""
    # Focus on main source files
    source_dirs = [
        "claude_remote_client",
    ]
    
    total_unused = 0
    files_with_unused = 0
    
    for source_dir in source_dirs:
        for py_file in Path(source_dir).rglob("*.py"):
            unused = find_unused_imports(py_file)
            
            if unused:
                files_with_unused += 1
                total_unused += len(unused)
                print(f"\n{py_file}:")
                for name, full_name in unused:
                    print(f"  - {name} (from {full_name})")
    
    print(f"\n\nSummary:")
    print(f"Files with unused imports: {files_with_unused}")
    print(f"Total unused imports: {total_unused}")


if __name__ == "__main__":
    main()