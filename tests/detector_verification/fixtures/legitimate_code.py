"""
LEGITIMATE CODE: Should NOT be flagged

This file contains code that SHOULD PASS all architectural checks.
It demonstrates legitimate patterns that are allowed.
"""

# ✅ ALLOWED: Technical configuration
CONFIG = {
    "max_message_length": 4096,
    "timeout_seconds": 30,
    "retry_attempts": 3,
}

# ✅ ALLOWED: Security permissions
PERMISSIONS = {
    "admin": ["read", "write", "delete"],
    "user": ["read", "write"],
    "guest": ["read"],
}

# ✅ ALLOWED: Generic student ID management
class StudentId:
    """Student identifier (not educational data)."""
    value: str

# ✅ ALLOWED: Account management
def get_student_record(student_id: StudentId):
    """Get student record by ID (not educational classification)."""
    # In reality, this would fetch from database
    return {"id": student_id.value, "name": "John Doe"}

# ✅ ALLOWED: Data validation
def validate_message_length(message: str) -> bool:
    """Validate message length (not educational decision)."""
    return len(message) <= CONFIG["max_message_length"]

# ✅ ALLOWED: Error messages (non-educational)
def get_validation_error():
    """Return validation error (not educational content)."""
    return "Message is too long. Maximum length is 4096 characters."

# ✅ ALLOWED: System status messages
def get_system_status():
    """Return system status (not educational content)."""
    return "System is operational"

# ✅ ALLOWED: Conditional based on technical properties
if CONFIG["max_message_length"] > 4000:
    print("Large message limit configured")

# ✅ ALLOWED: Type checking
def process_student(student_id):
    if not isinstance(student_id, StudentId):
        raise TypeError("Expected StudentId")
    return get_student_record(student_id)
