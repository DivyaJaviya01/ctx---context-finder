# Context Finder (ctx)

> **Find the right code context before asking AI to write code.**

Context Finder is a local CLI that helps developers identify the most relevant parts of a codebase before handing work to AI coding assistants.

Instead of letting AI explore your repository without direction, Context Finder helps you discover the right files, understand the surrounding architecture, identify risks, and prepare focused context you can actually trust.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

![Demo](./docs/images/demo.gif)

Context Finder helps you discover the right files, validate assumptions, and prepare focused prompts before collaborating with AI.

![Help](./docs/images/help.gif)

---

## Why Context Finder?

AI coding assistants are powerful, but they struggle with one thing:

**context.**

When working inside a real codebase, developers often end up doing one of three things:

* Dumping entire folders into ChatGPT or Claude.
* Letting AI search blindly through the repository.
* Iterating repeatedly because the assistant keeps asking for "one more file."

The result is wasted time, higher token usage, and lower confidence in the generated code.

Context Finder solves this problem.

It prepares focused, explainable context before you ask AI to write code.

---

## How It Works

```text
Find the right files
        ↓
Validate assumptions and risks
        ↓
Export focused context to your AI assistant
```

### 1. Discover

Find the files most relevant to a task.

```bash
ctx "Fix OAuth token refresh bug"
```

---

### 2. Validate

Identify assumptions, risks, and common AI mistakes before implementation begins.

```bash
ctx validate "Replace Stripe webhook handler"
```

---

### 3. Export

Generate a compressed, AI-ready prompt optimized for your preferred assistant.

```bash
ctx export "Add GitHub OAuth login" chatgpt --copy
```

---

## Who Is This For?

Context Finder is useful if you:

* Use ChatGPT or Claude through their web interfaces.
* Use Aider or other terminal-based coding assistants.
* Use Cursor or Windsurf but want more control over what context gets sent.
* Work in medium-to-large repositories where AI frequently explores irrelevant files.
* Prefer explainable recommendations instead of opaque indexing systems.
* Want to guide AI rather than letting AI drive the implementation process.

---

## Features

### 🔍 Find Relevant Files

Search your repository using task descriptions.

```bash
ctx "Fix login timeout"
```

Context Finder ranks files using explainable heuristics and confidence scores.

You see exactly why a file was selected.

---

### 🧠 Understand Subsystems

Explain the structure of a subsystem.

```bash
ctx explain auth
```

Identify:

* Core components
* Entry points
* Related tests
* Supporting modules

---

### 🗺️ Map Relationships

Generate lightweight relationship maps.

```bash
ctx map billing
```

Understand execution flow and dependencies without opening dozens of files.

---

### 📋 Plan Changes

Generate implementation sequences.

```bash
ctx plan "Support multi-tenant databases"
```

Suggested modification order helps reduce unintended side effects.

---

### ⚠️ Assess Risk

Identify areas requiring additional caution.

```bash
ctx risk "Refactor database connection pool"
```

Surface potential risks and recommended mitigations.

---

### 🛡️ Validate AI Tasks

Generate guardrails before letting AI modify code.

```bash
ctx validate "Replace Stripe webhook handler"
```

Validation reports include:

* Assumptions
* Common AI mistakes
* Risks
* Suggested modification order

![Validation Demo](./docs/images/validate.gif)

---

### 🧭 Strategy Guidance

Recommend repository-aware implementation approaches.

```bash
ctx strategy "Implement caching layer"
```

Encourages reuse of existing abstractions instead of duplication.

---

### 📏 Infer Repository Rules

Detect conventions already present in the codebase.

```bash
ctx rules
```

Examples:

* Thin controllers
* Service layers
* Test mirroring
* Repository patterns

---

### 📤 Export AI-Ready Context

Prepare focused prompts for AI assistants.

```bash
ctx export "Add OAuth login" claude --copy
```

Supported targets:

* ChatGPT
* Claude
* Gemini
* Aider
* Copilot
* Cursor
* Windsurf

Outputs are optimized for copy-paste workflows.

![Export Demo](./docs/images/export.gif)

---

## Why Not Just Use Cursor or Windsurf?

Modern editors already index repositories.

Context Finder solves a different problem.

Editors answer:

> "Where might the answer be?"

Context Finder answers:

> "What should I give the AI, why, what are the risks, and what should change first?"

It provides:

### Explainability

See why files were selected.

### Control

Review context before it reaches the AI.

### Planning

Generate implementation guidance before coding begins.

### Compatibility

Works with any assistant, not just one editor.

---

## Command Overview

```bash
ctx "query"             # Find relevant files
ctx explain auth        # Explain a subsystem
ctx map billing         # Show relationships
ctx plan "task"         # Generate modification order
ctx risk "task"         # Assess risks
ctx strategy "task"     # Suggest implementation approach
ctx rules               # Infer conventions
ctx validate "task"     # AI guardrails
ctx export "task" chatgpt --copy
```

---

## Installation

### From Source

```bash
git clone https://github.com/DivyaJaviya01/context-finder.git

cd context-finder

pip install -e .
```

---

## Quick Start

Find context:

```bash
ctx "Fix OAuth login expiration"
```

Validate a task:

```bash
ctx validate "Refactor payment retry logic"
```

Generate a plan:

```bash
ctx plan "Support multi-tenant databases"
```

Export context for ChatGPT:

```bash
ctx export "Add GitHub OAuth login" chatgpt --copy
```

Export context for Claude:

```bash
ctx export "Implement Redis caching" claude --copy
```

---

## Example Workflow

Imagine you're asked to:

> Add GitHub OAuth login.

You could:

### Find relevant files

```bash
ctx "Add GitHub OAuth login"
```

### Validate assumptions

```bash
ctx validate "Add GitHub OAuth login"
```

### Export context

```bash
ctx export "Add GitHub OAuth login" chatgpt --copy
```

Paste the exported prompt into ChatGPT or Claude and start implementation with focused context.

---

## Design Principles

Context Finder intentionally favors simplicity.

### Local-First

Repositories are analyzed locally.

No cloud services.

No API keys.

---

### Explainable

Every recommendation includes reasoning.

No opaque ranking systems.

---

### Minimal Dependencies

Built with Python and Typer.

Easy to install.

Easy to understand.

---

### Fast Enough

Heuristic-driven analysis provides practical results without heavyweight infrastructure.

---

## Philosophy

Context Finder is intentionally heuristic-driven.

It prioritizes:

* Explainability over black-box intelligence.
* Privacy over cloud indexing.
* Developer judgment over autonomous agents.
* Practical usefulness over theoretical completeness.

The goal is not to replace developers.

The goal is to help developers collaborate with AI more effectively.

---

## Limitations

Context Finder is not:

* A compiler.
* A static analysis platform.
* A full dependency graph engine.
* A code modification tool.
* A replacement for human review.

It relies on heuristics and repository conventions to provide practical guidance.

You should always review AI-generated changes before merging them.

---

## Roadmap

Future improvements may include:

* Project-specific synonym dictionaries.
* Additional language support.
* Enhanced architecture detection.
* Pre-commit integrations.
* Improved repository convention inference.

---

## Contributing

Contributions are welcome.

Before opening a pull request:

1. Keep dependencies minimal.
2. Preserve explainability.
3. Prefer simple solutions over complex abstractions.
4. Benchmark meaningful changes.
5. Run the test suite.

```bash
pytest
```

---

## License

Released under the MIT License.

See the LICENSE file for details.
