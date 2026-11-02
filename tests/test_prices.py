"""Pure price helpers (offline)."""
import pytest

from maid.prices import close_on, split_factor_after, total_return


def test_close_on():
    c = {"2025-03-28": 10.0, "2025-03-31": 11.0}
    assert close_on(c, "2025-03-31") == ("2025-03-31", 11.0)
    assert close_on(c, "2025-04-01") == ("2025-03-31", 11.0)
    assert close_on(c, "2025-03-30") == ("2025-03-28", 10.0)


def test_close_on_too_old():
    with pytest.raises(ValueError):
        close_on({"2025-03-01": 1.0}, "2025-03-31")


def test_split_factor_after():
    assert split_factor_after({"2024-06-10": 10.0, "2025-06-01": 2.0, "2026-01-05": 3.0}, "2025-03-31") == 6.0


def test_total_return():
    assert total_return({"2025-03-31": 100.0, "2026-03-31": 120.0}, "2025-04-01", "2026-03-31") == pytest.approx(0.2)
