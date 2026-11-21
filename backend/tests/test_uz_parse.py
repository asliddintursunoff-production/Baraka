from decimal import Decimal

import pytest

from apps.ai.uz_parse import looks_like_purchase, parse_amounts, parse_count, parse_percent

M = Decimal(1_000_000)


@pytest.mark.parametrize(
    ("text", "amounts"),
    [
        ("25 million so'mga jihoz olsam", [25 * M]),
        ("25 mln", [25 * M]),
        ("25 millionga oborudovaniye", [25 * M]),
        ("10 millionlik remont", [10 * M]),
        ("Yigirma besh million so'mga yangi jihoz olsam", [25 * M]),
        ("olti million ikki yuz ming", [Decimal(6_200_000)]),
        ("4 350 000 so'm", [Decimal(4_350_000)]),
        ("4,350,000", [Decimal(4_350_000)]),
        ("4.350.000", [Decimal(4_350_000)]),
        ("4,35 mln", [Decimal(4_350_000)]),
        ("2,5 млн рублей", [Decimal(2_500_000)]),
        ("500 ming so'm", [Decimal(500_000)]),
        ("Kassada 48 million turibdi, 10 millionlik remont", [48 * M, 10 * M]),
        ("3 oyga bo'lib to'lasam", []),
        ("2 ta xodim olsam", []),
    ],
)
def test_parse_amounts(text, amounts):
    assert parse_amounts(text) == amounts


def test_percent_and_count():
    assert parse_percent("Savdo 20% kamaysa") == Decimal(20)
    assert parse_percent("savdo 15 foiz tushsa") == Decimal(15)
    assert parse_percent("hech narsa") is None
    assert parse_count("Yana 2 ta xodim olsam") == 2
    assert parse_count("yana ikki ta xodim") == 2
    assert parse_count("3 nafar ofitsiant") == 3


@pytest.mark.parametrize(
    ("text", "yes"),
    [
        ("25 million so'mga jihoz olsam, oylikka yetadimi?", True),
        ("Agar yangi jihoz uchun 25 million so'm sarflasam", True),
        ("sotib olsam 12 mln", True),
        ("Hozir qancha pulim bor?", False),
        ("Agro Go'shtga doim 15 kun kechiktirib to'laymiz", False),
    ],
)
def test_looks_like_purchase(text, yes):
    assert looks_like_purchase(text) is yes
