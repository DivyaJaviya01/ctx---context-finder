from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from ctx_finder.models import MatchResult, FileAnalysis, Symbol
from ctx_finder.semantic import normalize_tokens, expand_query

def rank_files(
    analyses: List[FileAnalysis],
    query: str,
    base_path: Optional[Path] = None
) -> List[MatchResult]:
    """
    Rank files based on query keyword, symbol, directory, and dependency matches.
    """
    raw_query_tokens = normalize_tokens(query)
    expanded_tokens = expand_query(query)
    
    if not raw_query_tokens:
        return []

    # Map file path to analyses for dependency checking
    path_to_analysis = {a.path: a for a in analyses}
    
    # Pre-calculate module names for imports checking
    # e.g., "auth/jwt.py" -> module name "auth.jwt" or "jwt"
    file_modules: Dict[str, List[str]] = {}
    for a in analyses:
        p = Path(a.path)
        stem = p.stem
        # Generate possible module import names
        modules = [stem]
        parts = p.with_suffix("").parts
        if len(parts) > 1:
            modules.append(".".join(parts))
            modules.append("/".join(parts))
        file_modules[a.path] = modules

    results: List[MatchResult] = []
    
    # Maximum possible score for 1 query token
    # exact filename (20) + exact symbol (15) + directory (3) + import (5) = 43
    max_score_per_token = 43.0
    max_possible_score = len(raw_query_tokens) * max_score_per_token

    for a in analyses:
        score = 0.0
        explanations: List[str] = []
        
        rel_path = Path(a.path)
        path_str = a.path.lower()
        stem_lower = rel_path.stem.lower()
        
        # Basename stem tokens
        stem_tokens = normalize_tokens(rel_path.stem)
        
        # Parent directory names
        parent_parts = [p.lower() for p in rel_path.parent.parts]
        
        # Match Query Tokens
        matched_tokens = set()
        
        # Check matching against expanded query tokens
        for q_tok in expanded_tokens:
            is_expanded = q_tok not in raw_query_tokens
            source_label = "expanded synonym" if is_expanded else "query token"
            
            # 1. Filename matches
            if q_tok == stem_lower or q_tok in stem_tokens:
                score += 20.0
                matched_tokens.add(q_tok)
                explanations.append(f"Exact match in filename for {source_label} '{q_tok}' (+20)")
            elif q_tok in stem_lower:
                score += 10.0
                matched_tokens.add(q_tok)
                explanations.append(f"Substring match in filename for {source_label} '{q_tok}' (+10)")
                
            # 2. Symbol matches
            symbol_exacts = []
            symbol_substrings = []
            for sym in a.symbols:
                sym_name_lower = sym.name.lower()
                sym_tokens = normalize_tokens(sym.name)
                if q_tok == sym_name_lower or q_tok in sym_tokens:
                    symbol_exacts.append(sym.name)
                elif q_tok in sym_name_lower:
                    symbol_substrings.append(sym.name)
            
            if symbol_exacts:
                score += 15.0
                matched_tokens.add(q_tok)
                explanations.append(f"Exact match in symbol(s) {', '.join(symbol_exacts[:2])} for {source_label} '{q_tok}' (+15)")
            elif symbol_substrings:
                score += 8.0
                matched_tokens.add(q_tok)
                explanations.append(f"Substring match in symbol(s) {', '.join(symbol_substrings[:2])} for {source_label} '{q_tok}' (+8)")

            # 3. Directory matches
            if any(q_tok in part for part in parent_parts):
                score += 3.0
                matched_tokens.add(q_tok)
                explanations.append(f"Match in parent directory '{rel_path.parent}' for {source_label} '{q_tok}' (+3)")

            # 4. Dependency matches: imports matching query token
            matching_imports = [imp for imp in a.imports if q_tok in imp.lower()]
            if matching_imports:
                score += 5.0
                matched_tokens.add(q_tok)
                explanations.append(f"Import '{matching_imports[0]}' matches {source_label} '{q_tok}' (+5)")

        # 5. Dependency matches: check if other files import this file
        importers = []
        my_modules = file_modules.get(a.path, [])
        for other_path, other_analysis in path_to_analysis.items():
            if other_path == a.path:
                continue
            # Check if other file imports any of my module names
            for imp in other_analysis.imports:
                if any(my_mod in imp or imp in my_mod for my_mod in my_modules):
                    importers.append(other_path)
                    break
        if importers:
            score += 5.0
            explanations.append(f"Imported by {', '.join(importers[:2])} (+5)")

        # If no query/expanded tokens matched, don't include
        if not matched_tokens:
            continue

        # 6. Test file penalty: -2
        if "tests/" in path_str or "test_" in path_str or "/test_" in path_str:
            score -= 2.0
            explanations.append("Test file penalty (-2)")

        if score > 0:
            # Confidence rating based on raw score ratio
            confidence = min(100.0, max(10.0, (score / max_possible_score) * 100.0))
            results.append(
                MatchResult(
                    file_path=a.path,
                    score=score,
                    confidence=round(confidence, 1),
                    explanations=explanations
                )
            )

    # Sort descending by score, then alphabetically
    results.sort(key=lambda r: (-r.score, r.file_path))
    return results
