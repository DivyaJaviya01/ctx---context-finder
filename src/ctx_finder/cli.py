import sys
import typer
from pathlib import Path
from typing import Optional, List
from ctx_finder.cache import CacheManager
from ctx_finder.utils import analyze_repository, scan_repository_files, is_test_file
from ctx_finder.ranker import rank_files
from ctx_finder.architecture import detect_architecture, detect_constraints, detect_file_entry_point
from ctx_finder.planner import generate_plan, evaluate_risks, generate_senior_guidance, generate_strategy, build_validate_report
from ctx_finder.exporter import format_context_pack
from ctx_finder.clipboard import copy_to_clipboard
from ctx_finder.models import ContextPack

app = typer.Typer(help="Context Finder - The universal context layer for AI development.")

SUBCOMMANDS = {"explain", "map", "plan", "strategy", "rules", "validate", "search", "risk", "export"}

# Paths that produce noisy plan steps (benchmark scripts, deprecated, fixtures, stubs)
_NOISE_PATTERNS = {
    "benchmark", "bench", "deprecated", "fixture", "fixtures",
    "conftest", "setup", "stub", "stubs", "migration", "migrations",
    "script", "scripts", "example", "examples", "sample", "samples",
}

def _is_noise_file(file_path: str) -> bool:
    """Return True if file should be excluded from plan steps and export core files."""
    p = Path(file_path)
    parts_lower = {part.lower() for part in p.parts}
    stem_lower = p.stem.lower()
    # Check every directory component and the filename stem
    return bool(parts_lower.intersection(_NOISE_PATTERNS) or
                any(noise in stem_lower for noise in _NOISE_PATTERNS))

def filter_plan_matches(matches):
    """Remove benchmark/deprecated/fixture matches, keep tests separate."""
    return [m for m in matches if not _is_noise_file(m.file_path)]

def get_analyses_and_cache(path: Optional[Path]) -> tuple[List, CacheManager, Path]:
    base_path = Path.cwd() if path is None else path.resolve()
    if not base_path.exists():
        typer.echo(f"Error: Path '{base_path}' does not exist.", err=True)
        raise typer.Exit(code=1)
    
    cache_mgr = CacheManager(base_path)
    analyses = analyze_repository(base_path, cache_mgr)
    return analyses, cache_mgr, base_path

@app.callback()
def main(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Directory to scan (defaults to current working directory)"
    )
):
    """
    Context Finder callback (handles global options like path).
    """
    pass

@app.command(name="search", hidden=True)
def search(
    query: str = typer.Argument(..., help="Query describing the coding task"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy context pack to clipboard"),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="AI assistant target export (claude, chatgpt, gemini, copilot, cursor, windsurf, aider)"
    )
):
    """
    Search repository and retrieve relevant context for a task.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, query, base_path)
    
    if not matches:
        typer.echo("No matches found.")
        return

    # Generate complete ContextPack
    arch_signals = detect_architecture(analyses)
    risks = evaluate_risks(matches)
    plan = generate_plan(matches, analyses)
    conventions = generate_senior_guidance(matches)
    
    why_summary = f"Identified {len(matches)} files matching query '{query}'."

    pack = ContextPack(
        query=query,
        matches=matches,
        architecture_signals=arch_signals,
        risks=risks,
        plan=plan.steps,
        conventions=conventions,
        why_summary=why_summary
    )

    # If export format is requested
    if export:
        formatted = format_context_pack(pack, export)
        if copy:
            succeeded = copy_to_clipboard(formatted)
            if succeeded:
                typer.echo(f"Export prompt copied to clipboard for assistant '{export}'.")
            else:
                typer.echo("Failed to copy to clipboard. Displaying output:\n")
                typer.echo(formatted)
        else:
            typer.echo(formatted)
        return

    # Standard plain text CLI presentation
    typer.echo(f"Context Finder Search Results for: '{query}'")
    typer.echo("=" * 60)
    
    core_matches = []
    test_matches = []
    for m in matches:
        if is_test_file(m.file_path):
            test_matches.append(m)
        else:
            core_matches.append(m)

    typer.echo("Core Results:")
    if core_matches:
        for idx, m in enumerate(core_matches[:10], start=1):
            typer.echo(f"{idx}. {m.file_path} (Confidence: {m.confidence}%)")
            for exp in m.explanations:
                typer.echo(f"   - {exp}")
    else:
        typer.echo("  None identified.")

    typer.echo("\nRelated Tests:")
    if test_matches:
        for idx, m in enumerate(test_matches[:10], start=1):
            typer.echo(f"{idx}. {m.file_path} (Confidence: {m.confidence}%)")
            for exp in m.explanations:
                typer.echo(f"   - {exp}")
    else:
        typer.echo("  None identified.")
    
    if arch_signals:
        typer.echo("\nPossible Architecture Signals:")
        for a in arch_signals:
            typer.echo(f"- {a.pattern_name} (Confidence: {a.confidence}%): {a.explanation}")

    # If clipboard copy requested for default format
    if copy:
        formatted = format_context_pack(pack, "default")
        succeeded = copy_to_clipboard(formatted)
        if succeeded:
            typer.echo("\nContext pack copied to clipboard.")
        else:
            typer.echo("\nFailed to copy context pack to clipboard.")

@app.command(name="explain")
def explain(
    subsystem: str = typer.Argument(..., help="Subsystem name to explain (e.g. 'auth')"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Explain the structure, entrypoints, and files of a subsystem.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, subsystem, base_path)
    
    if not matches:
        typer.echo(f"No files found relating to subsystem '{subsystem}'.")
        return

    typer.echo(f"Subsystem Explanation: '{subsystem}'")
    typer.echo("=" * 60)
    
    # Heuristically list entry points vs core logic
    entrypoints_list = []
    core = []
    tests = []
    
    analysis_by_path = {a.path: a for a in analyses}
    
    for m in matches:
        p_str = m.file_path.lower()
        if is_test_file(m.file_path):
            tests.append(m.file_path)
            continue
            
        analysis = analysis_by_path.get(m.file_path)
        ep_detected = None
        if analysis:
            ep_detected = detect_file_entry_point(analysis, base_path)
            
        if ep_detected:
            confidence, why = ep_detected
            entrypoints_list.append((m.file_path, confidence, why))
        else:
            if any(k in p_str for k in ["route", "controller", "api", "entry", "views"]):
                entrypoints_list.append((m.file_path, 50.0, "Filename matches entry point naming conventions."))
            else:
                core.append(m.file_path)
            
    typer.echo("Entry Points:")
    if entrypoints_list:
        for ep, conf, why in entrypoints_list[:5]:
            typer.echo(f"* {ep}")
            typer.echo(f"  Confidence: {int(conf)}%")
            typer.echo("  Why:")
            typer.echo(f"  {why}")
    else:
        typer.echo("  - None identified.")
        
    typer.echo("\nCore Components:")
    for c in core[:5] if core else ["None identified."]:
        typer.echo(f"  - {c}")
        
    typer.echo("\nAssociated Tests:")
    for t in tests[:5] if tests else ["None identified."]:
        typer.echo(f"  - {t}")

def generate_subsystem_map(subsystem: str, matches: List, analyses: List, base_path: Path) -> str:
    from pathlib import Path
    
    # 1. Separate files
    test_files = []
    non_test_matches = []
    for m in matches:
        if is_test_file(m.file_path):
            test_files.append(m.file_path)
        else:
            non_test_matches.append(m)
            
    # 2. Find entry points among non_test_matches
    analysis_by_path = {a.path: a for a in analyses}
    entry_points = []
    other_core_files = []
    
    for m in non_test_matches:
        analysis = analysis_by_path.get(m.file_path)
        ep = detect_file_entry_point(analysis, base_path) if analysis else None
        if ep:
            entry_points.append((m.file_path, ep[0], ep[1]))
        else:
            other_core_files.append(m.file_path)
            
    # 3. Build import dependency graph among all non-test matched files
    all_non_test_paths = [ep[0] for ep in entry_points] + other_core_files
    
    adj = {path: [] for path in all_non_test_paths}
    in_degree = {path: 0 for path in all_non_test_paths}
    
    why_reasons = []
    
    for path1 in all_non_test_paths:
        a1 = analysis_by_path.get(path1)
        if not a1:
            continue
        for path2 in all_non_test_paths:
            if path1 == path2:
                continue
            # Check if path1 imports path2
            stem2 = Path(path2).stem
            mod2 = path2.replace(".py", "").replace("/", ".")
            is_imported = False
            for imp in a1.imports:
                if imp == stem2 or imp == mod2 or imp.endswith("." + stem2):
                    is_imported = True
                    break
            if is_imported:
                adj[path1].append(path2)
                in_degree[path2] += 1
                why_reasons.append(f"- Found import link from {path1} to {path2}.")

    # 4. Find the longest chain of connections (DAG paths)
    def dfs_longest_path(node, path_so_far, visited):
        longest = path_so_far
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                cand = dfs_longest_path(neighbor, path_so_far + [neighbor], visited | {neighbor})
                if len(cand) > len(longest):
                    longest = cand
        return longest

    # Find starting nodes (in-degree == 0, or entry points)
    start_nodes = [n for n in all_non_test_paths if in_degree[n] == 0]
    if not start_nodes and all_non_test_paths:
        start_nodes = [ep[0] for ep in entry_points] if entry_points else [all_non_test_paths[0]]
        
    core_flow = []
    for start in start_nodes:
        cand = dfs_longest_path(start, [start], {start})
        if len(cand) > len(core_flow):
            core_flow = cand
            
    # We only show Core Flow if it has length >= 2
    if len(core_flow) < 2:
        core_flow = []
        
    # 5. Supporting components are non-test paths not in core_flow and not in entry_points
    entry_point_paths = {ep[0] for ep in entry_points}
    supporting = [p for p in all_non_test_paths if p not in core_flow and p not in entry_point_paths]
    
    # 6. Format the output
    # If no connections at all and no entry points, return the fallback
    if not entry_points and not core_flow and not why_reasons:
        return "No direct relationships confidently identified."
        
    output = f"Relationship Map for Subsystem: '{subsystem}'\n"
    output += "=" * 60 + "\n\n"
    
    if entry_points:
        output += "Entry Points:\n"
        for ep, conf, why in entry_points:
            output += f"* {ep}\n  Why: {why}\n"
        output += "\n"
        
    if core_flow:
        output += "Core Flow:\n"
        # Print using basenames
        basenames = [Path(p).name for p in core_flow]
        output += "\n  v\n".join(basenames) + "\n\n"
        
    if supporting:
        output += "Supporting Components:\n"
        for p in supporting:
            output += f"* {Path(p).name}\n"
        output += "\n"
        
    if test_files:
        output += "Tests:\n"
        for p in test_files:
            output += f"* {Path(p).name}\n"
        output += "\n"
        
    if why_reasons:
        output += "Why:\n"
        output += "\n".join(why_reasons) + "\n"
        
    return output.strip()

@app.command(name="map")
def map_subsystem(
    subsystem: Optional[str] = typer.Argument(None, help="Optional subsystem to focus mapping"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Generate subsystem relationship maps.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    
    if subsystem:
        matches = rank_files(analyses, subsystem, base_path)
        if not matches:
            typer.echo(f"No files matching subsystem: '{subsystem}'")
            return
        
        map_output = generate_subsystem_map(subsystem, matches, analyses, base_path)
        typer.echo(map_output)
        return
        
    # Default folder-based repository map if no subsystem is provided
    files_to_map = [a.path for a in analyses]
    typer.echo("Repository Subsystem Map")
    typer.echo("=" * 60)
    
    categories = {}
    for f in files_to_map:
        p = Path(f)
        parent = str(p.parent).replace("\\", "/")
        if parent == "." or parent == "":
            parent = "Root"
        categories.setdefault(parent, []).append(p.name)

    for cat, files in categories.items():
        typer.echo(f"\n[{cat}]")
        for file in files:
            typer.echo(f"  -- {file}")

@app.command(name="plan")
def plan(
    query: str = typer.Argument(..., help="Proposed coding task query"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Generate implementation sequence steps and risk evaluation.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, query, base_path)
    
    if not matches:
        typer.echo("No relevant files to plan for.")
        return

    # Filter noise (benchmarks, deprecated, fixtures) from the modification order
    plan_matches = filter_plan_matches(matches)
    if not plan_matches:
        plan_matches = matches  # fallback: don't show empty plan

    impl_plan = generate_plan(plan_matches, analyses)
    risks = evaluate_risks(matches)  # risk uses ALL matches (unfiltered) for accuracy
    
    typer.echo(f"Implementation Plan for task: '{query}'")
    typer.echo("=" * 60)
    typer.echo(f"Complexity: {impl_plan.complexity}")
    typer.echo("\nSuggested Modification Order:")
    MAX_VISIBLE_PLAN_STEPS = 10
    visible_steps = impl_plan.steps[:MAX_VISIBLE_PLAN_STEPS]
    omitted_count = len(impl_plan.steps) - MAX_VISIBLE_PLAN_STEPS

    for step in visible_steps:
        typer.echo(step)
    if omitted_count > 0:
        typer.echo(f"+ {omitted_count} additional related files omitted.")

    typer.echo("\nRisk Assessment:")
    for r in risks:
        typer.echo(f"- Risk Level: {r.risk_level} (Confidence: {r.confidence}%)")
        typer.echo(f"  Why: {r.explanation}")
        typer.echo("  Mitigations:")
        for m in r.mitigations:
            typer.echo(f"    * {m}")

@app.command(name="risk")
def risk(
    query: str = typer.Argument(..., help="Proposed coding task query"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Evaluate the risks and potential side effects of a proposed task.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, query, base_path)
    
    if not matches:
        typer.echo("No matching files found to evaluate risk.")
        return

    risks = evaluate_risks(matches)
    
    typer.echo(f"Risk Evaluation for task: '{query}'")
    typer.echo("=" * 60)
    if not risks:
        typer.echo("Low risk. No specific risk signals detected.")
        return

    for r in risks:
        typer.echo(f"- Risk Level: {r.risk_level} (Confidence: {r.confidence}%)")
        typer.echo(f"  Why: {r.explanation}")
        if r.mitigations:
            typer.echo("  Mitigations:")
            for m in r.mitigations:
                typer.echo(f"    * {m}")

@app.command(name="strategy")
def strategy(
    query: str = typer.Argument(..., help="Proposed task query"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Display design patterns and implementation strategy recommendations.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, query, base_path)
    
    if not matches:
        typer.echo("No matching files found.")
        return

    typer.echo(f"Recommended Strategy for task: '{query}'")
    typer.echo("=" * 60 + "\n")
    
    strategy_output = generate_strategy(query, matches, analyses)
    typer.echo(strategy_output)

@app.command(name="rules")
def rules(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    Infer repository conventions and architectural guidelines.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    
    all_names = [Path(a.path).stem.lower() for a in analyses]
    
    typer.echo("Observed Repository Conventions")
    typer.echo("=" * 60)
    
    has_controllers = any("controller" in n for n in all_names)
    has_services = any("service" in n for n in all_names)
    has_repositories = any("repository" in n or "repo" in n for n in all_names)
    
    if has_controllers and has_services:
        typer.echo("* Controllers are thin: Route files delegate logic to dedicated service layers.")
        typer.echo("Avoid: Business logic inside controllers.")
    if has_services:
        typer.echo("* Services contain business logic: Logic and operations are encapsulated in service instances.")
    if has_repositories:
        typer.echo("* Repository Pattern detected: Database calls are structured through repo files.")
        typer.echo("Avoid: Direct SQL or database connections in endpoints.")
        
    test_files = [a.path for a in analyses if "test" in a.path.lower()]
    if test_files:
        typer.echo("* Tests mirror source: Test directory mirrors core file naming and packaging structure.")

@app.command(name="validate")
def validate(
    query: str = typer.Argument(..., help="Query describing the task to validate"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path")
):
    """
    AI guardrail: warn about risks, incorrect assumptions, and missing dependencies
    before asking an AI assistant to implement a task.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    constraints = detect_constraints(analyses)
    matches = rank_files(analyses, query, base_path)

    typer.echo(f"AI Guardrail Report for: '{query}'")
    typer.echo("=" * 60)

    report = build_validate_report(query, matches, analyses, constraints)
    typer.echo(report)

@app.command(name="export")
def export(
    query: str = typer.Argument(..., help="Task query to export context for"),
    target: str = typer.Argument(..., help="AI target: chatgpt, claude, gemini, aider, copilot, cursor, windsurf"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Directory path"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy output to clipboard"),
):
    """
    Export a compressed, AI-ready context pack for a specific assistant.
    """
    analyses, cache_mgr, base_path = get_analyses_and_cache(path)
    matches = rank_files(analyses, query, base_path)

    if not matches:
        typer.echo("No matching files found.")
        return

    # Filter noise for the exported file list and plan steps
    clean_matches = filter_plan_matches(matches)
    if not clean_matches:
        clean_matches = matches

    arch_signals = detect_architecture(analyses)
    risks = evaluate_risks(matches)          # unfiltered for risk accuracy
    plan = generate_plan(clean_matches, analyses)
    conventions = generate_senior_guidance(clean_matches)

    pack = ContextPack(
        query=query,
        matches=clean_matches,
        architecture_signals=arch_signals,
        risks=risks,
        plan=plan.steps,
        conventions=conventions,
        why_summary=f"Identified {len(clean_matches)} relevant files for '{query}'.",
    )

    formatted = format_context_pack(pack, target)

    if copy:
        from ctx_finder.clipboard import copy_to_clipboard
        succeeded = copy_to_clipboard(formatted)
        if succeeded:
            typer.echo(f"Context pack for '{target}' copied to clipboard.")
        else:
            typer.echo("Failed to copy. Displaying output:\n")
            typer.echo(formatted)
    else:
        typer.echo(formatted)

def preprocess_args():
    args = sys.argv[1:]
    if not args:
        return
        
    if any(h in args for h in ["--help", "-h", "--install-completion", "--show-completion"]):
        return
        
    # Check if a known subcommand is present in the arguments
    has_subcommand = any(arg in SUBCOMMANDS for arg in args)
    
    if not has_subcommand:
        # If no subcommand is specified, default to the search subcommand by inserting it at index 1.
        # Check to ensure we do not insert it multiple times.
        if len(sys.argv) > 1 and sys.argv[1] != "search":
            sys.argv.insert(1, "search")

# Wrap Typer.__call__ to dynamically preprocess args on every execution
_original_call = typer.Typer.__call__
def wrapped_call(self, *args, **kwargs):
    preprocess_args()
    return _original_call(self, *args, **kwargs)
typer.Typer.__call__ = wrapped_call

if __name__ == "__main__":
    app()
