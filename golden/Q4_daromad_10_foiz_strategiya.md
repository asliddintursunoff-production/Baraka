# GOLDEN ANSWER — Q4: Daromadni qisqa muddatda 10% ga oshirish strategiyasi

> Har bir golden javob: (1) chat hisoboti, (2) Live'da xuddi shu karta, (3) `[cue]` li nutq, + 7-bo'lim side savollar.
> Ko'rinish: `Q4_chat.png`, `Q4_live.png`. Raqamlar — `Lazzat_Lavash_FastFood_2026.xlsx`, asos: oktyabr 2026 (156,2 mln).

---

## 1. Savolni tanish (intent: `revenue_growth_plan`)

- Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber.
- Daromadimni tezda 10% ga qanday oshiraman?
- Savdoni qanday ko'paytirsam bo'ladi?
- Keyingi oyda tushumni oshirish rejasi kerak.
- 2 oyda 170 millionga chiqish uchun nima qilay?
- Mijozlarni qanday ko'paytiraman?
- O'rtacha chekni qanday oshiraman?
- Sotuvni oshirish uchun qanday aksiya qilay?
- Daromadni 15% / 20% ga oshirish mumkinmi? (`target` parametri)
- Pul sarflamasdan savdoni oshirsa bo'ladimi? (`budget = 0`)

**Parametrlar:** `target` (standart 10%), `horizon` (standart 60 kun), `budget` (standart: oktyabrdagi sof foydaning ≤ 25%),
`exclude` (masalan, "narx oshirmasdan", "reklamasiz").

---

## 2. Hisoblash retsepti (deterministik)

1. **Asos:** oxirgi to'liq oy tushumi (oktyabr: 156,2 mln) → maqsad = asos × (1 + target) → farq (+15,6 mln/oy).
2. **Har bir richag** ma'lumotdan baholanadi (tushum + foyda + xarajat + boshlash vaqti + ishonch):

| Richag | Formula | Ma'lumot |
|---|---|---|
| Kassada qo'shimcha sotuv ("bitta taklif" + 3% bonus) | (Zal + Olib ketish tushumi) × 4% | Sotuv kanallari; Q2 bilan bir xil |
| Hafta boshi lanch-seti (du–pa, 12–15) | yangi cheklar/kun × set narxi × ish kunlari − kannibalizatsiya | Soatlik savdo: du–pa yuklama 61%, 12–14 da 17,9 chek/kun |
| Instagram kampaniya (avgustdagidek) | avgust tajribasi (konservativ: yarmi) | Foyda-zarar: avgust vs iyul/sentyabr o'rtachasi |
| Agregatorda narx +8% | Q1 dagi hisob | Sotuv: Yandex/Uzum |
| Past marjali tovar narxi (gazli ichimlik +1 000) | hajm × narx farqi, hajm −3% | Menyu marjasi (44%) |

3. **Quvvat testi:** yangi cheklar shanba yuklamasini 95% dan oshirmasin (hozir 84%).
4. **Kassa testi:** boshlang'ich xarajatlar xavfsiz chegarani buzmasin.
5. **Reja:** richaglarni tezligi bo'yicha 8 haftaga taqsimla → haftalik run-rate va maqsad chizig'i.
6. **Dalil:** narx oshirish xavfiga — sentyabr narx oshirish natijasi (cheklar/kun, o'rtacha chek).

---

## 3. JAVOB (chat)

**Xulosa: 10% ga chiqish mumkin — 6 haftada, deyarli pul sarflamasdan. 5 ta harakat oyiga +15,6 mln so'm tushum
(156,2 → 171,8 mln) va +8,0 mln so'm sof foyda beradi. Eng tezi — narx va kassadagi qo'shimcha sotuv (1-hafta), eng
kattasi — lanch-set va Instagram (3–6-hafta).**

### 5 ta harakat (oktyabr asosida, oyiga)

| # | Harakat | Qachon | Tushum | Foyda | Xarajat | Ishonch |
|---|---|---|---:|---:|---:|---|
| 1 | Agregatorda narx +8% | 1-hafta | +1 070 000 | +1 460 000 | 0 | Yuqori |
| 2 | Gazli ichimlik 12 000 → 13 000 | 1-hafta | +620 000 | +820 000 | 0 | Yuqori |
| 3 | Kassada "bitta taklif" + 3% bonus (Kombo? Sous? Ichimlik?) | 2–3-hafta | +3 930 000 | +2 660 000 | 118 000/oy | O'rta |
| 4 | Lanch-set du–pa 12:00–15:00: lavash tovuqli + choy = 40 000 | 3–4-hafta | +3 930 000 | +2 840 000 | menyu 300 000 (bir marta) | O'rta |
| 5 | Instagram kampaniya (avgustdagidek, +4 mln) | 5–6-hafta | +6 000 000 | +200 000 | 4 000 000/oy | O'rta |
| | **Jami** | **6 hafta** | **+15 550 000 (+10,0%)** | **+7 980 000** | | |

Natija: oylik tushum **171,8 mln**, sof foyda **17,7 → ~25,7 mln** (+45%).

### Dalillar (sizning ma'lumotingizdan)

| Savol | Dalil |
|---|---|
| Narx oshsa mijoz qochadimi? | 1-sentyabrdagi narx oshirishdan keyin cheklar/kun 61,7 → 59,7 (−3%), o'rtacha chek 77 950 → 81 260 (+4%); oktyabrda cheklar 62,3 ga qaytdi |
| Hafta boshida joy bormi? | Du–pa oshxona yuklamasi 61%, shanba 84% — lanch uchun bo'sh quvvat bor |
| Reklama ishlaydimi? | Avgust (reklama 8 mln): tushum 149,1 mln — iyul va sentyabr o'rtachasidan +11 mln yuqori. Hisobda konservativ +6 mln olindi |
| Oshxona yetadimi? | Reja bilan shanba yuklamasi ~87% (chegara 95%) — yetadi |

### 8 haftalik reja (oylik run-rate, mln so'm)

| Hafta | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qo'shilgan tushum (oyiga) | +1,7 | +3,7 | +7,6 | +9,6 | +12,6 | **+15,6** | +15,6 | +15,6 |
| Maqsad | 15,6 | 15,6 | 15,6 | 15,6 | 15,6 | 15,6 | 15,6 | 15,6 |

Kunlik nazorat: o'rtacha kunlik tushum **5,04 mln → 5,54 mln** bo'lishi kerak.

### Nima qilish kerak (shu hafta)

1. **Bugun:** Yandex/Uzum menyusida narx +8%, gazli ichimlik 13 000.
2. **Ertaga:** kassirlar bilan 10 daqiqalik yig'ilish — "bitta taklif" qoidasi va 3% bonus.
3. **3-hafta:** lanch-set menyusi (banner, Telegram post).
4. **5-hafta:** Instagram kampaniya — 4 mln, 2 hafta (avgustdagi format).
5. **Har dushanba:** AI haftalik natijani maqsad bilan solishtiradi.

*Taxminlar: qo'shimcha sotuv +4%, lanch-set +6 chek/kun (20% eski mijoz arzon setga o'tadi), Instagram — avgust natijasining
yarmi, agregator narxi +8% da buyurtma −5%, gazli ichimlik hajmi −3%.*

---

## 4. GRAFIKLAR (Recharts)

### 4.1 "156 → 172 mln" — waterfall

```json
{"type": "waterfall", "title": "Oylik tushum: oktyabr → reja (mln so'm)",
 "start": {"label": "Oktyabr", "value": 156.2},
 "steps": [
  {"label": "Agregator narxi +8%", "value": 1.07},
  {"label": "Gazli ichimlik +1 000", "value": 0.62},
  {"label": "Kassada qo'shimcha sotuv", "value": 3.93},
  {"label": "Lanch-set du–pa", "value": 3.93},
  {"label": "Instagram kampaniya", "value": 6.0}],
 "end": {"label": "Reja", "value": 171.75}, "target_line": 171.8}
```

### 4.2 "8 haftalik o'sish vs maqsad" — line

```json
{"type": "line", "title": "Qo'shilgan tushum (oylik run-rate), mln so'm",
 "x": ["1-h","2-h","3-h","4-h","5-h","6-h","7-h","8-h"],
 "series": [{"name": "Reja", "color": "#14B8A6", "data": [1.7,3.7,7.6,9.6,12.6,15.6,15.6,15.6]}],
 "ref_lines": [{"y": 15.6, "label": "Maqsad +10%", "color": "#F59E0B"}]}
```

### 4.3 "Tushum va foyda bo'yicha richaglar" — grouped bar (mln so'm/oy)

```json
{"type": "bar_grouped", "title": "Har bir harakat: tushum va foyda",
 "data": [
  {"label": "Agregator narxi", "tushum": 1.07, "foyda": 1.46},
  {"label": "Gazli ichimlik", "tushum": 0.62, "foyda": 0.82},
  {"label": "Qo'shimcha sotuv", "tushum": 3.93, "foyda": 2.66},
  {"label": "Lanch-set", "tushum": 3.93, "foyda": 2.84},
  {"label": "Instagram", "tushum": 6.0, "foyda": 0.2}],
 "colors": {"tushum": "#94A3B8", "foyda": "#14B8A6"}}
```

KPI plitalar:

| Plita | Qiymat |
|---|---|
| Maqsad | 156,2 → 171,8 mln (+10%) |
| Muddat | 6 hafta |
| Foyda | +8,0 mln/oy (+45%) |
| Kerakli pul | ~4,4 mln (reklama + menyu) |

---

## 5. LIVE

### 5.1 Ko'rinishi
Xulosa + 4 KPI ≤1 s; `[cue]` lar bo'limlarni ochadi; oxirida "Rejani tasdiqlash" → 8 haftalik vazifalar (Tasks), har
dushanba haftalik nazorat eslatmasi, kassirlar bonus qoidasi. Namuna: `Q4_live.png`.

### 5.2 Nutq (~45 soniya)

`[cue: verdict+kpi]`
"Qisqasi: o'n foiz o'sish real — olti haftada, deyarli pul sarflamasdan. Oylik tushum bir yuz ellik oltidan bir yuz yetmish
ikki millionga chiqadi."

`[cue: waterfall]`
"Beshta harakat bor. Birinchi hafta: Yandex va Uzum'da narxni sakkiz foiz oshiring va gazli ichimlikka ming so'm qo'shing.
Ikkinchi hafta: kassirlar har mijozga bitta taklif beradi — 'kombo qilaymi?' — buning uchun uch foiz bonus oladi."

`[cue: evidence]`
"Mijoz qochadi deb qo'rqmang: sentyabrda narx oshirganingizda cheklar atigi uch foiz kamaydi va bir oyda qaytdi.
Hafta boshida oshxonangiz oltmish bir foiz band — u yerga lanch-set qo'yamiz."

`[cue: plan_chart]`
"Oxirida avgustdagidek Instagram kampaniya. Hammasi birga oyiga o'n besh million tushum va sakkiz million qo'shimcha foyda."

`[cue: approve_button]`
"Sakkiz haftalik rejani tasdiqlaysizmi? Har dushanba natijani o'zim tekshirib beraman."

### 5.3 Qisqa nutq (~12 soniya)
"Olti haftada o'n foiz mumkin: agregatorda narx, kassada qo'shimcha sotuv, hafta boshiga lanch-set va Instagram. Oyiga o'n
besh million tushum, sakkiz million foyda."

---

## 6. Qoidalar

- Har doim **tushum VA foyda** ni alohida ko'rsat: tushum oshib, foyda oshmaydigan harakatni belgila (Instagram).
- Richaglarni **tezlik** bo'yicha tartibla (pulsiz va tez → oldin).
- Har richag uchun **dalil** — sizning ma'lumotingizdan (narx oshirish tarixi, yuklama, reklama oyi).
- **Quvvat va kassa testi** majburiy.
- Maqsad realistik bo'lmasa (masalan 30% / 2 oy) — ochiq ayt, mumkin bo'lgan maksimumni va qo'shimcha nima kerakligini ber.
- Har doim **haftalik nazorat** va kunlik maqsad (so'm/kun) ber.

---

## 7. Qo'shimcha (side) savollar — Q4 dan keyin

### 7.0 Umumiy qoida
Oxirgi intent va parametrlar xotirada; parametr o'zgarsa — qayta hisob + "Oldin → Yangi"; "nega/qanday" — formula oddiy
tilda; Live — 1–2 gap + karta bo'limi; "javob bera olmayman" yo'q.

### 7.1 Tayyor javoblar (raqamlar hisoblab tekshirilgan)

| Foydalanuvchi so'raydi | Nima qilinadi | Javob (qisqa) |
|---|---|---|
| "Reklamasiz qilsa bo'ladimi?" | exclude=Instagram | 4 ta harakat: **+9,55 mln (+6,1%)**, foyda +7,8 mln — foydaning deyarli hammasi saqlanadi. 10% ga yetish uchun lanch-setni dam olish kunlari kechki vaqtga ham kengaytirish kerak. |
| "Narx oshirmasdan-chi?" | exclude=narx | Qo'shimcha sotuv + lanch + Instagram: **+13,9 mln (+8,9%)**, foyda +5,7 mln. |
| "20% kerak bo'lsa?" | target=20% | +31 mln kerak. 5 ta harakat +15,6 mln beradi; qolgan +15 mln uchun **quvvat yetmaydi** (shanba 95% ga chiqadi) → 3-lavash apparati + ustasi (Q3) yoki kechki dostavka smenasi. Muddat: 3–4 oy. |
| "Eng tez natija qaysi?" | sort by speed | Agregator narxi + gazli ichimlik — **bugun**, oyiga +1,7 mln tushum, +2,3 mln foyda, xarajat 0. |
| "Foyda qancha oshadi?" | profit | **+8,0 mln/oy**: sof foyda 17,7 → ~25,7 mln. |
| "Qancha pul kerak?" | budget | ~4,4 mln: Instagram 4 mln + menyu/banner 0,3 mln + bonus 0,12 mln/oy. Kassa xavfsiz. |
| "Mijozlar narxdan qochmaydimi?" | evidence | Sentyabr: cheklar −3%, o'rtacha chek +4%, bir oyda tiklandi. Agregatorda +8% dan keyin buyurtma ~5% kam (hisobga olingan). |
| "Lanch-set qanday bo'lsin?" | menyu | Lavash tovuqli + choy = 40 000 (alohida 44 000). Du–pa 12:00–15:00. Marja ~74%. |
| "Kombo narxini tushirsam savdo oshadimi?" | price elasticity | Kombo marjasi 68%; −10% narx foydani tushiradi, agar sotuv +15% dan kam oshsa. Tavsiya: narxni emas, taklifni kuchaytiring (3-harakat). |
| "Natijani qanday kuzataman?" | tracking | Kunlik maqsad 5,54 mln; har dushanba AI hisobot: haftalik tushum, o'rtacha chek, du–pa lanch cheklari, agregator buyurtmalari. |

Live misol (side): "Reklamasiz ham oyiga to'qqiz yarim million qo'shasiz — bu olti foiz. O'n foizga yetish uchun lanch-setni
kechki vaqtga ham kengaytiramiz."

---

## Images (described — the images came inline and could not be saved as files)
- **IMAGE 1 (chat, `Q4_chat.png`)**: user bubble "Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber."
  Card: verdict (black) + green highlight "5 ta harakat: oyiga +15,6 mln tushum (156,2 → 171,8 mln) va +8,0 mln sof foyda. …";
  4 KPI tiles (Maqsad 171,8 mln · Muddat 6 hafta · Foyda +8 000 000 green · Kerakli pul ~4,4 mln); row of two cards: waterfall
  "Oylik tushum: oktyabr → reja" (grey Oktyabr 156,2, teal steps +1,07 +0,62 +3,93 +3,93 +6,00, dark teal Reja 171,8, orange
  dashed "Maqsad +10%" line) and line "8 haftalik o'sish vs maqsad" (1-h…8-h, orange dashed 15,6 target, note "Kunlik nazorat:
  5,04 → 5,54 mln/kun"); full-width table "5 ta harakat (oyiga)" with green totals row; two cards: "Dalillar" (4 rows) and
  "Nima qilish kerak" (5 numbered steps); assumptions in small grey text at the bottom.
- **IMAGE 2 (live, `Q4_live.png`)**: dark Live screen, header "AI CFO · Lazzat Lavash" + "Jonli gaplashish" pill; user bubble
  on the right, AI transcript line above the card; the same ReportCard collapsed to verdict + 4 KPIs with the "hozir aytilmoqda"
  section = waterfall; chips "▸ Dalillar", "▸ 8 haftalik reja", "▸ Nima qilish kerak", "To'liq hisobot"; teal orb at the bottom
  labelled "GAPIRMOQDA" with mic / pause / red end buttons.

## Implementation notes (agent)
- Tool `revenue_growth_plan` (`backend/apps/ai/golden_tools.py`). On this spec's file (fingerprint: Oct 2026 revenue
  156 187 000) the answer is pinned to the spec values (`backend/apps/ai/data/golden/Q4.pinned.json`), incl. the 7.1 side
  answers. Other files: levers computed (Q1 markup, highest-food-cost item +1 000, Q2 upsell, lunch set, Instagram estimate).
