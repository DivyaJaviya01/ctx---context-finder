from typing import List
from ctx_finder.models import ContextPack
from ctx_finder.utils import is_test_file

# Strict signal-per-token limits for export output
_MAX_CORE_FILES = 5
_MAX_TEST_FILES = 3
_MAX_PLAN_STEPS = 5
_MAX_RISKS = 2
_MAX_CONVENTIONS = 3
_MAX_ARCH_SIGNALS = 3


def format_context_pack(pack: ContextPack, target: str) -> str:
    """
    Format a ContextPack into an AI-ready prompt optimized for the target assistant.
    Output is aggressively compressed: max 5 core files, 3 test files, 5 plan steps.
    Supported targets: chatgpt, claude, gemini, copilot, cursor, windsurf, aider.
    """
    target = target.lower().strip()

    # Partition matches
    core_matches = []
    test_matches = []
    for r in pack.matches:
        if is_test_file(r.file_path):
            test_matches.append(r)
        else:
            core_matches.append(r)

    # --- Core Files (capped) ---
    matches_str = "#### Core Files\n"
    core_slice = core_matches[:_MAX_CORE_FILES]
    if core_slice:
        for r in core_slice:
            why = r.explanations[0] if r.explanations else "Matched query."
            matches_str += f"- **{r.file_path}** ({r.confidence}%): {why}\n"
    else:
        matches_str += "None identified.\n"
    omitted_core = len(core_matches) - len(core_slice)
    if omitted_core > 0:
        matches_str += f"  _(+ {omitted_core} lower-confidence files omitted)_\n"

    # --- Test Files (capped) ---
    matches_str += "\n#### Related Tests\n"
    test_slice = test_matches[:_MAX_TEST_FILES]
    if test_slice:
        for r in test_slice:
            matches_str += f"- **{r.file_path}** ({r.confidence}%)\n"
    else:
        matches_str += "None identified.\n"
    omitted_tests = len(test_matches) - len(test_slice)
    if omitted_tests > 0:
        matches_str += f"  _(+ {omitted_tests} test files omitted)_\n"

    # --- Architecture Signals (capped) ---
    arch_signals = pack.architecture_signals[:_MAX_ARCH_SIGNALS]
    arch_str = ""
    for a in arch_signals:
        arch_str += f"- {a.pattern_name} ({a.confidence}%): {a.explanation}\n"

    # --- Risks (capped) ---
    risk_str = ""
    for r in pack.risks[:_MAX_RISKS]:
        mitigations = r.mitigations[:2]
        mit = "; ".join(mitigations)
        risk_str += f"- **{r.risk_level}** ({r.confidence}%): {r.explanation} Mitigations: {mit}\n"

    # --- Plan (capped at 5 steps) ---
    plan_steps = pack.plan[:_MAX_PLAN_STEPS]
    plan_str = "\n".join(plan_steps)
    omitted_plan = len(pack.plan) - len(plan_steps)
    if omitted_plan > 0:
        plan_str += f"\n_(+ {omitted_plan} steps omitted)_"

    # --- Conventions (capped) ---
    conv_str = "\n".join(pack.conventions[:_MAX_CONVENTIONS])

    # --- Target-specific headers ---
    prompt_header = ""
    prompt_footer = ""

    if target == "claude":
        prompt_header = (
            "You are an expert software developer modifying a codebase. Follow these instructions precisely.\n"
            "<context_constraints>\n"
            "- Work locally inside the provided project files.\n"
            "- Adhere to codebase rules and conventions.\n"
            "- Reuse existing classes, functions, and interfaces.\n"
            "</context_constraints>\n"
        )
        prompt_footer = "\nAnalyze the task, check the files above, and explain your plan in <thought> tags before responding with code edits."

    elif target == "chatgpt":
        prompt_header = (
            "## System Role\n"
            "You are a principal engineer modifying an existing system. Maintain architectural consistency.\n"
            "## Coding Constraints\n"
            "1. Reuse existing abstractions; do not create redundant modules.\n"
            "2. Follow folder structures and testing boundaries.\n"
        )
        prompt_footer = "\nExplain your design choices first, then provide implementation details."

    elif target == "gemini":
        prompt_header = (
            "You are a coding assistant with access to repository context.\n"
            "Study the existing architecture signals and risk reports carefully before modifying any code.\n"
            "Always prefer local and simple implementations.\n"
        )
        prompt_footer = "\nDraft your solution step-by-step. Highlight safety checks for high-risk files."

    elif target == "aider":
        prompt_header = (
            "You are editing a codebase using aider.\n"
            "Focus strictly on the relevant files listed below. Minimize modifications.\n"
        )
        prompt_footer = "\nProduce clean modifications. Do not write explanations outside of code comments."

    elif target in ["cursor", "windsurf", "copilot"]:
        prompt_header = (
            "You are modifying code in an editor workspace.\n"
            "Use the provided context to guide your inline edits and code completions.\n"
        )
        prompt_footer = "\nProceed with modifications following the implementation plan."

    else:
        prompt_header = "You are a software engineer assisting with a coding task.\n"
        prompt_footer = "\nProceed with the task using the context above."

    prompt = f"""{prompt_header}
### Task
Query: "{pack.query}"

### Relevant Files
{matches_str}
### Architecture
{arch_str or "No signals detected."}
### Suggested Modification Order
{plan_str or "No plan generated."}
### Conventions
{conv_str or "No rules detected."}
### Risks
{risk_str or "Low risk."}{prompt_footer}
"""
    return prompt
