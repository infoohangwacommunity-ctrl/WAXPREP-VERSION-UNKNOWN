"""
Fake Model Adapter - Stage 02
ONLY for testing registry. NOT a real model implementation.
"""


class FakeModelAdapter:
    """Fake model adapter. Proves registry architecture works."""

    name = "fake"

    async def generate(self, prompt: str) -> str:
        """Fake generator. Returns fake response."""
        return f"Fake response to: {prompt[:50]}..."
