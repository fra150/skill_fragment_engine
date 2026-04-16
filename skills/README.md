# Skill Fragment Engine - Add to Your AI Coding Tool

This folder contains the skill definition for the Skill Fragment Engine (SFE) to use with AI coding tools like **opencode**, **Claude Code**, or **ClawCode**.

## Supported Tools

- **opencode**: https://opencode.ai
- **Claude Code**: Anthropic's CLI agent
- **ClawCode**: Alternative AI coding tool

## How to Install

### For opencode

Copy the `skill-fragment-engine` folder to your opencode skills directory:

```bash
# Windows
copy /r skills\skill-fragment-engine %APPDATA%\opencode\skills\

# Linux/Mac
cp -r skills/skill-fragment-engine ~/.opencode/skills/
```

### For Claude Code

Claude Code uses MCP (Model Context Protocol). You need to create a custom skill:

```bash
# Copy to Claude Code skills directory
cp -r skills/skill-fragment-engine ~/.claude/skills/
```

### For ClawCode

```bash
# Copy to ClawCode skills directory
cp -r skills/skill-fragment-engine ~/.clawcode/skills/
```

## Usage

Once installed, the AI tool will automatically use this skill when working with the Skill Fragment Engine project.

The skill provides:
- Knowledge of SFE architecture and modules
- API usage examples
- Configuration guidance
- Best practices for working with fragments, clustering, versioning, etc.

## Files

- `skill.yaml` - Skill metadata
- `SKILL.md` - Detailed usage guide for the AI tool
- `SDK.md` - Python SDK documentation for end users

## Learn More

- GitHub: https://github.com/your-repo/skill-fragment-engine
- Documentation: See `SDK.md` for full API reference
