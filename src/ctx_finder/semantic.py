import re
from typing import List, Dict, Set

TASK_STOPWORDS: Set[str] = {
    # task-action verbs (stripped before ranking/expansion)
    "add", "new", "create", "implement", "build",
    "update", "modify", "change", "refactor",
    "improve", "fix", "make", "support",
    "enable", "allow", "introduce", "extend",
    "convert", "replace", "remove", "delete",
    "rewrite",
    # generic noise
    "bug", "issue",
    # articles / prepositions
    "how", "to", "the", "a", "an", "in", "on", "for", "of",
}

# Keep backward-compat alias
STOPWORDS = TASK_STOPWORDS

SEMANTIC_MAP: Dict[str, List[str]] = {
    "auth": ["jwt", "oauth", "token", "session", "credentials", "login", "signin", "logout", "signout", "password"],
    "authentication": ["auth", "jwt", "oauth", "token", "session", "credentials"],
    "authorization": ["auth", "oauth", "permission", "access"],
    "repository": ["repo"],
    "repositories": ["repo", "repository"],
    "provider": ["model", "llm", "backend"],
    "login": ["auth", "authentication", "signin", "oauth"],
    "logout": ["signout", "session"],
    "payment": ["billing", "checkout", "stripe", "invoice", "payment", "card", "transaction", "subscription"],
    "cache": ["redis", "ttl", "memory", "cache", "caching", "store"],
    "database": ["sql", "orm", "repository", "query", "db", "postgres", "mysql", "sqlite", "model", "migration"],
    "api": ["route", "controller", "endpoint", "url", "http", "request", "response", "handler"],
    "test": ["tests", "pytest", "unittest", "mock", "assert"],
}

def normalize_tokens(text: str) -> List[str]:
    """
    Split text into lowercase alphanumeric tokens and remove stopwords.
    """
    tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS]

def expand_query(query: str) -> List[str]:
    """
    Normalize query tokens and expand them with synonyms from SEMANTIC_MAP.
    """
    normalized = normalize_tokens(query)
    expanded = list(normalized)
    
    for token in normalized:
        # Check direct mapping
        if token in SEMANTIC_MAP:
            for syn in SEMANTIC_MAP[token]:
                if syn not in expanded:
                    expanded.append(syn)
        # Check reverse mapping (if query token is in value list of mapping, add key)
        for key, synonyms in SEMANTIC_MAP.items():
            if token in synonyms:
                if key not in expanded:
                    expanded.append(key)
                for syn in synonyms:
                    if syn not in expanded:
                        expanded.append(syn)
                        
    return expanded
