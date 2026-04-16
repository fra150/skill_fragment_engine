[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "skill-fragment-engine"
version = "1.0.0"
description = "Cognitive cache layer for AI agents with verified reuse"
readme = "README.md"
authors = [
    {name = "Francesco Bulla", email = "fb@example.com"}
]
license = {text = "MIT"}
requires-python = ">=3.10"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
    "aiohttp>=3.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.urls]
Homepage = "https://github.com/fb/skill-fragment-engine"
Documentation = "https://github.com/fb/skill-fragment-engine#readme"
Repository = "https://github.com/fb/skill-fragment-engine"

[tool.setuptools.packages.find]
where = ["."]
include = ["skill_fragment_engine*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
