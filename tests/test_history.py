from datetime import date
from fractions import Fraction


def test_real_ecb_cross_rate_replay_preserves_gaps_and_quote_direction():
    from settlement_recon.history import load_archive, replay

    archive = load_archive()
    result = replay(archive, "USD", "INR", date(2025, 1, 1), date(2025, 1, 7))
    assert [row["date"] for row in result["observations"]] == [
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
        "2025-01-07",
    ]
    jan2, _, jan6, _ = result["observations"]
    assert Fraction(jan2["numerator"], jan2["denominator"]) == Fraction("88.507") / Fraction(
        "1.0321"
    )
    assert jan2["change_percent"] is None
    assert jan6["days_since_previous"] == 3
    assert result["source"]["publication_dates"] == 7128


def test_archive_and_query_fail_closed():
    import pytest

    from settlement_recon.history import load_archive, parse_archive, replay

    with pytest.raises(ValueError, match="fingerprint"):
        parse_archive(b"invalid", "0" * 64)
    archive = load_archive()
    with pytest.raises(ValueError, match="366"):
        replay(archive, "USD", "INR", date(2020, 1, 1), date(2025, 1, 1))
    with pytest.raises(ValueError, match="currency"):
        replay(archive, "ZZZ", "INR", date(2025, 1, 1), date(2025, 1, 7))
    with pytest.raises(ValueError, match="No observations"):
        replay(archive, "RUB", "EUR", date(2025, 1, 1), date(2025, 1, 7))
