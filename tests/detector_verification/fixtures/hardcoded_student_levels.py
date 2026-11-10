"""
DELIBERATE VIOLATION: Hardcoded Student Levels

This file contains INTENTIONAL violations of WAXPREP-HARD-002
to test that our detectors catch them.

DO NOT USE THIS CODE IN PRODUCTION!
"""

# Violation: Hardcoded student levels
STUDENT_LEVELS = ["Beginner", "Intermediate", "Advanced"]

# Violation: Hardcoded Nigerian education levels
NIGERIAN_LEVELS = ["SS1", "SS2", "SS3", "JSS1", "JSS2", "JSS3"]

# Violation: Hardcoded level dictionary
LEVEL_DESCRIPTIONS = {
    "Beginner": "Just starting out",
    "Intermediate": "Has some experience",
    "Advanced": "Expert level",
}

# Violation: Level in conditional
def get_level_description(level):
    if level == "Beginner":
        return LEVEL_DESCRIPTIONS["Beginner"]
    elif level == "Intermediate":
        return LEVEL_DESCRIPTIONS["Intermediate"]
    return "Unknown"

# Violation: Level classification
def classify_student_level(student):
    if student.knowledge_score < 30:
        return "Beginner"
    elif student.knowledge_score < 70:
        return "Intermediate"
    return "Advanced"
