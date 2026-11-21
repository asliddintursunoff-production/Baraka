"""M0 voice spike: one fake tool (`evaluate_purchase`) with a fixed answer.

The verdict does not depend on the amount (it is fixed, as agreed for the spike); the
spike measures latency and whether the model reads the `speech` fields faithfully in
Uzbek. Real tools replace this in M3. Every display/speech string comes from uz_format.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from . import uz_format as uz

SPIKE_BUSINESS = "Navro'z Kafe"
SPIKE_TODAY = date(2026, 11, 21)

CASH = Decimal("48200000")
HARD_DAY = date(2026, 12, 10)
HARD_DAY_BALANCE = Decimal("18800000")
SHORTAGE = Decimal("-6200000")
RECOMMENDED = date(2027, 1, 12)
SPEND_LIMIT = Decimal("8000000")
INSTALLMENT_LOWEST = Decimal("9800000")

UPCOMING = [
    (date(2026, 11, 25), "Ta'minotchi Agro Go'sht", Decimal("22000000")),
    (date(2026, 12, 1), "Ijara", Decimal("15000000")),
    (date(2026, 12, 10), "Oylik (15 xodim)", Decimal("45000000")),
    (date(2026, 12, 10), "NBU kredit to'lovi", Decimal("18500000")),
    (date(2026, 12, 15), "Soliq", Decimal("8000000")),
]

EVALUATE_PURCHASE_SPEC: dict[str, Any] = {
    "name": "evaluate_purchase",
    "description": (
        "Xarid yoki katta xarajat qarori: shu summani sarflasa, majburiy to'lovlarga "
        "(oylik, kredit, ijara, soliq) pul yetadimi. Qaror, eng qiyin kun, tavsiya "
        "qilingan sana va bo'lib to'lash variantini qaytaradi. Javobdagi raqamlarni faqat "
        "'speech' maydonidan o'qing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Summa so'mda, butun son. Masalan 25 million = 25000000.",
            },
            "date": {
                "type": "string",
                "description": "Xarid sanasi YYYY-MM-DD (ixtiyoriy, bo'lmasa bugun).",
            },
            "installments": {
                "type": "integer",
                "description": "Bo'lib to'lash oylari soni (ixtiyoriy).",
            },
        },
        "required": ["amount"],
    },
}


def context_lines() -> list[str]:
    lines = [
        f"Hozirgi kassa: {uz.format_mln(CASH)} ({uz.speech_amount(CASH)}).",
        f"Eng qiyin kun: {uz.format_date(HARD_DAY)} ({uz.uz_ordinal_date(HARD_DAY)}), "
        f"o'sha kuni kassada {uz.format_mln(HARD_DAY_BALANCE)} "
        f"({uz.speech_amount(HARD_DAY_BALANCE)}) qoladi. Oylik va kredit bir kunga tushgan.",
        "Xavfsiz chegara: 10,0 mln (o'n million so'm).",
        "Keyingi majburiy to'lovlar:",
    ]
    for d, title, amount in UPCOMING:
        lines.append(
            f"  {uz.format_date(d)} ({uz.uz_ordinal_date(d)}) — {title}: "
            f"{uz.format_mln(amount)} ({uz.speech_amount(amount)})"
        )
    return lines


def validate_args(args: dict[str, Any]) -> dict[str, Any]:
    amount = args.get("amount")
    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("amount must be a positive integer (so'm)")
    if amount > 10_000_000_000:
        raise ValueError("amount is too large")
    out: dict[str, Any] = {"amount": amount}
    if args.get("date"):
        out["date"] = date.fromisoformat(str(args["date"])).isoformat()
    inst = args.get("installments")
    if inst is not None:
        if not isinstance(inst, int) or not 2 <= inst <= 12:
            raise ValueError("installments must be 2..12")
        out["installments"] = inst
    return out


def evaluate_purchase(args: dict[str, Any]) -> dict[str, Any]:
    clean = validate_args(args)
    amount = Decimal(clean["amount"])
    return {
        "ok": True,
        "verdict": "no",
        "facts": {
            "amount": f"{amount:.2f}",
            "shortage_date": HARD_DAY.isoformat(),
            "lowest_balance": f"{SHORTAGE:.2f}",
            "recommended_date": RECOMMENDED.isoformat(),
            "spend_limit_until_shortage_date": f"{SPEND_LIMIT:.2f}",
            "installments_lowest_balance": f"{INSTALLMENT_LOWEST:.2f}",
        },
        "display": {
            "amount": uz.format_mln(amount),
            "lowest_balance": uz.format_mln(SHORTAGE),
            "shortage_date": uz.format_date(HARD_DAY),
            "recommended_date": uz.format_date(RECOMMENDED),
            "spend_limit": uz.format_mln(SPEND_LIMIT, short=True),
            "installments_lowest_balance": uz.format_mln(INSTALLMENT_LOWEST),
        },
        "speech": {
            "decision": "Yo'q, hozir olmang.",
            "amount": uz.speech_amount(amount),
            "lowest_balance": uz.speech_amount(SHORTAGE),
            "shortage_date": uz.uz_ordinal_date(HARD_DAY),
            "recommended_date": uz.uz_ordinal_date(RECOMMENDED),
            "spend_limit": uz.speech_amount(SPEND_LIMIT),
            "installments": (
                "Uch oyga bo'lib to'lasangiz pul yetadi, lekin kassa xavfsiz chegaradan "
                f"pastga tushadi: eng kami {uz.speech_amount(INSTALLMENT_LOWEST)} qoladi."
            ),
        },
        "ui_blocks": [
            {"id": "b1", "type": "verdict", "status": "no", "headline": "Yo'q, hozir olmang."},
            {
                "id": "b2",
                "type": "compare_bars",
                "title": f"{uz.format_date(HARD_DAY)}, oylik kuni kassada qancha qoladi?",
                "rows": [
                    {
                        "label": "Hozir olsangiz",
                        "value": f"{SHORTAGE:.0f}",
                        "display": uz.format_mln(SHORTAGE, signed=True),
                        "status": "bad",
                        "status_text": "Yetmaydi",
                    },
                    {
                        "label": f"{uz.format_date(RECOMMENDED, 'da')} olsangiz",
                        "value": f"{HARD_DAY_BALANCE:.0f}",
                        "display": uz.format_mln(HARD_DAY_BALANCE, signed=True),
                        "status": "ok",
                        "status_text": "Yetadi",
                    },
                ],
            },
            {
                "id": "b3",
                "type": "steps",
                "items": [
                    f"Jihozni {uz.format_date(RECOMMENDED, 'da')} oling.",
                    f"{uz.format_date(HARD_DAY, 'gacha')} "
                    f"{uz.format_mln(SPEND_LIMIT, short=True)} so'mdan katta xarid qilmang.",
                    f"{uz.format_date(RECOMMENDED)} ertalab sizga o'zim eslataman.",
                ],
            },
        ],
        "proposed_plan": {
            "id": "spike-plan",
            "summary": f"{uz.format_date(RECOMMENDED)} 09:00 — jihoz xaridi eslatmasi",
        },
        "insufficient_data": False,
    }


def response_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


ANSWER_RULE = (
    "9. Agar tool javobida speech.answer bo'lsa, javobni aynan shu matn bilan, "
    "so'zma-so'z o'qi va hech narsa qo'shma."
)


def answer_sentence(installments: bool) -> str:
    """Ready-made spoken answer (variant 'answer' of the spike), built from uz_format."""
    if installments:
        return (
            "Yo'q, bo'lib to'lash ham xavfli. "
            "Uch oyga bo'lib to'lasangiz, kassada eng kami "
            f"{uz.speech_amount(INSTALLMENT_LOWEST)} qoladi, bu xavfsiz chegaradan past. "
            f"Jihozni {uz.uz_ordinal_date(RECOMMENDED, 'da')} bir yo'la oling. "
            "Shunday reja tuzaymi?"
        )
    return (
        "Yo'q, hozir olmang. "
        f"Agar hozir olsangiz, {uz.uz_ordinal_date(HARD_DAY, 'da')} oylikka "
        f"{uz.speech_amount(-SHORTAGE)} yetmay qoladi. "
        f"Jihozni {uz.uz_ordinal_date(RECOMMENDED, 'da')} oling. Shunday reja tuzaymi?"
    )


def evaluate_payload_for_model(
    args: dict[str, Any], *, with_answer: bool = False
) -> dict[str, Any]:
    """What the model receives: the envelope without ui_blocks (the browser renders those)."""
    result = evaluate_purchase(args)
    result.pop("ui_blocks", None)
    if with_answer:
        result["speech"] = {
            "answer": answer_sentence(bool(args.get("installments"))),
            **result["speech"],
        }
    return result
