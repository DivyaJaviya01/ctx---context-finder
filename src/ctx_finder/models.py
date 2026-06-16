from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any

@dataclass
class Symbol:
    name: str
    symbol_type: str  # 'function', 'class', 'method', 'import', 'decorator', 'route', 'export'
    line: int
    source: str       # file path as string

@dataclass
class FileAnalysis:
    path: str
    language: str
    size: int
    mtime: float
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)

@dataclass
class MatchResult:
    file_path: str
    score: float
    confidence: float  # 0.0 to 100.0
    explanations: List[str] = field(default_factory=list)

@dataclass
class ArchitectureSignal:
    pattern_name: str
    confidence: float  # 0.0 to 100.0
    explanation: str

@dataclass
class RiskReport:
    risk_level: str    # 'High', 'Medium', 'Low'
    confidence: float  # 0.0 to 100.0
    explanation: str
    mitigations: List[str] = field(default_factory=list)

@dataclass
class ImplementationPlan:
    steps: List[str]
    complexity: str    # 'Low', 'Medium', 'High'
    dependencies: List[str] = field(default_factory=list)
    guidance: List[str] = field(default_factory=list)

@dataclass
class ContextPack:
    query: str
    matches: List[MatchResult] = field(default_factory=list)
    architecture_signals: List[ArchitectureSignal] = field(default_factory=list)
    risks: List[RiskReport] = field(default_factory=list)
    plan: List[str] = field(default_factory=list)
    conventions: List[str] = field(default_factory=list)
    why_summary: str = ""
