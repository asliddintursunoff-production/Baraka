from datetime import date
from decimal import Decimal

import pytest

from apps.ai import uz_format as f

M = f.MINUS


@pytest.mark.parametrize(
    ("n", "words"),
    [
        (0, "nol"),
        (1, "bir"),
        (15, "o'n besh"),
        (100, "yuz"),
        (1_000, "bir ming"),
        (2_500_000, "ikki million besh yuz ming"),
        (6_200_000, "olti million ikki yuz ming"),
        (18_800_000, "o'n sakkiz million sakkiz yuz ming"),
        (63_500_000, "oltmish uch million besh yuz ming"),
        (-6_200_000, "minus olti million ikki yuz ming"),
        (-15, "minus o'n besh"),
        (40, "qirq"),
        (99, "to'qson to'qqiz"),
        (101, "yuz bir"),
        (110_000, "yuz o'n ming"),
        (1_001_000, "bir million bir ming"),
        (2_000_000_000, "ikki milliard"),
    ],
)
def test_number_words(n, words):
    assert f.uz_number_words(n) == words


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (0, "0,0 mln"),
        (1, "0,0 mln"),
        (2_500_000, "2,5 mln"),
        (6_200_000, "6,2 mln"),
        (6_185_000, "6,2 mln"),
        (18_815_000, "18,8 mln"),
        (12_255_000, "12,3 mln"),
        (63_500_000, "63,5 mln"),
        (45_000_000, "45,0 mln"),
        (-6_185_000, f"{M}6,2 mln"),
        (-7_504_000, f"{M}7,5 mln"),
        (Decimal("-6200000.00"), f"{M}6,2 mln"),
    ],
)
def test_format_mln(amount, text):
    assert f.format_mln(amount) == text


def test_format_mln_signed_and_short():
    assert f.format_mln(18_800_000, signed=True) == "+18,8 mln"
    assert f.format_mln(-6_200_000, signed=True) == f"{M}6,2 mln"
    assert f.format_mln(0, signed=True) == "0,0 mln"
    assert f.format_mln(22_000_000, short=True) == "22 mln"
    assert f.format_mln(8_000_000, short=True) == "8 mln"
    assert f.format_mln(18_500_000, short=True) == "18,5 mln"


def test_format_mln_number_and_som():
    assert f.format_mln_number(48_200_000) == "48,2"
    assert f.format_mln_number(196_400_000) == "196,4"
    assert f.format_som(4_350_000) == "4\u00a0350\u00a0000 so'm"
    assert f.format_som(-1_000) == f"{M}1\u00a0000 so'm"
    assert f.group_digits(2104) == "2\u00a0104"


def test_float_is_rejected():
    with pytest.raises(TypeError):
        f.format_mln(6.2)


@pytest.mark.parametrize(
    ("amount", "spoken"),
    [
        (-6_185_000, "minus olti million ikki yuz ming so'm"),
        (18_815_000, "o'n sakkiz million sakkiz yuz ming so'm"),
        (8_000_000, "sakkiz million so'm"),
        (2_100_000, "ikki million yuz ming so'm"),
        (850_400, "sakkiz yuz ellik ming so'm"),
        (0, "nol so'm"),
    ],
)
def test_speech_amount(amount, spoken):
    assert f.speech_amount(amount) == spoken


def test_floor_to():
    assert f.floor_to(Decimal("8815000"), 1_000_000) == Decimal("8000000")
    assert f.floor_to(Decimal("-200000"), 1_000_000) == Decimal("-1000000")


@pytest.mark.parametrize(
    ("n", "ordinal"),
    [
        (1, "birinchi"),
        (2, "ikkinchi"),
        (3, "uchinchi"),
        (4, "to'rtinchi"),
        (6, "oltinchi"),
        (7, "yettinchi"),
        (9, "to'qqizinchi"),
        (10, "o'ninchi"),
        (12, "o'n ikkinchi"),
        (20, "yigirmanchi"),
        (21, "yigirma birinchi"),
        (30, "o'ttizinchi"),
        (31, "o'ttiz birinchi"),
    ],
)
def test_ordinals(n, ordinal):
    assert f.uz_ordinal_words(n) == ordinal


def test_dates():
    assert f.uz_ordinal_date(date(2026, 12, 10)) == "o'ninchi dekabr"
    assert f.uz_ordinal_date(date(2027, 1, 12)) == "o'n ikkinchi yanvar"
    assert f.uz_ordinal_date(date(2026, 12, 10), "da") == "o'ninchi dekabrda"
    assert f.format_date(date(2026, 12, 10)) == "10-dekabr"
    assert f.format_date(date(2026, 12, 10), "da") == "10-dekabrda"
    assert f.format_date(date(2026, 12, 10), "ga") == "10-dekabrga"
    assert f.format_date(date(2026, 12, 10), "gacha") == "10-dekabrgacha"
    assert f.format_date(date(2027, 1, 12), "dan") == "12-yanvardan"
    assert f.format_date_short(date(2026, 11, 25)) == "25-noy"
    assert f.format_date_long(date(2026, 11, 21)) == "21-noyabr, shanba"


def test_all_month_names():
    names = [f.format_date(date(2026, m, 1)) for m in range(1, 13)]
    assert names == [
        "1-yanvar",
        "1-fevral",
        "1-mart",
        "1-aprel",
        "1-may",
        "1-iyun",
        "1-iyul",
        "1-avgust",
        "1-sentyabr",
        "1-oktyabr",
        "1-noyabr",
        "1-dekabr",
    ]


def test_case_suffix_consonant_assimilation():
    assert f.add_case("bank", "ga") == "bankka"
    assert f.add_case("Agro Go'sht", "ga") == "Agro Go'shtga"
    assert f.add_case("qishloq", "gacha") == "qishloqqacha"
