from decimal import Decimal

import pytest

from app.xtb.classify import Classified, classify


def test_stock_purchase_parses_quantity_and_price() -> None:
    assert classify("Stock purchase", "OPEN BUY 2.5 @ 500.50") == Classified("buy", Decimal("2.5"), Decimal("500.50"))


def test_stock_sale_parses_partial_close() -> None:
    assert classify("Stock sale", "CLOSE BUY 5/10 @ 130.00") == Classified("sell", Decimal("5"), Decimal("130.00"))


def test_purchase_with_unexpected_comment_is_unknown() -> None:
    assert classify("Stock purchase", "coś innego").type == "unknown"


@pytest.mark.parametrize(
    ("xtb_type", "comment", "expected"),
    [
        ("Deposit", "Adyen BLIK deposit, id=1", "deposit"),
        ("IKE deposit", "PAYU deposit", "deposit"),
        ("Withdrawal", "", "withdrawal"),
        ("DIVIDENT", "VIE.FR USD 0.5/ SHR", "dividend"),
        ("Dividend", "", "dividend"),
        ("Withholding tax", "", "withholding_tax"),
        ("Free-funds Interest", "", "interest"),
        ("Free-funds Interest Tax", "", "interest_tax"),
        ("SEC fee", "", "fee"),
        ("Coś zupełnie nowego", "", "unknown"),
        ("", "", "unknown"),
    ],
)
def test_types_are_mapped_case_insensitively(xtb_type: str, comment: str, expected: str) -> None:
    assert classify(xtb_type, comment).type == expected
    assert classify(xtb_type.upper(), comment).type == expected


@pytest.mark.parametrize(
    ("comment", "expected_type"),
    [
        ("Transfer out operation on account with id 56216965", "transfer_out"),
        ("Transfer in operation on account with id 56204082", "transfer_in"),
    ],
)
def test_internal_transfers_carry_counterparty(comment: str, expected_type: str) -> None:
    result = classify("IKE deposit", comment)

    assert result.type == expected_type
    assert result.counterparty_account == comment.rsplit(" ", 1)[1]


@pytest.mark.parametrize(
    "comment",
    [
        "OPEN BUY 2.5 @ 1,500.50",
        "OPEN BUY 1,000 @ 5.00",
        "CLOSE BUY 5/10 @ 1,300.00",
        "OPEN BUY 2.5 @ 500.5.1",
    ],
)
def test_partially_parsed_numbers_are_unknown(comment: str) -> None:
    assert classify("Stock purchase", comment).type == "unknown"


def test_valid_numbers_with_trailing_whitespace_separated_text() -> None:
    result = classify("Stock purchase", "OPEN BUY 2 @ 500.5 EUR")
    assert result.type == "buy"
    assert result.quantity == Decimal("2")
    assert result.price == Decimal("500.5")
