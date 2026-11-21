"""Pure parsing layer of spreadsheet ingestion: normalizers, header detection, heuristics.

Fixtures in backend/fixtures/sheets/*.json are Sheets-style rows ({"title", "rows"}); the
last tests run the same functions over the real messy demo workbook (openpyxl cells).
"""

import json
import pickle
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.ingestion.header import detect_header, header_signature
from apps.ingestion.heuristics import (
    CONFIRM_THRESHOLD,
    FIELDS,
    SHEET_KINDS,
    ColumnGuess,
    MappingGuess,
    guess_mapping,
    header_keyword_hits,
    keyword_field,
    title_kind,
)
from apps.ingestion.normalize import (
    InvalidDate,
    classify_cell,
    clean_name,
    from_serial,
    is_blank,
    name_key,
    parse_amount,
    parse_date,
    parse_day_of_month,
    parse_direction,
    text_key,
    to_latin,
)

TODAY = date(2026, 11, 21)
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sheets"
D = Decimal


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def header_and_data(rows: list[list]) -> tuple[int, list[str], list[list]]:
    h = detect_header(rows)
    assert h is not None
    headers = ["" if c is None else str(c) for c in rows[h]]
    data = [r for r in rows[h + 1 :] if any(not is_blank(c) for c in r)]
    return h, headers, data


def column(name: str, header: str) -> list:
    """All data-row values of one fixture column (ragged rows padded with None)."""
    _, headers, data = header_and_data(load(name)["rows"])
    i = headers.index(header)
    return [r[i] if i < len(r) else None for r in data]


def mapping_of(name: str) -> MappingGuess:
    sheet = load(name)
    _, headers, data = header_and_data(sheet["rows"])
    return guess_mapping(headers, data, title=sheet["title"])


def try_date(value, today: date = TODAY):
    try:
        return parse_date(value, today=today)
    except InvalidDate as exc:
        return ("invalid", exc.suggestion)


# --- parse_amount -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # the formats cafés really type
        ("4 350 000", "4350000"),
        ("4 350 000", "4350000"),  # NBSP
        ("4 350 000", "4350000"),  # narrow NBSP
        ("4 350 000", "4350000"),  # thin space
        ("4,350,000", "4350000"),
        ("4.350.000", "4350000"),
        ("4'350'000", "4350000"),
        ("4350000", "4350000"),
        ("4350000 so'm", "4350000"),
        ("4350000 so‘m", "4350000"),
        ("4350000so'm", "4350000"),
        ("4 350 000 som", "4350000"),
        ("4 350 000 sum", "4350000"),
        ("4 350 000 сўм", "4350000"),
        ("4 350 000 сум", "4350000"),
        ("4 350 000 UZS", "4350000"),
        ("UZS 4 350 000", "4350000"),
        ("4 350 000 (so'm)", "4350000"),
        ("  4 350 000  ", "4350000"),
        ("4 350 000.", "4350000"),
        ("4,35 mln", "4350000"),
        ("4.35 млн", "4350000"),
        ("4,35mln", "4350000"),
        ("4,35 mln so'm", "4350000"),
        ("4,35 млн сўм", "4350000"),
        ("25 mln", "25000000"),
        ("2,5 million", "2500000"),
        ("2,5 миллион", "2500000"),
        ("500 ming", "500000"),
        ("500 минг", "500000"),
        ("500 тыс.", "500000"),
        ("500k", "500000"),
        ("1,2 mlrd", "1200000000"),
        ("1,250 mln", "1250000"),  # with a scale word one separator is always decimal
        # negatives
        ("-4 350 000", "-4350000"),
        ("- 4 350 000", "-4350000"),
        ("−4 350 000", "-4350000"),  # typographic minus
        ("–4 350 000", "-4350000"),  # en dash
        ("(4 350 000)", "-4350000"),  # accounting
        ("(4 350 000 so'm)", "-4350000"),
        ("+4 350 000", "4350000"),
        # decimal vs thousands with a single separator
        ("4,5", "4.5"),
        ("4.5", "4.5"),
        ("4,500", "4500"),
        ("4.500", "4500"),
        ("0,500", "0.5"),
        ("4350,000", "4350"),  # 4 digits before: not a thousands group
        ("4350000.0", "4350000"),
        ("4350000.00", "4350000"),
        ("4 350 000,50", "4350000.50"),
        ("4 350 000.50", "4350000.50"),
        ("4,350,000.50", "4350000.50"),
        ("4.350.000,50", "4350000.50"),
        ("12", "12"),
        ("007", "7"),
        ("0", "0"),
        # Sheets / openpyxl numbers
        (4350000, "4350000"),
        (4350000.0, "4350000"),
        (-4350000, "-4350000"),
        (0.1 + 0.2, "0.30"),  # never binary float arithmetic
        (1234.565, "1234.57"),  # str(1234.565) == "1234.565" -> half-up
        (D("4350000.004"), "4350000.00"),
    ],
)
def test_parse_amount(value, expected):
    result = parse_amount(value)
    assert result == D(expected)
    assert isinstance(result, Decimal)
    assert result.as_tuple().exponent == -2  # always 2 decimals


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        " ",
        "so'm",
        "abc",
        "Jami",
        "12a",
        "4 35 000",  # broken grouping
        "4350 000",
        "+998 90 123 45 67",  # a phone number is not money
        "4,35,000",
        "4.350,000.5",
        "$100",
        "100 rubl",
        "100 USD",
        "20%",
        "2 ta",
        "=SUM(B2:B9)",
        "#REF!",
        "#N/A",
        "14.11.2026",
        "2026-11-14",
        "4 350 000 so'mlik",
        True,
        False,
        float("nan"),
        float("inf"),
        D("NaN"),
        date(2026, 11, 14),
        datetime(2026, 11, 14, 10, 0),
        [4350000],
    ],
)
def test_parse_amount_rejects(value):
    assert parse_amount(value) is None


# --- parse_date -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("14.11.2026", date(2026, 11, 14)),
        ("14/11/2026", date(2026, 11, 14)),
        ("14-11-2026", date(2026, 11, 14)),
        ("2026-11-14", date(2026, 11, 14)),
        ("2026/11/14", date(2026, 11, 14)),
        ("2026.11.14", date(2026, 11, 14)),
        ("4.1.2027", date(2027, 1, 4)),
        ("14.11.26", date(2026, 11, 14)),
        ("  14.11.2026 ", date(2026, 11, 14)),
        ("14.11.2026 10:30", date(2026, 11, 14)),
        ("2026-11-14 00:00:00", date(2026, 11, 14)),
        ("2026-11-14T10:00:00Z", date(2026, 11, 14)),
        ("2026-11-14T10:00:00+05:00", date(2026, 11, 14)),
        ("14.11.2026 y.", date(2026, 11, 14)),
        ("14.11.2026 й.", date(2026, 11, 14)),
        ("11/14/2026", date(2026, 11, 14)),  # unambiguous US order
        # month names: Uzbek Latin, Uzbek Cyrillic, Russian, English
        ("14 noyabr 2026", date(2026, 11, 14)),
        ("14-noyabr", date(2026, 11, 14)),
        ("14-noyabr 2026", date(2026, 11, 14)),
        ("14 noyabr, 2026", date(2026, 11, 14)),
        ("14 Noyabr 2026 yil", date(2026, 11, 14)),
        ("2026 yil 14 noyabr", date(2026, 11, 14)),
        ("2026-yil 14-noyabr", date(2026, 11, 14)),
        ("14 noy 2026", date(2026, 11, 14)),
        ("3 sentyabr 2026", date(2026, 9, 3)),
        ("3 sentabr 2026", date(2026, 9, 3)),
        ("26 mart 2026", date(2026, 3, 26)),
        ("1 may 2026", date(2026, 5, 1)),
        ("14 ноября 2026", date(2026, 11, 14)),
        ("14 ноября 2026 г.", date(2026, 11, 14)),
        ("14 ноября 2026 года", date(2026, 11, 14)),
        ("14 ноября", date(2026, 11, 14)),
        ("14 ноябр", date(2026, 11, 14)),
        ("14 ноябрь 2026", date(2026, 11, 14)),
        ("14-ноябр 2026", date(2026, 11, 14)),
        ("1 января 2027", date(2027, 1, 1)),
        ("8 марта 2026", date(2026, 3, 8)),
        ("9 мая 2026", date(2026, 5, 9)),
        ("10 сентябр 2026", date(2026, 9, 10)),
        ("2 ўктябр 2026", None),  # not a month (ў is not о)
        ("2 октябр 2026", date(2026, 10, 2)),
        ("Nov 14, 2026", date(2026, 11, 14)),
        ("14 November 2026", date(2026, 11, 14)),
        ("november 14 2026", date(2026, 11, 14)),
        # serial numbers (Sheets SERIAL_NUMBER) and date objects (openpyxl)
        (46340, date(2026, 11, 14)),
        (46340.0, date(2026, 11, 14)),
        (46340.75, date(2026, 11, 14)),  # time of day is dropped
        (D("46340"), date(2026, 11, 14)),
        ("46340", date(2026, 11, 14)),
        (25569, date(1970, 1, 1)),
        (20000, date(1954, 10, 3)),
        (80000, date(2119, 1, 11)),
        (date(2026, 11, 14), date(2026, 11, 14)),
        (datetime(2026, 11, 14, 23, 59), date(2026, 11, 14)),
        # empty / garbage
        (None, None),
        ("", None),
        ("   ", None),
        ("hello", None),
        ("Jami", None),
        ("14 foo 2026", None),
        ("13.13.2026", None),
        ("00.11.2026", None),
        ("32.11.2026", None),
        ("14.00.2026", None),
        ("14.11.1850", None),
        ("4350000", None),
        ("4 350 000", None),
        (4350000, None),
        (19999, None),
        (80001, None),
        (2026, None),
        (True, None),
        (float("nan"), None),
        ([2026, 11, 14], None),
    ],
)
def test_parse_date(value, expected):
    assert parse_date(value, today=TODAY) == expected


@pytest.mark.parametrize(
    ("value", "today", "expected"),
    [
        # no year: the year that puts the date nearest to today
        ("14 noyabr", TODAY, date(2026, 11, 14)),
        ("14-noyabr", TODAY, date(2026, 11, 14)),
        ("14 ноября", TODAY, date(2026, 11, 14)),
        ("14.11", TODAY, date(2026, 11, 14)),
        ("20 dekabr", TODAY, date(2026, 12, 20)),
        ("5 yanvar", TODAY, date(2027, 1, 5)),  # 45 days ahead beats 320 days back
        ("5.01", TODAY, date(2027, 1, 5)),
        ("25 may", TODAY, date(2026, 5, 25)),  # 180 back vs 185 ahead
        ("21 may", TODAY, date(2027, 5, 21)),  # 184 back vs 181 ahead
        ("28 dekabr", date(2026, 1, 3), date(2025, 12, 28)),
        ("3 yanvar", date(2026, 12, 30), date(2027, 1, 3)),
        ("29 fevral", date(2027, 11, 21), date(2028, 2, 29)),  # only the leap year fits
        ("1 iyun", TODAY, date(2026, 6, 1)),
    ],
)
def test_parse_date_infers_nearest_year(value, today, expected):
    assert parse_date(value, today=today) == expected


@pytest.mark.parametrize(
    ("value", "suggestion"),
    [
        ("31.11.2026", date(2026, 11, 30)),
        ("31/11/2026", date(2026, 11, 30)),
        ("2026-11-31", date(2026, 11, 30)),
        ("31-11-2026", date(2026, 11, 30)),
        ("30.02.2026", date(2026, 2, 28)),
        ("29.02.2027", date(2027, 2, 28)),
        ("30.02.2028", date(2028, 2, 29)),  # leap year: the 29th is the last day
        ("31.04.2026", date(2026, 4, 30)),
        ("31.09.2026", date(2026, 9, 30)),
        ("31 noyabr 2026", date(2026, 11, 30)),
        ("31 ноября 2026", date(2026, 11, 30)),
        ("31-noyabr", date(2026, 11, 30)),  # no year: nearest year
        ("31 сентября", date(2026, 9, 30)),
        ("29.02", date(2027, 2, 28)),  # no leap year among 2025..2027
    ],
)
def test_parse_date_impossible_day_suggests_last_day(value, suggestion):
    with pytest.raises(InvalidDate) as info:
        parse_date(value, today=TODAY)
    assert info.value.suggestion == suggestion
    assert info.value.text == value.strip()
    assert isinstance(info.value, ValueError)
    assert value in str(info.value)


def test_invalid_date_keeps_the_cleaned_text_and_pickles():
    with pytest.raises(InvalidDate) as info:
        parse_date("  31.11.2026 ", today=TODAY)
    assert info.value.text == "31.11.2026"
    assert info.value.text.split(".")[0] == "31"  # the pipeline shows the day like this
    copy = pickle.loads(pickle.dumps(info.value))
    assert (copy.text, copy.suggestion) == ("31.11.2026", date(2026, 11, 30))


def test_parse_date_requires_today_keyword():
    with pytest.raises(TypeError):
        parse_date("14.11.2026", TODAY)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (46340, date(2026, 11, 14)),
        (46340.99, date(2026, 11, 14)),
        (D("46366"), date(2026, 12, 10)),
        (19999.9, None),
        (80000.5, None),
        (float("inf"), None),
    ],
)
def test_from_serial(value, expected):
    assert from_serial(value) == expected


# --- direction / names / day of month ---------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("kirim", "in"),
        ("Kirim", "in"),
        ("KIRIM", "in"),
        ("kirimlar", "in"),
        ("Kirim (so'm)", "in"),
        ("Kirim summasi", "in"),
        ("кирим", "in"),
        ("tushum", "in"),
        ("daromad", "in"),
        ("Savdo", "in"),
        ("приход", "in"),
        ("Приход", "in"),
        ("доход", "in"),
        ("поступление", "in"),
        ("выручка", "in"),
        ("income", "in"),
        ("Revenue", "in"),
        ("in", "in"),
        ("+", "in"),
        (" + ", "in"),
        ("chiqim", "out"),
        ("Chiqim", "out"),
        ("chiqimlar", "out"),
        ("Chiqim (so'm)", "out"),
        ("чиқим", "out"),
        ("xarajat", "out"),
        ("harajat", "out"),
        ("харажат", "out"),
        ("sarf", "out"),
        ("расход", "out"),
        ("Расходы", "out"),
        ("затраты", "out"),
        ("expense", "out"),
        ("out", "out"),
        ("-", "out"),
        ("−", "out"),
        ("Kirim/chiqim", None),  # names both
        ("приход/расход", None),
        ("Summa", None),
        ("Qoldiq", None),
        ("Jami to'lov", None),
        ("Tushlik", None),  # "lunch", not "tushum"
        ("Naqd", None),
        ("", None),
        (None, None),
        (5, None),
        (-5, None),
        (True, None),
    ],
)
def test_parse_direction(value, expected):
    assert parse_direction(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Agro   Go'sht  ", "Agro Go'sht"),
        ("Agro Go'sht", "Agro Go'sht"),
        ("Agro\tGo'sht\n", "Agro Go'sht"),
        ("Goʻsht", "Go'sht"),  # ʻ
        ("Goʼsht", "Go'sht"),  # ʼ
        ("Go‘sht", "Go'sht"),  # ‘
        ("Go’sht", "Go'sht"),  # ’
        ("Go`sht", "Go'sht"),
        ("Go´sht", "Go'sht"),  # ´
        ("Oʻzbekiston Gʻaznasi", "O'zbekiston G'aznasi"),
        ("Non​ sexi", "Non sexi"),  # zero-width space
        ('"Agro Go\'sht" MChJ', '"Agro Go\'sht" MChJ'),  # quotes are kept for display
        ("Шуҳрат", "Шуҳрат"),
        (None, ""),
        ("", ""),
        (5, "5"),
        (5.0, "5"),
        (5.5, "5.5"),
    ],
)
def test_clean_name(value, expected):
    assert clean_name(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Agro Go'sht", "agro go'sht"),
        ('"Agro Go‘sht" MChJ', "agro go'sht"),
        ("«Agro Go'sht» MChJ", "agro go'sht"),
        ("AGRO GO'SHT XK", "agro go'sht"),
        ("Agro Go'sht mas'uliyati cheklangan jamiyati", "agro go'sht"),
        ("ООО «Агро Гўшт»", "agro go'sht"),
        ("Агро Гўшт МЧЖ", "agro go'sht"),
        ("“Agro Go’sht” LLC", "agro go'sht"),
        ("Шуҳрат Каримов", "shuhrat karimov"),
        ("Ғайрат Қодиров", "g'ayrat qodirov"),
        ("Ёқубжон", "yoqubjon"),
        ("Юлдуз", "yulduz"),
        ("Яшнобод", "yashnobod"),
        ("Цемент Савдо", "tsement savdo"),
        ("Чорсу бозори", "chorsu bozori"),
        ("Елена", "yelena"),  # word-initial е -> ye
        ("Тошкент", "toshkent"),
        ("Таъминот", "ta'minot"),
        ("'Bog' Kafe'", "bog' kafe"),  # quote-like apostrophes go, g' stays
        ("Coca-Cola ichimliklari", "coca cola ichimliklari"),
        ("  Non   sexi ", "non sexi"),
        ("YaTT Karimov", "karimov"),
        ("ИП Каримов", "karimov"),
        ("", ""),
        (None, ""),
    ],
)
def test_name_key(value, expected):
    assert name_key(value) == expected


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ('"Agro Go‘sht" MChJ', "ООО «Агро Гўшт»"),
        ("Agro Goʻsht", "agro go`sht xk"),
        ("Chorsu bozori", "Чорсу бозори"),
        ("Hududgaz", "HUDUDGAZ  "),
        ("Ulug'bek Yo'ldoshev", "Улуғбек Йўлдошев"),
        ("Shuhrat Karimov", "Шуҳрат Каримов"),
    ],
)
def test_name_key_matches_spellings_of_one_counterparty(a, b):
    assert name_key(a) == name_key(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [("Agro Go'sht", "Halol Go'sht"), ("Non sexi", "Non va un"), ("Hududgaz", "Hududgaz 2")],
)
def test_name_key_keeps_different_names_apart(a, b):
    assert name_key(a) != name_key(b)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Шуҳрат", "Shuhrat"),
        ("ЎЗБЕКИСТОН", "O'ZBEKISTON"),
        ("ғалла", "g'alla"),
        ("щётка", "shyotka"),
        ("объект", "ob'yekt"),
        ("Agro", "Agro"),
    ],
)
def test_to_latin(text, expected):
    assert to_latin(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Ф.И.Ш.", "f i sh"),
        ("Ойлик маош (сўм)", "oylik maosh so'm"),
        ("Тўлов куни", "to'lov kuni"),
        ("Naqd/karta", "naqd karta"),
        ("Summa (so'm)", "summa so'm"),
        ("Сумма", "summa"),
    ],
)
def test_text_key(value, expected):
    assert text_key(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", 10),
        (" 10 ", 10),
        (10, 10),
        (10.0, 10),
        ("10.0", 10),
        (D("25"), 25),
        ("har oy 25", 25),
        ("Har oy 25-sanada", 25),
        ("25-sana", 25),
        ("ҳар ой 10-санада", 10),
        ("10-сана", 10),
        ("25 число", 25),
        ("1", 1),
        ("31", 31),
        ("0", None),
        ("32", None),
        (0, None),
        (45, None),
        (10.5, None),
        ("har kuni", None),
        ("10, 25", None),  # twice a month: ambiguous
        ("25.11.2026", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_day_of_month(value, expected):
    assert parse_day_of_month(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "empty"),
        ("", "empty"),
        ("  ", "empty"),
        (True, "bool"),
        (4350000, "number"),
        (46340, "number"),  # a serial or an amount: the column decides
        (4.5, "number"),
        (date(2026, 11, 14), "date"),
        (datetime(2026, 11, 14), "date"),
        ("14.11.2026", "date"),
        ("31.11.2026", "date"),  # impossible, but date-shaped
        ("14 noyabr 2026", "date"),
        ("4 350 000", "amount"),
        ("4,35 mln", "amount"),
        ("10", "amount"),
        ("46340", "amount"),
        ("Sana", "text"),
        ("har oy 25", "text"),
        ("+998 90 123 45 67", "text"),
    ],
)
def test_classify_cell(value, expected):
    assert classify_cell(value) == expected


# --- header detection -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("kirim_header_row3", 2),  # title + blank row above
        ("kassa_qoldiq", 2),
        ("oylik_cyrillic", 1),  # Cyrillic, under a title
        ("nbu_kredit", 1),
        ("kassa_daftari_kirim_chiqim", 1),
        ("chiqim_mixed_dates", 0),
        ("rasxody_duplicates_ru", 0),
        ("taminotchilar", 0),  # mostly text rows, but known header words
        ("transactions_en", 0),
        ("header_only", 1),  # a header and nothing else
        ("izohlar_notes", None),  # notes: no table to map
    ],
)
def test_detect_header_on_fixtures(fixture, expected):
    assert detect_header(load(fixture)["rows"]) == expected


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([], None),
        ([[]], None),
        ([["", None], [None]], None),
        ([["Navro'z Kafe — kirimlar"]], None),  # title only
        ([["Sana", "Summa"]], 0),  # header only
        ([["Kirimlar"], [], ["Sana", "Summa"]], 2),  # header only, under a title
        (
            [["Sana", "Summa", "Izoh"], ["14.11.2026", "4 350 000", "savdo"]],
            0,
        ),
        (
            [[None, None], [None, "Sana", "Summa"], [None, 46340, 4350000]],
            1,
        ),
        (
            # a two-cell title row is not the header
            [
                ["Navro'z Kafe", "Noyabr hisoboti"],
                [],
                ["Sana", "Summa", "Izoh"],
                ["14.11.2026", "4 350 000", "savdo"],
                ["15.11.2026", "4 120 000", "savdo"],
            ],
            2,
        ),
        (
            # ... even when the real header uses words we do not know
            [
                ["Hisobot", "Noyabr"],
                ["Kun", "Pul", "Nima", "Kim"],
                ["14.11.2026", 4350000, "savdo", "Ali"],
                ["15.11.2026", 4120000, "savdo", "Vali"],
            ],
            1,
        ),
        (
            # unknown header words, data below: still the header
            [["Kun", "Pul", "Nima"], ["14.11.2026", 4350000, "savdo"], ["15.11", 1, "x"]],
            0,
        ),
        (
            # all-text two-column notes
            [["Mavzu", "Matn"], ["Gaz", "tekshirish kerak"], ["Ofitsiant", "shartnoma"]],
            None,
        ),
        (
            # data rows only, no header
            [["14.11.2026", "4 350 000"], ["15.11.2026", "4 120 000"]],
            None,
        ),
        (
            # most rows below must carry data; one dated line after notes is not a table
            [["A matn", "B matn"], ["x", "y"], ["z", "w"], ["14.11.2026", "q"]],
            None,
        ),
        (
            # notes, then a real table with a recognizable header
            [
                ["Gaz hisoblagichini tekshirish", "ertaga"],
                ["Shartnoma", "Madina bilan"],
                ["Sana", "Summa", "Izoh"],
                ["14.11.2026", "4 350 000", "savdo"],
                ["15.11.2026", "4 120 000", "savdo"],
            ],
            2,
        ),
        (
            # "key | value" lines above the table are not the header
            [
                ["Kafe nomi", "Navro'z"],
                ["Manzil", "Toshkent"],
                ["Telefon", "+998 90 123 45 67"],
                [],
                ["Sana", "Summa", "Izoh"],
                ["14.11.2026", "4 350 000", "savdo"],
                ["15.11.2026", "4 120 000", "savdo"],
                ["16.11.2026", "3 900 000", "savdo"],
            ],
            4,
        ),
        (
            # a genuine two-column table with unknown words
            [["Kun", "Pul"], ["14.11.2026", 4350000], ["15.11.2026", 4120000]],
            0,
        ),
        (
            # openpyxl cells: datetimes, padded Nones
            [
                ["NBU kredit jadvali", None, None],
                ["To'lov sanasi", "Jami to'lov", None],
                [datetime(2026, 12, 10), 18500000, None],
            ],
            1,
        ),
    ],
)
def test_detect_header_cases(rows, expected):
    assert detect_header(rows) == expected


def test_detect_header_handles_big_sheets_quickly():
    rows = [["Hisobot"], [], ["Sana", "Summa", "Izoh"]]
    rows += [["14.11.2026", f"{i} 000", "savdo"] for i in range(100, 5100)]
    assert detect_header(rows) == 2


def test_header_keyword_hits():
    assert header_keyword_hits(["Sana", "Summa (so'm)", "Izoh", "", None, 5]) == 3
    assert header_keyword_hits(["Navro'z Kafe", "Noyabr hisoboti"]) == 0


def test_header_signature_is_stable_and_normalized():
    base = header_signature(["Sana", "Summa (so'm)", "Izoh"])
    assert len(base) == 64 and int(base, 16) >= 0
    assert base == header_signature(["  sana ", "SUMMA (so‘m)", "Izoh"])
    assert base == header_signature(["Sana", "Summa (so'm)", "Izoh", "", None])  # padding
    assert base == header_signature(("Sana", "Summa (so'm)", "Izoh"))
    assert base != header_signature(["Sana", "Summa", "Izoh"])  # renamed
    assert base != header_signature(["Summa (so'm)", "Sana", "Izoh"])  # moved
    assert base != header_signature(["Sana", "Summa (so'm)", "Izoh", "Kimga"])  # added
    assert base != header_signature(["", "Sana", "Summa (so'm)", "Izoh"])  # shifted right
    assert header_signature([2026, "Sana"]) == header_signature([2026.0, "Sana"])
    assert header_signature([]) == header_signature([None, ""])


def test_header_signature_of_fixtures_differ():
    sigs = set()
    for path in FIXTURES.glob("*.json"):
        rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
        h = detect_header(rows)
        if h is not None:
            sigs.add(header_signature(rows[h]))
    assert len(sigs) == 10


# --- heuristics: fixtures ---------------------------------------------------------------

EXPECTED_MAPPINGS = [
    (
        "kirim_header_row3",
        "transactions_in",
        ["date", "amount", "method", "note"],
    ),
    (
        "chiqim_mixed_dates",
        "transactions_out",
        ["date", "amount", "category", "counterparty", "due_date", "method", "status"],
    ),
    (
        "rasxody_duplicates_ru",
        "transactions_out",
        ["date", "amount", "category", "counterparty", "note"],
    ),
    (
        "kassa_daftari_kirim_chiqim",
        "transactions_mixed",
        ["date", "amount", "amount", "ignore", "note"],
    ),
    (
        "transactions_en",
        "transactions_mixed",
        ["date", "direction", "amount", "category", "note"],
    ),
    (
        "oylik_cyrillic",
        "payroll",
        ["ignore", "counterparty", "note", "amount", "due_date"],
    ),
    (
        "nbu_kredit",
        "loan_schedule",
        ["due_date", "ignore", "ignore", "amount", "ignore"],
    ),
    (
        "taminotchilar",
        "counterparties",
        ["counterparty", "ignore", "due_date", "amount", "note"],
    ),
    ("kassa_qoldiq", "cash_balance", ["date", "amount", "note"]),
    ("header_only", "transactions_out", ["date", "amount", "counterparty", "note"]),
]


@pytest.mark.parametrize(("fixture", "kind", "fields"), EXPECTED_MAPPINGS)
def test_guess_mapping_on_fixtures(fixture, kind, fields):
    guess = mapping_of(fixture)
    assert guess.sheet_kind == kind
    assert guess.kind_confidence >= CONFIRM_THRESHOLD
    assert [c.field for c in guess.columns] == fields
    assert [c.index for c in guess.columns] == list(range(len(fields)))
    for c in guess.columns:
        assert c.field in FIELDS
        assert 0.0 <= c.confidence <= 1.0
        if c.field == "status":
            assert c.confidence < CONFIRM_THRESHOLD  # paid vs planned: always confirm
    assert guess.sheet_kind in SHEET_KINDS


@pytest.mark.parametrize(
    ("fixture", "header", "low", "high"),
    [
        ("chiqim_mixed_dates", "Sana", 0.9, 1.0),
        ("chiqim_mixed_dates", "Summa (so'm)", 0.9, 1.0),
        ("chiqim_mixed_dates", "Kimga", 0.8, 1.0),
        ("chiqim_mixed_dates", "Naqd/karta", 0.8, 1.0),
        ("chiqim_mixed_dates", "Holati", 0.5, 0.79),
        ("oylik_cyrillic", "Ф.И.Ш.", 0.8, 1.0),
        ("oylik_cyrillic", "Ойлик маош (сўм)", 0.9, 1.0),
        ("oylik_cyrillic", "Тўлов куни", 0.8, 1.0),
        ("oylik_cyrillic", "Лавозими", 0.3, 0.79),  # role -> note: please confirm
        ("oylik_cyrillic", "№", 0.9, 1.0),
        ("nbu_kredit", "Jami to'lov", 0.9, 1.0),
        ("nbu_kredit", "Foiz", 0.5, 0.79),
        ("kassa_daftari_kirim_chiqim", "Kirim", 0.8, 1.0),
        ("kassa_daftari_kirim_chiqim", "Qoldiq", 0.8, 1.0),
    ],
)
def test_guess_mapping_confidence(fixture, header, low, high):
    guess = mapping_of(fixture)
    col = next(c for c in guess.columns if c.header == header)
    assert low <= col.confidence <= high


def test_split_kirim_chiqim_columns_carry_their_direction():
    guess = mapping_of("kassa_daftari_kirim_chiqim")
    amounts = [c for c in guess.columns if c.field == "amount"]
    assert [(c.header, c.direction) for c in amounts] == [("Kirim", "in"), ("Chiqim", "out")]
    # the pipeline derives the same direction from the header text
    assert [parse_direction(c.header) for c in amounts] == ["in", "out"]
    assert guess.column_for("note") == ColumnGuess(4, "Izoh", "note", 0.9)
    assert guess.column_for("direction") is None


def test_needs_confirmation_lists_low_columns():
    guess = mapping_of("chiqim_mixed_dates")
    assert [c.header for c in guess.needs_confirmation()] == ["Holati"]
    assert guess.needs_confirmation(threshold=0.0) == []


# --- heuristics: inline cases -----------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("Sana", "date"),
        ("сана", "date"),
        ("Дата", "date"),
        ("Date", "date"),
        ("Summa", "amount"),
        ("Сумма", "amount"),
        ("Сумма (сўм)", "amount"),
        ("Amount", "amount"),
        ("Qoldiq", "amount"),
        ("Остаток", "amount"),
        ("Kirim", "direction"),
        ("Chiqim", "direction"),
        ("Turi", "direction"),
        ("Kirim/chiqim", "direction"),
        ("Nima uchun", "category"),
        ("Kategoriya", "category"),
        ("Статья", "category"),
        ("Xarajat turi", "category"),
        ("Kimga", "counterparty"),
        ("Kontragent", "counterparty"),
        ("Ta'minotchi", "counterparty"),
        ("Ta‘minotchilar", "counterparty"),
        ("Поставщик", "counterparty"),
        ("Ф.И.Ш.", "counterparty"),
        ("ФИО", "counterparty"),
        ("Muddat", "due_date"),
        ("To'lov sanasi", "due_date"),
        ("Срок", "due_date"),
        ("Срок оплаты", "due_date"),
        ("To'lov kuni", "due_date"),
        ("Naqd", "method"),
        ("Karta", "method"),
        ("To'lov turi", "method"),
        ("Usul", "method"),
        ("To'lov usuli", "method"),
        ("Способ оплаты", "method"),
        ("Holati", "status"),
        ("Статус", "status"),
        ("Izoh", "note"),
        ("Изоҳ", "note"),
        ("Примечание", "note"),
        ("Note", "note"),
        ("№", "ignore"),
        ("Telefon", "ignore"),
        ("Qoldiq qarz", "ignore"),
    ],
)
def test_keyword_field(header, field):
    found = keyword_field(header)
    assert found is not None and found[0] == field


@pytest.mark.parametrize("header", ["", None, "Navro'z Kafe", "Xyz", "Mavzu"])
def test_keyword_field_unknown(header):
    assert keyword_field(header) is None


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("Kirim", "transactions_in"),
        ("Kirimlar 2026", "transactions_in"),
        ("Savdo", "transactions_in"),
        ("Приход", "transactions_in"),
        ("Chiqim", "transactions_out"),
        ("Xarajatlar", "transactions_out"),
        ("Oylik xarajatlar", "transactions_out"),  # "oylik" = monthly here
        ("Расходы", "transactions_out"),
        ("Kirim-chiqim", "transactions_mixed"),
        ("Kirim va chiqim", "transactions_mixed"),
        ("Kassa daftari", "transactions_mixed"),
        ("Oylik", "payroll"),
        ("Иш ҳақи", "payroll"),
        ("Зарплата", "payroll"),
        ("NBU kredit", "loan_schedule"),
        ("Кредит", "loan_schedule"),
        ("Kassa", "cash_balance"),
        ("Qoldiq", "cash_balance"),
        ("Izohlar", "ignore"),
        ("Notes", "ignore"),
        ("Ta'minotchilar", "counterparties"),
        ("Поставщики", "counterparties"),
        ("To'lovlar jadvali", "obligations_schedule"),
        ("Sheet1", None),
        ("", None),
        (None, None),
    ],
)
def test_title_kind(title, kind):
    assert title_kind(title) == kind


def test_title_hint_conflicting_with_columns_lowers_confidence():
    headers = ["Sana", "Kirim", "Chiqim", "Izoh"]
    samples = [["14.11.2026", "5 800 000", "", "savdo"], ["14.11.2026", "", "741 000", "gaz"]]
    guess = guess_mapping(headers, samples, title="Kirim")
    assert guess.sheet_kind == "transactions_mixed"  # the columns win over the title
    assert guess.kind_confidence < CONFIRM_THRESHOLD


def test_direction_column_with_values():
    headers = ["Sana", "Turi", "Summa"]
    samples = [["14.11.2026", "kirim", 5800000], ["14.11.2026", "chiqim", 741000]]
    guess = guess_mapping(headers, samples)
    assert [c.field for c in guess.columns] == ["date", "direction", "amount"]
    assert guess.columns[1].confidence >= CONFIRM_THRESHOLD
    assert guess.sheet_kind == "transactions_mixed"


def test_turi_with_payment_methods_is_method():
    headers = ["Sana", "Summa", "Turi"]
    samples = [["14.11.2026", 5800000, "Naqd"], ["14.11.2026", 741000, "Karta"]]
    guess = guess_mapping(headers, samples, title="Kirim")
    assert guess.columns[2].field == "method"
    assert guess.columns[2].confidence < CONFIRM_THRESHOLD


def test_value_types_decide_unknown_headers():
    headers = ["Kun", "Pul", "Nima", "X"]
    samples = [
        [46340, 4350000, "savdo", "kirim"],
        [46341, 4120000, "savdo", "chiqim"],
        [46342, 3900000, "ijara", "kirim"],
    ]
    guess = guess_mapping(headers, samples)
    fields = {c.header: c.field for c in guess.columns}
    assert fields["Pul"] == "amount"
    assert fields["X"] == "direction"
    assert all(c.confidence < CONFIRM_THRESHOLD for c in guess.columns if c.header != "Kun")


def test_serials_vs_round_amounts_without_headers():
    samples = [[46340, 46000], [46341, 52000], [46342, 48000], [46345, 50000]]
    guess = guess_mapping(["", ""], samples)
    assert [c.field for c in guess.columns] == ["date", "amount"]
    assert all(c.confidence <= 0.5 for c in guess.columns)  # no header: always confirm


def test_serial_range_amounts_under_an_amount_header():
    samples = [["14.11.2026", 46000], ["15.11.2026", 52300]]
    guess = guess_mapping(["Sana", "Summa"], samples)
    assert guess.columns[1].field == "amount"
    assert guess.columns[1].confidence >= CONFIRM_THRESHOLD


def test_only_one_plain_amount_column_survives():
    headers = ["Sana", "Summa", "Jami", "Qoldiq"]
    samples = [["14.11.2026", "4 350 000", "4 350 000", "40 000 000"]]
    guess = guess_mapping(headers, samples, title="Chiqim")
    assert [c.field for c in guess.columns] == ["date", "amount", "ignore", "ignore"]
    assert all(c.confidence < CONFIRM_THRESHOLD for c in guess.columns[2:])


def test_duplicate_date_columns_keep_the_better_one():
    headers = ["Sana", "Kiritilgan sana", "Summa"]
    samples = [["14.11.2026", "", "4 350 000"], ["15.11.2026", "x", "1 000 000"]]
    guess = guess_mapping(headers, samples)
    assert [c.field for c in guess.columns] == ["date", "ignore", "amount"]


def test_header_only_kirim_chiqim_columns_are_flow_amounts():
    guess = guess_mapping(["Sana", "Kirim", "Chiqim"], [], title="Pul")
    assert [(c.field, c.direction) for c in guess.columns] == [
        ("date", None),
        ("amount", "in"),
        ("amount", "out"),
    ]
    assert guess.sheet_kind == "transactions_mixed"
    assert all(c.confidence < 0.9 for c in guess.columns)


def test_obligations_schedule_from_due_dates_without_txn_dates():
    headers = ["Nima uchun", "Summa", "Muddat"]
    samples = [["Ijara", "15 000 000", "01.12.2026"], ["Soliq", "8 000 000", "15.12.2026"]]
    guess = guess_mapping(headers, samples)
    assert guess.sheet_kind == "obligations_schedule"
    assert guess.kind_confidence < CONFIRM_THRESHOLD
    guess = guess_mapping(headers, samples, title="To'lovlar jadvali")
    assert guess.sheet_kind == "obligations_schedule"
    assert guess.kind_confidence >= CONFIRM_THRESHOLD


def test_notes_sheet_maps_to_ignore():
    rows = load("izohlar_notes")["rows"]
    guess = guess_mapping(rows[0], rows[1:], title="Izohlar")
    assert guess.sheet_kind == "ignore"
    assert guess.kind_confidence >= CONFIRM_THRESHOLD
    assert guess_mapping([], [], title="Izohlar").sheet_kind == "ignore"


def test_untitled_plain_transactions_ask_for_confirmation():
    guess = guess_mapping(["Sana", "Summa"], [["14.11.2026", "4 350 000"]])
    assert guess.sheet_kind in ("transactions_mixed", "transactions_out")
    assert guess.kind_confidence < CONFIRM_THRESHOLD
    signed = guess_mapping(["Sana", "Summa"], [["14.11.2026", "4 350 000"], ["15.11", "-1 000"]])
    assert signed.sheet_kind == "transactions_mixed"


def test_ragged_rows_and_extra_columns():
    headers = ["Sana", "Summa"]
    samples = [["14.11.2026"], ["15.11.2026", "1 000 000", "stray"], []]
    guess = guess_mapping(headers, samples)
    assert [c.index for c in guess.columns] == [0, 1, 2]
    assert guess.columns[2].header == ""
    assert guess.columns[2].confidence <= 0.5


def test_empty_input():
    guess = guess_mapping([], [])
    assert guess == MappingGuess("ignore", guess.kind_confidence, [])
    assert guess.columns == []


def test_mapping_dataclasses_are_frozen():
    col = ColumnGuess(0, "Sana", "date", 0.9)
    assert col.direction is None
    with pytest.raises(AttributeError):
        col.field = "amount"  # type: ignore[misc]


# --- fixtures: cell-level parsing ---------------------------------------------------------


def test_kirim_fixture_amount_and_date_formats():
    amounts = [parse_amount(v) for v in column("kirim_header_row3", "Summa (so'm)")]
    assert amounts == [
        D(4_350_000),
        D(3_218_000),
        D(4_350_000),
        D(4_350_000),
        D(2_354_000),
        D(3_530_000),
        D(2_145_000),
        D(4_350_000),
        D(4_350_000),
    ]
    dates = [parse_date(v, today=TODAY) for v in column("kirim_header_row3", "Sana")]
    assert [d.day for d in dates] == [14, 14, 15, 15, 16, 16, 17, 17, 18]
    assert {(d.year, d.month) for d in dates} == {(2026, 11)}


def test_chiqim_fixture_mixed_dates_and_one_impossible_day():
    dates = [try_date(v) for v in column("chiqim_mixed_dates", "Sana")]
    assert dates == [
        date(2026, 11, 14),
        date(2026, 11, 14),
        date(2026, 11, 15),  # serial 46341
        date(2026, 11, 15),
        date(2026, 11, 16),
        date(2026, 11, 16),  # "16-noyabr": year inferred
        date(2026, 11, 17),  # Russian month name
        date(2026, 11, 17),  # float serial
        ("invalid", date(2026, 11, 30)),  # 31.11.2026
        None,  # planned rows have no txn date ...
        None,
        date(2026, 11, 21),
    ]
    dues = [try_date(v) for v in column("chiqim_mixed_dates", "Muddat")]
    assert [d for d in dues if d] == [date(2026, 12, 15), date(2026, 12, 25)]  # ... but a due date


def test_chiqim_fixture_amounts_negative_and_empty():
    amounts = [parse_amount(v) for v in column("chiqim_mixed_dates", "Summa (so'm)")]
    assert amounts[5] == D(-120_000)  # "(120 000)": a refund
    assert amounts[3] == D(4_350_000)  # "4,35 mln"
    assert amounts[-1] is None  # empty amount
    assert sum(1 for a in amounts if a is None) == 1


def test_duplicates_and_empty_amounts_fixture():
    sheet = load("rasxody_duplicates_ru")
    _, _, data = header_and_data(sheet["rows"])

    def norm(row):
        return (
            parse_date(row[0], today=TODAY),
            parse_amount(row[1]),
            clean_name(row[2]),
            name_key(row[3]),
            clean_name(row[4]),
        )

    parsed = [norm(r) for r in data]
    assert parsed[0] == parsed[1]  # an exact duplicate
    assert parsed[6] == parsed[7]
    assert len(set(parsed)) == len(parsed) - 2
    assert [p[1] for p in parsed if p[1] is None] == [None, None]  # "" and null
    assert parsed[3][:2] == (date(2026, 11, 15), D(1_250_000))  # "15.11.26", "1.250.000"
    assert parsed[4][1] == D(350_000)  # "UZS 350 000"
    assert parsed[2][0] == date(2026, 11, 15)  # "15 ноября 2026 г."


def test_counterparty_spellings_across_fixtures_share_a_key():
    names = {
        name_key(v)
        for fixture, header in [
            ("chiqim_mixed_dates", "Kimga"),
            ("rasxody_duplicates_ru", "Поставщик"),
            ("taminotchilar", "Kontragent"),
        ]
        for v in column(fixture, header)
        if v and "go" in name_key(v)
    }
    assert names == {"agro go'sht"}


def test_payroll_fixture():
    salaries = column("oylik_cyrillic", "Ойлик маош (сўм)")
    names = column("oylik_cyrillic", "Ф.И.Ш.")
    total = [parse_amount(s) for s, n in zip(salaries, names) if n != "Жами"]
    assert sum(total) == D(20_000_000) == parse_amount(salaries[-1])
    days = {parse_day_of_month(v) for v in column("oylik_cyrillic", "Тўлов куни")}
    assert days == {10, None}  # the "Жами" row has none
    assert name_key(names[2]) == "bekzod g'aniyev"


def test_loan_fixture_totals_and_serial_due_dates():
    _, _, data = header_and_data(load("nbu_kredit")["rows"])
    for row in data:
        principal, interest, total = (parse_amount(v) for v in row[1:4])
        assert principal + interest == total
        assert parse_date(row[0], today=TODAY).day == 10


def test_counterparties_fixture_payment_days():
    days = [parse_day_of_month(v) for v in column("taminotchilar", "To'lov kuni")]
    assert days == [25, None, None, 25]
    phones = [parse_amount(v) for v in column("taminotchilar", "Telefon")]
    assert phones == [None] * 4


def test_split_columns_fixture_totals():
    flows_in = [parse_amount(v) for v in column("kassa_daftari_kirim_chiqim", "Kirim")]
    flows_out = [parse_amount(v) for v in column("kassa_daftari_kirim_chiqim", "Chiqim")]
    assert sum(a for a in flows_in if a) == D(19_600_000)
    assert sum(a for a in flows_out if a) == D(16_941_000)


def test_english_fixture_directions():
    kinds = [parse_direction(v) for v in column("transactions_en", "Type")]
    assert kinds == ["in", "out", "in", "out", "in", "out"]


# --- the real demo workbook (openpyxl cells) -------------------------------------------


@pytest.fixture(scope="module")
def demo_workbook(tmp_path_factory):
    openpyxl = pytest.importorskip("openpyxl")
    from apps.finance.demo import build_navroz
    from apps.finance.demo_export import export_xlsx

    path = export_xlsx(build_navroz(TODAY), tmp_path_factory.mktemp("demo") / "demo.xlsx")
    wb = openpyxl.load_workbook(path, data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


@pytest.mark.parametrize(
    ("title", "header_row", "kind"),
    [
        ("Kassa", 2, "cash_balance"),
        ("Kirim", 2, "transactions_in"),
        ("Chiqim", 0, "transactions_out"),
        ("Oylik", 1, "payroll"),
        ("Ta'minotchilar", 0, "counterparties"),
        ("NBU kredit", 1, "loan_schedule"),
        ("Izohlar", None, None),
    ],
)
def test_demo_workbook_sheets(demo_workbook, title, header_row, kind):
    rows = demo_workbook[title]
    assert detect_header(rows) == header_row
    if header_row is None:
        return
    headers = ["" if c is None else str(c).strip() for c in rows[header_row]]
    data = [r for r in rows[header_row + 1 :] if any(not is_blank(c) for c in r)]
    guess = guess_mapping(headers, data[:20], title=title)
    assert guess.sheet_kind == kind
    assert guess.kind_confidence >= CONFIRM_THRESHOLD


def test_demo_workbook_cells_all_parse(demo_workbook):
    kirim = demo_workbook["Kirim"][3:]
    assert all(parse_amount(r[1]) for r in kirim)
    assert all(isinstance(parse_date(r[0], today=TODAY), date) for r in kirim)

    chiqim = demo_workbook["Chiqim"][1:]
    invalid, no_date, no_amount = [], 0, 0
    for r in chiqim:
        try:
            no_date += parse_date(r[0], today=TODAY) is None
        except InvalidDate as exc:
            invalid.append(exc)
        no_amount += parse_amount(r[1]) is None
    assert len(invalid) == 1  # the deliberately impossible date
    assert invalid[0].suggestion.day == 30
    assert no_amount == 1  # the deliberately empty amount
    planned = [r for r in chiqim if r[0] is None]
    assert no_date == len(planned) > 0
    assert all(parse_date(r[4], today=TODAY) > TODAY for r in planned)
