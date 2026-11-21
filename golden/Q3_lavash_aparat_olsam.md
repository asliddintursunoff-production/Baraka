# GOLDEN ANSWER — Q3: X so'mga lavash apparati olsam — investitsiyami yoki zarariga ishlaydimi?

> Har bir golden javob 3 qismdan iborat va agent ULARNING HAMMASINI bajaradi:
> (1) chatdagi hisobot, (2) Live'da xuddi shu hisobot kartasi, (3) `[cue]` li nutq. + 7-bo'lim: side savollar.
> Ko'rinish: `Q3_chat.png`, `Q3_live.png`. Raqamlar — `Lazzat_Lavash_FastFood_2026.xlsx`, 22.11.2026 holati, X = 25 000 000 so'm.

---

## 1. Savolni tanish (intent: `equipment_investment`)

- X so'mga lavash apparat olmoqchiman, bu investitsiya bo'ladimi yoki zarariga ishlaydimi?
- Yangi lavash apparati olsam arziydimi?
- 25 millionga yana bitta stansiya olsam foyda bo'ladimi?
- Apparat olsam necha oyda o'zini qoplaydi?
- Qachon apparat olganim to'g'ri?
- Pulim yetmasa apparatni qanday olaman?
- Apparatni kreditga / bo'lib to'lashga olsam-chi?
- Shaurma apparati / gril / fritur / pech olsam? (xuddi shu shablon, `equipment` parametri bilan)
- Yangi jihozga X so'm sarflasam, nima muammolar keladi?
- Oyiga foyda qancha oshadi apparat olsam?

**Parametrlar:** `equipment` (lavash apparati | fritur | gril | pech | muzlatgich | …), `price` (X; aytilmasa — so'ra yoki
shu turdagi oxirgi xarid narxi), `reason` (qo'shimcha quvvat | eskisi buzildi/almashtirish | yangi mahsulot | ish haqini
tejash), `financing` (o'z puli | bo'lib to'lash | kredit), `date` (hozir | ma'lum sana).

---

## 2. Hisoblash retsepti (deterministik)

**A. Uskuna nimani o'zgartiradi (`reason` bo'yicha):**

| Sabab | Foyda manbai | Ma'lumot |
|---|---|---|
| Qo'shimcha quvvat (standart) | Yo'qotilgan buyurtmalarni qaytarish | Smena "ulgurmadi" kunlari, shanba cheklari ÷ oshxona quvvati (90), soatlik pik |
| Almashtirish (buzildi) | Uskunasiz kunlarda yo'qotiladigan savdo | Quvvat 1 stansiyaga tushganda (60/kun) savdo farqi |
| Yangi mahsulot | Yangi taom × marja | Menyu marjasi, o'xshash taom savdosi |
| Ish haqini tejash | Kamaygan ish soatlari | Ish haqi |

**B. Hozirgi bo'sh quvvat:** shanba yuklamasi = shanba o'rtacha cheklari (oxirgi 3 oy) ÷ 90; "ulgurmadi" kunlari (oxirgi 3 oy).
Agar yuklama < 95% va "ulgurmadi" = 0 → qo'shimcha foyda hozir ≈ 0 ("zarariga ishlaydi").

**C. Quvvat qachon tugaydi:** shanba cheklari × (1 + o'rtacha oylik o'sish)ⁿ ≥ 85 (95%) → **sotib olish oyi** (1 oy oldin
o'rnatish/o'qitish uchun).

**D. Quvvat to'lganda foyda (asos — o'z tajribasi):** Investitsiyalar varag'idagi 2-lavash stansiyasi natijasi:
umumiy o'sishdan tashqari **+8,16 mln yalpi foyda/oy**. Xarajatlar: elektr 10 kVt·soat/kun × tarif, servis 100 000/oy,
yangi lavash ustasi (3,3 mln + ovqat). Amortizatsiya — foyda hisobida (naqd emas).

**E. Kassa testi:** xarid sanasida kassa prognozi − X ≥ xavfsiz chegara (7 kunlik qat'iy chiqimlar ≈ 17 mln) — eng qiyin
kun (oylik kuni) bo'yicha.

**F. Moliyalashtirish variantlari:** o'z puli (jamg'arma rejasi), bo'lib to'lash (20% boshlang'ich, 6 oy, ~20%/yil ustama),
bank krediti (24%/yil, 12 oy annuitet). Har biri: oylik to'lov, jami ortiqcha xarajat, qarz yopilish muddati, kassaga ta'sir.

**G. J-egri chiziq:** "hozir olish" va "eng yaxshi oyda olish" — 13 oylik yig'ma naqd natija.

---

## 3. JAVOB (chat)

**Xulosa: Hozir olsangiz — zarariga ishlaydi: ikkala lavash stansiyangiz hali to'lmagan, iyundan beri birorta buyurtma
navbat sababli yo'qolmagan. Apparat 2027-yil may oyida investitsiyaga aylanadi: shunda oyiga +4,3 mln so'm foyda beradi va
25 mln ni ~6 oyda qoplaydi. Hozirdan oyiga 5 mln dan jamg'arib boring — mayda qarzsiz olasiz.**

### Hozir olsangiz nima bo'ladi

| | Oyiga |
|---|---:|
| Qo'shimcha savdo | ~0 (quvvat yetarli) |
| Elektr (10 kVt·soat/kun × 1 100) | −330 000 |
| Servis | −100 000 |
| **Naqd natija** | **−430 000** |
| Amortizatsiya (25 mln ÷ 84 oy) | −298 000 |
| **Foyda bo'yicha natija** | **−728 000** |
| 5-dekabr (oylik kuni) kassa: 44,7 mln → **19,7 mln** | xavfsiz chegara ~17 mln — **juda yaqin** |

### Quvvat qachon tugaydi (shanba cheklari, oshxona quvvati 90)

| Oy | Dek 26 | Fev 27 | Apr 27 | **May 27** | Iyul 27 | Avg 27 |
|---|---:|---:|---:|---:|---:|---:|
| Shanba cheklari | 77,2 | 80,7 | 84,2 | **86,0** | 89,8 | 91,8 |
| Yuklama | 86% | 90% | 94% | **96%** | 100% | 102% — buyurtma yo'qoladi |

(O'sish: oxirgi 9 oy o'rtachasi oyiga +2,2%.)

### May 2027 da olsangiz (quvvat to'lganda)

| | Oyiga |
|---|---:|
| Qo'shimcha yalpi foyda (2-stansiya tajribasi) | +8 160 000 |
| Elektr + servis | −430 000 |
| Yangi lavash ustasi (oylik + ovqat) | −3 412 000 |
| **Sof naqd natija** | **+4 320 000** |
| **Qoplash muddati** | **~5,8 oy** (2027-yil noyabr) |

### Hozir vs may — 13 oylik yig'ma natija

| | Dek 2027 holatida |
|---|---:|
| Hozir olish | +7,4 mln |
| **May 2027 da olish** | **+9,5 mln** |
| Farq | hozir olish **2,2 mln qimmatga** tushadi + dekabrda kassa xavfli |

### Pul yetmasa — qanday olish (25 mln, may 2027)

| Variant | Hozir to'laysiz | Oyiga | Muddati | Ortiqcha to'lov | Apparat foydasidan keyin oyiga |
|---|---:|---:|---|---:|---:|
| ✅ **Jamg'arma** (dek–apr har oy 5 mln) | 0 (oldindan yig'ilgan) | — | — | **0** | **+4 320 000** |
| Bo'lib to'lash (20% + 6 oy) | 5 000 000 | 3 667 000 | 6 oy | 2 000 000 | +653 000 |
| Bank krediti (24%, 12 oy) | 0 | 2 364 000 | 12 oy | 3 370 000 | +1 956 000 |

Kredit olsangiz ham apparat o'z to'lovini o'zi to'laydi: oyiga +4,32 mln foyda − 2,36 mln to'lov = **+1,96 mln** qoladi.
Foydaning hammasini qarzga yo'naltirsangiz — kredit **7 oyda** yopiladi.

### Nima qilish kerak

1. **Hozir olmang.**
2. **Jamg'arma:** dekabrdan aprelgacha har oy **5 mln** alohida hisobga (oktyabrdagi sof foyda 17,7 mln — bemalol).
3. **Signal:** shanba cheklari 85 dan oshsa yoki "ulgurmadi" kunlari oyiga 2 tadan ko'paysa — AI xabar beradi, sotib olish vaqti.
4. **Apparat bilan birga lavash ustasi** oling (aks holda quvvat ishlamaydi).
5. Agar eski apparat **buzilsa** — kutmang, darhol oling (side savol 7.1 ga qarang).

*Taxminlar: oshxona quvvati 90 chek/kun, o'sish 2,2%/oy, elektr 10 kVt·soat/kun, servis 100 000/oy, foyda — 2-stansiya
tajribasi (+8,16 mln), xavfsiz chegara — 7 kunlik qat'iy chiqimlar (~17 mln), bo'lib to'lash ustamasi ~20%/yil, kredit 24%.*

---

## 4. GRAFIKLAR (Recharts)

### 4.1 "Quvvat qachon tugaydi" — line + chegaralar

```json
{"type": "line", "title": "Shanba cheklari va oshxona quvvati",
 "x": ["Dek 26","Yan 27","Fev 27","Mar 27","Apr 27","May 27","Iyun 27","Iyul 27","Avg 27","Sen 27","Okt 27","Noy 27","Dek 27"],
 "series": [{"name": "Shanba cheklari (prognoz)", "color": "#2DD4BF",
   "data": [77.2,78.9,80.7,82.4,84.2,86.0,87.9,89.8,91.8,93.8,95.8,97.9,100.1]}],
 "ref_lines": [{"y": 90, "label": "Quvvat — 90", "color": "#DC2626"}, {"y": 85, "label": "95% — olish vaqti", "color": "#F59E0B"}],
 "marker": {"x": "May 27", "label": "Apparat olish"}}
```

### 4.2 "Hozir vs may — yig'ma natija" (mln so'm)

```json
{"type": "line", "title": "13 oylik yig'ma naqd natija, mln so'm", "zero_line": true,
 "x": ["Dek 26","Yan 27","Fev 27","Mar 27","Apr 27","May 27","Iyun 27","Iyul 27","Avg 27","Sen 27","Okt 27","Noy 27","Dek 27"],
 "series": [
  {"name": "Hozir olish", "color": "#F87171", "data": [-25.43,-25.86,-26.29,-26.72,-27.15,-22.83,-18.51,-14.20,-9.88,-5.56,-1.24,3.08,7.39]},
  {"name": "May 2027 da olish (tavsiya)", "color": "#14B8A6", "data": [0,0,0,0,0,-20.68,-16.36,-12.05,-7.73,-3.41,0.91,5.23,9.54]}]}
```

### 4.3 "Moliyalashtirish" — jadval (yuqoridagi) + bar "ortiqcha to'lov": Jamg'arma 0, Bo'lib to'lash 2,0 mln, Kredit 3,37 mln.

KPI plitalar:

| Plita | Qiymat |
|---|---|
| Hozir olsangiz | −430 000 so'm/oy |
| Olish vaqti | May 2027 |
| O'shanda foyda | +4 320 000 so'm/oy |
| Qoplash | ~5,8 oy |

---

## 5. LIVE

### 5.1 Ko'rinishi
Q1/Q2 kabi: xulosa + 4 KPI ≤1 s; `[cue]` lar bo'limlarni ochadi; oxirida "Rejani tasdiqlash" → jamg'arma rejasi (oyiga 5 mln,
dek–apr), signal kuzatuvi (shanba ≥ 85, "ulgurmadi" ≥ 2), may 2027 eslatmasi. Namuna: `Q3_live.png`.

### 5.2 Nutq (~45 soniya)

`[cue: verdict+kpi]`
"Qisqasi: hozir olsangiz, apparat zarariga ishlaydi — oyiga to'rt yuz ming so'm faqat elektr va servisga ketadi."

`[cue: capacity_chart]`
"Sababi: ikkala lavash stansiyangiz hali to'lmagan. Shanba kuni ham oshxona sakson to'rt foiz band, iyundan beri birorta
mijoz navbat sababli ketmagan. Savdo shu sur'atda o'ssa, quvvat kelasi may oyida tugaydi."

`[cue: may_table]`
"Ana o'shanda apparat haqiqiy investitsiya bo'ladi: oyiga to'rt million uch yuz ming foyda va olti oyda o'zini qoplaydi."

`[cue: jcurve]`
"Hozir olish sizga ikki million qimmatga tushadi va beshinchi dekabrda kassani xavfli chegaraga yaqinlashtiradi."

`[cue: financing]`
"Pul masalasi: hozirdan har oy besh million jamg'arsangiz, mayda qarzsiz olasiz. Kredit olsangiz ham apparat to'lovini
o'zi to'laydi va yetti oyda yopiladi."

`[cue: approve_button]`
"Jamg'arma rejasini va signal kuzatuvini yoqaymi?"

### 5.3 Qisqa nutq (~12 soniya)
"Hozir olmang — oyiga to'rt yuz ming zarar. Quvvat mayda tugaydi: o'shanda oling, oyiga to'rt million foyda beradi. Hozirdan
oyiga besh million jamg'aring."

---

## 6. Qoidalar

- Avval **bo'sh quvvatni isbotla** (yuklama, "ulgurmadi" kunlari). Quvvat bor bo'lsa — "hozir zarariga", **sana** bilan
  "qachon investitsiyaga aylanadi".
- Har doim **kassa testi** (xarid sanasidagi eng qiyin kun − X vs xavfsiz chegara).
- Har doim **3 ta moliyalashtirish varianti** va "apparat foydasidan keyin oyiga" ustuni.
- Foyda taxmini o'z tajribasidan bo'lsa (2-stansiya) — manbani ayt; yo'q bo'lsa — konservativ/asosiy ikki holat.
- `reason = almashtirish` bo'lsa — mantiq o'zgaradi: kutish = yo'qotilgan savdo; odatda "darhol oling" + eng arzon moliyalash.
- X aytilmasa — so'ra yoki oxirgi xarid narxini (32 mln, 2-stansiya) taklif qil.

---

## 7. Qo'shimcha (side) savollar — Q3 dan keyin

### 7.0 Umumiy qoida
Oxirgi intent va parametrlar xotirada; parametr o'zgarsa — qayta hisob + "Oldin → Yangi" jadvali; "nega/qanday" — formula
oddiy tilda; Live — 1–2 gap + kartaning tegishli bo'limi yangilanadi; "javob bera olmayman" yo'q.

### 7.1 Tayyor javoblar (raqamlar hisoblab tekshirilgan)

| Foydalanuvchi so'raydi | Nima qilinadi | Javob (qisqa) |
|---|---|---|
| "Eski apparat buzildi, majburman" | reason=almashtirish | **Darhol oling.** Bitta stansiya bilan quvvat ~60/kun — iyungacha 27 kun buyurtma yo'qolgan edi; kutish oyiga ~8 mln yalpi foydani yo'qotadi. Kassa uchun: 20% + 6 oy bo'lib to'lash (oyiga 3,67 mln) — 5-dekabr xavfsiz qoladi. |
| "Apparat 40 mln bo'lsa?" | price=40M | Hozir: −430 000/oy (+amortizatsiya 476 000). May 2027 da: +4,32 mln/oy, qoplash **~9,3 oy**. Kredit 12 oy: 3,78 mln/oy. Jamg'arma: dek–apr oyiga 8 mln. |
| "Bo'lib to'lasam oyiga qancha?" | financing=installment | 5 mln hozir + **3 667 000 × 6 oy**, ortiqcha 2,0 mln. |
| "Kredit olsam necha oyda yopaman?" | financing=loan | 12 oylik: **2 364 000/oy**, ortiqcha 3,37 mln. Apparat foydasini (4,32 mln) to'liq qarzga bersangiz — **7 oyda** yopiladi. |
| "Qaysi bankdan kredit olay?" | web_lookup | 3–5 ta joriy taklif (bank, stavka, muddat, manba) — jadval; biznesingizga mosligi. |
| "Savdo tezroq o'ssa-chi (4%/oy)?" | growth=4% | Quvvat **~fevral 2027** da tugaydi → apparatni yanvar oxirida oling. |
| "Ishchi olmasam bo'lmaydimi?" | cook=0 | Lavash ustasisiz ikkinchi apparat to'liq ishlamaydi; agar mavjud oshpazlar qoplasa: foyda +7,7 mln/oy, qoplash ~3,2 oy — lekin xizmat sekinlashish xavfi. |
| "Elektrni qancha yeydi?" | energy | ~10 kVt·soat/kun → **330 000 so'm/oy** (1 100 so'm/kVt·soat, 1-iyun 2026 tarifi). |
| "Hozir olsam umuman qancha yo'qotaman?" | idle cost | Mayga qadar 5 oy: naqd **−2,15 mln**, foyda bo'yicha −3,6 mln (amortizatsiya bilan). |
| "Uning o'rniga 2-filial ochsam-chi?" | boshqa intent | Q10 (filial) shabloniga o'tish taklif qilinadi. |

Live misol (side): "Agar eskisi buzilgan bo'lsa — kutmang, bugun oling: har kuni kutish sizga savdo yo'qotadi. Bo'lib
to'lashga oling, oyiga uch million olti yuz ming — kassa xavfsiz qoladi."

---

## Implementation notes (agent)
- Tool `equipment_investment` (`backend/apps/ai/golden_tools.py`); images `Q3_chat.png`, `Q3_live.png`.
- On this spec's file (Lazzat, Oct-2026 revenue 156 187 000) with X = 25 mln (or no price) the answer is pinned to the spec
  (`backend/apps/ai/data/golden/Q3.pinned.json`), incl. the 7.1 side answers. Other files / prices / equipment: computed —
  capacity from Smena (Saturday checks ÷ 90, "ulgurmadi" notes), buy month from the 9-month growth, extra gross profit at full
  capacity = 7,5% of revenue × hall margin (estimate when there is no "2nd station" history), cook = cheapest lavash-usta salary
  + staff meals, installment 20% + 6 months at ~20%/yr, loan 24% 12-month annuity.
- "Qaysi bankdan kredit olay?" is left to the full-context chat + web_lookup (side-question context mode).
