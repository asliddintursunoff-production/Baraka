# GOLDEN ANSWER — Q1: Yandex/Uzum yoki o'z dostavkam?

> Har bir golden javob 3 qismdan iborat va agent ULARNING HAMMASINI bajaradi:
> (1) chatdagi hisobot (matn + jadval + grafik), (2) Live'da xuddi shu hisobot kartasi ochiladi,
> (3) Live uchun nutq — `[cue]` lar bilan hisobot bo'limlariga bog'langan.
> Ko'rinish namunalari: `Q1_report_preview.png` (chat), `Q1_live_preview.png` (live).

> Agent uchun: bu savol (va ma'nosi bir xil savollar) kelganda AYNAN shu tuzilmada javob ber.
> Raqamlarni har doim fayldan qayta hisobla (quyidagi "Hisoblash retsepti"). Bu yerdagi raqamlar —
> `Lazzat_Lavash_FastFood_2026.xlsx` uchun to'g'ri javob (oktyabr 2026 — oxirgi to'liq oy).

---

## 1. Savolni tanish (intent: `channel_economics`)

Shu va shunga o'xshash savollar bitta shablonga tushadi:

- Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi? Qaysi biri ko'proq foyda olib keladi?
- Agregatorlar foydalimi?
- Yandex Eats'dan chiqib ketsam nima bo'ladi?
- O'z dostavkam foydaliroqmi yoki Uzum Tezkor?
- Qaysi savdo kanali eng foydali?
- Kuryer olsam arziydimi yoki Yandex'da qolaymi?
- Dostavkadan qancha foyda qolyapti?
- Uzum komissiyasi meni yeb qo'yyaptimi?

Parametr chiqsa (masalan "50% ini o'tkazsam", "Uzum'dan chiqsam", "2-kuryer olsam") — o'sha parametr bilan
xuddi shu hisobni qayta bajar.

---

## 2. Hisoblash retsepti (deterministik — LLM hisoblamaydi)

Davr: oxirgi to'liq oy (`last_full_month`), qo'shimcha tekshiruv — oxirgi 3 oy o'rtachasi.

Har bir kanal uchun (Sotuv varag'i, ustun G = Kanal):

| Ko'rsatkich | Manba |
|---|---|
| Tushum | Σ Sotuv.M (Summa) |
| Tannarx | Σ Sotuv.U (Tannarx jami) |
| Komissiya | Σ Sotuv.Q (Yandex 20%, Uzum 18% — Spravochnik) |
| Qadoq | tushum × 2,2% (Kassa "Qadoqlash materiallari" / Zal'dan tashqari tushum) |
| O'z dostavka xarajati | Kuryer oyligi (Ish haqi, "Kuryer") + yoqilg'i (Kassa "Taksi va yetkazish") |
| Buyurtmalar soni | Smena/kanal bo'yicha (yo'q bo'lsa: tushum ÷ o'rtacha chek) |
| Kanaldan keyingi foyda | Tushum − Tannarx − Komissiya − Qadoq − (o'z dostavka uchun: kuryer + yoqilg'i) |
| 100 000 so'mdan qoladi | Foyda ÷ Tushum × 100 000 |
| Kuryer yuklamasi | O'z dostavka buyurtmalari ÷ kuryer quvvati (standart 15 buyurtma/kun = 450/oy) |
| Agregatorda turgan pul | Kontragentlar: Yandex + Uzum saldosi (oy oxiri) |

Ssenariylar (parametrlar foydalanuvchi o'zgartira oladi):

| Parametr | Standart |
|---|---|
| O'z dostavkaga o'tkaziladigan agregator buyurtmalari | 30% |
| O'tishga rag'bat (chegirma) | 5% |
| Har qo'shimcha buyurtmaga yoqilg'i | 6 000 so'm |
| Agregatordagi narx ustamasi | +8% |
| Ustama tufayli agregator buyurtmalari kamayishi | −5% |
| Kuryer quvvati | 450 buyurtma/oy |

---

## 3. JAVOB (aynan shunday ko'rsatiladi — chat)

**Xulosa: Yandex va Uzum'dan chiqmang — ular foydali. Lekin o'z dostavkangiz hozir eng kam foyda qoldiryapti, chunki kuryeringiz kuniga atigi ~6 ta buyurtma tashiyapti. Uni to'ldirsangiz, o'z dostavka eng foydali kanalga aylanadi. To'g'ri yo'l — ikkalasini birga ishlatish: oyiga +2,0 mln so'm foyda va ~10 mln so'm pul tezroq qo'lingizga keladi.**

### Har 100 000 so'mlik buyurtmadan sizga qancha qoladi (oktyabr 2026)

| Kanal | Tushum (oy) | Buyurtma | O'rtacha chek | Masalliq | Komissiya / dostavka | Qadoq | **Sizga qoladi** |
|---|---:|---:|---:|---:|---:|---:|---:|
| Uzum Tezkor | 17 320 000 | 174 | 99 500 | 30 370 | 18 010 (komissiya 18%) | 2 200 | **49 400** |
| Yandex Eats | 23 840 000 | 257 | 92 800 | 29 490 | 20 010 (komissiya 20%) | 2 200 | **48 300** |
| O'z dostavka | 16 790 000 | 189 | 88 800 | 29 720 | 25 020 (kuryer + yoqilg'i) | 2 200 | **43 100** |

**Nega o'z dostavka kam qoldiryapti?** Kuryer oyligi (2,5 mln) va yoqilg'i (1,7 mln) — qat'iy xarajat. Hozir kuryer oyiga
189 ta buyurtma tashiydi, quvvati ~450 ta. Ya'ni **42% yuklangan**. Har bir qo'shimcha buyurtma unga atigi
~6 000 so'mlik yoqilg'i qo'shadi, agregator esa har buyurtmadan ~19 000 so'm komissiya oladi.

### Kanal bo'yicha oylik foyda (komissiya va dostavkadan keyin)

| Kanal | Foyda (oktyabr) |
|---|---:|
| Yandex Eats | 11 520 000 |
| Uzum Tezkor | 8 560 000 |
| O'z dostavka | 7 230 000 |
| **Jami dostavka kanallari** | **27 310 000** |

### Variantlarni solishtirish (oyiga, oktyabr asosida)

| Variant | Nima qilasiz | Oylik foyda o'zgarishi | Yillik | Xavf |
|---|---|---:|---:|---|
| ❌ Agregatorlardan chiqish | Yandex + Uzum'ni o'chirish | **−20 070 000** | −240 mln | Mijozlarning ko'pi qaytmaydi |
| 1. Mijozni o'z dostavkaga o'tkazish | Agregator buyurtmalarining 30% (~129 ta) ni 5% chegirma bilan Telegram/sayt orqali olish | **+990 000** | +11,9 mln | Kam; kuryer yuklamasi 42% → 71% |
| 2. Agregatorda narxni +8% qo'yish | Yandex/Uzum menyusida narx 8% yuqori (komissiyani qoplaydi) | **+1 460 000** | +17,5 mln | Buyurtmalar ~5% kamayishi mumkin |
| ✅ **1 + 2 birga (tavsiya)** | Ikkalasi | **+2 010 000** | **+24,1 mln** | Kam |

Natija: dostavka kanallaridan oylik foyda **27,3 mln → 29,3 mln**. Bu oktyabrdagi sof foydangizga (17,7 mln) nisbatan **+11%**.
O'z dostavkangiz har 100 000 so'mdan **49 900** qoldiradigan bo'ladi — eng foydali kanal.

### Pul qachon keladi (yashirin foyda)

| | Agregatorlar | O'z dostavka |
|---|---|---|
| Pul qachon tushadi | Keyingi oyning 8–10-sanasida | Shu kuni (naqd / Click / Payme) |
| 31-oktyabrda agregatorlarda turgan pulingiz | **33 300 000** (Yandex 19,1 mln + Uzum 14,2 mln) | 0 |
| Reja bajarilsa | ~10 000 000 so'm har oy **3–5 hafta oldin** qo'lingizga keladi | |

Bu sizning asosiy muammongizga bevosita yordam beradi: oylik to'lanadigan **5-dekabrda** kassada ko'proq pul bo'ladi.

### Nima qilish kerak (shu hafta)

1. **Agregatorlarni o'chirmang.** Ular oyiga 20 mln foyda va yangi mijoz olib keladi.
2. **Telegram-bot yoki sayt orqali buyurtma** oching: "o'zimizdan buyurtma bersangiz −5%". Har agregator paketiga varaqcha (QR-kod) soling.
3. **Yandex va Uzum menyusida narxni 8% yuqori qo'ying** (masalan, lavash mol go'shtli 45 000 → 48 600). Zal va olib ketish narxi o'zgarmaydi.
4. **Hozircha 2-kuryer olmang.** Birinchi kuryer ~70% yuklanguncha (oyiga ~320 buyurtma) kuting. Undan keyin 2-kuryer (2,5 mln) arziydi.
5. 30 kundan keyin natijani tekshiring: o'z dostavka buyurtmalari 189 → ~318 bo'lishi kerak.

*Taxminlar: kuryer quvvati 450 buyurtma/oy, qo'shimcha buyurtmaga yoqilg'i 6 000 so'm, mijozlarning 30% i o'tadi,
narx +8% bo'lsa agregator buyurtmalari 5% kamayadi. Bularni o'zgartirsangiz, qayta hisoblayman.*

---

## 4. GRAFIKLAR (Recharts uchun ma'lumot)

### 4.1 "100 000 so'mdan qayerga ketadi" — stacked bar (horizontal)

```json
{
  "type": "stacked_bar_horizontal",
  "title": "Har 100 000 so'mlik buyurtmadan qayerga ketadi",
  "unit": "so'm",
  "series": ["Masalliq", "Komissiya / dostavka", "Qadoq", "Sizga qoladi"],
  "colors": ["#94A3B8", "#F87171", "#CBD5E1", "#2DD4BF"],
  "data": [
    {"kanal": "Uzum Tezkor", "Masalliq": 30370, "Komissiya / dostavka": 18010, "Qadoq": 2200, "Sizga qoladi": 49420},
    {"kanal": "Yandex Eats", "Masalliq": 29490, "Komissiya / dostavka": 20010, "Qadoq": 2200, "Sizga qoladi": 48300},
    {"kanal": "O'z dostavka (hozir)", "Masalliq": 29720, "Komissiya / dostavka": 25020, "Qadoq": 2200, "Sizga qoladi": 43060},
    {"kanal": "O'z dostavka (reja)", "Masalliq": 30440, "Komissiya / dostavka": 17420, "Qadoq": 2200, "Sizga qoladi": 49940}
  ],
  "highlight": "Sizga qoladi"
}
```

### 4.2 "Variantlar: oylik foyda o'zgarishi" — bar

```json
{
  "type": "bar",
  "title": "Oylik foyda o'zgarishi, so'm",
  "data": [
    {"variant": "Agregatordan chiqish", "qiymat": -20070000, "color": "#F87171"},
    {"variant": "30% ni o'zimizga o'tkazish", "qiymat": 990000, "color": "#5EEAD4"},
    {"variant": "Agregatorda narx +8%", "qiymat": 1460000, "color": "#5EEAD4"},
    {"variant": "Ikkalasi birga (tavsiya)", "qiymat": 2010000, "color": "#2DD4BF"}
  ]
}
```

### 4.3 "Kuryer yuklamasi" — gauge / progress

```json
{"type": "progress", "title": "Kuryer yuklamasi", "now": 0.42, "plan": 0.71, "hire_second_at": 0.70,
 "label_now": "189 / 450 buyurtma", "label_plan": "318 / 450 buyurtma"}
```

### 4.4 "Agregatorlarda turgan pul" — line (oy oxiri, mln so'm)

```json
{
  "type": "line",
  "title": "Oy oxirida agregatorlarda turgan pulingiz",
  "unit": "mln so'm",
  "data": [
    {"oy": "Yan 2026", "qiymat": 17.1}, {"oy": "Fev 2026", "qiymat": 20.0}, {"oy": "Mar 2026", "qiymat": 18.3},
    {"oy": "Apr 2026", "qiymat": 19.7}, {"oy": "May 2026", "qiymat": 23.6}, {"oy": "Iyun 2026", "qiymat": 23.4},
    {"oy": "Iyul 2026", "qiymat": 27.3}, {"oy": "Avg 2026", "qiymat": 29.5}, {"oy": "Sen 2026", "qiymat": 30.7},
    {"oy": "Okt 2026", "qiymat": 33.3}
  ]
}
```

Karta tartibi: Xulosa → KPI plitalar (4 ta) → 4.1 → jadval "100 000 so'mdan" → 4.2 + variantlar jadvali →
4.3 + 4.4 yonma-yon → "Nima qilish kerak" → taxminlar (kichik shrift).

KPI plitalar:

| Plita | Qiymat |
|---|---|
| Eng foydali kanal hozir | Uzum — 49 400 / 100 000 |
| O'z dostavka hozir | 43 100 / 100 000 (kuryer 42% yuklangan) |
| Tavsiya natijasi | +2 010 000 so'm/oy |
| Agregatorda turgan pul | 33 300 000 so'm |

---

## 5. LIVE (ovozli rejim) — xuddi shu hisobot ochiladi + nutq

### 5.1 Live'da qanday ko'rinadi
- Savol tanilgan zahoti (≤1 s) orb ustida **xuddi chatdagi hisobot kartasi** paydo bo'ladi (bir xil komponent, bir xil ma'lumot).
- Karta avval yig'ilgan holda: Xulosa + 4 ta KPI. AI gapira boshlaganda har bir nutq bo'lagi o'z bo'limini **ochadi va
  belgilaydi** (pastdagi `[cue]` lar bo'yicha) — foydalanuvchi aynan gapirilayotgan raqamni ekranda ko'radi.
- Oxirida "Rejani tasdiqlash" tugmasi chiqadi (eslatma + reja yaratiladi — pul harakati yo'q).
- "To'liq hisobot" tugmasi — chatdagi bilan bir xil hisobotni to'liq ekranda ochadi (PDF eksport bilan).
- Foydalanuvchi gapni bo'lsa: nutq to'xtaydi, karta qoladi.
- Ko'rinish namunasi: `Q1_live_preview.png`.

### 5.2 Nutq (to'liq, ~45 soniya) — `[cue]` = ekranda ochiladigan bo'lim

> Raqamlar og'zaki, yaxlitlangan holda aytiladi. Ekranda aniq raqamlar turadi.

`[cue: verdict+kpi]`
"Qisqasi: Yandex va Uzum'dan chiqmang — ular sizga foydali. Lekin o'z dostavkangizdan to'liq foydalanmayapsiz."

`[cue: chart_100k]`
"Qarang: har yuz ming so'mlik buyurtmadan Uzum sizga qirq to'qqiz ming, Yandex qirq sakkiz ming so'm qoldiradi.
O'z dostavkangiz esa qirq uch ming — chunki kuryeringiz kuniga atigi oltita buyurtma tashiydi, vaqtining yarmidan ko'pi bo'sh."

`[cue: variants]`
"Agregatorlardan butunlay chiqsangiz, oyiga yigirma million foyda yo'qotasiz — buni qilmang.
Buning o'rniga ikki ish qiling: doimiy mijozlarni besh foiz chegirma bilan o'z Telegram-botingizga o'tkazing,
va Yandex bilan Uzum'da narxni sakkiz foiz yuqori qo'ying."

`[cue: kpi_result + receivables]`
"Shunda oyiga yana ikki million so'm foyda olasiz — yiliga yigirma to'rt million.
Yana bir bonus: hozir agregatorlarda o'ttiz uch million pulingiz turibdi. Reja bilan har oy o'n millioni ancha oldin
qo'lingizga keladi — beshinchi dekabrdagi oylikda juda asqotadi."

`[cue: courier + actions]`
"Ikkinchi kuryerni hozircha olmang — avval birinchisini to'ldiring.
Shu rejani tasdiqlaysizmi? Tasdiqlasangiz, eslatmalarni qo'yib, o'ttiz kundan keyin natijani tekshiraman."

`[cue: approve_button]` — "Rejani tasdiqlash" tugmasi ko'rinadi.

### 5.3 Qisqa nutq (agar foydalanuvchi "qisqaroq" desa yoki vaqt kam bo'lsa, ~12 soniya)
"Yandex va Uzum'dan chiqmang — ular oyiga yigirma million foyda beradi. Lekin mijozlarni o'z Telegram-botingizga
o'tkazib, agregatorda narxni sakkiz foiz oshirsangiz, oyiga yana ikki million foyda qo'shiladi."

### 5.4 Nutq qoidalari (barcha javoblar uchun)
- Birinchi gap = xulosa (ha/yo'q/qilish kerak).
- Raqamlar: og'zaki, yaxlit ("ikki million", "qirq to'qqiz ming"), 1 gapda ≤ 2 ta raqam.
- Har bo'lak ≤ 2 gap va bitta `[cue]` ga bog'langan.
- Oxirgi gap = harakat taklifi + tasdiqlash so'rovi.
- Ekranda aytilmagan raqam bo'lishi mumkin, lekin aytilgan raqam ekranda bo'lishi SHART.

## 6. Qoidalar (shu shablon uchun)

- Har doim "100 000 so'mdan qoladi" jadvalini ko'rsat — bu eng tushunarli o'lchov.
- "Agregatordan chiqish" variantini har doim jadvalda ko'rsat (salbiy raqam bilan), lekin tavsiya qilma.
- Kuryer yuklamasi 70% dan oshsa — 2-kuryerni tavsiya qil, oyligini xarajatga qo'sh.
- Raqamlar faqat fayldan; taxminlar alohida "Taxminlar" qatorida, foydalanuvchi o'zgartira oladi.
- Davrni aniq yoz: "oktyabr 2026 (oxirgi to'liq oy)". Noyabr qisman — ishlatma.

## 7. Qo'shimcha (side) savollar — Q1 dan keyin


### 7.0 Umumiy qoida (barcha golden javoblar uchun)
- Hisobotdan keyingi savollar **shu hisobot kontekstida** qabul qilinadi: oxirgi intent va parametrlar xotirada turadi
  (masalan, "50% qilsam-chi?" → Q1 ni s=50% bilan qayta hisobla).
- Parametr o'zgarsa: **qayta hisobla** va kichik "Oldin → Yangi" jadvalini ko'rsat (asosiy KPI'lar), karta yangilanadi.
- Tushuntirish so'ralsa ("nega?", "qanday hisobladi?"): retseptdagi formulani oddiy tilda, aniq raqamlar bilan ko'rsat.
- Yaqin, lekin boshqa savol bo'lsa: to'liq-kontekst chat javob beradi, hisobot raqamlariga tayanib; kerak bo'lsa boshqa golden intentga o'tadi.
- Live'da: 1–2 gaplik og'zaki javob + kartaning tegishli bo'limi yangilanadi/belgilanadi.
- Hech qachon "bu savolga javob bera olmayman" dema — kamida taxmin (belgilangan) va keyingi qadamni ber.

### 7.1 Tayyor javoblar (Lazzat, oktyabr 2026 — raqamlar hisoblab tekshirilgan)

| Foydalanuvchi so'raydi | Nima qilinadi | Javob (qisqa) |
|---|---|---|
| "30% emas, 50% ini o'tkazsam-chi?" | s=0.5 qayta hisob | Oyiga **+2,37 mln** (30% da +2,01). Kuryer 404/450 = **90%** — chegarada, sifat tushishi mumkin. 2-kuryer olsangiz natija **−0,13 mln** — hali erta. |
| "2-kuryer olsam-chi?" | kur=2 | 30% rejada 2-kuryer bilan **−0,49 mln/oy** — olmang. Yuklama 70% dan oshib, o'z dostavka buyurtmalari ~450 ga yetganda oling. |
| "Narxni oshirmasam, faqat mijozni o'tkazsam?" | up=0 | **+0,99 mln/oy** (narx bilan +2,01). |
| "Narxni 8% emas, 5% qilsam?" | up=0.05, vol=0.97 | **+1,67 mln/oy**. Xavf kamroq, foyda biroz kam. |
| "Uzum'dan butunlay chiqsam-chi?" | Uzum=0, 40% mijoz o'zimizga o'tadi | **−4,65 mln/oy**. Uzum oyiga 8,56 mln foyda beradi — chiqmang. |
| "Nega Uzum Yandex'dan foydaliroq?" | tushuntirish | Komissiya 18% vs 20% va o'rtacha chek 99 500 vs 92 800. |
| "Bu raqamlar qanday chiqdi?" | formula | Tushum − masalliq − komissiya − qadoq (2,2%) − (o'z dostavka uchun: kuryer 2,5 mln + yoqilg'i 1,7 mln). Manba: Sotuv, Ish haqi, Kassa (oktyabr). |
| "Agregatordagi pulni qachon olaman?" | Kontragentlar | Yandex — har oyning ~8-sanasi, Uzum — ~10-sanasi; 31-oktyabrda jami 33,3 mln turgan edi. |
| "Telegram-bot qilish qancha turadi, arziydimi?" | taxmin + qoplash | Oddiy bot/sayt ~3–5 mln (taxmin). Oyiga +0,99 mln foyda bilan **3–5 oyda** qoplaydi. |
| "Yandex komissiyasini kamaytirsa bo'ladimi?" | maslahat | Muzokara: hajm 24 mln/oy; 2 punkt chegirma = oyiga ~0,48 mln. Alternativa — narx ustamasi (variant 2). |

Live misol (side): "Ellik foiz o'tkazsangiz, oyiga ikki million uch yuz ming bo'ladi, lekin kuryer to'qson foiz band bo'lib
qoladi — hozircha o'ttiz foizdan boshlang."

## Implementation notes (agent)
- Tool: `channel_economics` (`backend/apps/ai/golden_tools.py`, engine `backend/apps/engine/channels.py`).
- Ambiguity 1: orders per channel are not in the file (no order ids in Sotuv, no channel counts in Smena). Default:
  revenue ÷ the month's average check (flagged "taxmin" with *); exact counts can be passed as the `orders` param.
  The golden test passes the spec's counts (174 / 257 / 189).
- Ambiguity 2: the file's Kassa packaging ratio is 1,95% (2,78% incl. Kirim packaging); the recipe says 2,2% — used as the
  default parameter, the file ratio is shown in the assumptions as a check.
- Images: `Q1_chat.png` (chat), `Q1_live.png` (live).
