from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from ctx_finder.models import ArchitectureSignal, FileAnalysis

# Minimum confidence threshold for emitting an architecture signal.
# Signals below this are too speculative to be useful.
_MIN_SIGNAL_CONFIDENCE = 40.0


def detect_architecture(analyses: List[FileAnalysis]) -> List[ArchitectureSignal]:
    """
    Scan analysed files to identify architectural signals and patterns.
    Signals below 40% confidence are suppressed to avoid noise.
    Each signal includes a probabilistic observation count so the user
    can judge how strongly the evidence supports the claim.
    """
    signals: List[ArchitectureSignal] = []
    if not analyses:
        return signals

    all_dirs: Set[str] = set()
    all_filenames: Set[str] = set()

    for a in analyses:
        p = Path(a.path)
        all_filenames.add(p.name.lower())
        for part in p.parent.parts:
            all_dirs.add(part.lower())

    def _emit(
        pattern_name: str,
        found: Set[str],
        base_conf: float,
        per_match: float,
        source: str,
    ) -> None:
        """Compute confidence and emit signal only if above threshold."""
        if not found:
            return
        confidence = min(95.0, base_conf + len(found) * per_match)
        if confidence < _MIN_SIGNAL_CONFIDENCE:
            return
        count = len(found)
        obs_label = "directory" if source == "dir" else "filename indicator"
        obs_plural = obs_label + ("ies" if obs_label == "directory" else "s") if count != 1 else obs_label
        found_str = ", ".join(sorted(found))
        explanation = (
            f"{count} supporting {obs_plural} observed ({found_str}). "
            f"Confidence reflects strength of structural evidence."
        )
        signals.append(
            ArchitectureSignal(
                pattern_name=pattern_name,
                confidence=round(confidence, 1),
                explanation=explanation,
            )
        )

    # MVC Pattern
    mvc_dirs = {"views", "controllers", "models", "templates", "view", "controller", "model"}
    _emit("MVC Pattern", mvc_dirs.intersection(all_dirs), 30.0, 15.0, "dir")

    # Service Layer Pattern
    service_indicators = {"services", "repositories", "service", "repository", "repos"}
    found_service = service_indicators.intersection(all_dirs)
    if not found_service:
        found_service = {ind for ind in service_indicators if any(ind in f for f in all_filenames)}
    _emit("Service Layer Pattern", found_service, 40.0, 15.0, "dir")

    # Clean / Layered Architecture
    clean_indicators = {"entities", "usecases", "infrastructure", "presentation", "domain", "core"}
    _emit("Clean/Layered Architecture", clean_indicators.intersection(all_dirs), 35.0, 15.0, "dir")

    # Feature-Based Layout
    feature_indicators = {"features", "modules", "feature", "module"}
    _emit("Feature-Based Layout", feature_indicators.intersection(all_dirs), 50.0, 15.0, "dir")

    return signals

def detect_constraints(analyses: List[FileAnalysis]) -> Dict[str, Tuple[str, str]]:
    """
    Detect existing subsystem constraints to avoid duplication.
    Returns dict mapping system name -> (file_path, details).
    """
    constraints = {}
    
    for a in analyses:
        path_lower = a.path.lower()
        
        # Email provider
        if "email" in path_lower or "mailer" in path_lower or "sendgrid" in path_lower or "smtp" in path_lower:
            if "email" not in constraints:
                constraints["Email System"] = (a.path, "Email sending logic or utilities observed.")
                
        # Token utilities
        if "jwt" in path_lower or "token" in path_lower or "jwt_auth" in path_lower:
            if "token" not in constraints:
                constraints["Token System"] = (a.path, "JWT or token utility modules observed.")

        # Authentication
        if "auth" in path_lower or "login" in path_lower or "session" in path_lower:
            # Skip test files if possible to find core
            if "test" not in path_lower or "auth" not in constraints:
                constraints["Authentication System"] = (a.path, "Authentication middleware or routes observed.")

        # Storage
        if "storage" in path_lower or "upload" in path_lower or "s3" in path_lower or "blob" in path_lower:
            if "storage" not in constraints:
                constraints["Storage System"] = (a.path, "File storage or upload utilities observed.")
                
    return constraints

def detect_file_entry_point(analysis: FileAnalysis, base_path: Path) -> Optional[Tuple[float, str]]:
    """
    Detect if a file is a probable subsystem entry point.
    Returns (confidence, why_explanation) if it is, else None.
    """
    confidence = 0.0
    reasons = []
    
    # 1. Symbol checks
    symbol_names = {s.name for s in analysis.symbols}
    symbol_types = {s.symbol_type for s in analysis.symbols}
    
    if "main" in symbol_names:
        confidence += 40.0
        reasons.append("main() function")
    if any(s.startswith("cmd_") for s in symbol_names):
        confidence += 35.0
        reasons.append("command registration and dispatch logic (cmd_*)")
    if "run" in symbol_names or "do_run" in symbol_names:
        confidence += 25.0
        reasons.append("run/do_run methods")
    if any(t == "decorator" and s in {"command", "click", "typer"} for s, t in zip(symbol_names, symbol_types)):
        confidence += 35.0
        reasons.append("CLI command decorator(s)")
        
    # 2. Import checks
    import_names = {imp.lower() for imp in analysis.imports}
    if any(k in import_names for k in ["argparse", "fire", "click", "typer", "commander"]):
        confidence += 30.0
        reasons.append("CLI/argument parser utility imports")

    # 3. Read file content for heuristics
    file_abs = base_path / analysis.path
    if file_abs.exists():
        try:
            content = file_abs.read_text(encoding="utf-8", errors="ignore")
            if "__main__" in content:
                confidence += 45.0
                reasons.append("__main__ execution block")
            if "app.get(" in content or "app.post(" in content or "router.get(" in content:
                confidence += 40.0
                reasons.append("Express route definitions")
            if "createRoot(" in content or "ReactDOM.render(" in content:
                confidence += 40.0
                reasons.append("React application mount points")
            if "commander" in content or ".command(" in content:
                confidence += 35.0
                reasons.append("commander CLI definitions")
        except Exception:
            pass

    if confidence > 0:
        confidence = min(95.0, confidence)
        # Clean up why string to sound natural and match specs
        if "command registration and dispatch logic (cmd_*)" in reasons:
            why = "Contains command registration and dispatch logic."
        elif "__main__ execution block" in reasons and "main() function" in reasons:
            why = "Contains main() function and __main__ execution block."
        else:
            why = "Contains " + ", ".join(reasons) + "."
        return confidence, why

    return None
