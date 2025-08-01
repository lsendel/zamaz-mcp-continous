"""
Setup script for Claude Remote Client.

A Python application for remote Claude AI interaction through Slack.
Enables project-aware Claude conversations, session management, and task automation.
"""

from setuptools import setup, find_packages
import os
import re

# Get version from __init__.py
def get_version():
    init_path = os.path.join(os.path.dirname(__file__), 'claude_remote_client', '__init__.py')
    if os.path.exists(init_path):
        with open(init_path, 'r', encoding='utf-8') as f:
            content = f.read()
            version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", content, re.M)
            if version_match:
                return version_match.group(1)
    return "0.1.0"

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Claude Remote Client - A Python application for remote Claude AI interaction through Slack."

# Read requirements from requirements.txt, filtering out dev dependencies
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    requirements = []
    dev_packages = {'pytest', 'pytest-asyncio', 'pytest-mock', 'pytest-cov', 'mypy', 'types-'}
    
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Skip dev dependencies for main install
                    if not any(dev_pkg in line.lower() for dev_pkg in dev_packages):
                        requirements.append(line)
    return requirements

setup(
    name="claude-remote-client",
    version=get_version(),
    author="Claude Remote Client Team",
    author_email="support@claude-remote-client.com",
    description="Remote Claude AI interaction through Slack with project management and task automation",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/claude-remote-client/claude-remote-client",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "examples"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
        "Topic :: Office/Business :: Scheduling",
        "Environment :: Console",
        "Framework :: AsyncIO",
    ],
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=8.2.2",
            "pytest-asyncio>=0.23.7",
            "pytest-mock>=3.14.0",
            "pytest-cov>=5.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.10.0",
            "types-PyYAML",
            "types-croniter",
            "types-psutil",
        ],
        "enhanced": [
            "croniter>=2.0.2",
            "psutil>=5.9.8",
            "aiofiles>=23.2.1",
        ],
        "all": [
            "croniter>=2.0.2",
            "psutil>=5.9.8",
            "aiofiles>=23.2.1",
            "pytest>=8.2.2",
            "pytest-asyncio>=0.23.7",
            "pytest-mock>=3.14.0",
            "pytest-cov>=5.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.10.0",
            "types-PyYAML",
            "types-croniter",
            "types-psutil",
        ]
    },
    entry_points={
        "console_scripts": [
            "claude-remote-client=claude_remote_client.cli:main",
            "kiro-next=claude_remote_client.claude_client.kiro_next:main",
        ],
    },
    include_package_data=True,
    package_data={
        "claude_remote_client": [
            "*.yaml",
            "*.yml",
            "config/*.yaml",
            "config/*.yml",
            "templates/*.txt",
            "templates/*.md",
        ],
    },
    data_files=[
        ('share/claude-remote-client/examples', ['claude-remote-client.example.yaml']),
        ('share/claude-remote-client/docs', ['docs/USER_GUIDE.md', 'docs/PACKAGE_README.md']),
    ],
    zip_safe=False,
    keywords="claude ai slack remote development automation project-management task-queue cron",
    project_urls={
        "Bug Reports": "https://github.com/claude-remote-client/claude-remote-client/issues",
        "Source": "https://github.com/claude-remote-client/claude-remote-client",
        "Documentation": "https://github.com/claude-remote-client/claude-remote-client/blob/main/README.md",
        "Changelog": "https://github.com/claude-remote-client/claude-remote-client/blob/main/CHANGELOG.md",
        "Discussions": "https://github.com/claude-remote-client/claude-remote-client/discussions",
        "Contributing": "https://github.com/claude-remote-client/claude-remote-client/blob/main/CONTRIBUTING.md",
    },
)