"""
DELIBERATE VIOLATION: Hardcoded Subjects

This file contains INTENTIONAL violations of WAXPREP-HARD-001
to test that our detectors catch them.

DO NOT USE THIS CODE IN PRODUCTION!
"""

# Violation: Hardcoded subject list
SUBJECTS = ["Anatomy", "Biology", "Chemistry", "Physics", "Mathematics"]

# Violation: Hardcoded subject dictionary
SUBJECT_CODES = {
    "BIO101": "Biology 101",
    "CHEM202": "Chemistry 202",
    "PHYS301": "Physics 301",
}

# Violation: Hardcoded subject set
AVAILABLE_SUBJECTS = {"Anatomy", "Biology", "Chemistry"}

# Violation: Subject in conditional
if subject in SUBJECTS:
    print(f"{subject} is a valid subject")

# Violation: Hardcoded subject check
def is_valid_subject(subject_name):
    return subject_name in SUBJECTS

# Violation: Subject classification
def classify_subject(subject):
    if subject == "Anatomy":
        return "Medical"
    elif subject == "Biology":
        return "Life Science"
    elif subject == "Chemistry":
        return "Physical Science"
    return "Unknown"
