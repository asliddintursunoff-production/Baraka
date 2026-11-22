"""Chat orchestrator (spec §5.5) as an async event stream.

1. Parallel: memory retrieval (skipped when nothing is embedded) + cash status from cache.
2. Chips: tool + template answer, no LLM (fast path).
3. Purchase-looking text: evaluate_purchase runs immediately (speculative) -> `blocks`
   within ~200 ms. If the LLM calls the same tool with the same args, the cached result
   is reused; different args -> the LLM's result wins and the cards are replaced.
4. LLM via the fallback chain, <= 3 tool rounds, final structured answer (JSON schema).
5. Number guard; one retry; then the engine-made template answer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from google.genai import errors as genai_errors
from google.genai import types

from apps.actions.audit import audit
from apps.insights import advice
from apps.knowledge.models import BusinessRule
from apps.telemetry.models import LatencyEvent
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business
from config import app_settings as cfg

from . import uz_format as uz
from .cfo_router import route
from .gemini import scrub
from .guard import concrete_step, pairing_violations, payment_keys, violations
from .llm import AllModelsFailed, generate
from .models import Conversation, Message
from .playbooks import playbook_text
from .router import advisor_hint, classify
from .tools import TOOLS, ToolArgError, ToolContext, for_model, run_tool
from .uz_parse import looks_like_purchase, parse_amounts

log = logging.getLogger(__name__)

CHIPS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "cash": ("Hozir qancha pulim bor?", "get_cash_status", {}),
    "revenue_drop": (
        "Savdo kamaysa nima bo'ladi?",
        "simulate_change",
        {"kind": "revenue_pct", "value": -20},
    ),
    "staff": (
        "Yana 2 ta xodim olsam bo'ladimi?",
        "simulate_change",
        {"kind": "new_staff", "value": 2},
    ),
}
CONTROL_TOOLS = {"remember_fact", "set_staff_count", "propose_plan", "confirm_plan"}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["yes", "no", "risky", "info"]},
        "headline": {"type": "string", "description": "<= 60 belgi, avval qaror"},
        "reason": {"type": "string", "description": "bitta jumla"},
        "steps": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "chips": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "show_blocks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "headline", "reason", "steps"],
}
SYSTEM = """Sen {app} — "{biz}" biznesining shaxsiy AI moliyaviy direktorisan (AI CFO). Bugun: {today}.
Qoidalar:
1. Faqat o'zbek tilida (lotin) yoz.
2. Raqam, summa va sanani FAQAT tool natijasidan yoki pastdagi kontekstdan ol, o'zing hisoblama. Summalarni tool'dagi "display" ko'rinishida yoz (masalan "6,2 mln").
3. Pul haqidagi savolda avval tegishli tool'ni chaqir: xarid yoki katta xarajat -> evaluate_purchase; "agar..." -> simulate_change; aniq kun -> explain_day; kelgusi to'lovlar yoki kelgusi xarajatlar -> get_upcoming_payments; o'tgan oylar xarajati, oylik xarajatlar, tushum, kategoriyalar -> get_expenses; kassa -> get_cash_status; prognoz -> get_forecast; foydalanuvchi biznes qoidasini yoki tuzatishni aytsa -> remember_fact; xodimlar sonini aytsa -> set_staff_count.
4. Batafsil savollar uchun tool'lar: mahsulot (un, kartoshka, go'sht, yog'...) xaridi yoki narxi -> product_costs; taom, menyu, retsept, 1 porsiya tannarxi -> menu_analysis; isrof, kamomad, hisobdan chiqarish -> losses; xodimlar, kimga qancha ish haqi -> staff_costs; ombor -> stock_status; jihozlar -> fixed_assets; zararsizlik -> break_even; savdo tushsa -> stress_test; kassadagi pul qayerdan -> cash_sources; qarzlar va majburiyatlar -> net_position; kredit jadvali -> debt_schedule; KPI, food cost, marja -> kpi_scorecard; reja-fakt -> plan_vs_actual; tushum nega o'zgardi -> driver_decomposition; haftalik trend -> trend_watch.
{md_rules}
5. Oddiy so'zlar: kassa, majburiy to'lov, oylik, kredit, ta'minotchi, xavfsiz chegara. "stsenariy", "zaxira", "deterministik" so'zlarini ishlatma.
6. Raqam o'ylab topma: avval qidir (lookup), keyin hisobla, bo'lmasa "taxmin" deb belgilab oraliq ber va bitta aniqlashtiruvchi savol ber.
7. Reja yoki eslatmani faqat taklif qil; tasdiqlashni foydalanuvchi tugma bilan qiladi. remember_fact faqat taklif yaratadi: foydalanuvchi tasdiqlamaguncha qoida prognozga qo'shilmaydi.
Kontekst:
{context}"""
MD_RULES = """Javob formati — markdown (JSON emas), o'zbek tilida:
- 1-qator: **qalin to'g'ridan-to'g'ri javob** (summa va/yoki sana bilan). Kassa yoki hisobot haqida bo'lsa holat sanasini yili bilan yoz (masalan "31-oktyabr 2026 holatiga").
- Keyin faqat savolga kerakli bo'limlar, "### " sarlavha bilan: ### Nima uchun (2–4 band, raqamlar tool'dan); ### Kelajakda nima bo'ladi; ### Variantlar (jadval bo'lishi mumkin); ### Tavsiyam (bitta aniq tavsiya); ### Reja (ko'pi bilan 5 ta raqamlangan qadam: sana yoki muddat + aniq harakat + summa); ### Menga kerak (faqat ma'lumot yetishmasa, aniq savol).
- Biznes holati yoki umumiy tahlil so'ralsa yana: ### Pul manbai, ### Yashirin xavf, ### Yakuniy baho.
- Tool natijasidagi "md" matni tayyor jadval va raqamlar: undan foydalan, jadvallarni qisqartirib bo'lsa ham ko'rsat. Mahsulot, taom, xodim nomlarini aniq yoz; "boshqa xarajatlar" deb umumlashtirma.
- Tool natijasida yo'q sana yoki sonni yozma (masalan "2-noyabrgacha buyurtma bering" — bunday sana yo'q bo'lsa, "shu hafta" de). Jami, farq yoki o'rtachani o'zing hisoblama; tool'da "combined_total" kabi tayyor jami bo'lsa, faqat o'shani ishlat.
- Qisqa savolga ham TO'LIQ javob ber: raqam + SABAB (pul qayerga ketdi: qaysi modda, qaysi mahsulot, qancha, o'tgan oyga nisbatan) + nima qilish kerak. "Shuncha bor edi" deb to'xtama — nega o'zgarganini tushuntir. Qisqa savol oldingi xabarlarning davomi bo'lishi mumkin: suhbat tarixidan mavzuni ol ("nech pulga?" — oldingi tavsiyadagi narx haqida).
- Narx tavsiya qilsang, bozor narxlari bilan solishtir (market_prices tool: Toshkentdagi raqobatchilar — Oqtepa Lavash, Evos, Max Way va h.k.).
- Eng oxirgi qator: "CHIPS: savol 1 | savol 2 | savol 3" — shu javobga bog'liq keyingi 3 ta savol."""
ADVISOR_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "to'g'ridan-to'g'ri javob: sana va/yoki summa bilan",
        },
        "reason": {"type": "string", "description": "bitta jumla"},
        "plan": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "when": {"type": "string"},
                    "action": {"type": "string"},
                    "amount": {"type": "string"},
                },
                "required": ["when", "action"],
            },
        },
        "numbers_block_ids": {"type": "array", "items": {"type": "string"}},
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "key": {"type": "string"}},
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
        "question": {"type": "string"},
        "chips": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": ["headline", "plan"],
}
ADVISOR_SYSTEM = """Sen {app} — "{biz}" biznesining shaxsiy moliyaviy maslahatchisisan (AI CFO). Bugun: {today}.
Vazifang: qaror qabul qilishga yordam berish va aniq, sanali reja berish.
Qoidalar:
1. Faqat o'zbek tilida (lotin) yoz.
2. Har bir raqam, summa va sana FAQAT tool natijasidan. O'zing hisoblama, raqam o'ylab topma. Summalarni tool'dagi ko'rinishda yoz ("8,8 mln").
3. Avval kerakli tool'ni chaqir: xaridni qachon qilish -> when_can_afford; pul yig'ish -> savings_goal; foydalanuvchi qarzini aytsa -> record_debt (u qarzni yozadi va to'lash variantlarini solishtiradi); qarzni to'lash -> debt_payoff; kredit -> loan_affordability (foiz noma'lum bo'lsa so'ra); uskuna yoki investitsiya -> evaluate_investment (narx bilan; foyda + kassa + vaqt + verdikt OLING/KUTING/OLMANG; hech qachon faqat 'kassa tushadi' dema — pul uskunaga aylanadi, zarar emas); foydani oshirish / nima qilish kerak -> growth_plan; rentabellik/top taomlar -> profitability; reklama/qancha ko'p sotish -> promote_target; kontragent qarzlari -> payables; yangi ishchi -> hire_payback; qo'shimcha pul qayerga -> allocate_capital; 'hozir olaymi, oylikdan keyinmi, bo'lib to'laymi' -> suhbatdagi oxirgi narx bilan evaluate_investment (unda oylik/kredit tekshiruvi va variantlar jadvali bor); har javobda isbot (qaysi varaq/raqam) va guideline ber, pulni yo'qotish xavfini ayt; (narx aytilmagan bo'lsa AVVAL web_price_lookup, keyin topilgan narx bilan evaluate_investment: internetdan Toshkent narxini topadi; topilgan typical narx bilan evaluate_investment chaqir, foydalanuvchidan narx so'rama; topilmasa narxni so'ra; quvvat (capacity_portions_day) bo'lsa, rejadagi porsiya undan oshmasligini ayt; foydalanuvchi porsiya aytmasa, web_price_lookup jadvalidagi 20/30/50 porsiya holatlarini maslahat qil); savdoni oshirish -> revenue_growth_target; narx -> price_change; "biznesim qanday" -> business_snapshot; "agar..." -> simulate_change. Kerak bo'lsa bir nechta tool chaqir.
4. Tool "needs" qaytarsa: o'sha savolni "question" ga yoz va headline'da "Buni aniq hisoblash uchun ... kerak" de. Raqamni taxmin qilma.
5. CFO modullari ham bor: break_even, stress_test, cash_sources, net_position, debt_schedule, kpi_scorecard, plan_vs_actual, driver_decomposition, trend_watch, product_costs, menu_analysis, losses, staff_costs.
{md_rules}
6. Taqiqlangan: sana, summa yoki aniq ob'ektsiz umumiy qadamlar ("Kassani tekshiring", "Kuzatib boring", "Chora ko'ring").
7. Strategiya taklif qilsang, uni shu biznes ma'lumotiga bog'la (masalan: "Dushanba savdosi shanbadan 35% past -> tushlik seti") va ta'sir raqamini faqat tool orqali ber, "taxmin" deb belgila.
8. Qarz yoki reja faqat taklif: tasdiqlashni foydalanuvchi tugma bilan qiladi.
Maslahatlar bazasi (umumiy yondashuvlar, raqamsiz):
{playbooks}
Kontekst:
{context}"""


T = TypeVar("T")


async def db[T](business: Business, fn: Callable[[], T]) -> T:
    """Run ORM work in a thread with the tenant context set inside that thread
    (never held across an async generator's yields)."""

    def _run() -> T:
        with tenant_context(business):
            return fn()

    return await sync_to_async(_run)()


def sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n".encode()


@dataclass
class Turn:
    business: Business
    user_id: int
    author: str
    conversation: Conversation
    text: str
    chip: str | None = None
    voice: dict[str, Any] | None = None
    t0: float = field(default_factory=time.perf_counter)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "quick"  # quick | advisor (apps.ai.router)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)  # name -> last result
    blocks_sent_ms: float | None = None

    def ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000


def context_lines(ctx: ToolContext) -> list[str]:
    base = ctx.base
    if base.insufficient_data:
        return ["Ma'lumot kam: ishonchli prognoz uchun kamida 2 haftalik tarix kerak."]
    cash = base.close_on(base.today)
    from .tools import freshness_note

    fresh = freshness_note(ctx.business)
    q = ctx.business.data_quality or {}
    gap = (
        [
            "Ma'lumot kiritilmagan davr: "
            f"{uz.format_date(date.fromisoformat(q['missing_from']))} – "
            f"{uz.format_date(date.fromisoformat(q['missing_to']))}."
        ]
        if fresh and q.get("missing_from") and q.get("missing_to")
        else []
    )
    lines = [
        *gap,
        f"Hozirgi kassa: {uz.format_mln(cash)}"
        + (
            f" ({fresh}). Kassa haqida gapirganda shu holat sanasini albatta ayt." if fresh else "."
        ),
        f"Eng qiyin kun (keyingi 60 kun): {uz.format_date(base.min_date)} {base.min_date.year}, {uz.format_mln(base.min_balance)} qoladi.",
        f"Xavfsiz chegara: {uz.format_mln(base.safe_min)}.",
        "Yaqin majburiy to'lovlar: "
        + "; ".join(
            f"{uz.format_date(p.date)} {p.title} {uz.format_mln(p.amount)}"
            for p in [o for o in base.obligations if o.date > base.today][:5]
        ),
    ]
    rules = list(
        BusinessRule.objects.filter(enabled=True)
        .order_by("-created_at")
        .values_list("text_uz", flat=True)[:10]
    )
    if rules:
        lines.append("Tasdiqlangan qoidalar: " + "; ".join(rules))
    if ctx.business.staff_count:
        lines.append(f"Xodimlar soni: {ctx.business.staff_count}.")
    return lines


def template_answer(result: dict[str, Any]) -> dict[str, Any]:
    a = dict(result.get("answer") or {})
    a.setdefault("verdict", result.get("verdict") or "info")
    a.setdefault("steps", [])
    return a


def _texts_of(result: dict[str, Any]) -> list[str]:
    return [
        json.dumps(for_model(result), ensure_ascii=False, default=str),
        json.dumps(result.get("answer") or {}, ensure_ascii=False),
        json.dumps(result.get("ui_blocks") or [], ensure_ascii=False, default=str),
    ]


def finalize(turn: Turn, answer: dict[str, Any], model: str) -> dict[str, Any]:
    """Merge the chosen answer with engine-made parts (blocks, plan, candidate, explain)."""
    primary = next(reversed(turn.results.values()), None) if turn.results else None
    blocks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for r in turn.results.values():
        for blk in r.get("ui_blocks", []):
            bid = str(blk.get("id") or len(blocks))
            if bid not in seen_ids:
                seen_ids.add(bid)
                blocks.append(blk)
    wanted = answer.get("show_blocks")
    if wanted:
        chosen = [b for b in blocks if b.get("id") in wanted]
        blocks = chosen or blocks
    tmpl = (primary or {}).get("answer") or {}
    last_tool = turn.tool_calls[-1]["name"] if turn.tool_calls else ""
    if last_tool in CONTROL_TOOLS and tmpl:
        # State-changing tools: the exact engine/template wording, never an LLM paraphrase
        # (e.g. a rule is NOT applied until the person confirms it).
        answer = {**tmpl, "chips": answer.get("chips") or tmpl.get("chips", [])}
    out = {
        "verdict": answer.get("verdict") or tmpl.get("verdict") or "info",
        "headline": (answer.get("headline") or tmpl.get("headline") or "")[:80],
        "reason": answer.get("reason") or tmpl.get("reason") or "",
        "steps": list(answer.get("steps") or tmpl.get("steps") or [])[:3],
        "blocks": blocks,
        "chips": list(answer.get("chips") or tmpl.get("chips") or [])[:3],
        "plan": (primary or {}).get("proposed_plan"),
        "candidate": (primary or {}).get("candidate"),
        "explain": tmpl.get("explain", []),
        "speech": (primary or {}).get("say")
        or " ".join([answer.get("headline", ""), answer.get("reason", "")]).replace("**", ""),
        "model": model,
        "mode": turn.mode,
        "advisor": None,
        "markdown": answer.get("markdown")
        or (template_markdown(turn) if model == "template" else ""),
    }
    if turn.mode == "advisor":
        plan = [
            p
            for p in (answer.get("plan") or tmpl.get("plan") or [])
            if isinstance(p, dict) and p.get("action")
        ]
        plan = plan[: cfg.ADVISOR_PLAN_MAX]
        tool_assumptions = list((primary or {}).get("assumptions") or [])
        needs = (primary or {}).get("needs") or []
        out["advisor"] = {
            "plan": [
                {
                    "when": str(p.get("when", "")),
                    "action": str(p["action"]),
                    "amount": str(p.get("amount") or ""),
                }
                for p in plan
            ],
            "assumptions": tool_assumptions,
            "risks": [str(r) for r in (answer.get("risks") or [])][:2],
            "question": answer.get("question") or (needs[0]["text"] if needs else None),
        }
        out["steps"] = [f"{p.get('when', '')}: {p['action']}" for p in plan][:3]
        ids = answer.get("numbers_block_ids")
        if ids:
            out["blocks"] = [b for b in blocks if b.get("id") in ids] or blocks
    return out


async def run_tool_async(
    turn: Turn, ctx: ToolContext, name: str, args: dict[str, Any], *, source: str
) -> dict[str, Any]:
    t = time.perf_counter()

    def _run() -> dict[str, Any]:
        with tenant_context(turn.business):
            try:
                result = run_tool(ctx, name, args)
            except ToolArgError:
                raise
            except Exception as exc:  # a tool bug must never hang the chat stream
                log.warning("tool %s failed: %s", name, scrub(str(exc))[:200])
                result = {
                    "error": "tool_failed",
                    "md": f"'{name}' hisobini hozir bajarib bo'lmadi — boshqa ma'lumot bilan javob ber.",
                    "ui_blocks": [],
                }
            audit(
                "ai",
                "tool_call",
                tool=name,
                args={**args, "source": source},
                result=for_model(result),
            )
            return result

    result = await sync_to_async(_run)()
    turn.tool_calls.append(
        {
            "name": name,
            "args": args,
            "ms": round((time.perf_counter() - t) * 1000, 1),
            "source": source,
        }
    )
    store_result(turn, name, args, result)
    return result


def store_result(turn: Turn, name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    """One entry per distinct call: two products in one question keep both results."""
    if any(r is result for r in turn.results.values()):
        return
    key = name if name not in turn.results else _args_key(name, args)
    turn.results.pop(key, None)  # re-insert at the end: the newest result stays primary
    turn.results[key] = result


def _args_key(name: str, args: dict[str, Any]) -> str:
    return name + json.dumps(
        {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in args.items()},
        sort_keys=True,
        default=str,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


FULL_CONTEXT_RULES = """Sen — egasining shaxsiy CFO'si va biznes maslahatchisisan (ChatGPT kabi erkin, lekin biznesni to'liq bilasan). Faqat o'zbek tilida (lotin) javob ber.
- Pul, biznes, bank, kredit, bo'lib to'lash, soliq, narx/bozor, raqobatchilar, ta'minotchilar, xodimlar, o'sish, xavf, investitsiya — HAR QANDAY savolga javob ber.
- "Biznesimni qanday qulatishim mumkin?" kabi savolga ochiq javob ber: SHU biznes qanday yo'llar bilan qulashi mumkin (digest raqamlari bilan) va har birining oldini olish — xavf xaritasi jadvali.
- Biznes raqamlari faqat pastdagi BIZNES DIGEST va tool natijalaridan. Bozor, bank foizlari, benchmarklar — web_lookup (manbasi bilan); imkon bo'lmasa asosli taxmin ber va "taxmin" deb belgila.
- Hech qachon faqat "ma'lumot yo'q" dema: nima yetishmayotganini ayt, baribir eng yaxshi javobni ber va bitta yetishmayotgan ma'lumotni so'ra.
- Qat'iy bo'l: avval verdikt (qalin), keyin raqamlar, keyin reja. Har qanday solishtirish, reja, jadval, variantlar — markdown jadval bilan.
- Faqat aniq aloqasiz mavzularni (tarix, mashhurlar, uy vazifasi) bitta gap bilan rad et va biznes tomonini taklif qil.
- JAVOB SIYOSATI (qat'iy): 1) AVVAL QIDIR — barcha varaqlar va digestdan sinonimlar bilan (oylik = ish haqi = oklad = maosh; oshpaz ⊇ "Bosh oshpaz", "Oshpaz N", "Lavash ustasi", "Fritur / burger"; xodim = ishchi). Kerak bo'lsa lookup tool'ini chaqir. 2) HISOBLA — har qanday what-if (oylik, narx, xodim, ijara, kredit, xarid, hajm): oylik foydaga ta'sir, kassa necha oyga yetadi, verdikt, 2 alternativa (salary_change va boshqa tool'lar). 3) TAXMIN QIL — ma'lumot haqiqatan yo'q bo'lsa: yaqin ma'lumot, benchmark yoki web_lookup; "taxmin" deb belgila, oraliq va farazlar bilan; keyin BITTA aniqlashtiruvchi savol ber. 4) "Ma'lumot yo'q" faqat aniq fakt yo'q bo'lsa (telefon raqami, shartnoma bandi) — shunda ham eng yaqin faktni va uni qanday qo'shishni ayt. 5) TAQIQLANGAN yakka javoblar: "Bu ma'lumot jadvalingizda yo'q." va "Men faqat biznesingiz puli bo'yicha yordam bera olaman" — biznes/pul mavzusida hech qachon.
- Hissiy xabar ("xafa bo'ldim"): bitta iliq, hamdard gap, keyin yordamni davom ettir (holat, bitta ijobiy fakt, bitta aniq qadam).
- Prognoz "TAXMINIY" bo'lsa, buni bir gap bilan ayt, lekin javob berishdan bosh tortma.
- Tool natijasida tayyor hisobot (golden report, "md") bo'lsa: uni o'zgartirmasdan asos qil — xulosa va raqamlar aynan shu yerdan; o'zingdan raqam qo'shma, jadvallarni saqlab qol.
- Hisobotdan keyingi qo'shimcha savollar SHU hisobot kontekstida: "nega?" — sababini hisobot raqamlari bilan; "qanday hisobladi?" — formulani oddiy tilda (manba varaqlari bilan); "qachon pul tushadi?" — kontragent/sanalar; bozor narxi ("Telegram-bot qancha turadi?") — taxmin (belgilangan) + qoplash muddati hisobot foydasi bilan; muzokara ("komissiyani kamaytirsa?") — hajm × punkt. Qisqa (3–6 qator), aniq; hech qachon "javob bera olmayman" dema."""


def recent_dialogue(business: Any, exclude: int | None = None, n: int = 12) -> str:
    """Last messages across chat + voice conversations (Live and new chats keep the context)."""
    qs = Message.objects.filter(business=business)
    if exclude:
        qs = qs.exclude(conversation_id=exclude)
    rows = list(qs.order_by("-created_at").values("role", "content", "answer")[:n])[::-1]
    out = []
    for r in rows:
        text = r["content"] or ""
        if (
            r["role"] != "user"
            and isinstance(r.get("answer"), dict)
            and r["answer"].get("markdown")
        ):
            text = str(r["answer"]["markdown"])[:600]
        out.append(f"{'Foydalanuvchi' if r['role'] == 'user' else 'AI'}: {text[:600]}")
    return "\n".join(out)


def parse_answer(text: str) -> dict[str, Any] | None:
    """Markdown answer (the contract) or the older JSON answer; chips from the last line."""
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith(("{", "```json")):
        return _extract_json(raw)
    chips: list[str] = []
    lines = raw.rstrip().split("\n")
    keep = []
    for ln in lines:  # a CHIPS line anywhere (not only last) is never shown as text
        if re.match(r"^\W*chips\W*:", ln, re.IGNORECASE):
            chips = chips or [
                c.strip(" *`") for c in ln.split(":", 1)[1].split("|") if c.strip(" *`")
            ]
        else:
            keep.append(ln)
    raw = "\n".join(keep).rstrip()
    first = next((ln for ln in raw.split("\n") if ln.strip()), "")
    headline = re.sub(r"[*#`_]", "", first).strip()
    return {"markdown": raw, "headline": headline, "reason": "", "steps": [], "chips": chips[:3]}


def template_markdown(turn: Turn) -> str:
    """The engine-made fallback: each module's own markdown, in the order they ran."""
    md = "\n\n".join(str(r["md"]) for r in turn.results.values() if r.get("md"))
    return re.sub(r"(?im)^\W*chips\W*:.*$\n?", "", md).strip()


def md_chunks(md: str, size: int = 400) -> list[str]:
    """Paragraph-sized `delta` chunks (the answer is checked by the guard before it streams)."""
    out, buf = [], ""
    for para in md.split("\n\n"):
        piece = (buf + "\n\n" if buf else "") + para
        if len(piece) > size and buf:
            out.append(buf + "\n\n")
            buf = para
        else:
            buf = piece
    if buf:
        out.append(buf)
    return out


def demo_final(turn: Turn, d: dict[str, Any]) -> dict[str, Any]:
    """A demo-router answer in the chat's answer shape (model "golden" / "demo")."""
    r = d.get("result") or {}
    if d.get("intent"):
        turn.tool_calls.append({"name": d["intent"], "args": {}, "ms": 0, "source": "demo"})
    report = next((b for b in d["blocks"] if b.get("type") == "report"), None)
    head = (
        f"{report['verdict']} {report.get('verdict_highlight', '')}".strip()
        if report
        else (d["markdown"].split("\n")[0] if d["markdown"] else "")
    )
    return {
        "verdict": "info",
        "headline": re.sub(r"[*#`_]", "", head)[:80],
        "reason": "",
        "steps": [],
        "blocks": d["blocks"],
        "chips": [],
        "plan": r.get("proposed_plan"),
        "candidate": None,
        "explain": [],
        "speech": d["say"],
        "model": "golden" if d.get("intent") else "demo",
        "mode": turn.mode,
        "advisor": None,
        "markdown": d["markdown"],
        "demo": {
            "kind": d["kind"],
            "intent": d.get("intent"),
            "cards": d["cards"],
            "clip": d["clip"],
            "speech_key": d["speech_key"],
            "expand": d["expand"],
        },
    }


async def stream_turn(turn: Turn) -> AsyncIterator[bytes]:
    b = turn.business
    user_msg = await db(
        b,
        lambda: Message.objects.create(
            business=b,
            conversation=turn.conversation,
            role="user",
            author_name=turn.author,
            content=turn.text,
            answer={"voice": turn.voice} if turn.voice else None,
        ),
    )
    yield sse("meta", {"conversation_id": turn.conversation.pk, "user_message_id": user_msg.pk})
    yield sse("status", {"text": "Hisoblayapman…"})
    ctx = ToolContext(b, turn.user_id, "chat", last_user_text=turn.text)
    final: dict[str, Any] | None = None
    try:
        if cfg.DEMO_GOLDEN_ONLY and not turn.chip:
            # demo: Q1–Q4 only, every answer deterministic (no LLM call at all)
            from . import demo
            from .golden_tools import last_intent

            prev = await db(b, lambda: last_intent(turn.conversation.pk))
            d = await db(b, lambda: demo.answer(ctx, turn.text, prev))
            if d["kind"] != "other":  # anything outside Q1–Q4: the normal AI pipeline below
                final = demo_final(turn, d)
            if final is not None and final["blocks"]:
                turn.blocks_sent_ms = turn.ms()
                yield sse("blocks", {"blocks": final["blocks"], "replace": True})
        if final is None:
            # 1. context (cache) — embeddings are skipped until memory is embedded (M7)
            lines = await db(b, lambda: context_lines(ctx))

            # 2. chip fast path
            if turn.chip:
                _, tool, args = CHIPS[turn.chip]
                result = await run_tool_async(turn, ctx, tool, args, source="chip")
                turn.blocks_sent_ms = turn.ms()
                yield sse("blocks", {"blocks": result.get("ui_blocks", []), "replace": True})
                final = finalize(turn, template_answer(result), "template")
            else:
                speculative: dict[str, dict[str, Any]] = {}
                turn.mode = classify(turn.text)
                from .golden_tools import last_intent

                prev = await db(b, lambda: last_intent(turn.conversation.pk))
                routed = await db(b, lambda: route(turn.text, prev))
                from .golden_tools import INTENTS as _GI
                from .golden_tools import is_side_question

                if prev and (not routed or is_side_question(turn.text)):
                    # side question about the last golden report ("nega?", "qanday hisobladi?"):
                    # the report is recomputed as context and the model answers from it
                    g_tool = next((i.tool for i in _GI if i.id == prev), None)
                    if g_tool:
                        routed = [(g_tool, {})]
                        turn.golden_context = True  # type: ignore[attr-defined]
                routed_blocks: list[dict[str, Any]] = []
                for name, args in routed:
                    try:
                        result = await run_tool_async(turn, ctx, name, dict(args), source="router")
                    except ToolArgError:
                        continue
                    speculative[_args_key(name, dict(args))] = result
                    routed_blocks += result.get("ui_blocks", [])
                totals = [
                    Decimal(r["facts"]["total_raw"])
                    for r in turn.results.values()
                    if isinstance(r.get("facts"), dict) and r["facts"].get("total_raw")
                ]
                if len(totals) > 1:  # "un va kartoshkaga": the sum comes from code, not the LLM
                    turn.results["combined_total"] = {
                        "facts": {"combined_total": uz.format_mln(sum(totals, Decimal(0)))}
                    }
                if routed_blocks:
                    turn.blocks_sent_ms = turn.ms()
                    yield sse(
                        "blocks", {"blocks": routed_blocks, "replace": True, "speculative": True}
                    )
                hint = advisor_hint(turn.text) if turn.mode == "advisor" else None
                if hint:
                    try:
                        result = await run_tool_async(
                            turn, ctx, hint[0], dict(hint[1]), source="speculative"
                        )
                        speculative[_args_key(hint[0], dict(hint[1]))] = result
                        turn.blocks_sent_ms = turn.ms()
                        yield sse(
                            "blocks",
                            {
                                "blocks": result.get("ui_blocks", []),
                                "replace": True,
                                "speculative": True,
                            },
                        )
                    except ToolArgError:
                        pass
                elif looks_like_purchase(turn.text):
                    amounts = parse_amounts(turn.text)
                    spec_args: dict[str, Any] = {"amount": int(amounts[0])}
                    try:
                        result = await run_tool_async(
                            turn, ctx, "evaluate_purchase", spec_args, source="speculative"
                        )
                        speculative[_args_key("evaluate_purchase", spec_args)] = result
                        turn.blocks_sent_ms = turn.ms()
                        yield sse(
                            "blocks",
                            {
                                "blocks": result.get("ui_blocks", []),
                                "replace": True,
                                "speculative": True,
                            },
                        )
                    except ToolArgError:
                        pass
                final, _model = None, "template"
                from .golden_tools import GOLDEN_TOOLS

                golden = {t.name for t in GOLDEN_TOOLS} | {"catalog", "bad_intent"}
                gres = next(
                    (
                        turn.results[k]
                        for k in reversed(list(turn.results))
                        if any(k.startswith(g) for g in golden)
                    ),
                    None,
                )
                if gres is not None and gres.get("pinned_side"):
                    final = finalize(turn, template_answer(gres), "golden")
                    final["markdown"] = str(gres.get("md") or "")
                elif gres is not None and not getattr(turn, "golden_context", False):
                    # golden question: the golden tool's answer (report, or its failure explanation)
                    # is final — never let the model switch to another intent
                    # golden report: the deterministic card IS the answer (no LLM, every number from the tool)
                    final = finalize(turn, template_answer(gres), "golden")
                    md = str(gres.get("md") or "")
                    has_report = any(bl.get("type") == "report" for bl in gres.get("ui_blocks", []))
                    final["markdown"] = (
                        "" if has_report else re.sub(r"\n?CHIPS:.*$", "", md.rstrip())
                    )
                    last = md.rstrip().splitlines()[-1] if md.strip() else ""
                    if last.upper().startswith("CHIPS:"):
                        final["chips"] = [
                            c.strip() for c in last.split(":", 1)[1].split("|") if c.strip()
                        ][:3]
                try:
                    if final is None:
                        async for item in llm_loop(turn, ctx, lines, speculative):
                            if isinstance(item, bytes):
                                yield item
                            else:
                                final, _model = item
                except (genai_errors.APIError, ValueError) as exc:  # never break the stream
                    log.warning("llm loop failed, using template: %s", str(exc)[:200])
                if final is None:
                    # the model's text was rejected (or failed): a deterministic report the model
                    # itself called (catalog / golden) is the cleanest answer — card only, no glued text
                    card = next(
                        (
                            turn.results[k]
                            for k in reversed(list(turn.results))
                            if any(k.startswith(g) for g in golden)
                            and any(
                                b.get("type") == "report"
                                for b in turn.results[k].get("ui_blocks", [])
                            )
                        ),
                        None,
                    )
                    primary = card or next(reversed(turn.results.values()), None)
                    if primary is None:
                        raise AllModelsFailed("no answer and no tool result")
                    final = finalize(
                        turn, template_answer(primary), "golden" if card else "template"
                    )
                    if card is not None:
                        final["markdown"] = ""
                        final["blocks"] = list(card.get("ui_blocks", []))
    except AllModelsFailed:
        yield sse(
            "error",
            {
                "message": "AI hozir band. Bir daqiqadan keyin qayta so'rang yoki pastdagi tayyor savollardan foydalaning."
            },
        )
        return
    except ToolArgError as exc:
        log.info("tool arg error: %s", exc)
        yield sse("error", {"message": "Savolni tushunmadim. Summa yoki sanani aniqroq yozing."})
        return
    for chunk in md_chunks(final.get("markdown") or ""):
        yield sse("delta", {"text": chunk})
    yield sse("answer", final)
    latency = turn.ms()
    msg = await db(
        b,
        lambda: Message.objects.create(
            business=b,
            conversation=turn.conversation,
            role="assistant",
            author_name="AI CFO",
            content=final["headline"],
            answer=final,
            ui_blocks=final["blocks"],
            tool_calls=turn.tool_calls,
            model=final["model"],
            latency_ms=round(latency),
        ),
    )
    events = [
        LatencyEvent(
            business=b,
            channel="chat",
            name="send_to_answer",
            ms=latency,
            model=final["model"],
            meta={"chip": turn.chip or "", "tools": [t["name"] for t in turn.tool_calls]},
        )
    ]
    if turn.blocks_sent_ms is not None:
        events.append(
            LatencyEvent(
                business=b,
                channel="chat",
                name="send_to_blocks",
                ms=turn.blocks_sent_ms,
                model=final["model"],
                meta={},
            )
        )
    await db(b, lambda: LatencyEvent.objects.bulk_create(events))
    yield sse("done", {"message_id": msg.pk, "latency_ms": round(latency), "model": final["model"]})


async def llm_loop(
    turn: Turn, ctx: ToolContext, lines: list[str], speculative: dict[str, dict[str, Any]]
) -> AsyncIterator[bytes | tuple[dict[str, Any], str]]:
    advisor = turn.mode == "advisor"
    fmt = {
        "app": settings.APP_NAME,
        "biz": turn.business.name,
        "today": uz.format_date_long(ctx.base.today),
        "context": "\n".join(lines),
    }
    if advisor:
        fmt["playbooks"] = await db(turn.business, lambda: playbook_text(turn.business, turn.text))
    fmt["md_rules"] = MD_RULES
    from .growth_tools import market_facts_text

    fmt["md_rules"] += "\n- " + market_facts_text()[:1500].replace("{", "(").replace("}", ")")
    system = (ADVISOR_SYSTEM if advisor else SYSTEM).format(**fmt)
    from .digest import digest_for

    digest = await db(turn.business, lambda: digest_for(turn.business))
    system = (
        FULL_CONTEXT_RULES
        + "\n\n"
        + system
        + "\n\n# BIZNES DIGEST (hamma raqamlar shu yerdan va tool'lardan)\n"
        + digest
    )
    lines = [*lines, *digest.splitlines()]
    guard_ctx = await db(turn.business, lambda: guard_context(ctx))
    history = await db(
        turn.business,
        lambda: list(
            Message.objects.filter(conversation=turn.conversation)
            .order_by("-created_at")
            .values("role", "content", "answer")[1:15]
        ),
    )

    def _hist_text(h: dict[str, Any]) -> str:
        if (
            h["role"] != "user"
            and isinstance(h.get("answer"), dict)
            and h["answer"].get("markdown")
        ):
            return str(h["answer"]["markdown"])[:1800]
        return h["content"] or "…"

    contents: list[types.Content] = [
        types.Content(
            role="user" if h["role"] == "user" else "model",
            parts=[types.Part(text=_hist_text(h))],
        )
        for h in reversed(history)
    ]
    voice_ctx = await db(
        turn.business, lambda: recent_dialogue(turn.business, exclude=turn.conversation.pk)
    )
    if voice_ctx and len(history) < 2:
        system += "\n\nOldingi suhbatlar (ovozli va boshqa chatlar, kontekst uchun):\n" + voice_ctx
    pre = [
        f"{name}: {json.dumps(for_model(r), ensure_ascii=False, default=str)}"
        for name, r in turn.results.items()
    ]
    user_text = turn.text
    if pre:
        user_text += (
            "\n\n[Oldindan hisoblangan tool natijalari — shulardan foydalan, yetmasa boshqa tool chaqir]\n"
            + "\n".join(pre)
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
    decls = [
        types.FunctionDeclaration(
            name=t.name, description=t.description, parameters_json_schema=t.parameters
        )
        for t in TOOLS.values()
    ]
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=decls)],
        max_output_tokens=8192,  # thinking counts too: 4000 cut long answers mid-sentence
    )
    model = "template"
    gen_kw: dict[str, Any] = {
        # owner 2026-11-22: quick facts on the fast model, plans/strategy on the strong one
        "chain": cfg.CHAT_FULL_CHAIN if advisor else cfg.CHAT_QUICK_CHAIN,
        "deadline_s": cfg.CHAT_FULL_DEADLINE_S if advisor else cfg.CHAT_QUICK_DEADLINE_S,
        "thinking": cfg.CHAT_FULL_THINKING,
        "kind": "advisor" if advisor else "chat",
    }
    for _round in range(cfg.ADVISOR_MAX_ROUNDS if advisor else 3):
        try:
            res = await generate(contents, config, **gen_kw)
        except genai_errors.ClientError as exc:
            if config.response_json_schema is not None:  # model can't mix tools + schema
                log.info("retrying without schema: %s", str(exc)[:120])
                config = config.model_copy(
                    update={"response_json_schema": None, "response_mime_type": None}
                )
                continue
            raise
        except AllModelsFailed:
            return
        model = res.model
        cand = res.response.candidates[0] if res.response.candidates else None
        parts = (cand.content.parts if cand and cand.content else None) or []
        calls = [p.function_call for p in parts if p.function_call]
        if not calls:
            answer = parse_answer(res.response.text or "")
            if answer is None:
                return
            checked = await check_answer(turn, answer, lines, guard_ctx)
            if checked is None:  # one retry with the violations pointed out
                contents.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=answer.get("markdown")
                                or json.dumps(answer, ensure_ascii=False)
                            )
                        ],
                    )
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text="Javobdagi ba'zi raqam, sana yoki to'lov-sana juftligi tool natijasiga mos emas, yoki qadam aniq emas (sana, summa yoki aniq ob'ekt yo'q). Faqat tool natijasidagi raqam va sanalar bilan, aniq qadamlar bilan markdown javobni qayta yoz."
                            )
                        ],
                    )
                )
                try:
                    res2 = await generate(contents, config, **gen_kw)
                    answer2 = parse_answer(res2.response.text or "")
                    checked = (
                        await check_answer(turn, answer2, lines, guard_ctx) if answer2 else None
                    )
                    model = res2.model
                    side = getattr(turn, "golden_context", False)
                    if checked is None and answer2 and (not turn.results or side):
                        log.info("guard still unhappy, no tool data: answering anyway")
                        checked = answer2
                except (AllModelsFailed, genai_errors.APIError):
                    checked = None
            if checked is None and (not turn.results or getattr(turn, "golden_context", False)):
                checked = (
                    answer  # side question / no tool data: never refuse (estimates are labelled)
                )
            if checked is None:
                return  # invented numbers: the tool-built template answer is used instead
            yield (finalize(turn, checked, model), model)
            return
        contents.append(cand.content)  # type: ignore[union-attr, arg-type]
        responses: list[types.Part] = []
        for call in calls:
            name = call.name or ""
            args = dict(call.args or {})
            key = _args_key(name, args)
            try:
                if key in speculative:
                    result = speculative[key]
                    store_result(turn, name, args, result)
                    turn.tool_calls.append(
                        {"name": name, "args": args, "ms": 0, "source": "speculative_hit"}
                    )
                else:
                    result = await run_tool_async(turn, ctx, name, args, source="llm")
                    if result.get("ui_blocks"):
                        if turn.blocks_sent_ms is None:
                            turn.blocks_sent_ms = turn.ms()
                        yield sse("blocks", {"blocks": result["ui_blocks"], "replace": True})
                payload = for_model(result)
            except ToolArgError as exc:
                payload = {"ok": False, "error": str(exc)}
            responses.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id, name=name, response=payload
                    )
                )
            )
        contents.append(types.Content(role="user", parts=responses))
    return


def guard_context(ctx: ToolContext) -> dict[str, Any]:
    """Real payment dates (for date<->payment pairing) and concrete object names."""
    base = ctx.base
    pairs = [
        ((o.date.day, o.date.month), payment_keys(o.category, o.counterparty, o.title))
        for o in base.obligations
    ]
    names = {o.counterparty for o in base.obligations if o.counterparty} | {
        o.title for o in base.obligations
    }
    names |= set(uz.WEEKDAYS) | {
        "tushlik",
        "yetkazib",
        "menyu",
        "narx",
        "chek",
        "porsiya",
        "ta'minotchi",
        "kredit",
        "qarz",
        "ijara",
        "oylik",
        "soliq",
        "jamg'ar",
        "set",
        "aksiya",
        "uskuna",
        "plita",
        "savdo",
        "xarid",
    }
    return {"pairs": pairs, "names": names}


async def check_answer(
    turn: Turn, answer: dict[str, Any], lines: list[str], guard_ctx: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    plan = [p for p in (answer.get("plan") or []) if isinstance(p, dict)]
    plan_texts = [" ".join(str(p.get(k, "")) for k in ("when", "action", "amount")) for p in plan]
    texts = [
        str(answer.get("headline", "")),
        str(answer.get("reason", "")),
        *[str(s) for s in answer.get("steps", [])],
        *plan_texts,
        *[str(r) for r in answer.get("risks", []) or []],
        str(answer.get("question", "") or ""),
        re.sub(r"(?m)^\s*(\d+[.)]|#+)\s", " ", str(answer.get("markdown", "") or "")),
    ]
    allowed = [turn.text, *lines]
    for r in turn.results.values():
        allowed += _texts_of(r)
    bad = violations(texts, allowed)
    if guard_ctx:
        bad += pairing_violations(texts, guard_ctx["pairs"])
        if turn.mode == "advisor":
            bad += [f"generic: {t}" for t in plan_texts if not concrete_step(t, guard_ctx["names"])]
    if bad:
        log.info("number guard rejected: %s", bad[:5])
        return None
    return answer


async def warm_brief(business: Business) -> dict[str, str]:
    """The proactive 'AI CFO · 08:00' message (same data as the dashboard banner)."""
    from apps.insights.forecasting import get_forecast

    def _b() -> dict[str, str]:
        base = get_forecast(business).result  # get_forecast sets its own tenant context
        bn = advice.banner(base)
        if base.verdict == "yes":
            pays = advice.payments_on(base, base.min_date)
            words = advice.join_uz([advice.payment_word(p) for p in pays])
            return {
                "lead": "Xayrli tong! Bugun hammasi joyida. Faqat bitta narsa:",
                "strong": f"{uz.format_date(base.min_date)} qiyin kun bo'ladi",
                "rest": f"— {words} bir kunga tushgan. Ungacha katta xarid qilmang."
                if len(pays) > 1
                else "— ungacha katta xarid qilmang.",
            }
        return {"lead": "Xayrli tong!", "strong": bn["headline"], "rest": bn["instruction"]}

    return await sync_to_async(_b)()


def now_hhmm(business: Business) -> str:
    from zoneinfo import ZoneInfo

    return timezone.localtime(timezone.now(), ZoneInfo(business.timezone)).strftime("%H:%M")


__all__ = ["CHIPS", "Turn", "asyncio", "stream_turn", "warm_brief"]


async def collect_answer(turn: Turn) -> dict[str, Any] | None:
    """Run the normal pipeline without streaming (Live demo: questions outside Q1–Q4)."""
    final: dict[str, Any] | None = None
    async for chunk in stream_turn(turn):
        for ev in chunk.decode().split("\n\n"):
            lines = ev.splitlines()
            data = next((ln[6:] for ln in lines if ln.startswith("data: ")), "{}")
            if any(ln == "event: answer" for ln in lines):
                final = json.loads(data)
            elif any(ln == "event: error" for ln in lines):
                log.warning("free answer error event: %s", data[:200])
    return final
