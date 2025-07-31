"""
Project manager for handling project discovery and validation.

This module manages project configuration, discovery, validation,
and provides project-related utilities for session management.
"""

import os
import logging
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

from ..models import ClaudeSession
from ..config import Config, ProjectConfig
from ..exceptions import SessionError, ConfigurationError
from ..utils import setup_logging, validate_project_path, ensure_directory_exists


class ProjectManager:
    """
    Manager for project discovery, validation, and configuration.
    
    Handles project path validation, discovery of available projects,
    and project-specific configuration management.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the project manager.
        
        Args:
            config: Application configuration containing project settings
        """
        self.config = config
        self.logger = setup_logging()
        
        # Project cache
        self._project_cache: Dict[str, ProjectConfig] = {}
        self._cache_timestamp = 0
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # Project metadata file
        self.projects_metadata_file = Path(config.data_dir) / "projects_metadata.json"
        
        # Initialize project cache
        self._refresh_project_cache()
    
    def get_available_projects(self, refresh_cache: bool = False) -> List[ProjectConfig]:
        """
        Get list of available projects.
        
        Args:
            refresh_cache: Whether to refresh the project cache
        
        Returns:
            List[ProjectConfig]: List of available projects
        """
        if refresh_cache or self._should_refresh_cache():
            self._refresh_project_cache()
        
        return list(self._project_cache.values())
    
    def get_project_by_name(self, name: str) -> Optional[ProjectConfig]:
        """
        Get project configuration by name.
        
        Args:
            name: Project name to search for
        
        Returns:
            Optional[ProjectConfig]: Project configuration or None if not found
        """
        if self._should_refresh_cache():
            self._refresh_project_cache()
        
        return self._project_cache.get(name)
    
    def get_project_by_path(self, path: str) -> Optional[ProjectConfig]:
        """
        Get project configuration by path.
        
        Args:
            path: Project path to search for
        
        Returns:
            Optional[ProjectConfig]: Project configuration or None if not found
        """
        if self._should_refresh_cache():
            self._refresh_project_cache()
        
        normalized_path = str(Path(path).resolve())
        
        for project in self._project_cache.values():
            if str(Path(project.path).resolve()) == normalized_path:
                return project
        
        return None
    
    def validate_project_path(self, path: str) -> bool:
        """
        Validate that a project path is valid and accessible.
        
        Args:
            path: Project path to validate
        
        Returns:
            bool: True if path is valid, False otherwise
        """
        return validate_project_path(path)
    
    def discover_projects_in_directory(self, base_dir: str, max_depth: int = 2) -> List[ProjectConfig]:
        """
        Discover projects in a directory by looking for common project indicators.
        
        Args:
            base_dir: Base directory to search in
            max_depth: Maximum depth to search
        
        Returns:
            List[ProjectConfig]: List of discovered projects
        """
        discovered_projects = []
        
        if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
            self.logger.warning(f"Base directory does not exist: {base_dir}")
            return discovered_projects
        
        try:
            base_path = Path(base_dir).resolve()
            
            for root, dirs, files in os.walk(base_path):
                current_depth = len(Path(root).relative_to(base_path).parts)
                
                # Limit search depth
                if current_depth > max_depth:
                    dirs.clear()  # Don't recurse deeper
                    continue
                
                # Check for project indicators
                if self._is_project_directory(root, files):
                    project_name = Path(root).name
                    project_path = str(Path(root).resolve())
                    
                    # Skip if already in configured projects
                    if not self.get_project_by_path(project_path):
                        project = ProjectConfig(
                            name=project_name,
                            path=project_path,
                            description=f"Auto-discovered project in {project_path}"
                        )
                        discovered_projects.append(project)
                        
                        self.logger.info(f"Discovered project: {project_name} at {project_path}")
        
        except Exception as e:
            self.logger.error(f"Error discovering projects in {base_dir}: {e}")
        
        return discovered_projects
    
    def _is_project_directory(self, directory: str, files: List[str]) -> bool:
        """
        Check if a directory appears to be a project directory.
        
        Args:
            directory: Directory path to check
            files: List of files in the directory
        
        Returns:
            bool: True if directory appears to be a project
        """
        # Common project indicators
        project_indicators = [
            # Python projects
            'setup.py', 'pyproject.toml', 'requirements.txt', 'Pipfile', 'poetry.lock',
            # Node.js projects
            'package.json', 'yarn.lock', 'package-lock.json',
            # Java projects
            'pom.xml', 'build.gradle', 'build.gradle.kts',
            # Rust projects
            'Cargo.toml',
            # Go projects
            'go.mod', 'go.sum',
            # Ruby projects
            'Gemfile', 'Rakefile',
            # PHP projects
            'composer.json',
            # C/C++ projects
            'Makefile', 'CMakeLists.txt',
            # General
            'README.md', 'README.rst', 'README.txt',
            # Version control
            '.git',
        ]
        
        # Check for files
        for indicator in project_indicators:
            if indicator in files:
                return True
        
        # Check for directories (like .git)
        for indicator in project_indicators:
            if os.path.isdir(os.path.join(directory, indicator)):
                return True
        
        return False
    
    def add_project(self, name: str, path: str, description: str = "") -> ProjectConfig:
        """
        Add a new project to the configuration.
        
        Args:
            name: Project name
            path: Project path
            description: Optional project description
        
        Returns:
            ProjectConfig: Created project configuration
        
        Raises:
            SessionError: If project cannot be added
        """
        if not self.validate_project_path(path):
            raise SessionError(f"Invalid project path: {path}")
        
        if self.get_project_by_name(name):
            raise SessionError(f"Project with name '{name}' already exists")
        
        if self.get_project_by_path(path):
            raise SessionError(f"Project with path '{path}' already exists")
        
        try:
            # Create project configuration
            project = ProjectConfig(
                name=name,
                path=str(Path(path).resolve()),
                description=description or f"Project at {path}"
            )
            
            # Add to cache
            self._project_cache[name] = project
            
            # Save to metadata
            self._save_project_metadata()
            
            self.logger.info(f"Added project: {name} at {path}")
            
            return project
        
        except Exception as e:
            raise SessionError(f"Failed to add project: {str(e)}")
    
    def remove_project(self, name: str) -> bool:
        """
        Remove a project from the configuration.
        
        Args:
            name: Name of project to remove
        
        Returns:
            bool: True if project was removed, False if not found
        """
        if name not in self._project_cache:
            return False
        
        try:
            del self._project_cache[name]
            self._save_project_metadata()
            
            self.logger.info(f"Removed project: {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error removing project {name}: {e}")
            return False
    
    def update_project(self, name: str, path: Optional[str] = None, 
                      description: Optional[str] = None) -> Optional[ProjectConfig]:
        """
        Update an existing project configuration.
        
        Args:
            name: Project name to update
            path: New project path (optional)
            description: New project description (optional)
        
        Returns:
            Optional[ProjectConfig]: Updated project or None if not found
        
        Raises:
            SessionError: If update fails
        """
        if name not in self._project_cache:
            return None
        
        try:
            project = self._project_cache[name]
            
            if path is not None:
                if not self.validate_project_path(path):
                    raise SessionError(f"Invalid project path: {path}")
                project.path = str(Path(path).resolve())
            
            if description is not None:
                project.description = description
            
            # Save changes
            self._save_project_metadata()
            
            self.logger.info(f"Updated project: {name}")
            
            return project
        
        except Exception as e:
            raise SessionError(f"Failed to update project: {str(e)}")
    
    def get_project_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a project.
        
        Args:
            name: Project name
        
        Returns:
            Optional[Dict[str, Any]]: Project information or None if not found
        """
        project = self.get_project_by_name(name)
        if not project:
            return None
        
        try:
            project_path = Path(project.path)
            
            # Basic project info
            info = {
                "name": project.name,
                "path": project.path,
                "description": project.description,
                "exists": project_path.exists(),
                "is_directory": project_path.is_dir() if project_path.exists() else False,
                "absolute_path": str(project_path.resolve()) if project_path.exists() else None,
            }
            
            if project_path.exists():
                # File system info
                stat = project_path.stat()
                info.update({
                    "size_bytes": sum(f.stat().st_size for f in project_path.rglob('*') if f.is_file()),
                    "modified_time": stat.st_mtime,
                    "created_time": stat.st_ctime,
                })
                
                # Project type detection
                info["project_type"] = self._detect_project_type(project.path)
                
                # File counts
                info["file_counts"] = self._get_file_counts(project.path)
                
                # Git information
                git_info = self._get_git_info(project.path)
                if git_info:
                    info["git"] = git_info
            
            return info
        
        except Exception as e:
            self.logger.error(f"Error getting project info for {name}: {e}")
            return None
    
    def _detect_project_type(self, path: str) -> List[str]:
        """
        Detect the type(s) of a project based on files present.
        
        Args:
            path: Project path
        
        Returns:
            List[str]: List of detected project types
        """
        project_types = []
        project_path = Path(path)
        
        # Check for various project types
        type_indicators = {
            "python": ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile"],
            "nodejs": ["package.json", "yarn.lock", "package-lock.json"],
            "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
            "rust": ["Cargo.toml"],
            "go": ["go.mod", "go.sum"],
            "ruby": ["Gemfile", "Rakefile"],
            "php": ["composer.json"],
            "c_cpp": ["Makefile", "CMakeLists.txt"],
            "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        }
        
        for project_type, indicators in type_indicators.items():
            for indicator in indicators:
                if (project_path / indicator).exists():
                    project_types.append(project_type)
                    break
        
        return project_types
    
    def _get_file_counts(self, path: str) -> Dict[str, int]:
        """
        Get file counts by extension for a project.
        
        Args:
            path: Project path
        
        Returns:
            Dict[str, int]: File extension to count mapping
        """
        file_counts = {}
        project_path = Path(path)
        
        try:
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    extension = file_path.suffix.lower()
                    if not extension:
                        extension = "no_extension"
                    
                    file_counts[extension] = file_counts.get(extension, 0) + 1
        
        except Exception as e:
            self.logger.error(f"Error counting files in {path}: {e}")
        
        return file_counts
    
    def _get_git_info(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get Git repository information for a project.
        
        Args:
            path: Project path
        
        Returns:
            Optional[Dict[str, Any]]: Git information or None if not a Git repo
        """
        project_path = Path(path)
        git_dir = project_path / ".git"
        
        if not git_dir.exists():
            return None
        
        try:
            git_info = {
                "is_git_repo": True,
                "git_dir": str(git_dir),
            }
            
            # Try to get current branch
            head_file = git_dir / "HEAD"
            if head_file.exists():
                with open(head_file, 'r') as f:
                    head_content = f.read().strip()
                    if head_content.startswith("ref: refs/heads/"):
                        git_info["current_branch"] = head_content[16:]  # Remove "ref: refs/heads/"
            
            return git_info
        
        except Exception as e:
            self.logger.error(f"Error getting Git info for {path}: {e}")
            return {"is_git_repo": True, "error": str(e)}
    
    def _refresh_project_cache(self) -> None:
        """Refresh the project cache from configuration and metadata."""
        import time
        
        self._project_cache.clear()
        
        # Load from main configuration
        for project in self.config.projects:
            self._project_cache[project.name] = project
        
        # Load from metadata file
        self._load_project_metadata()
        
        self._cache_timestamp = time.time()
        
        self.logger.debug(f"Refreshed project cache with {len(self._project_cache)} projects")
    
    def _should_refresh_cache(self) -> bool:
        """Check if project cache should be refreshed."""
        import time
        return (time.time() - self._cache_timestamp) > self.cache_ttl
    
    def _load_project_metadata(self) -> None:
        """Load project metadata from file."""
        if not self.projects_metadata_file.exists():
            return
        
        try:
            with open(self.projects_metadata_file, 'r') as f:
                metadata = json.load(f)
            
            for project_data in metadata.get('projects', []):
                project = ProjectConfig(
                    name=project_data['name'],
                    path=project_data['path'],
                    description=project_data.get('description', '')
                )
                
                # Only add if path is still valid and not already in cache
                if (project.name not in self._project_cache and 
                    self.validate_project_path(project.path)):
                    self._project_cache[project.name] = project
        
        except Exception as e:
            self.logger.error(f"Error loading project metadata: {e}")
    
    def _save_project_metadata(self) -> None:
        """Save project metadata to file."""
        try:
            # Only save projects that are not in main config
            config_project_names = {p.name for p in self.config.projects}
            
            metadata_projects = []
            for name, project in self._project_cache.items():
                if name not in config_project_names:
                    metadata_projects.append({
                        'name': project.name,
                        'path': project.path,
                        'description': project.description
                    })
            
            metadata = {
                'projects': metadata_projects,
                'last_updated': time.time()
            }
            
            # Ensure directory exists
            ensure_directory_exists(str(self.projects_metadata_file.parent))
            
            with open(self.projects_metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        except Exception as e:
            self.logger.error(f"Error saving project metadata: {e}")
    
    def get_project_names(self) -> List[str]:
        """
        Get list of all project names.
        
        Returns:
            List[str]: List of project names
        """
        if self._should_refresh_cache():
            self._refresh_project_cache()
        
        return sorted(self._project_cache.keys())
    
    def search_projects(self, query: str) -> List[ProjectConfig]:
        """
        Search projects by name or path.
        
        Args:
            query: Search query
        
        Returns:
            List[ProjectConfig]: List of matching projects
        """
        if self._should_refresh_cache():
            self._refresh_project_cache()
        
        query_lower = query.lower()
        matching_projects = []
        
        for project in self._project_cache.values():
            if (query_lower in project.name.lower() or 
                query_lower in project.path.lower() or
                query_lower in project.description.lower()):
                matching_projects.append(project)
        
        return matching_projects
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the project manager.
        
        Returns:
            Dict[str, Any]: Manager statistics
        """
        import time
        
        return {
            "total_projects": len(self._project_cache),
            "config_projects": len(self.config.projects),
            "metadata_projects": len(self._project_cache) - len(self.config.projects),
            "cache_age_seconds": time.time() - self._cache_timestamp,
            "cache_ttl_seconds": self.cache_ttl,
            "projects_metadata_file": str(self.projects_metadata_file),
            "projects_metadata_exists": self.projects_metadata_file.exists()
        }