"""
AST Analysis Rules for Detecting Hardcoded Educational Patterns

Each rule examines the Abstract Syntax Tree (AST) of Python code
to detect patterns that violate WaxPrep's architectural principles.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class Severity(Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFORMATIONAL = "informational"


@dataclass
class Violation:
    """Represents a detected architectural violation."""
    rule_id: str
    rule_name: str
    line: int
    column: int
    message: str
    severity: Severity
    evidence: str
    file: str = ""
    suggestion: str = ""
    
    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity.value,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
        }


class BaseASTRule:
    """Base class for AST analysis rules."""
    
    rule_id: str = ""
    rule_name: str = ""
    severity: Severity = Severity.WARNING
    description: str = ""
    
    def __init__(self):
        if not self.rule_id or not self.rule_name:
            raise ValueError("Rule must have an ID and name")
    
    def visit(self, node: ast.AST) -> Optional[Violation]:
        """Visit an AST node and return a violation if detected."""
        raise NotImplementedError
    
    def get_violations(self, tree: ast.AST, file: str) -> List[Violation]:
        """Traverse the AST and collect all violations."""
        violations = []
        for node in ast.walk(tree):
            violation = self.visit(node)
            if violation:
                # Set the file on the violation
                violation.file = file
                violations.append(violation)
        return violations


class HardcodedStringsRule(BaseASTRule):
    """
    Detects conditional branching based on fixed educational strings.
    
    Rule: WAXPREP-HARD-005
    Severity: BLOCKING
    
    Detects patterns like:
    - if "anatomy" in message:
    - if message == "biology":
    - elif subject in ["Chemistry", "Physics"]:
    """
    
    rule_id = "WAXPREP-HARD-005"
    rule_name = "no_educational_conditional_branching"
    severity = Severity.BLOCKING
    description = "No conditional branching on educational strings"
    
    # Educational keywords to detect
    EDUCATIONAL_KEYWORDS = {
        # Subjects
        "anatomy", "biology", "chemistry", "physics", "mathematics",
        "science", "history", "geography", "literature", "art",
        "music", "pe" , "physical education",
        
        # Student levels
        "beginner", "intermediate", "advanced",
        "ss1", "ss2", "ss3", "sss1", "sss2", "sss3",
        "jss1", "jss2", "jss3", "primary", "secondary",
        "undergraduate", "postgraduate", "phd",
        
        # Teaching methods
        "explanation", "lecture", "tutorial", "quiz", "test",
        "exam", "assignment", "homework", "exercise",
        
        # Educational contexts
        "class", "lesson", "chapter", "topic", "subject",
        "curriculum", "syllabus", "grade", "score", "mark",
    }
    
    def visit(self, node: ast.AST) -> Optional[Violation]:
        # Check if-elif-else statements
        if isinstance(node, (ast.If, ast.IfExp)):
            # Check test condition
            test_str = ast.unparse(node.test) if hasattr(ast, 'unparse') else str(node.test)
            return self._check_condition(test_str, node.lineno, node.col_offset)
        
        # Check comparisons
        if isinstance(node, ast.Compare):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant):
                    value = str(comparator.value).lower()
                    if value in self.EDUCATIONAL_KEYWORDS:
                        return Violation(
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            line=node.lineno,
                            column=node.col_offset,
                            message=f"Educational string '{comparator.value}' used in comparison",
                            severity=self.severity,
                            evidence=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                            suggestion="Use AI model for educational intent detection instead"
                        )
        
        return None
    
    def _check_condition(self, condition: str, line: int, col: int) -> Optional[Violation]:
        """Check if a condition contains educational keywords."""
        condition_lower = condition.lower()
        
        for keyword in self.EDUCATIONAL_KEYWORDS:
            if keyword in condition_lower:
                # Check if it's a string literal
                if ('"' + keyword + '"' in condition_lower or 
                    "'" + keyword + "'" in condition_lower or
                    keyword in condition_lower.split()):
                    return Violation(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        line=line,
                        column=col,
                        message=f"Educational keyword '{keyword}' used in conditional",
                        severity=self.severity,
                        evidence=condition,
                        suggestion="Use AI model for educational intent detection instead"
                    )
        return None


class HiddenDictionaryRule(BaseASTRule):
    """
    Detects dictionaries that may contain educational knowledge.
    
    Rule: WAXPREP-HARD-006
    Severity: BLOCKING
    
    Detects patterns like:
    - SUBJECTS = {"anatomy": "Anatomy", ...}
    - TOPICS = {"bio101": "Biology 101", ...}
    
    Only flags dictionaries with suspicious variable names OR
    dictionaries containing educational keywords in values.
    """
    
    rule_id = "WAXPREP-HARD-006"
    rule_name = "no_hidden_educational_dictionaries"
    severity = Severity.BLOCKING
    description = "No dictionaries containing educational knowledge"
    
    EDUCATIONAL_KEYWORDS = HardcodedStringsRule.EDUCATIONAL_KEYWORDS
    
    # Dictionary name patterns that suggest educational content
    SUSPICIOUS_DICT_NAMES = {
        "subjects", "topics", "levels", "grades", "courses",
        "lessons", "chapters", "modules", "units",
        "teaching", "learning", "educational", "curriculum",
        "syllabus", "student", "class", "school",
    }
    
    # Safe keywords that should NOT trigger violations
    SAFE_KEYWORDS = {
        "operation", "status", "error", "message", "code",
        "details", "config", "settings", "timeout", "retry",
        "limit", "value", "name", "id", "type", "data",
        "result", "response", "request", "context", "info",
    }
    
    def visit(self, node: ast.AST) -> Optional[Violation]:
        # Check variable assignments with dict values
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    
                    # Check if variable name is suspicious
                    if any(keyword in var_name for keyword in self.SUSPICIOUS_DICT_NAMES):
                        # Check if value is a dict
                        if isinstance(node.value, ast.Dict):
                            return Violation(
                                rule_id=self.rule_id,
                                rule_name=self.rule_name,
                                line=node.lineno,
                                column=node.col_offset,
                                message=f"Suspicious dictionary variable name: '{target.id}'",
                                severity=self.severity,
                                evidence=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                                suggestion="Rename variable or move educational data to AI model"
                            )
                    
                    # Check dict keys and values for educational keywords
                    if isinstance(node.value, ast.Dict):
                        for key, value in zip(node.value.keys, node.value.values):
                            key_str = ast.unparse(key) if hasattr(ast, 'unparse') else str(key)
                            val_str = ast.unparse(value) if hasattr(ast, 'unparse') else str(value)
                            
                            # Skip if it's a safe keyword
                            key_lower = key_str.lower()
                            val_lower = val_str.lower()
                            
                            if any(safe in key_lower for safe in self.SAFE_KEYWORDS):
                                continue
                            if any(safe in val_lower for safe in self.SAFE_KEYWORDS):
                                continue
                            
                            if any(kw in key_str.lower() for kw in self.EDUCATIONAL_KEYWORDS) or \
                               any(kw in val_str.lower() for kw in self.EDUCATIONAL_KEYWORDS):
                                return Violation(
                                    rule_id=self.rule_id,
                                    rule_name=self.rule_name,
                                    line=node.lineno,
                                    column=node.col_offset,
                                    message=f"Dictionary contains educational keyword",
                                    severity=self.severity,
                                    evidence=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                                    suggestion="Remove educational data from dictionary or use AI model"
                                )
        
        return None


class HardcodedResponseRule(BaseASTRule):
    """
    Detects functions that return hardcoded educational responses.
    
    Rule: WAXPREP-HARD-004
    Severity: BLOCKING
    
    Detects patterns like:
    - def greet(): return "Welcome to WaxPrep"
    - def explain(): return "Anatomy is..."
    
    Only flags responses that contain educational keywords AND are in
    functions with suspicious names.
    """
    
    rule_id = "WAXPREP-HARD-004"
    rule_name = "no_hardcoded_responses"
    severity = Severity.BLOCKING
    description = "No hardcoded educational responses"
    
    EDUCATIONAL_KEYWORDS = HardcodedStringsRule.EDUCATIONAL_KEYWORDS
    
    # Function names that suggest educational responses
    SUSPICIOUS_FUNCTION_NAMES = {
        "greet", "welcome", "explain", "teach", "tutor",
        "respond", "answer", "reply", "help", "assist",
        "describe", "define", "clarify", "summarize",
    }
    
    # Non-educational keywords that should NOT trigger violations
    SAFE_KEYWORDS = {
        "system", "status", "operational", "ready", "error",
        "success", "failed", "complete", "processing", "valid",
        "invalid", "permission", "access", "authentication",
        "authorization", "database", "connection", "timeout",
        "retry", "limit", "maximum", "minimum", "configuration",
    }
    
    def visit(self, node: ast.AST) -> Optional[Violation]:
        # Check function definitions
        if isinstance(node, ast.FunctionDef):
            func_name = node.name.lower()
            
            # Only check functions with suspicious names
            if not any(keyword in func_name for keyword in self.SUSPICIOUS_FUNCTION_NAMES):
                return None
            
            # Check if function returns a string literal
            for stmt in node.body:
                if isinstance(stmt, ast.Return):
                    if isinstance(stmt.value, ast.Constant):
                        if isinstance(stmt.value.value, str):
                            value = str(stmt.value.value).lower()
                            
                            # Skip if it's a safe (non-educational) response
                            if any(safe_kw in value for safe_kw in self.SAFE_KEYWORDS):
                                continue
                            
                            # Check if it's an educational response
                            if len(value) > 20:  # Long enough to be educational
                                if any(kw in value for kw in self.EDUCATIONAL_KEYWORDS):
                                    return Violation(
                                        rule_id=self.rule_id,
                                        rule_name=self.rule_name,
                                        line=stmt.lineno,
                                        column=stmt.col_offset,
                                        message=f"Hardcoded educational response in function '{node.name}'",
                                        severity=self.severity,
                                        evidence=ast.unparse(stmt) if hasattr(ast, 'unparse') else str(stmt),
                                        suggestion="Use AI model to generate response dynamically"
                                    )
            
            # Check all return statements for educational keywords
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                    if isinstance(stmt.value.value, str):
                        value = str(stmt.value.value).lower()
                        
                        # Skip if it's a safe response
                        if any(safe_kw in value for safe_kw in self.SAFE_KEYWORDS):
                            continue
                        
                        if any(kw in value for kw in self.EDUCATIONAL_KEYWORDS):
                            return Violation(
                                rule_id=self.rule_id,
                                rule_name=self.rule_name,
                                line=stmt.lineno,
                                column=stmt.col_offset,
                                message=f"Hardcoded educational string in function '{node.name}'",
                                severity=self.severity,
                                evidence=ast.unparse(stmt) if hasattr(ast, 'unparse') else str(stmt),
                                suggestion="Use AI model to generate content dynamically"
                            )
        
        return None


class EducationalConditionalRule(BaseASTRule):
    """
    Detects complex conditional logic that may indicate educational decision-making.
    
    Rule: WAXPREP-HARD-005 (Extended)
    Severity: BLOCKING
    
    Detects patterns like:
    - if-elif chains with educational conditions
    - match-case statements with educational subjects
    """
    
    rule_id = "WAXPREP-HARD-005-EXT"
    rule_name = "no_complex_educational_conditionals"
    severity = Severity.BLOCKING
    description = "No complex conditional logic for educational decisions"
    
    EDUCATIONAL_KEYWORDS = HardcodedStringsRule.EDUCATIONAL_KEYWORDS
    
    def visit(self, node: ast.AST) -> Optional[Violation]:
        # Check if-elif chains
        if isinstance(node, ast.If):
            # Count educational keywords in the entire if-elif chain
            educational_count = 0
            current = node
            
            while current:
                test_str = ast.unparse(current.test) if hasattr(ast, 'unparse') else str(current.test)
                educational_count += sum(1 for kw in self.EDUCATIONAL_KEYWORDS if kw in test_str.lower())
                current = current.orelse[0] if current.orelse and isinstance(current.orelse[0], ast.If) else None
            
            # If we have multiple educational conditionals in a chain
            if educational_count >= 2:
                return Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Complex educational conditional chain detected ({educational_count} educational conditions)",
                    severity=self.severity,
                    evidence=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                    suggestion="Simplify using AI model for intent detection"
                )
        
        # Check match-case statements (Python 3.10+)
        if hasattr(ast, 'Match') and isinstance(node, ast.Match):
            subject_str = ast.unparse(node.subject) if hasattr(ast, 'unparse') else str(node.subject)
            educational_count = sum(1 for kw in self.EDUCATIONAL_KEYWORDS if kw in subject_str.lower())
            
            if educational_count > 0:
                return Violation(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Match statement on educational subject: {node.subject}",
                    severity=self.severity,
                    evidence=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                    suggestion="Use AI model for pattern matching instead"
                )
        
        return None


# Registry of all rules
AST_RULES = [
    HardcodedStringsRule(),
    HiddenDictionaryRule(),
    HardcodedResponseRule(),
    EducationalConditionalRule(),
]


def get_rule_by_id(rule_id: str) -> Optional[BaseASTRule]:
    """Get a rule by its ID."""
    for rule in AST_RULES:
        if rule.rule_id == rule_id:
            return rule
    return None


def get_all_rules() -> List[BaseASTRule]:
    """Get all AST rules."""
    return AST_RULES
