# Contributing to Claude Remote Client

Thank you for your interest in contributing to Claude Remote Client! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Documentation](#documentation)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to help us maintain a welcoming and inclusive community.

### Our Standards

- **Be respectful**: Treat everyone with respect and kindness
- **Be inclusive**: Welcome newcomers and help them get started
- **Be collaborative**: Work together to solve problems and improve the project
- **Be constructive**: Provide helpful feedback and suggestions
- **Be patient**: Remember that everyone has different experience levels

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.9+** installed (3.11+ recommended)
- **Git** for version control
- **Claude CLI** installed and configured
- **Slack workspace** for testing (optional but recommended)

### First Contribution

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/claude-remote-client.git
   cd claude-remote-client
   ```
3. **Set up development environment** (see below)
4. **Create a feature branch** for your changes
5. **Make your changes** following our guidelines
6. **Test your changes** thoroughly
7. **Submit a pull request**

## Development Setup

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/claude-remote-client.git
cd claude-remote-client

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e .[dev]
```

### 2. Verify Installation

```bash
# Run tests to verify setup
pytest

# Check code quality
black --check claude_remote_client tests
flake8 claude_remote_client tests
mypy claude_remote_client

# Verify CLI works
claude-remote-client --help
```

### 3. Configure Development Environment

```bash
# Copy example configuration
cp claude-remote-client.example.yaml ~/.claude-remote-client/config.yaml

# Edit configuration with your settings
# (Optional: Set up test Slack workspace)
```

## Contributing Guidelines

### Code Style

We follow Python best practices and use automated tools to maintain code quality:

- **Formatting**: [Black](https://black.readthedocs.io/) for code formatting
- **Linting**: [Flake8](https://flake8.pycqa.org/) for style and error checking
- **Type Checking**: [mypy](https://mypy.readthedocs.io/) for static type analysis
- **Import Sorting**: [isort](https://pycqa.github.io/isort/) for import organization

### Code Quality Standards

- **Type Hints**: All functions should have type hints
- **Docstrings**: All public functions and classes need docstrings
- **Error Handling**: Proper exception handling with specific exception types
- **Logging**: Use structured logging with appropriate levels
- **Testing**: All new features need comprehensive tests

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(slack): add support for thread replies
fix(session): resolve memory leak in session cleanup
docs(readme): update installation instructions
test(queue): add integration tests for task processing
```

## Pull Request Process

### Before Submitting

1. **Update your branch** with the latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Run the full test suite**:
   ```bash
   pytest
   black claude_remote_client tests
   flake8 claude_remote_client tests
   mypy claude_remote_client
   ```

3. **Update documentation** if needed
4. **Add tests** for new functionality
5. **Update CHANGELOG.md** if appropriate

### Pull Request Template

When creating a pull request, please include:

- **Description**: Clear description of changes
- **Motivation**: Why this change is needed
- **Testing**: How you tested the changes
- **Screenshots**: If UI changes are involved
- **Breaking Changes**: Any breaking changes
- **Related Issues**: Link to related issues

### Review Process

1. **Automated Checks**: All CI checks must pass
2. **Code Review**: At least one maintainer review required
3. **Testing**: Verify tests pass and coverage is maintained
4. **Documentation**: Ensure documentation is updated
5. **Approval**: Maintainer approval required for merge

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

- **Environment**: OS, Python version, package version
- **Steps to Reproduce**: Clear steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Error Messages**: Full error messages and stack traces
- **Configuration**: Relevant configuration (sanitized)
- **Logs**: Relevant log entries

### Feature Requests

For feature requests, please include:

- **Use Case**: Why this feature is needed
- **Proposed Solution**: How you envision it working
- **Alternatives**: Alternative solutions considered
- **Implementation**: Any implementation ideas

### Issue Labels

We use labels to categorize issues:

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `question`: Further information is requested

## Development Workflow

### Branch Strategy

- **main**: Stable release branch
- **develop**: Development integration branch
- **feature/***: Feature development branches
- **fix/***: Bug fix branches
- **docs/***: Documentation branches

### Development Process

1. **Create Issue**: Create or find an issue to work on
2. **Create Branch**: Create feature branch from main
3. **Develop**: Make changes following guidelines
4. **Test**: Run tests and ensure quality
5. **Document**: Update documentation as needed
6. **Submit PR**: Create pull request for review
7. **Address Feedback**: Respond to review comments
8. **Merge**: Maintainer merges approved PR

### Local Development Commands

```bash
# Run tests
pytest                              # All tests
pytest tests/unit/                  # Unit tests only
pytest tests/integration/           # Integration tests only
pytest --cov=claude_remote_client   # With coverage

# Code quality
black claude_remote_client tests    # Format code
flake8 claude_remote_client tests   # Lint code
mypy claude_remote_client           # Type checking
isort claude_remote_client tests    # Sort imports

# Documentation
sphinx-build -b html docs docs/_build/html  # Build docs

# Package testing
pip install -e .                    # Install in development mode
claude-remote-client --help         # Test CLI
```

## Testing

### Test Structure

```
tests/
├── unit/                   # Unit tests
│   ├── test_config.py
│   ├── test_models.py
│   └── ...
├── integration/            # Integration tests
│   ├── test_slack_integration.py
│   ├── test_claude_integration.py
│   └── ...
├── fixtures/               # Test fixtures
└── conftest.py            # Pytest configuration
```

### Testing Guidelines

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **Mock External Dependencies**: Use mocks for Slack API, Claude CLI
- **Test Edge Cases**: Include error conditions and edge cases
- **Maintain Coverage**: Aim for >90% test coverage

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config.py

# Run with coverage
pytest --cov=claude_remote_client --cov-report=html

# Run integration tests (requires setup)
pytest tests/integration/ -m integration

# Run tests in parallel
pytest -n auto
```

## Documentation

### Documentation Types

- **README.md**: Project overview and quick start
- **User Guide**: Comprehensive usage documentation
- **Installation Guide**: Detailed installation instructions
- **API Documentation**: Generated from code docstrings
- **Contributing Guide**: This document

### Documentation Standards

- **Clear and Concise**: Easy to understand
- **Examples**: Include practical examples
- **Up to Date**: Keep synchronized with code changes
- **Accessible**: Consider different skill levels

### Building Documentation

```bash
# Install documentation dependencies
pip install -e .[docs]

# Build documentation
sphinx-build -b html docs docs/_build/html

# Serve documentation locally
python -m http.server 8000 -d docs/_build/html
```

## Release Process

### Version Management

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps

1. **Update Version**: Update version in `__init__.py`
2. **Update Changelog**: Add release notes to CHANGELOG.md
3. **Create Release PR**: Submit PR with version updates
4. **Tag Release**: Create git tag after merge
5. **Build Package**: Build and upload to PyPI
6. **Update Documentation**: Update documentation sites

### Pre-release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped appropriately
- [ ] No breaking changes (or properly documented)
- [ ] Security review completed

## Getting Help

### Community Resources

- **GitHub Issues**: [Report bugs and request features](https://github.com/your-org/claude-remote-client/issues)
- **GitHub Discussions**: [Community Q&A](https://github.com/your-org/claude-remote-client/discussions)
- **Documentation**: [Project documentation](https://github.com/your-org/claude-remote-client/blob/main/README.md)

### Maintainer Contact

For questions about contributing:

- Create an issue with the `question` label
- Start a discussion in GitHub Discussions
- Reach out to maintainers in pull request comments

## Recognition

We appreciate all contributions! Contributors will be:

- **Listed in CONTRIBUTORS.md**
- **Mentioned in release notes**
- **Recognized in project documentation**

Thank you for helping make Claude Remote Client better! 🚀

---

*This contributing guide is inspired by open source best practices and is continuously improved based on community feedback.*