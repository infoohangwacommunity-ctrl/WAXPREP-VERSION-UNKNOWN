"""
DELIBERATE VIOLATION: Hardcoded Responses

This file contains INTENTIONAL violations of WAXPREP-HARD-004
to test that our detectors catch them.

DO NOT USE THIS CODE IN PRODUCTION!
"""

# Violation: Hardcoded greeting
def welcome_student():
    return "Welcome to WaxPrep. How can I help you today?"

# Violation: Hardcoded explanation
def explain_anatomy():
    return "Anatomy is the study of the structure of living things."

# Violation: Hardcoded biology explanation
def explain_biology():
    return "Biology is the study of life and living organisms."

# Violation: Hardcoded help message
def get_help_message():
    return "I can help you with Anatomy, Biology, Chemistry, and Physics."

# Violation: Hardcoded error message with educational content
def get_unsupported_subject_error(subject):
    return f"Sorry, {subject} is not supported. We only support Anatomy, Biology, Chemistry, and Physics."
