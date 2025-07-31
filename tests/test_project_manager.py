"""
Unit tests for project manager.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch

from claude_remote_client.session_manager.project_manager import ProjectManager
from claude_remote_client.config import Config, ProjectConfig, ClaudeConfig, SlackConfig
from claude_remote_client.exceptions import SessionError


@pytest.fixture
def temp_config():
    """Create a test configuration with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some test projects
        project1_dir = Path(temp_dir) / "project1"
        project2_dir = Path(temp_dir) / "project2"
        project1_dir.mkdir()
        project2_dir.mkdir()
        
        # Add project indicators
        (project1_dir / "setup.py").touch()
        (project2_dir / "package.json").touch()
        
        config = Config(
            data_dir=temp_dir,
            projects=[
                ProjectConfig(name="project1", path=str(project1_dir), description="Test project 1"),
                ProjectConfig(name="project2", path=str(project2_dir), description="Test project 2")
            ],
            claude=ClaudeConfig(),
            slack=SlackConfig()
        )
        yield config, temp_dir, project1_dir, project2_dir


@pytest.fixture
def project_manager(temp_config):
    """Create a project manager with test configuration."""
    config, temp_dir, project1_dir, project2_dir = temp_config
    manager = ProjectManager(config)
    return manager, temp_dir, project1_dir, project2_dir


class TestProjectManager:
    """Test cases for ProjectManager."""
    
    def test_manager_initialization(self, temp_config):
        """Test project manager initialization."""
        config, temp_dir, project1_dir, project2_dir = temp_config
        manager = ProjectManager(config)
        
        assert manager.config == config
        assert len(manager._project_cache) == 2
        assert "project1" in manager._project_cache
        assert "project2" in manager._project_cache
    
    def test_get_available_projects(self, project_manager):
        """Test getting available projects."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        projects = manager.get_available_projects()
        
        assert len(projects) == 2
        project_names = [p.name for p in projects]
        assert "project1" in project_names
        assert "project2" in project_names
    
    def test_get_project_by_name(self, project_manager):
        """Test getting project by name."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Existing project
        project = manager.get_project_by_name("project1")
        assert project is not None
        assert project.name == "project1"
        assert project.path == str(project1_dir)
        
        # Non-existent project
        project = manager.get_project_by_name("nonexistent")
        assert project is None
    
    def test_get_project_by_path(self, project_manager):
        """Test getting project by path."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Existing project
        project = manager.get_project_by_path(str(project1_dir))
        assert project is not None
        assert project.name == "project1"
        
        # Non-existent project
        project = manager.get_project_by_path("/nonexistent/path")
        assert project is None
    
    def test_validate_project_path(self, project_manager):
        """Test project path validation."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Valid path
        assert manager.validate_project_path(str(project1_dir)) is True
        
        # Invalid path
        assert manager.validate_project_path("/nonexistent/path") is False
    
    def test_is_project_directory(self, project_manager):
        """Test project directory detection."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Python project (has setup.py)
        files1 = ["setup.py", "main.py"]
        assert manager._is_project_directory(str(project1_dir), files1) is True
        
        # Node.js project (has package.json)
        files2 = ["package.json", "index.js"]
        assert manager._is_project_directory(str(project2_dir), files2) is True
        
        # Not a project directory
        files3 = ["random.txt", "data.csv"]
        assert manager._is_project_directory(str(temp_dir), files3) is False
    
    def test_discover_projects_in_directory(self, project_manager):
        """Test project discovery in directory."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Create additional project for discovery
        project3_dir = Path(temp_dir) / "project3"
        project3_dir.mkdir()
        (project3_dir / "Cargo.toml").touch()  # Rust project
        
        # Discover projects (should find project3, but not project1/2 as they're already configured)
        discovered = manager.discover_projects_in_directory(temp_dir)
        
        # Should find the new project
        discovered_names = [p.name for p in discovered]
        assert "project3" in discovered_names
        
        # Should not find already configured projects
        assert "project1" not in discovered_names
        assert "project2" not in discovered_names
    
    def test_add_project(self, project_manager):
        """Test adding a new project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Create new project directory
        new_project_dir = Path(temp_dir) / "new_project"
        new_project_dir.mkdir()
        
        # Add project
        project = manager.add_project("new_project", str(new_project_dir), "New test project")
        
        assert project.name == "new_project"
        assert project.path == str(new_project_dir.resolve())
        assert project.description == "New test project"
        
        # Verify it's in cache
        assert "new_project" in manager._project_cache
        
        # Verify it's saved to metadata
        assert manager.projects_metadata_file.exists()
    
    def test_add_project_duplicate_name(self, project_manager):
        """Test adding project with duplicate name."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Create new project directory
        new_project_dir = Path(temp_dir) / "new_project"
        new_project_dir.mkdir()
        
        # Try to add project with existing name
        with pytest.raises(SessionError) as exc_info:
            manager.add_project("project1", str(new_project_dir))
        
        assert "already exists" in str(exc_info.value)
    
    def test_add_project_invalid_path(self, project_manager):
        """Test adding project with invalid path."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Try to add project with invalid path
        with pytest.raises(SessionError) as exc_info:
            manager.add_project("invalid_project", "/nonexistent/path")
        
        assert "Invalid project path" in str(exc_info.value)
    
    def test_remove_project(self, project_manager):
        """Test removing a project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Add a project first
        new_project_dir = Path(temp_dir) / "removable_project"
        new_project_dir.mkdir()
        manager.add_project("removable_project", str(new_project_dir))
        
        # Verify it exists
        assert "removable_project" in manager._project_cache
        
        # Remove project
        result = manager.remove_project("removable_project")
        
        assert result is True
        assert "removable_project" not in manager._project_cache
    
    def test_remove_project_not_found(self, project_manager):
        """Test removing non-existent project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        result = manager.remove_project("nonexistent")
        assert result is False
    
    def test_update_project(self, project_manager):
        """Test updating a project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Add a project first
        new_project_dir = Path(temp_dir) / "updatable_project"
        new_project_dir.mkdir()
        manager.add_project("updatable_project", str(new_project_dir))
        
        # Update description
        updated_project = manager.update_project("updatable_project", description="Updated description")
        
        assert updated_project is not None
        assert updated_project.description == "Updated description"
        
        # Verify in cache
        cached_project = manager._project_cache["updatable_project"]
        assert cached_project.description == "Updated description"
    
    def test_update_project_not_found(self, project_manager):
        """Test updating non-existent project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        result = manager.update_project("nonexistent", description="New description")
        assert result is None
    
    def test_get_project_info(self, project_manager):
        """Test getting detailed project information."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Get info for existing project
        info = manager.get_project_info("project1")
        
        assert info is not None
        assert info["name"] == "project1"
        assert info["path"] == str(project1_dir)
        assert info["exists"] is True
        assert info["is_directory"] is True
        assert "project_type" in info
        assert "python" in info["project_type"]  # Has setup.py
        assert "file_counts" in info
    
    def test_get_project_info_not_found(self, project_manager):
        """Test getting info for non-existent project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        info = manager.get_project_info("nonexistent")
        assert info is None
    
    def test_detect_project_type(self, project_manager):
        """Test project type detection."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Python project
        types1 = manager._detect_project_type(str(project1_dir))
        assert "python" in types1
        
        # Node.js project
        types2 = manager._detect_project_type(str(project2_dir))
        assert "nodejs" in types2
    
    def test_get_file_counts(self, project_manager):
        """Test file counting by extension."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Add some files
        (project1_dir / "main.py").touch()
        (project1_dir / "test.py").touch()
        (project1_dir / "README.md").touch()
        
        counts = manager._get_file_counts(str(project1_dir))
        
        assert counts[".py"] == 3  # setup.py + main.py + test.py
        assert counts[".md"] == 1  # README.md
    
    def test_get_git_info_no_git(self, project_manager):
        """Test Git info for non-Git project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        git_info = manager._get_git_info(str(project1_dir))
        assert git_info is None
    
    def test_get_git_info_with_git(self, project_manager):
        """Test Git info for Git project."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Create fake .git directory
        git_dir = project1_dir / ".git"
        git_dir.mkdir()
        
        # Create HEAD file
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/main\n")
        
        git_info = manager._get_git_info(str(project1_dir))
        
        assert git_info is not None
        assert git_info["is_git_repo"] is True
        assert git_info["current_branch"] == "main"
    
    def test_get_project_names(self, project_manager):
        """Test getting project names."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        names = manager.get_project_names()
        
        assert isinstance(names, list)
        assert len(names) == 2
        assert "project1" in names
        assert "project2" in names
        assert names == sorted(names)  # Should be sorted
    
    def test_search_projects(self, project_manager):
        """Test searching projects."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Search by name
        results = manager.search_projects("project1")
        assert len(results) == 1
        assert results[0].name == "project1"
        
        # Search by partial name
        results = manager.search_projects("project")
        assert len(results) == 2
        
        # Search by path
        results = manager.search_projects(str(project1_dir))
        assert len(results) == 1
        assert results[0].name == "project1"
        
        # No matches
        results = manager.search_projects("nonexistent")
        assert len(results) == 0
    
    def test_save_load_project_metadata(self, project_manager):
        """Test saving and loading project metadata."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Add a project (not in main config)
        new_project_dir = Path(temp_dir) / "metadata_project"
        new_project_dir.mkdir()
        manager.add_project("metadata_project", str(new_project_dir), "Metadata test project")
        
        # Verify metadata file was created
        assert manager.projects_metadata_file.exists()
        
        # Clear cache and reload
        manager._project_cache.clear()
        manager._load_project_metadata()
        
        # Should only load the metadata project (not config projects)
        assert "metadata_project" in manager._project_cache
        
        # Config projects should be loaded by refresh_cache
        manager._refresh_project_cache()
        assert "project1" in manager._project_cache
        assert "project2" in manager._project_cache
        assert "metadata_project" in manager._project_cache
    
    def test_cache_refresh(self, project_manager):
        """Test cache refresh mechanism."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Force cache to be old
        manager._cache_timestamp = 0
        
        # Should refresh cache
        assert manager._should_refresh_cache() is True
        
        # Get projects (should trigger refresh)
        projects = manager.get_available_projects()
        assert len(projects) == 2
        
        # Cache should now be fresh
        assert manager._should_refresh_cache() is False
    
    def test_get_manager_stats(self, project_manager):
        """Test getting manager statistics."""
        manager, temp_dir, project1_dir, project2_dir = project_manager
        
        # Add a metadata project
        new_project_dir = Path(temp_dir) / "stats_project"
        new_project_dir.mkdir()
        manager.add_project("stats_project", str(new_project_dir))
        
        stats = manager.get_manager_stats()
        
        assert stats["total_projects"] == 3  # 2 config + 1 metadata
        assert stats["config_projects"] == 2
        assert stats["metadata_projects"] == 1
        assert "cache_age_seconds" in stats
        assert "cache_ttl_seconds" in stats
        assert stats["projects_metadata_exists"] is True