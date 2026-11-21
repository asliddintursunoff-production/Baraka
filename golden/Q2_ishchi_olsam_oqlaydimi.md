# GOLDEN ANSWER — Q2: Yana bitta ishchi (ofitsiant) olsam, necha oyda o'zini oqlaydi?

> Har bir golden javob 3 qismdan iborat va agent ULARNING HAMMASINI bajaradi:
> (1) chatdagi hisobot (matn + jadval + grafik), (2) Live'da xuddi shu hisobot kartasi ochiladi,
> (3) Live uchun nutq — `[cue]` lar bilan hisobot bo'limlariga bog'langan.
> Ko'rinish namunalari: `Q2_chat.png` (chat), `Q2_live.png` (live).
> Raqamlar — `Lazzat_Lavash_FastFood_2026.xlsx` uchun to'g'ri javob (oktyabr 2026 — oxirgi to'liq oy).

---

## 1. Savolni tanish (intent: `hire_payback`)

- Yana bitta ofitsiant olsam, u o'zini necha oyda oqlaydi?
- Yana bitta ofitsam olsam, o'zini oqlaydimi?
- Yangi ishchi olsam arziydimi?
- Yana bir oshpaz / lavash ustasi kerakmi?
- Kassir qo'shsam foyda bo'ladimi?
- Ikkinchi kuryer olsam o'zini qoplaydimi?
- Xodim yetishmayaptimi, yana odam olaymi?
- Kechki smenaga odam qo'shsam-chi?
- 3 millionlik ishchi olsam necha oyda qaytadi?
- Ishchi olish vaqti keldimi?

**Parametrlar:** `role` (ofitsiant | oshpaz/lavash ustasi | kassir | kuryer | farrosh | boshqa), `salary` (aytilmasa —
shu lavozimdagi joriy oylik yoki bozor standarti), `official` (Ha/Yo'q), `shift` (to'liq | kechki | dam olish kunlari).
"Ofitsam" = "ofitsiant" (og'zaki variant). Lavozim aytilmasa → eng yuklangan bo'lim uchun hisobla va so'ra.

---

## 2. Hisoblash retsepti (deterministik)

**A. Ishchi narxi (oyiga):**
oklad + savdodan % (o'xshash lavozim bo'yicha) + ijtimoiy soliq 12% (agar rasmiy) + xodim ovqati (12 porsiya × eng arzon
asosiy taom tannarxi) + bir martalik: forma/o'qitish 300 000 so'm, birinchi oy samaradorlik 50%.

**B. Lavozim bo'yicha foyda mexanizmi (qaysi biri qo'llanadi):**

| Lavozim | Foyda qayerdan keladi | Ma'lumot |
|---|---|---|
| Ofitsiant / zal xodimi | Zalda o'rtacha chek oshishi (tavsiya, qo'shimcha sotuv) — standart +4% | Sotuv: Zal kanali tushumi va marjasi |
| Oshpaz / lavash ustasi | Yo'qotilgan buyurtmalarni qaytarish | Smena izohi "ulgurmadi" kunlari, kunlik cheklar ÷ oshxona quvvati |
| Kassir | Pik soatda navbat sababli ketgan mijozlar | Soatlik savdo: pik soat cheklari ÷ kassir quvvati (30 chek/soat) |
| Kuryer | O'z dostavka hajmi | Buyurtmalar ÷ 450 (kuryer quvvati) |

**C. Natija:** oylik sof effekt = qo'shimcha yalpi foyda − ishchi narxi. Qoplash muddati = bir martalik xarajat ÷ oylik sof
effekt (manfiy bo'lsa → "qoplamaydi"). 12 oylik yig'ma natija (1-oy 50%).

**D. Zararsizlik nuqtasi:** ishchi o'zini oqlashi uchun kerak bo'lgan o'sish (%, so'm) va shu nuqtaga qachon yetilishi
(oxirgi 9 oydagi o'rtacha oylik o'sish bilan).

**E. Yuklama jadvali (har doim ko'rsatiladi):** Oshxona (shanba cheklari ÷ 90), Kassa (pik soat ÷ 2×30), Kuryer (÷450),
"ulgurmadi" kunlari (oxirgi 3 oy).

**F. Alternativa:** shu pulga yaxshiroq natija beradigan variant (standart: kassirlarga qo'shimcha sotuvdan 3% bonus,
Zal + Olib ketish tushumida +4% qo'shimcha sotuv).

---

## 3. JAVOB (chat)

**Xulosa: Hozir yangi ofitsiant o'zini oqlamaydi — har oy ~630 000 so'm zarar qiladi. Sababi: oshxona va kassa hali bo'sh
quvvatda, 10-iyundan beri birorta buyurtma navbat sababli yo'qolmagan. Buning o'rniga kassirlarga qo'shimcha sotuv uchun bonus
bering — oyiga +2,66 mln so'm. Ofitsiant taxminan 2027-yil may oyida kerak bo'ladi.**

*Eslatma: sizda buyurtma kassada olinadi (fast food), shuning uchun ofitsiantning ishi — taomni stolga olib borish va
qo'shimcha taom tavsiya qilish.*

### Ofitsiantning narxi va foydasi (oyiga, oktyabr asosida)

| | So'm / oy |
|---|---:|
| Oklad | 2 000 000 |
| Zal savdosidan 0,3% | 176 000 |
| Xodim ovqati | 112 000 |
| **Jami narxi** | **2 288 000** |
| Zal o'rtacha chekining +4% o'sishi (75 500 → 78 500) | +2 344 000 tushum |
| Shundan yalpi foyda (zal marjasi 70,6%) | **+1 655 000** |
| **Oylik sof natija** | **−633 000** |
| **Qoplash muddati** | **Qoplamaydi** (12 oyda −8,7 mln) |

### O'zini oqlashi uchun nima kerak

| Shart | Hozir | Kerak |
|---|---:|---:|
| Zal o'rtacha chekining o'sishi | +4% (taxmin) | **+5,5%** (har chekka +4 200 so'm) |
| yoki zal savdosi (oyiga, +4% bilan) | 58,6 mln | **81,0 mln** |
| Zal savdosi o'sishi | oyiga ~2,2% | → 81 mln ga ~**15 oyda** yetadi |

### Xodimlaringiz yuklamasi (sentyabr–noyabr)

| Bo'lim | Yuklama | Holat |
|---|---:|---|
| Oshxona (lavash stansiyalari), shanba | 75,6 / 90 chek → **84%** | Yaxshi, chegara 95% |
| Oshxona, ish kunlari | 55 / 90 → **61%** | Bo'sh quvvat bor |
| Kassa, eng band soat (juma 13:00) | 9,8 / 60 chek/soat → **16%** | Juda bo'sh |
| Kuryer | 189 / 450 → **42%** | Bo'sh |
| Navbat sababli yo'qotilgan kunlar (10-iyundan beri) | **0** | 2-lavash stansiyasidan keyin muammo yo'q |

### Shu pulga yaxshiroq variant

| Variant | Oylik xarajat | Oylik sof natija | 12 oyda |
|---|---:|---:|---:|
| ❌ Yangi ofitsiant | 2 288 000 | **−633 000** | **−8,7 mln** |
| ✅ Kassirlarga qo'shimcha sotuv bonusi (3%) | 118 000 | **+2 655 000** | **+30,5 mln** |

Bonus qanday ishlaydi: kassir har buyurtmada bitta taklif qiladi — "Kombo qilib beraymi?", "Sous qo'shaymi?", "Ichimlik
kerakmi?". Zal va olib ketish tushumi (oyiga 98,2 mln) 4% oshsa: +3,93 mln tushum → +2,77 mln yalpi foyda; kassirlarga
3% bonus — 118 000 so'm.

### Qachon ishchi olish kerak (signal)

| Signal | Hozir | Ishchi olish vaqti |
|---|---|---|
| Shanba kunlik cheklari | 75,6 | ≥ 85 (oshxona 95%) → **~2027-yil may** (lavash ustasi) |
| "Ulgurmadi" kunlari | 0 / oy | ≥ 2 kun / oy |
| Pik soat cheklari | 9,8 / soat | ≥ 45 / soat (kassa 75%) |
| Zal savdosi | 58,6 mln | ≥ 81 mln / oy (ofitsiant) |

AI bu signallarni har kuni kuzatadi va vaqti kelganda o'zi xabar beradi.

### Nima qilish kerak

1. **Hozir ofitsiant olmang.**
2. **Kassirlar uchun "bitta taklif" qoidasi va 3% bonus** — shu haftadan.
3. **30 kundan keyin tekshiring:** zal va olib ketishda o'rtacha chek 4% oshdimi.
4. **Signal kuzatuvini yoqing** — shanba 85 chekdan oshsa, lavash ustasi olish vaqti.

*Taxminlar: ofitsiant oklad 2,0 mln (bozor standarti), zal o'rtacha cheki +4%, kassir quvvati 30 chek/soat, oshxona
quvvati 90 chek/kun, zal savdosi o'sishi oyiga 2,2% (yanvar–oktyabr). O'zgartirsangiz, qayta hisoblayman.*

---

## 4. GRAFIKLAR (Recharts)

### 4.1 "12 oylik yig'ma natija" — line (mln so'm)

```json
{
  "type": "line",
  "title": "12 oyda qancha yutasiz yoki yutqazasiz (yig'ma, mln so'm)",
  "zero_line": true,
  "series": [
    {"name": "Yangi ofitsiant", "color": "#F87171",
     "data": [-1.76,-2.39,-3.03,-3.66,-4.29,-4.92,-5.56,-6.19,-6.82,-7.46,-8.09,-8.72]},
    {"name": "Kassirga bonus (tavsiya)", "color": "#14B8A6",
     "data": [1.33,3.98,6.64,9.30,11.95,14.61,17.27,19.92,22.58,25.24,27.89,30.55]}
  ],
  "x": ["Dek","Yan","Fev","Mar","Apr","May","Iyun","Iyul","Avg","Sen","Okt","Noy"]
}
```

### 4.2 "Xodimlar yuklamasi" — progress bars

```json
{"type": "progress_list", "title": "Xodimlar yuklamasi", "threshold": 0.85,
 "items": [
  {"label": "Oshxona — shanba", "value": 0.84, "note": "75,6 / 90 chek"},
  {"label": "Oshxona — ish kunlari", "value": 0.61, "note": "55 / 90"},
  {"label": "Kassa — eng band soat", "value": 0.16, "note": "9,8 / 60 chek/soat"},
  {"label": "Kuryer", "value": 0.42, "note": "189 / 450 buyurtma"}
 ]}
```

### 4.3 "Narx va foyda" — waterfall (so'm/oy)

```json
{"type": "waterfall", "title": "Ofitsiant: oyiga narxi va foydasi",
 "steps": [
  {"label": "Qo'shimcha yalpi foyda", "value": 1655000},
  {"label": "Oklad", "value": -2000000},
  {"label": "Savdodan 0,3%", "value": -176000},
  {"label": "Ovqat", "value": -112000}
 ], "total_label": "Sof natija", "total": -633000}
```

KPI plitalar:

| Plita | Qiymat |
|---|---|
| Ofitsiant: oylik natija | −633 000 so'm |
| Qoplash muddati | Qoplamaydi |
| Yaxshiroq variant | +2 655 000 so'm/oy |
| Ishchi kerak bo'ladi | ~2027-yil may |

Karta tartibi: Xulosa → 4 KPI → 4.1 → narx/foyda jadvali (+4.3) → yuklama (4.2) + jadval → "Shu pulga yaxshiroq variant"
→ signallar → "Nima qilish kerak" → taxminlar.

---

## 5. LIVE

### 5.1 Live'da qanday ko'rinadi
Xuddi Q1 kabi: ≤1 s ichida shu ReportCard (xulosa + 4 KPI) orb ustida ochiladi; har `[cue]` o'z bo'limini ochib belgilaydi;
oxirida "Rejani tasdiqlash" (bonus qoidasi + 30 kunlik tekshiruv eslatmasi + signal kuzatuvi). Namuna: `Q2_live.png`.

### 5.2 Nutq (~40 soniya)

`[cue: verdict+kpi]`
"Qisqasi: hozir ofitsiant olmang — u o'zini oqlamaydi, har oy olti yuz ming so'mga yaqin zarar qiladi."

`[cue: load]`
"Sababi oddiy: oshxonangiz shanba kuni ham sakson to'rt foiz band, kassa eng band soatda ham deyarli bo'sh.
Iyundan beri birorta mijoz navbat sababli ketmagan."

`[cue: chart_cumulative]`
"Ofitsiant bir yilda sakkiz yarim million zarar keltiradi. Uning o'rniga kassirlaringizga har qo'shimcha sotuvdan uch foiz
bonus bering — 'kombo qilib beraymi?' degan bitta savol. Bu oyiga ikki yarim million, yiliga o'ttiz million foyda."

`[cue: signals]`
"Ishchi qachon kerak bo'ladi? Taxminan kelasi may oyida, shanba kunlari sakson beshta chekdan oshganda. Men buni kuzatib,
vaqti kelganda sizga o'zim aytaman."

`[cue: approve_button]`
"Bonus rejasini tasdiqlaysizmi?"

### 5.3 Qisqa nutq (~12 soniya)
"Hozir ofitsiant olmang — oyiga olti yuz ming zarar qiladi, chunki xodimlaringiz hali to'liq band emas. Uning o'rniga
kassirlarga qo'shimcha sotuv bonusi bering — oyiga ikki yarim million foyda."

---

## 6. Qoidalar (shu shablon uchun)

- Har doim **yuklama jadvali** ko'rsatilsin — "ishchi kerakmi" savoliga isbot shu.
- Natija manfiy bo'lsa: "qoplamaydi" de, **zararsizlik sharti** va **qachon kerak bo'lishini** sana bilan ber, va **alternativa** taklif qil.
- Natija musbat bo'lsa: qoplash muddati (oy), 12 oylik yig'ma va eng yaxshi boshlash sanasi (kassa xavfsiz chegarasi bilan tekshir).
- Biznes formati bilan mos kelmasa (fast food'da ofitsiant) — 1 gapda tushuntir, lekin hisobni baribir qil.
- Lavozim aytilmasa — eng yuklangan bo'limni tanla va "… uchun hisobladim, boshqa lavozimmi?" deb so'ra.
- Davr: oxirgi to'liq oy; yuklama — oxirgi 3 oy.
