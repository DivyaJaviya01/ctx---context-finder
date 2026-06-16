from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from ctx_finder.models import ImplementationPlan, RiskReport, FileAnalysis, MatchResult

# --------------------------------------------------------------------------- #
#  Plan Generation                                                             #
# --------------------------------------------------------------------------- #

def generate_plan(matched_results: List[MatchResult], analyses: List[FileAnalysis]) -> ImplementationPlan:
    """
    Generate an implementation plan ordering files from lower dependency to higher
    (Models -> Services -> Controllers -> Tests).
    Visible sequence is capped at 10 steps.
    """
    matched_paths = {r.file_path for r in matched_results}

    models: List[str] = []
    services: List[str] = []
    controllers: List[str] = []
    tests: List[str] = []
    others: List[str] = []

    for r in matched_results:
        p_str = r.file_path.lower()
        if "test" in p_str or "spec" in p_str:
            tests.append(r.file_path)
        elif any(k in p_str for k in ["model", "db", "schema", "entity"]):
            models.append(r.file_path)
        elif any(k in p_str for k in ["service", "repository", "repo", "logic"]):
            services.append(r.file_path)
        elif any(k in p_str for k in ["controller", "route", "view", "api", "endpoint"]):
            controllers.append(r.file_path)
        else:
            others.append(r.file_path)

    ordered_files = models + services + others + controllers + tests

    steps = []
    for idx, f in enumerate(ordered_files, start=1):
        if f in models:
            action = "Define data schemas/models"
        elif f in services:
            action = "Implement business logic / repositories"
        elif f in controllers:
            action = "Expose APIs / view controllers"
        elif f in tests:
            action = "Verify functionality via unit tests"
        else:
            action = "Update components"
        steps.append(f"{idx}. {action} in: {f}")

    complexity = "Low"
    if len(ordered_files) > 5:
        complexity = "High"
    elif len(ordered_files) > 2:
        complexity = "Medium"

    guidance = [
        "Models: Implement first to establish database schemas and data shapes.",
        "Services: Bind business rules and validation to the models.",
        "Controllers: Keep routes thin and delegate complex operations to services.",
        "Tests: Verify behaviors and prevent regression before deploying.",
    ]

    return ImplementationPlan(
        steps=steps,
        complexity=complexity,
        dependencies=list(matched_paths),
        guidance=guidance,
    )


# --------------------------------------------------------------------------- #
#  Risk Evaluation (Fix 4/5 – improved heuristics)                            #
# --------------------------------------------------------------------------- #

# Infrastructure-heavy domains that always deserve elevated risk scoring
_INFRA_PATTERNS: List[Tuple[str, str, str]] = [
    # (keyword_set_as_frozenset_str, risk_level, domain_label)
    ("auth|login|jwt|token|password|session|cookie|security|crypto|credential|oauth", "High", "Authentication/Security"),
    ("payment|billing|stripe|invoice|checkout|card|transaction|wallet|payout", "High", "Billing/Payment"),
    ("migration|migrate|schema|alembic|flyway|liquibase|alter_table", "High", "Database Migration"),
    ("db|sql|database|orm|repository|repo|persist|table", "Medium", "Database Persistence"),
    ("config|settings|env|secret|dotenv|vault", "Medium", "Configuration/Secrets"),
    ("deploy|ci|cd|pipeline|infra|terraform|docker|kubernetes|k8s|helm", "Medium", "Infrastructure/Deployment"),
]


def _score_file_risk(file_path: str) -> Optional[Tuple[str, str, str]]:
    """Return (risk_level, domain_label, file_path) for a file, or None."""
    p_str = file_path.lower()
    basename = Path(file_path).name.lower()

    for pattern_str, risk_level, domain in _INFRA_PATTERNS:
        keywords = set(pattern_str.split("|"))
        if any(kw in p_str or kw in basename for kw in keywords):
            return risk_level, domain, file_path
    return None


def evaluate_risks(matched_results: List[MatchResult]) -> List[RiskReport]:
    """
    Evaluate risk levels based on files impacted by the task.
    Improved heuristics: infrastructure-heavy tasks (Auth, DB, Provider, Migration)
    are scored higher, and the explanation names concrete files/domains.
    """
    if not matched_results:
        return []

    high_risk: List[Tuple[str, str]] = []   # (file_path, domain)
    med_risk:  List[Tuple[str, str]] = []

    for r in matched_results:
        fp = r.file_path
        fp_lower = fp.lower()
        # Skip test files — they match auth/db keywords but aren't production code.
        # Risk should be driven by the production files being modified.
        is_test = (
            "/test_" in fp_lower or "test_" in fp_lower.split("/")[-1]
            or "tests/" in fp_lower or "\\tests\\" in fp_lower
            or fp_lower.startswith("test_")
        )
        if is_test:
            continue
        result = _score_file_risk(fp)
        if result:
            risk_level, domain, matched_fp = result
            if risk_level == "High":
                high_risk.append((matched_fp, domain))
            else:
                med_risk.append((matched_fp, domain))

    reports: List[RiskReport] = []

    if high_risk:
        details = "; ".join(f"{fp} [{domain}]" for fp, domain in high_risk[:3])
        confidence = min(92.0, 75.0 + len(high_risk) * 5.0)
        reports.append(
            RiskReport(
                risk_level="High",
                confidence=round(confidence, 1),
                explanation=f"Modifying critical infrastructure files: {details}.",
                mitigations=[
                    "Isolate credential management; verify tokens and secrets are not logged.",
                    "Ensure all existing unit tests covering this domain pass before merging.",
                    "Review access control and authorization checks after changes.",
                    "Perform a security review if authentication or payment logic is modified.",
                ],
            )
        )

    if med_risk and not high_risk:
        details = "; ".join(f"{fp} [{domain}]" for fp, domain in med_risk[:3])
        confidence = min(88.0, 65.0 + len(med_risk) * 5.0)
        reports.append(
            RiskReport(
                risk_level="Medium",
                confidence=round(confidence, 1),
                explanation=f"Modifying persistence, configuration, or deployment files: {details}.",
                mitigations=[
                    "Validate schema compatibility for rolling updates.",
                    "Verify rollback scripts exist prior to running migrations.",
                    "Review config changes against all deployment environments.",
                ],
            )
        )

    if med_risk and high_risk:
        # Surface medium-risk supplemental note
        med_details = "; ".join(f"{fp} [{domain}]" for fp, domain in med_risk[:2])
        reports.append(
            RiskReport(
                risk_level="Medium",
                confidence=70.0,
                explanation=f"Additional medium-risk files affected: {med_details}.",
                mitigations=[
                    "Review config and persistence changes alongside high-risk items.",
                ],
            )
        )

    if not reports:
        reports.append(
            RiskReport(
                risk_level="Low",
                confidence=70.0,
                explanation="Standard codebase features targeted. No infrastructure-heavy signals detected.",
                mitigations=["Confirm functionality through local test suite execution."],
            )
        )

    return reports


# --------------------------------------------------------------------------- #
#  Senior Guidance                                                             #
# --------------------------------------------------------------------------- #

def generate_senior_guidance(matched_results: List[MatchResult]) -> List[str]:
    """Produce senior engineer recommendations."""
    guidelines = [
        "Always reuse existing abstractions instead of creating duplicates.",
        "Write tests matching the package conventions (unit files in tests/ matching source hierarchy).",
    ]
    matched_stems = [Path(r.file_path).stem.lower() for r in matched_results]
    if any("controller" in stem for stem in matched_stems):
        guidelines.append(
            "Advice: Ensure controllers are thin. Business logic belongs in the service layer."
        )
    if any("service" in stem or "repository" in stem for stem in matched_stems):
        guidelines.append(
            "Advice: Business logic should not perform direct database ORM transactions inside loop queries."
        )
    return guidelines


# --------------------------------------------------------------------------- #
#  Strategy Generation                                                         #
# --------------------------------------------------------------------------- #

def generate_strategy(
    query: str, matched_results: List[MatchResult], analyses: List[FileAnalysis]
) -> str:
    """
    Generate a repository-aware strategy based on matched files, query intent,
    and conventions.
    """
    query_lower = query.lower()

    # 1. Identify query domain
    provider_kws = {"provider", "llm", "backend", "openai", "anthropic", "gemini", "client", "model"}
    auth_kws = {"auth", "login", "signup", "user", "jwt", "token", "session", "permission", "security", "credentials"}
    db_kws = {"database", "db", "sql", "query", "orm", "repository", "repo", "migration", "save", "persist", "schema", "table"}
    api_kws = {"api", "route", "endpoint", "controller", "http", "request", "response", "views", "handler"}

    domain = None
    if any(kw in query_lower for kw in provider_kws):
        domain = "provider"
    elif any(kw in query_lower for kw in auth_kws):
        domain = "auth"
    elif any(kw in query_lower for kw in db_kws):
        domain = "db"
    elif any(kw in query_lower for kw in api_kws):
        domain = "api"

    # 2. Collect domain-relevant files
    domain_file_keywords = {
        "provider": {"provider", "model", "registry", "backend", "llm", "client"},
        "auth": {"auth", "login", "user", "jwt", "token", "session", "permission", "security", "credentials"},
        "db": {"db", "sql", "orm", "repository", "repo", "migration", "schema", "database", "table"},
        "api": {"api", "route", "endpoint", "controller", "views", "handler"},
    }

    relevant_core_files: List[str] = []
    relevant_test_files: List[str] = []

    if domain:
        kws = domain_file_keywords[domain]
        for r in matched_results:
            p_str = r.file_path.lower()
            is_test = "/test_" in p_str or "test_" in p_str or "tests/" in p_str
            if any(kw in p_str for kw in kws):
                if is_test:
                    relevant_test_files.append(r.file_path)
                else:
                    relevant_core_files.append(r.file_path)

    # 3. Calculate confidence
    confidence = 50.0
    if domain:
        confidence = 55.0
        if relevant_core_files:
            confidence += 15.0
        if relevant_test_files:
            confidence += 10.0
        confidence = min(95.0, confidence)

    # 4. Repository-aware output (>= 60%) or generic fallback
    if confidence >= 60.0 and domain:
        core_files_str = ", ".join(relevant_core_files[:2])
        test_file = relevant_test_files[0] if relevant_test_files else "tests/"

        domain_templates = {
            "provider": {
                "header": "[+] Provider-related components detected.",
                "suggested": [
                    f"Reuse existing provider/model abstractions in {relevant_core_files[0]}.",
                    (
                        f"Register the provider through the existing registry or selection logic in {relevant_core_files[1]}."
                        if len(relevant_core_files) > 1
                        else f"Register the new provider following patterns in {relevant_core_files[0]}."
                    ),
                    "Extend provider selection and client loading tests.",
                    "Validate compatibility with LLM request/response formatting.",
                ],
                "risks": ["* Avoid duplicating model connection or API client logic."],
                "testing": [f"* Update provider tests in {test_file}."],
                "why": f"Provider registration symbols and conventions detected: {core_files_str}.",
            },
            "auth": {
                "header": "[+] Authentication/Security components detected.",
                "suggested": [
                    f"Leverage existing authentication mechanism in {relevant_core_files[0]}.",
                    (
                        f"Implement new access control checks consistent with {relevant_core_files[1]}."
                        if len(relevant_core_files) > 1
                        else f"Implement access control checks following conventions in {relevant_core_files[0]}."
                    ),
                    "Validate input parameters and sanitize credentials.",
                    "Ensure session state is handled securely.",
                ],
                "risks": ["* Ensure sensitive data or credentials are not logged or exposed."],
                "testing": [f"* Add test cases in {test_file} to verify unauthorized access is blocked."],
                "why": f"Authentication or security-related files detected: {core_files_str}.",
            },
            "db": {
                "header": "[+] Database persistence components detected.",
                "suggested": [
                    f"Define or update data models in {relevant_core_files[0]}.",
                    (
                        f"Query database through the existing repository or abstraction layer in {relevant_core_files[1]}."
                        if len(relevant_core_files) > 1
                        else f"Query database following repository patterns in {relevant_core_files[0]}."
                    ),
                    "Create standard database migration scripts if schema changes.",
                    "Keep database transactions transaction-safe and handle rollbacks.",
                ],
                "risks": ["* Avoid writing raw SQL queries; reuse the ORM or repository layers."],
                "testing": [f"* Ensure persistence tests in {test_file} verify rollback and commit behavior."],
                "why": f"Database model, schema, or persistence files detected: {core_files_str}.",
            },
            "api": {
                "header": "[+] API routing or controller layers detected.",
                "suggested": [
                    f"Define new HTTP endpoint/route following existing patterns in {relevant_core_files[0]}.",
                    (
                        f"Delegate business logic to the service layer (e.g. {relevant_core_files[1]})."
                        if len(relevant_core_files) > 1
                        else "Delegate business logic from controller to service layer."
                    ),
                    "Validate incoming request payloads.",
                    "Standardize success and error HTTP response formats.",
                ],
                "risks": ["* Keep controllers/handlers thin; do not mix business logic with routing."],
                "testing": [f"* Add HTTP mock tests in {test_file} to verify response status codes."],
                "why": f"API endpoint, routing, or request handling files detected: {core_files_str}.",
            },
        }

        tmpl = domain_templates[domain]
        out = f"Existing Systems:\n{tmpl['header']}\n\n"
        out += "Relevant Files:\n"
        for f in relevant_core_files[:2]:
            out += f"* {f}\n"
        out += "\nSuggested Approach:\n"
        for idx, step in enumerate(tmpl["suggested"], start=1):
            out += f"{idx}. {step}\n"
        out += "\nRisks:\n"
        for r in tmpl["risks"]:
            out += f"{r}\n"
        out += "\nTesting Guidance:\n"
        for t in tmpl["testing"]:
            out += f"{t}\n"
        out += f"\nConfidence:\n{int(confidence)}%\n"
        out += f"\nWhy:\n{tmpl['why']}"
        return out

    # Generic fallback
    out = "Repository-specific guidance could not be confidently generated.\n\n"
    out += "Suggested Approach:\n"
    out += "1. Analyze existing code structure and design patterns.\n"
    out += "2. Reuse existing utility functions and helpers.\n"
    out += "3. Implement changes following file structure conventions.\n"
    out += "4. Write corresponding unit tests.\n\n"
    out += "Risks:\n"
    out += "* Avoid adding redundant dependencies.\n"
    out += "* Prevent regressions by checking existing test coverage.\n\n"
    out += "Testing Guidance:\n"
    out += "* Add tests mirroring the folder layout.\n\n"
    out += "Confidence:\n50%\n\n"
    out += "Why:\nNo repository-specific domain components matched with sufficient confidence (minimum 60% required)."
    return out


# --------------------------------------------------------------------------- #
#  Validate Guardrail (Fix 1)                                                  #
# --------------------------------------------------------------------------- #

def build_validate_report(
    query: str,
    matched_results: List[MatchResult],
    analyses: List[FileAnalysis],
    constraints: Dict,
) -> str:
    """
    Build an AI guardrail report: aggregates risk, strategy, and constraint
    detection into a single actionable warning summary.
    Returns a formatted string ready to print.
    """
    query_lower = query.lower()
    lines: List[str] = []

    # --- Section 1: Existing System Conflicts / Assumptions ---
    lines.append("Assumptions & Existing System Conflicts:")

    # Auth
    if any(kw in query_lower for kw in ["auth", "login", "signup", "jwt", "session", "token", "permission"]):
        if "Authentication System" in constraints:
            fp = constraints["Authentication System"][0]
            lines.append(f"  [OK]  Authentication system exists: {fp}")
            lines.append("         -> Reuse it. Do NOT create a parallel auth mechanism.")
        else:
            lines.append("  [!]   No authentication system detected in repository.")
            lines.append("         -> You may need to design one from scratch.")

    # Token
    if any(kw in query_lower for kw in ["token", "jwt"]):
        if "Token System" in constraints:
            fp = constraints["Token System"][0]
            lines.append(f"  [OK]  Token/JWT utility exists: {fp}")
            lines.append("         -> Reuse token logic; avoid custom token generation.")
        else:
            lines.append("  [!]   No token utility class detected.")
            lines.append("         -> Reuse auth sessions if possible, or add a minimal JWT helper.")

    # Email
    if any(kw in query_lower for kw in ["email", "mail", "mailer"]):
        if "Email System" in constraints:
            fp = constraints["Email System"][0]
            lines.append(f"  [OK]  Email service exists: {fp}")
        else:
            lines.append("  [!]   No email provider detected.")
            lines.append("         -> Ensure an email library or SMTP config is in place before implementing.")

    # Storage
    if any(kw in query_lower for kw in ["upload", "file", "storage", "s3", "blob"]):
        if "Storage System" in constraints:
            fp = constraints["Storage System"][0]
            lines.append(f"  [OK]  Storage abstraction exists: {fp}")
        else:
            lines.append("  [!]   No storage abstraction detected.")
            lines.append("         -> Choose a storage backend before implementing upload logic.")

    if len(lines) == 1:
        # No constraint keywords matched — provide a generic note
        lines.append("  No specific system conflicts detected for this query.")

    # --- Section 2: Risk Warnings ---
    risks = evaluate_risks(matched_results)
    lines.append("")
    lines.append("Risk Assessment:")
    for r in risks:
        lines.append(f"  [{r.risk_level}] (Confidence: {r.confidence}%)")
        lines.append(f"         {r.explanation}")
        for m in r.mitigations[:2]:
            lines.append(f"         -> {m}")

    # --- Section 3: Common AI Mistakes for this domain ---
    lines.append("")
    lines.append("Common AI Mistakes to Avoid:")

    warned = False
    if any(kw in query_lower for kw in ["auth", "login", "jwt", "token", "session"]):
        lines.append("  * Do not log sensitive tokens, passwords, or credentials anywhere.")
        lines.append("  * Do not reinvent auth middleware if one already exists in the repository.")
        lines.append("  * Do not hardcode secrets; use environment variables or a secrets manager.")
        warned = True
    if any(kw in query_lower for kw in ["provider", "llm", "model", "openai", "anthropic"]):
        lines.append("  * Do not duplicate provider client initialization; reuse the existing registry.")
        lines.append("  * Validate API key configuration before making requests.")
        warned = True
    if any(kw in query_lower for kw in ["database", "db", "sql", "migration", "schema"]):
        lines.append("  * Always back up production data before running migrations.")
        lines.append("  * Do not write raw SQL outside the ORM or query-builder layer.")
        lines.append("  * Test rollback scripts before deploying schema changes.")
        warned = True
    if any(kw in query_lower for kw in ["api", "endpoint", "route", "http"]):
        lines.append("  * Validate and sanitize all incoming request parameters.")
        lines.append("  * Return consistent HTTP status codes and error formats.")
        warned = True
    if not warned:
        lines.append("  * Reuse existing abstractions. Do not create duplicate utility modules.")
        lines.append("  * Follow file structure and naming conventions visible in this repository.")

    # --- Section 4: Strategy Quick Summary ---
    if matched_results:
        strategy_text = generate_strategy(query, matched_results, analyses)
        # Extract just the "Suggested Approach" block to keep output concise
        if "Suggested Approach:" in strategy_text:
            approach_start = strategy_text.index("Suggested Approach:")
            # Cut at the next blank section
            approach_block = strategy_text[approach_start:]
            next_section = approach_block.find("\n\n", 20)
            if next_section != -1:
                approach_block = approach_block[:next_section]
            lines.append("")
            lines.append("Suggested Modification Order:")
            lines.append(approach_block.replace("Suggested Approach:\n", "").strip())

    lines.append("")
    lines.append("Validation complete.")
    return "\n".join(lines)
