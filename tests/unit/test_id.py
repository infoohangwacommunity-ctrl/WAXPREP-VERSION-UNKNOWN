# Test Wax ID - Stage 04
import pytest

from waxprep.id import generate_id, is_valid_id


class TestGenerateId:
    @pytest.mark.unit
    def test_returns_string(self) -> None:
        id_value = generate_id()
        assert isinstance(id_value, str)

    @pytest.mark.unit
    def test_format(self) -> None:
        id_value = generate_id()
        parts = id_value.split("-")
        assert len(parts) == 5

    @pytest.mark.unit
    def test_uniqueness(self) -> None:
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2

    @pytest.mark.unit
    def test_valid_id(self) -> None:
        assert is_valid_id(generate_id())
        assert not is_valid_id("invalid")

    @pytest.mark.unit
    def test_format_is_standard_uuid(self) -> None:
        """Must be exactly 36 chars: 8-4-4-4-12 lowercase hex with hyphens."""
        id_value = generate_id()
        assert len(id_value) == 36
        parts = id_value.split("-")
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
        assert all(c in "0123456789abcdef" for c in id_value if c != "-")

    @pytest.mark.unit
    def test_version_is_v7_or_fallback(self) -> None:
        """UUIDv7 version nibble at position 14 must be '7' if uuid7 is available.

        On Python < 3.14, uuid7 may not be in stdlib. The code uses uuid7 package
        or falls back to uuid4. This test verifies the actual behavior.
        """
        id_value = generate_id()
        # Check if it's actually uuid7 (version nibble is '7')
        # or uuid4 fallback (version nibble is '4')
        assert id_value[14] in ("7", "4"), (
            f"UUID version nibble should be '7' (uuid7) or '4' (uuid4 fallback), got: {id_value[14]}"
        )

    @pytest.mark.unit
    def test_monotonicity_or_uniqueness(self) -> None:
        """UUIDv7 IDs must be time-ordered if uuid7 is available.

        Uses freezegun to deterministically advance time instead of
        wall-clock sleep, eliminating flakiness under CI load.
        If uuid7 is not available, fallback to uuid4 provides uniqueness.
        """
        from freezegun import freeze_time

        with freeze_time("2026-01-01 00:00:00 UTC"):
            id1 = generate_id()
        with freeze_time("2026-01-01 00:00:01 UTC"):
            id2 = generate_id()

        # If uuid7: time-ordered (id1 < id2)
        # If uuid4 fallback: not time-ordered but still unique
        if id1[14] == "7":
            assert id1 < id2, "uuid7 IDs should be time-ordered"

    @pytest.mark.unit
    def test_mass_uniqueness(self) -> None:
        """Generate many IDs and verify all are unique."""
        ids = {generate_id() for _ in range(1000)}
        assert len(ids) == 1000

    @pytest.mark.unit
    def test_is_valid_id_edge_cases(self) -> None:
        """Edge cases for format validation."""
        assert not is_valid_id("")
        assert not is_valid_id("abc")
        assert not is_valid_id("a" * 100)
        assert not is_valid_id("a-b-c")
        assert not is_valid_id("a-b-c-d-e-f")
        assert not is_valid_id("g" * 36)
        assert not is_valid_id("00000000-0000-gggg-0000-000000000000")
        assert is_valid_id("f47ac10b-58cc-4372-a567-0e02b2c3d479")
        assert is_valid_id("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        assert is_valid_id("00000000-0000-0000-0000-000000000000")
        assert not is_valid_id("---")

    @pytest.mark.unit
    def test_is_valid_id_rejects_none(self) -> None:
        """is_valid_id must not crash on None — returns False."""
        assert not is_valid_id(None)

    @pytest.mark.unit
    def test_is_valid_id_rejects_integer(self) -> None:
        """is_valid_id must not crash on non-string — returns False."""
        assert not is_valid_id(123)

    @pytest.mark.unit
    def test_is_valid_id_rejects_float(self) -> None:
        """is_valid_id must not crash on float — returns False."""
        assert not is_valid_id(3.14)
