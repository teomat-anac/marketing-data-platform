from decimal import Decimal

from mdp_api.service import PCT_PLACES, _round


def test_a_change_that_rounds_to_zero_is_not_negative() -> None:
    # 29,999 vs 30,000 sessions: -0.0000333 rounds to 0, never to -0.0
    shown = _round(Decimal(-1) / Decimal(30000), PCT_PLACES)
    assert shown == 0
    assert str(shown) == "0.0"
