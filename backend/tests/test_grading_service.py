from app.services.grading_service import grade_moneyline, grade_spread


def test_moneyline_grading() -> None:
    assert grade_moneyline(0.6, 21, 17) == "WIN"
    assert grade_moneyline(0.6, 17, 21) == "LOSS"
    assert grade_moneyline(0.6, 21, 21) == "PUSH"


def test_spread_grading_supports_win_loss_and_push() -> None:
    assert grade_spread(6, -3, 7) == "WIN"
    assert grade_spread(6, -3, 2) == "LOSS"
    assert grade_spread(6, -3, 3) == "PUSH"
