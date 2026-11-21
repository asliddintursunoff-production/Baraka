"""Fayl tahlili analyst: a strong model with read-only tools over the per-file DuckDB.

Tools: wb_catalog, wb_sql (SELECT only), wb_cells (raw A1 range), calculate. All numbers come
from tool results; the model only reads and explains. Usage is logged in AiUsage under kind
"analyst" with its own daily cap.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
import re
import time
from decimal import Decimal
from typing import Any

from google.genai import types

from config import app_settings as cfg

from . import store

log = logging.getLogger(__name__)
MAX_STEPS = 10

SYSTEM = """Sen — kichik biznes uchun moliyaviy direktor (CFO) va Excel tahlilchisisan. Faqat o'zbek tilida (lotin) yozasan.
Foydalanuvchi Excel fayl yukladi. Fayl to'liq DuckDB jadvallariga yuklangan; katalog quyida.
Qoidalar:
1. Har bir raqamni faqat tool natijasidan ol (wb_sql, wb_cells, calculate). Hech qachon raqam o'ylab topma va xayolan hisoblama: yig'indi, foiz, farqni SQL yoki calculate bilan hisobla.
2. Kerakli jadvalni katalogdan top, wb_sql bilan so'ra. Keng (oylik ustunli) jadvallar uchun *_long jadvallari bor (label, period, value). Hisobot varaqlari (Foyda-zarar, Pul oqimi, Balans, Reja-fakt, Bosh sahifa) tayyor natijalarni saqlaydi — avval ulardan foydalan, jurnallar bilan tekshir.
3. Ustun nomi noaniq bo'lsa wb_cells bilan sarlavha atrofini o'qi.
4. Summalarni o'zbekcha yoz: 1 mln dan katta bo'lsa "1 439,5 mln", kichik bo'lsa "152 000 so'm"; foiz "36,2%"; sana "31-oktyabr 2026".
5. Javob markdown: birinchi qator — qalin to'g'ridan-to'g'ri javob. Keyin "### Nima uchun" (2-4 band, raqamlar bilan), kerak bo'lsa jadval (| ... |), "### Kelajak/xavf", "### Tavsiyam", "### Reja" (aniq qadamlar), "### Menga kerak" (yetishmayotgan ma'lumot bo'lsa). Qisqa va aniq.
6. Oxirgi qator: CHIPS: savol 1 | savol 2 | savol 3 (keyingi 3 ta foydali savol).
7. Fayldagi ma'lumotni hech qayerga yuborma; internet ishlatma."""

SUMMARY_Q = """"Fayl xulosasi" ni tayyorla:
- bu qanday fayl va nima uchun;
- davri va oxirgi ma'lumot sanasi;
- asosiy ko'rsatkichlar: oxirgi oy tushumi, sof foyda, oy oxiridagi kassa (pul qoldig'i), qarzlar (kredit qoldig'i, foizi);
- kassadagi pul qayerdan kelgan: operatsion faoliyat vs ta'sischi kiritmasi vs kredit (yil boshidan);
- reja-fakt (reja bo'lsa): cheklar soni va o'rtacha chek rejaga nisbatan;
- 3 ta yashirin xavf yoki topilma (masalan food cost maqsaddan yuqori, agregatorlar qarzi);
- ma'lumot sifati bo'yicha izohlar;
- 3 ta taklif qilinadigan savol (CHIPS)."""


def catalog_text(c: dict[str, Any]) -> str:
    lines = [
        f"Fayl: {c['filename']} · {c['sheets']} varaq · davr {c['period'].get('from')} – {c['period'].get('to')}"
        + (f" · shablon: {c['template']}" if c.get("template") else "")
    ]
    for t in c["tables"]:
        cols = []
        for cm in t["columns"][:40]:
            extra = ""
            if cm.get("from"):
                extra = f"[{cm['from']}..{cm['to']}]"
            cols.append(f"{cm['name']}:{cm['type'][0].lower()}{extra}")
        head = f"- {t['table']} (varaq «{t['sheet']}», {t['role_label']}, {t['rows']} qator, sarlavha {t['header_row']}/{t['first_col']}{', e`tiborsiz' if t.get('ignored') else ''})"
        lines.append(head + ": " + ", ".join(cols))
        if t.get("long_table"):
            lines.append(
                f"  {t['long_table']}: {', '.join(t['long_columns'])} (davr {t['periods'][0]}..{t['periods'][1]})"
            )
        if t.get("sample") and not t.get("ignored") and t["rows"]:
            lines.append(f"  namuna: {json.dumps(t['sample'][:2], ensure_ascii=False)[:300]}")
    if c.get("notes"):
        lines.append("Izohlar: " + "; ".join(c["notes"][:10]))
    return "\n".join(lines)


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expr: str) -> str:
    def ev(n: ast.AST) -> Decimal:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return Decimal(str(n.value))
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            if isinstance(n.op, ast.Pow):
                return Decimal(float(ev(n.left)) ** float(ev(n.right)))
            return _OPS[type(n.op)](ev(n.left), ev(n.right))  # type: ignore[no-any-return]
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))  # type: ignore[no-any-return]
        raise ValueError("faqat + - * / ** va sonlar")

    if len(expr) > 300:
        raise ValueError("juda uzun")
    return str(ev(ast.parse(expr.replace(",", "."), mode="eval")).quantize(Decimal("0.0001")))


DECLS = [
    types.FunctionDeclaration(
        name="wb_sql",
        description="Fayl jadvallariga bitta o'qish SQL so'rovi (DuckDB, faqat SELECT/WITH). Maks 500 qator.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
    types.FunctionDeclaration(
        name="wb_cells",
        description="Varaqning xom kataklari (A1 diapazon, masalan B3:L12) — noodatiy joylashuvlar uchun.",
        parameters={
            "type": "object",
            "properties": {"sheet": {"type": "string"}, "a1_range": {"type": "string"}},
            "required": ["sheet", "a1_range"],
        },
    ),
    types.FunctionDeclaration(
        name="calculate",
        description="Arifmetika (masalan 1439533314.83 - 1000000000). Faqat + - * / ** va sonlar.",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    ),
    types.FunctionDeclaration(
        name="wb_catalog",
        description="Fayl katalogi: jadvallar, ustunlar, qator soni, sanalar.",
        parameters={"type": "object", "properties": {}},
    ),
]


def _run(
    business_id: int, file_id: str, cat: dict[str, Any], name: str, args: dict[str, Any]
) -> Any:
    try:
        if name == "wb_sql":
            return store.run_sql(business_id, file_id, str(args.get("query", "")))
        if name == "wb_cells":
            return store.cells(
                business_id, file_id, str(args.get("sheet", "")), str(args.get("a1_range", ""))
            )
        if name == "calculate":
            return {"result": calculate(str(args.get("expression", "")))}
        if name == "wb_catalog":
            return {"catalog": catalog_text(cat)}
    except Exception as exc:
        from apps.ai.gemini import scrub

        return {"error": scrub(str(exc))[:400]}
    return {"error": "unknown tool"}


_DEEP = re.compile(
    r"tahlil|nega|nima uchun|strategi|reja|prognoz|xavf|solishtir|tavsiya|qanday qilib|sabab|"
    r"baho|kelajak|optimallash|tejash|ko'paytir|oshir|risk|xulosa",
    re.I,
)


def is_deep(question: str) -> bool:
    return question == SUMMARY_Q or len(question) > 160 or bool(_DEEP.search(question))


def models(deep: bool = False) -> tuple[str, ...]:
    return tuple(cfg.AI_ANALYST_DEEP_CHAIN if deep else cfg.AI_ANALYST_CHAIN)


def analyst_spent_today() -> Decimal:
    from django.db.models import Sum
    from django.utils import timezone

    from apps.telemetry.models import AiUsage

    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    v = AiUsage.objects.filter(kind="analyst", created_at__gte=start).aggregate(s=Sum("cost_usd"))[
        "s"
    ]
    return Decimal(v or 0)


def ask(
    business_id: int, file_id: str, question: str, history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    from apps.ai import budget
    from apps.ai.gemini import client

    budget.check("analyst")
    if analyst_spent_today() >= Decimal(str(cfg.AI_ANALYST_DAILY_BUDGET_USD)):
        return {
            "markdown": "**Bugungi chuqur tahlil limiti tugadi.** Ertaga qayta urinib ko'ring.",
            "model": "limit",
            "steps": 0,
        }
    cat = store.load_catalog(business_id, file_id)
    sys_text = SYSTEM + "\n\nKATALOG:\n" + catalog_text(cat)
    contents: list[types.Content] = []
    for h in (history or [])[-6:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=str(h.get("text", ""))[:4000])])
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    t0 = time.perf_counter()
    last_err = None
    deep = is_deep(question)
    for model in models(deep):
        thinking = (cfg.AI_ANALYST_DEEP_THINKING if deep else cfg.AI_ANALYST_THINKING).get(model)
        conf = types.GenerateContentConfig(
            system_instruction=sys_text,
            tools=[types.Tool(function_declarations=DECLS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2,
            max_output_tokens=6000,
            **(
                {"thinking_config": types.ThinkingConfig(thinking_level=thinking)}
                if thinking
                else {}
            ),
        )
        convo = list(contents)
        sql_log: list[dict[str, Any]] = []
        try:
            for step in range(MAX_STEPS):
                r = client().models.generate_content(model=model, contents=convo, config=conf)
                budget.record(
                    "analyst",
                    model,
                    usage=getattr(r, "usage_metadata", None),
                    business_id=business_id,
                )
                cand = r.candidates[0] if r.candidates else None
                parts = list(cand.content.parts or []) if cand and cand.content else []
                calls = [p.function_call for p in parts if p.function_call]
                if not calls:
                    text = "".join(
                        p.text or "" for p in parts if not getattr(p, "thought", False)
                    ).strip()
                    if not text:
                        raise RuntimeError("empty answer")
                    return {
                        "markdown": text,
                        "model": model,
                        "steps": step,
                        "ms": round((time.perf_counter() - t0) * 1000),
                        "queries": sql_log,
                    }
                convo.append(cand.content)
                resp_parts = []
                for fc in calls:
                    args = dict(fc.args or {})
                    out = _run(business_id, file_id, cat, fc.name, args)
                    sql_log.append({"tool": fc.name, "args": args, "ok": "error" not in out})
                    resp_parts.append(
                        types.Part.from_function_response(name=fc.name, response={"result": out})
                    )
                convo.append(types.Content(role="user", parts=resp_parts))
            # out of steps: ask for the answer without tools
            convo.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text="Endi tool chaqirmasdan, topilgan natijalar bilan yakuniy javobni yoz."
                        )
                    ],
                )
            )
            r = client().models.generate_content(
                model=model,
                contents=convo,
                config=types.GenerateContentConfig(
                    system_instruction=sys_text, temperature=0.2, max_output_tokens=6000
                ),
            )
            budget.record(
                "analyst", model, usage=getattr(r, "usage_metadata", None), business_id=business_id
            )
            return {
                "markdown": (r.text or "").strip(),
                "model": model,
                "steps": MAX_STEPS,
                "ms": round((time.perf_counter() - t0) * 1000),
                "queries": sql_log,
            }
        except Exception as exc:
            from apps.ai.gemini import scrub

            last_err = scrub(str(exc))[:200]
            log.warning("analyst model %s failed: %s", model, last_err)
            continue
    return {
        "markdown": "**Hozir tahlil qila olmadim.** Birozdan keyin qayta urinib ko'ring.",
        "model": "error",
        "error": last_err,
        "steps": 0,
    }
