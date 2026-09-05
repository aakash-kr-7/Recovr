from app.utils.money import format_inr, paise_to_inr


def test_paise_to_inr():
    assert paise_to_inr(150000) == 1500.0
    assert paise_to_inr(199) == 1.99


def test_format_inr_small_amount():
    assert format_inr(500.0) == "\u20b9500.00"


def test_format_inr_indian_grouping():
    assert format_inr(1234567.5) == "\u20b912,34,567.50"


def test_format_inr_negative():
    assert format_inr(-250.0) == "-\u20b9250.00"
