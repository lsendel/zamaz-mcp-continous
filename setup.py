"""
Setup script for Claude Remote Client.
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Claude Remote Client - A Python application for remote Claude AI interaction through Slack."

# Read requirements from requirements.txt
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    requirements = []
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    requirements.append(line)
    return requirements

setup(
    name="claude-remote-client",
    version="0.1.0",
    author="Claude Remote Client Team",
    author_email="support@claude-remote-client.com",
    description="A Python application for remote Claude AI interaction through Slack",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/claude-remote-client",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
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
    ],
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "enhanced": [
            "croniter>=1.3.0",
            "psutil>=5.9.0",
            "aiofiles>=23.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "claude-remote-client=claude_remote_client.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "claude_remote_client": [
            "config/*.yaml",
            "templates/*.txt",
        ],
    },
    zip_safe=False,
    keywords="claude ai slack remote development automation",
    project_urls={
        "Bug Reports": "https://github.com/your-org/claude-remote-client/issues",
        "Source": "https://github.com/your-org/claude-remote-client",
        "Documentation": "https://claude-remote-client.readthedocs.io/",
    },
)