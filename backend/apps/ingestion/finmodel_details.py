"""Item-level detail from a Restoran FinModel workbook (stored in DataSource.summary["details"]).

Every product purchase (Kirim), dish sales (Sotuv), menu prices and cost per portion (Menyu,
Menyu tahlili), recipes with ingredient costs (Texkarta), write-offs (Hisobdan chiqarish),
stock-count differences (Inventarizatsiya), stock (Ombor hisoboti), payroll per employee
(Ish haqi) and fixed assets (Asosiy vositalar). Amounts are strings (Decimal-safe JSON).
Months are ISO first-of-month keys. A missing sheet gives an empty section.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .finmodel import _col, _date, _find_header, _keys, _num, _sheet
from .normalize import text_key
from .readers import SheetData

Q2 = Decimal("0.01")


def _s(x: Decimal) -> str:
    return str(x.quantize(Q2))


def _raw(v: Any) -> Decimal:
    """Full precision for ratios and recipe norms (parse_amount rounds to tiyin)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Decimal(str(v))
    return _num(v)


def _cell(row: list[Any], i: int | None) -> Any:
    return row[i] if i is not None and i < len(row) else None


def _txt(row: list[Any], i: int | None) -> str:
    v = _cell(row, i)
    return "" if v is None else str(v).strip()


def _month(d: date) -> str:
    return d.replace(day=1).isoformat()


def _table(sheet: SheetData | None, *needles: str) -> tuple[list[Any], list[list[Any]]] | None:
    if sheet is None:
        return None
    h = _find_header(sheet.rows, *needles)
    if h is None:
        return None
    return sheet.rows[h], sheet.rows[h + 1 :]


def purchases(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Kirim: per product -> unit, category, suppliers, months {m: [qty, amount, avg price]}."""
    t = _table(_sheet(sheets, "kirim"), "sana", "mahsulot", "miqdor")
    if t is None:
        return {}
    header, rows = t
    i_d, i_p, i_q = _col(header, "sana"), _col(header, "mahsulot"), _col(header, "miqdor")
    i_sum = _col(header, "summa so'm", "summa valyutada", "jami summa")
    i_price, i_unit = _col(header, "narx birlik", "narx"), _col(header, "birlik")
    i_sup, i_paid = _col(header, "yetkazib beruvchi"), _col(header, "darhol to'langan")
    cats = {}
    cat_t = _table(_sheet(sheets, "mahsulotlar"), "nomi", "birlik")
    if cat_t is not None:
        ch, crow = cat_t
        i_n, i_c = _col(ch, "nomi"), _col(ch, "kategoriya")
        cats = {_txt(r, i_n): _txt(r, i_c) for r in crow if _txt(r, i_n)}
    out: dict[str, dict[str, Any]] = {}
    acc: dict[str, dict[str, list[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [Decimal(0)] * 3)
    )
    sup: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for r in rows:
        d, name = _date(_cell(r, i_d), today), _txt(r, i_p)
        if d is None or not name:
            continue
        qty = _num(_cell(r, i_q))
        amount = _num(_cell(r, i_sum)) or qty * _num(_cell(r, i_price))
        if amount <= 0:
            continue
        a = acc[name][_month(d)]
        a[0] += qty
        a[1] += amount
        a[2] += amount if _txt(r, i_paid) else Decimal(0)  # paid at once (cash)
        sup[name][_txt(r, i_sup) or "—"] += amount
        out.setdefault(name, {"unit": _txt(r, i_unit), "category": cats.get(name, "")})
    for name, months in acc.items():
        out[name]["months"] = {
            m: {
                "qty": _s(v[0]),
                "amount": _s(v[1]),
                "price": _s(v[1] / v[0]) if v[0] else "0",
                "cash": _s(v[2]),
            }
            for m, v in sorted(months.items())
        }
        out[name]["suppliers"] = {
            k: _s(v) for k, v in sorted(sup[name].items(), key=lambda kv: -kv[1])
        }
    return out


def dish_sales(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Sotuv: per dish -> category, months {m: [portions, revenue]}, channels {ch: revenue}."""
    t = _table(_sheet(sheets, "sotuv"), "sana", "taom", "miqdor")
    if t is None:
        return {}
    header, rows = t
    i_d, i_t, i_q = _col(header, "sana"), _col(header, "taom"), _col(header, "miqdor")
    i_rev = _col(header, "sof tushum", "summa")
    i_ch, i_cat = _col(header, "kanal"), _col(header, "kategoriya")
    i_com, i_cost, i_gp = (
        _col(header, "komissiya so'm"),
        _col(header, "tannarx jami"),
        _col(header, "yalpi foyda"),
    )
    acc: dict[str, dict[str, list[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [Decimal(0)] * 5)
    )
    chan: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    cat: dict[str, str] = {}
    for r in rows:
        d, name = _date(_cell(r, i_d), today), _txt(r, i_t)
        if d is None or not name:
            continue
        rev = _num(_cell(r, i_rev))
        a = acc[name][_month(d)]
        a[0] += _num(_cell(r, i_q))
        a[1] += rev
        a[2] += _num(_cell(r, i_com))
        a[3] += _num(_cell(r, i_cost))
        a[4] += _num(_cell(r, i_gp))
        chan[name][_txt(r, i_ch) or "—"] += rev
        cat.setdefault(name, _txt(r, i_cat))
    return {
        name: {
            "category": cat.get(name, ""),
            "months": {
                m: {
                    "qty": _s(v[0]),
                    "revenue": _s(v[1]),
                    "commission": _s(v[2]),
                    "cost": _s(v[3]),
                    "gross_profit": _s(v[4]),
                }
                for m, v in sorted(months.items())
            },
            "channels": {k: _s(v) for k, v in sorted(chan[name].items(), key=lambda kv: -kv[1])},
        }
        for name, months in acc.items()
    }


def menu(sheets: list[SheetData]) -> dict[str, Any]:
    """Menyu: price, cost per portion, food cost %, profit per portion, status."""
    sh = next((s for s in sheets if text_key(s.title) == "menyu"), None)
    t = _table(sh, "taom nomi", "sotuv narxi")
    if sh is None or t is None:
        return {}
    header, rows = t
    h = sh.rows.index(header)
    sold_cols, cost_cols = month_blocks(sh.rows[h - 1] if h else [])
    i_n, i_cat, i_p = (
        _col(header, "taom nomi"),
        _col(header, "kategoriya"),
        _col(header, "sotuv narxi"),
    )
    i_c, i_fc = _col(header, "tannarx"), _col(header, "food cost")
    i_m, i_st = _col(header, "marja"), _col(header, "holat")
    out = {}
    for r in rows:
        name = _txt(r, i_n)
        price = _num(_cell(r, i_p))
        if not name or price <= 0:
            continue
        out[name] = {
            "category": _txt(r, i_cat),
            "price": _s(price),
            "cost": _s(_num(_cell(r, i_c))),
            "food_cost": str(_raw(_cell(r, i_fc)).quantize(Decimal("0.0001"))),
            "margin": _s(_num(_cell(r, i_m))),
            "status": _txt(r, i_st),
            "sold": {m: _s(_num(_cell(r, i))) for m, i in sold_cols.items() if _num(_cell(r, i))},
            "cost_by_month": {
                m: _s(_num(_cell(r, i)))
                for m, i in cost_cols.items()
                if _num(_cell(r, i)) and _num(_cell(r, sold_cols.get(m)))
            },
        }
    return out


def month_blocks(date_row: list[Any]) -> tuple[dict[str, int], dict[str, int]]:
    """Two blocks of month columns (first: quantities, second: costs) from a row of dates."""
    first: dict[str, int] = {}
    second: dict[str, int] = {}
    for i, c in enumerate(date_row):
        d = _date(c, date(2100, 1, 1)) if isinstance(c, (date, datetime)) else None
        if d is None:
            continue
        (second if _month(d) in first else first)[_month(d)] = i
    return first, second


def menu_analysis(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Menyu tahlili (menu engineering for the period the sheet is set to)."""
    sh = _sheet(sheets, "menyu tahlili")
    t = _table(sh, "taom", "kategoriya", "narx")
    if sh is None or t is None:
        return {}
    period = [
        c if not isinstance(c, datetime) else c.date()
        for r in sh.rows[:6]
        for c in r
        if isinstance(c, (date, datetime))
    ][:2]
    header, rows = t
    cols = {
        k: _col(header, k)
        for k in (
            "taom",
            "sotilgan",
            "sof tushum",
            "tannarx",
            "yalpi foyda",
            "food cost",
            "porsiya foydasi",
            "mashhurlik ulushi",
            "marja",
        )
    }
    cols["mashhurlik"] = next((i for i, k in enumerate(_keys(header)) if k == "mashhurlik"), None)
    out = {}
    for r in rows:
        name = _txt(r, cols["taom"])
        if not name or _num(_cell(r, cols["sotilgan"])) <= 0:
            continue
        out[name] = {
            "sold": _s(_num(_cell(r, cols["sotilgan"]))),
            "revenue": _s(_num(_cell(r, cols["sof tushum"]))),
            "cost": _s(_num(_cell(r, cols["tannarx"]))),
            "gross_profit": _s(_num(_cell(r, cols["yalpi foyda"]))),
            "food_cost": str(_raw(_cell(r, cols["food cost"])).quantize(Decimal("0.0001"))),
            "portion_profit": _s(_num(_cell(r, cols["porsiya foydasi"]))),
            "popularity": _txt(r, cols["mashhurlik"]),
            "margin_class": _txt(r, cols["marja"]),
        }
    return {
        "from": period[0].isoformat() if period else None,
        "to": period[1].isoformat() if len(period) > 1 else None,
        "dishes": out,
    }


def recipes(sheets: list[SheetData]) -> dict[str, Any]:
    """Texkarta: dish -> [ingredient, netto per portion, unit, cost per portion (latest month)]."""
    t = _table(_sheet(sheets, "texkarta"), "taom", "ingredient")
    if t is None:
        return {}
    header, rows = t
    i_t, i_i, i_u = _col(header, "taom"), _col(header, "ingredient"), _col(header, "birlik")
    i_n = _col(header, "norma", "netto")
    i_cost, i_kind = _col(header, "tannarx"), _col(header, "turi")
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        dish, ing = _txt(r, i_t), _txt(r, i_i)
        if not dish or not ing:
            continue
        out[dish].append(
            {
                "ingredient": ing,
                "kind": _txt(r, i_kind),
                "qty": str(_raw(_cell(r, i_n)).normalize()),
                "unit": _txt(r, i_u),
                "cost": _s(_num(_cell(r, i_cost))),
            }
        )
    return dict(out)


def semi_recipes(sheets: list[SheetData]) -> dict[str, Any]:
    """YT retsept: semi-finished item -> [product, qty per batch, unit], batch output."""
    t = _table(_sheet(sheets, "yt retsept"), "yarim tayyor", "mahsulot")
    if t is None:
        return {}
    header, rows = t
    i_y, i_p, i_u = _col(header, "yarim tayyor"), _col(header, "mahsulot"), _col(header, "birlik")
    i_n, i_out = _col(header, "norma partiyaga"), _col(header, "partiya chiqishi")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        y, p = _txt(r, i_y), _txt(r, i_p)
        if not y or not p:
            continue
        e = out.setdefault(y, {"batch": str(_num(_cell(r, i_out))), "items": []})
        e["items"].append([p, str(_raw(_cell(r, i_n)).normalize()), _txt(r, i_u)])
    return out


def writeoffs(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Hisobdan chiqarish: months {m: {reason: amount}}, items {m: [[name, qty, unit, amount, reason]]}."""
    t = _table(_sheet(sheets, "hisobdan"), "sana", "nomi", "sabab")
    if t is None:
        return {}
    header, rows = t
    i_d, i_n, i_q = _col(header, "sana"), _col(header, "nomi"), _col(header, "miqdor")
    i_r, i_u, i_s = _col(header, "sabab"), _col(header, "birlik"), _col(header, "summa")
    by: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    items: dict[str, list[list[str]]] = defaultdict(list)
    for r in rows:
        d, name = _date(_cell(r, i_d), today), _txt(r, i_n)
        amount = _num(_cell(r, i_s))
        if d is None or not name or amount <= 0:
            continue
        reason = _txt(r, i_r) or "—"
        by[_month(d)][reason] += amount
        items[_month(d)].append([name, str(_num(_cell(r, i_q))), _txt(r, i_u), _s(amount), reason])
    return {
        "months": {m: {k: _s(v) for k, v in rs.items()} for m, rs in sorted(by.items())},
        "items": dict(items),
    }


def stock_counts(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Inventarizatsiya: months {m: [[product, qty diff, unit, amount diff]]} (negative = shortage)."""
    t = _table(_sheet(sheets, "inventarizatsiya"), "sana", "mahsulot")
    if t is None:
        return {}
    header, rows = t
    i_d, i_p, i_u = _col(header, "sana"), _col(header, "mahsulot"), _col(header, "birlik")
    i_f, i_fs = _col(header, "farq"), _col(header, "farq summasi")
    out: dict[str, list[list[str]]] = defaultdict(list)
    for r in rows:
        d, name = _date(_cell(r, i_d), today), _txt(r, i_p)
        if d is None or not name:
            continue
        out[_month(d)].append(
            [name, str(_num(_cell(r, i_f)).quantize(Q2)), _txt(r, i_u), _s(_num(_cell(r, i_fs)))]
        )
    return dict(out)


def stock(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Ombor hisoboti (the month the sheet is set to): qty, value, min, status per product."""
    sh = _sheet(sheets, "ombor")
    t = _table(sh, "mahsulot", "birlik", "kategoriya")
    if sh is None or t is None:
        return {}
    month = ""
    for r in sh.rows[:5]:
        cells = [c for c in r if c not in (None, "")]
        if len(cells) > 1 and text_key(str(cells[0])) == "oy":
            month = str(cells[1])
            break
    header, rows = t
    i_p, i_u = _col(header, "mahsulot"), _col(header, "birlik")
    i_end, i_v = _col(header, "oy oxiri"), _col(header, "qiymat")
    i_use, i_min, i_st = _col(header, "sarf"), _col(header, "min"), _col(header, "holat")
    items = {}
    for r in rows:
        name = _txt(r, i_p)
        if not name or _cell(r, i_end) in (None, ""):
            continue
        items[name] = {
            "unit": _txt(r, i_u),
            "end_qty": str(_num(_cell(r, i_end)).quantize(Q2)),
            "used": str(_num(_cell(r, i_use)).quantize(Q2)),
            "value": _s(_num(_cell(r, i_v))),
            "min": str(_num(_cell(r, i_min))),
            "status": _txt(r, i_st),
        }
    return {"month": month, "items": items}


def payroll(sheets: list[SheetData], today: date) -> dict[str, Any]:
    """Ish haqi: months {m: {employee: [position, department, accrued, total cost, net paid]}}."""
    t = _table(_sheet(sheets, "ish haqi"), "oy", "xodim", "lavozim")
    if t is None:
        return {}
    header, rows = t
    i_m, i_x = _col(header, "oy oyning"), _col(header, "xodim")
    i_l, i_b = _col(header, "lavozim"), _col(header, "bo'lim")
    i_acc, i_tot, i_net = (
        _col(header, "hisoblangan"),
        _col(header, "jami xarajat"),
        _col(header, "qo'lga"),
    )
    out: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for r in rows:
        d, name = _date(_cell(r, i_m), today), _txt(r, i_x)
        if d is None or not name:
            continue
        acc_ = _num(_cell(r, i_acc))
        out[_month(d)][name] = [
            _txt(r, i_l),
            _txt(r, i_b),
            _s(acc_),
            _s(_num(_cell(r, i_tot)) or acc_),
            _s(_num(_cell(r, i_net))),
        ]
    return dict(out)


def assets(sheets: list[SheetData], today: date) -> list[dict[str, str]]:
    t = _table(_sheet(sheets, "asosiy vositalar"), "nomi", "guruh")
    if t is None:
        return []
    header, rows = t
    i_n, i_g, i_d = _col(header, "nomi"), _col(header, "guruh"), _col(header, "sana")
    i_v, i_l, i_a = (
        _col(header, "boshl qiymat"),
        _col(header, "foydali muddat"),
        _col(header, "oylik amortizatsiya"),
    )
    out = []
    for r in rows:
        name, value = _txt(r, i_n), _num(_cell(r, i_v))
        if not name or value <= 0:
            continue
        d = _date(_cell(r, i_d), today)
        out.append(
            {
                "name": name,
                "group": _txt(r, i_g),
                "date": d.isoformat() if d else "",
                "value": _s(value),
                "life_months": str(_num(_cell(r, i_l))),
                "monthly_depr": _s(_num(_cell(r, i_a))),
            }
        )
    return out


def details(sheets: list[SheetData], today: date) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, fn in (
        ("purchases", purchases),
        ("dish_sales", dish_sales),
        ("menu_analysis", menu_analysis),
        ("writeoffs", writeoffs),
        ("stock_counts", stock_counts),
        ("stock", stock),
        ("payroll", payroll),
        ("assets", assets),
    ):
        try:
            out[key] = fn(sheets, today)
        except (
            ValueError,
            TypeError,
            IndexError,
            ArithmeticError,
        ):  # one odd sheet never breaks a sync
            out[key] = {}
    for key, fn2 in (("menu", menu), ("recipes", recipes), ("semi_recipes", semi_recipes)):
        try:
            out[key] = fn2(sheets)
        except (ValueError, TypeError, IndexError, ArithmeticError):
            out[key] = {}
    return out
