# AI CFO — 100 ta savol uchun shablonlar katalogi (MVP)

> Bu fayl agent uchun. Har savol: intent, variantlar, parametrlar, manba, hisoblash retsepti, hisobot ko'rinishi,
> Live nutq va side savollar. Raqamlar har doim foydalanuvchi faylidan qayta hisoblanadi; `{...}` — joy egasi.
> Misollardagi raqamlar `Lazzat_Lavash_FastFood_2026.xlsx` (01.01–21.11.2026) ga mos yo'nalishda berilgan.

---

## 0. TAQDIMOT SAVOLLARI (zaxiralangan — bu katalogga KIRMAYDI)

| # | Savol | Intent |
|---|---|---|
| Q1 | Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi? Qaysi biri ko'proq foyda olib keladi? | `channel_economics` |
| Q2 | Yana bitta ofitsiant olsam, o'zini necha oyda oqlaydi? | `hire_payback` |
| Q3 | X so'mga lavash apparat olmoqchiman, bu hozir investitsiya bo'ladimi yoki zarariga ishlaydimi? | `equipment_investment` |
| Q4 | Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber. | `revenue_growth_plan` |

**Himoya qoidalari (majburiy):**
1. Q1–Q4 intentlari **ustuvor**: router avval ularni tekshiradi. Katalogdagi 100 intent Q1–Q4 ning
   variantlari bilan to'qnashmasligi kerak (embedding o'xshashlik ≥ 0.80 bo'lsa — katalog intenti o'chiriladi yoki qayta yoziladi).
2. Q1–Q4 javoblari (raqamlar, xulosa, nutq) **o'zgarmaydi**: katalog intentlari Q1–Q4 tool'larini chaqirmaydi va ularning
   natijasini qayta yozmaydi. Kerak bo'lsa faqat havola: "→ Q3 (taqdimot savoli)".
3. Katalogdan olib tashlangan (Q1–Q4 bilan to'qnashgani uchun) PDF savollari: #1, #3, #5, #21, #30, #33, #34, #36, #38, #39, #42.
   Ularning o'rniga 63 ta yangi savol (N01–N63) qo'shildi. Jami: PDF dan 37 (S..) + yangi 63 (N..) = **100**.
4. **Muvofiqlik (yagona haqiqat manbai):** quvvat (shanba yuklamasi, "ulgurmadi" kunlari), eng tang kun, kassa, kredit,
   agregator qarzi — hamma javoblarda bitta umumiy tool'dan olinadi; Q2/Q3 dagi raqamlar bilan zid kelmasligi shart.
5. **Yomon niyatli so'rov** ("biznesni qulatmoqchiman/uxlatmoqchiman", sabotaj, firibgarlik): «Mening vazifam —
   biznesingizga foyda keltirish.» + qonuniy muqobil (masalan, risk xaritasi N60 yoki biznesni to'g'ri yopish/sotish rejasi).
   "Biznesimni NIMA qulatishi mumkin?" — bu qonuniy xavf savoli → N60.

---

## 1. Umumiy hisobot shabloni (ReportCard) — barcha 100 savol uchun

| Bo'lim | Majburiy | Tarkib |
|---|---|---|
| Xulosa | ✅ | 1–2 gap: aniq javob (ha/yo'q/qancha/qachon) + asosiy raqam. Birinchi gap — qaror. |
| KPI plitalar | ✅ | 3 ta (ba'zan 4): katta raqam + izoh; rang: yashil — yaxshi, sariq — e'tibor, qizil — xavf. |
| Grafik | agar ko'rsatilgan bo'lsa | Recharts: line / bar / waterfall / stacked / heatmap / scatter / gauge. Sanalarda yil bo'lsin. |
| Jadval | agar ko'rsatilgan bo'lsa | Raqamlar o'ngga, "71 121 526" formati, manfiy — qizil; 5–10 qator. |
| Nima qilish kerak | ✅ | 3 qadam, har biri pul ta'siri yoki sana bilan; "AI maslahati" ovozida. |
| Taxminlar | agar taxmin bo'lsa | Kichik shrift; foydalanuvchi o'zgartira oladi → qayta hisob. |
| Manba | ✅ | Varaq!ustun, qatorlar soni, davr (masalan "Sotuv!G, 14 406 qator, okt 2026"). |
| Chips | ✅ | 2–3 ta side savol (pastdagi "Side" dan). |

**Davr qoidasi:** standart — oxirgi yopilgan oy (oktyabr 2026); joriy oy ("noyabr 1–21") faqat run-rate sifatida.

**Ma'lumot yo'q bo'lsa:** avval barcha varaqlarni sinonimlar bilan qidir → topilmasa hisobla → baribir yo'q bo'lsa
"taxmin" (diapazon + taxminlar) + bitta aniqlashtiruvchi savol. Faqat aniq fakt (telefon, shartnoma bandi) uchun "ma'lumot yo'q".

**Side savollar:** oxirgi intent va parametrlar xotirada; parametr o'zgarsa → qayta hisob + "Oldin → Yangi" jadvali;
"nega/qanday" → formula oddiy tilda.

## 2. Live (ovozli) qoidalari

- Savol tanilgan zahoti xuddi shu ReportCard (yig'ilgan: xulosa + KPI) ekranga chiqadi; nutq bo'laklari bo'limlarni ochadi.
- Nutq: 1-gap — qaror; raqamlar og'zaki va yaxlit ("o'n yetti million"); bir gapda ≤ 2 raqam; aytilgan raqam ekranda bo'lsin.
- Katalog savollari uchun nutq 1–2 gap (pastda "Live"); "batafsil" desa — karta bo'limlari bo'yicha davom etadi.
- Harakat bo'lsa — oxirida "tasdiqlaysizmi?" → Tasks/eslatma (pul harakati yo'q).

## 3. Katalog tuzilmasi

| Kod | Soha | Soni |
|---|---|---|
| S02–S48 | PDF dan (Rahbar, Investor, CFO, Buxgalteriya, Savdo, Oshxona) | 37 |
| N01–N07 | Kassa va to'lovlar | 7 |
| N08–N15 | Moliyalashtirish va qarz | 8 |
| N16–N22 | Kapital qarorlari | 7 |
| N23–N27, N63 | Narx va menyu (what-if) | 6 |
| N28–N34 | Xodimlar (what-if) | 7 |
| N35–N40 | Xarajatlar | 6 |
| N41–N49 | Prognoz va maqsad | 9 |
| N50–N56 | Nazorat va monitoring | 7 |
| N57–N62 | Egasi uchun | 6 |
| | **Jami** | **100** |

---

## 4. SAVOLLAR


### — Rahbar —


#### S02 · Oktyabrdagi foyda o'sishi barqarormi yoki bir martalik omillar hisobigami?

- **Intent:** `profit_growth_quality` · **Soha:** Rahbar
- **Variantlar:** «Foydam nega oshdi — bu davom etadimi?» · «O'sish tasodifiymi yoki doimiymi?»
- **Parametrlar:** davr (standart: yanvar→oxirgi yopilgan oy)
- **Manba:** Foyda-zarar, Menyu, Reja-fakt
- **Hisoblash:** Tushum o'sishini 3 ga ajrat: cheklar soni × o'rtacha chek (hajm/narx), food/labor ulushi o'zgarishi; bir martalik omillar (narx oshirish oyi, reklama oyi, bayramlar) belgilanadi.
- **Hisobot:**
  - Xulosa: «O'sish asosan {barqaror/bir martalik}: {x}% mijozlar sonidan, {y}% chekdan. {bir martalik omil} — alohida.»
  - KPI: Cheklar hissasi % | Chek hissasi % | Yalpi marja (oldin → keyin)
  - Grafik: waterfall: tushum o'sishi = hajm + narx + mix
  - Jadval: oylar: cheklar/kun, o'rtacha chek, yalpi marja
  - Nima qilish kerak: 1) Kunlik cheklarni asosiy KPI qiling → 2) Navbatdagi narx oshirishni 12 oy kuting → 3) Har oy o'sishni hajm/narx/xarajatga ajrating
- **Live:** «O'sishning katta qismi mijozlar sonidan — demak barqaror. Narx oshirish bir martalik bonus edi.»
- **Side:** «Keyingi oy ham shunday bo'ladimi?» → N42 prognozga o'tish · «Qaysi oy eng yaxshi edi va nega?» → oylar jadvali + omillar

#### S04 · Rejadan orqada qolishimiz strategik xatomi yoki ijro muammosimi?

- **Intent:** `plan_gap_diagnosis` · **Soha:** Rahbar
- **Variantlar:** «Nega rejani bajara olmayapmiz?» · «Reja noto'g'rimi yoki biz yomon ishlayapmizmi?»
- **Parametrlar:** oy (standart: oxirgi yopilgan)
- **Manba:** Reja-fakt, Fin reja
- **Hisoblash:** Har qator bo'yicha farq: cheklar (taxmin), o'rtacha chek, food cost, labor (ijro). Taxmin farqi = reja trafigi − real trafik; ijro farqi = narx/xarajat qatorlari.
- **Hisobot:**
  - Xulosa: «Asosan {reja taxmini / ijro}: rejada kuniga {r} chek, fakt {f}. Ijro: chek {+/-}%, food cost {..}, xodimlar {+..%}.»
  - KPI: Cheklar reja/fakt | O'rtacha chek vs reja | Xodimlar xarajati vs reja
  - Grafik: bar: reja vs fakt (asosiy 6 qator)
  - Jadval: Reja-fakt jadvali (reja, fakt, farq %, baho ✓/✗)
  - Nima qilish kerak: 1) Rejani real trafik bilan qayta tuzing → 2) Trafik o'sishini alohida loyiha qiling → 3) Chetga chiqqan xarajatni rejaga qaytaring
- **Live:** «Muammo asosan rejada: trafik taxmini baland qo'yilgan. Ijro yomon emas — faqat xodimlar xarajati rejadan yuqori.»
- **Side:** «Rejani qayta tuzib ber» → S20 byudjet ssenariylari · «Qaysi xarajat eng ko'p chetga chiqdi?» → Reja-fakt top-3 farq

#### S06 · Biznes qaysi tashqi omilga eng sezgir va zarbaga qanchalik chidamli?

- **Intent:** `sensitivity_stress` · **Soha:** Rahbar
- **Variantlar:** «Savdo 20% tushsa nima bo'ladi?» · «Go'sht qimmatlasa qancha zarar ko'raman?»
- **Parametrlar:** omil, o'zgarish % (standart: tushum −10%, go'sht +10%, komissiya +5 p.)
- **Manba:** Foyda-zarar, Kirim, Mahsulot rentabelligi
- **Hisoblash:** Har omil uchun oylik sof foydaga ta'sir: tushum (marjinal foyda bilan), xom ashyo (ulush × o'zgarish), komissiya (agregator tushumi × punkt). Chidamlilik = kassa / oylik zarar.
- **Hisobot:**
  - Xulosa: «Eng sezgir omil — {omil}: {o'zgarish} foydani {x} mln/oy kamaytiradi. Kassa {y} oy chidaydi.»
  - KPI: Tushum −10% | Go'sht +10% | Komissiya +5 p.
  - Grafik: tornado chart: omillar bo'yicha foyda ta'siri
  - Jadval: omil | o'zgarish | foyda ta'siri | himoya choras
  - Nima qilish kerak: 1) 1 oylik xarajatga teng zaxira ushlang → 2) Go'sht narxini oldindan kelishing → 3) Agregator ulushini 30% dan oshirmang
- **Live:** «Eng katta xavf — mijozlar oqimi: o'n foiz kamaysa foydaning yarmi ketadi. Bir oylik zaxira ushlang.»
- **Side:** «Savdo 30% tushsa-chi?» → param bilan qayta hisob · «Qancha zaxira kerak?» → N04

#### S07 · Bizda narx belgilash kuchi bormi?

- **Intent:** `pricing_power` · **Soha:** Rahbar
- **Variantlar:** «Mijozlar narxga qanchalik sezgir?» · «Narxni oshirsam mijoz qochadimi (umuman)?»
- **Parametrlar:** davr (narx o'zgargan oy atrofida)
- **Manba:** Menyu, Foyda-zarar, Smena
- **Hisoblash:** Elastiklik = cheklar/kun % o'zgarishi ÷ o'rtacha narx % o'zgarishi (narx o'zgarishidan 1 oy oldin vs 1 oy keyin); tiklanish muddati.
- **Hisobot:**
  - Xulosa: «Narx kuchi {past/o'rtacha/yuqori}: narx {+x}% → cheklar {−y}%, {n} oyda tiklandi (elastiklik ~{e}).»
  - KPI: Narx o'zgarishi | Cheklar o'zgarishi | Elastiklik
  - Grafik: line: kunlik cheklar (narx o'zgarishi belgisi bilan)
  - Jadval: oldin/keyin: cheklar, o'rtacha chek, tushum
  - Nima qilish kerak: 1) Narxni yiliga 1 marta inflyatsiya darajasida oshiring → 2) Avval kam sotiladigan taomda sinang → 3) 4 hafta cheklarni kuzating
- **Live:** «Mijozlaringiz narxga kam sezgir: sentyabrda narx oshganda cheklar atigi uch foiz kamaydi va bir oyda qaytdi.»
- **Side:** «Bitta taom narxini oshirsam?» → N23 · «Raqobatchilar narxi qancha?» → N63

#### S08 · Agar faqat 3 ta ko'rsatkichni kuzatsam, biznes sog'ligini qaysilari eng yaxshi ko'rsatadi?

- **Intent:** `north_star_kpis` · **Soha:** Rahbar
- **Variantlar:** «Qaysi raqamlarga har kuni qarashim kerak?» · «Asosiy KPI'larim qaysilar?»
- **Parametrlar:** —
- **Manba:** Bosh sahifa, Foyda-zarar
- **Hisoblash:** Prime cost % (food+labor), kunlik cheklar, pul qoldig'i — joriy qiymat, maqsad, trend (3 oy).
- **Hisobot:**
  - Xulosa: «Uchta: prime cost ({x}%, maqsad ≤60%), kunlik cheklar ({y}), pul qoldig'i ({z} mln). Hozir {holat}.»
  - KPI: Prime cost % | Kunlik cheklar | Pul qoldig'i
  - Grafik: 3 ta sparkline (12 hafta)
  - Jadval: KPI | hozir | maqsad | trend | holat
  - Nima qilish kerak: 1) Har dushanba Bosh sahifada ko'ring → 2) Chegaradan chiqsa shu hafta chora → 3) Oy yopilgach Reja-fakt
- **Live:** «Uchta raqam yetadi: prime cost, kunlik cheklar va kassadagi pul. Hozir uchalasi ham normada.»
- **Side:** «Har dushanba shuni yuborib tur» → N53 haftalik hisobot obunasi · «Prime cost nega muhim?» → tushuntirish

### — Investor —


#### S09 · Bu biznes kapitalimga qancha daromad keltiryapti — bankdagi foizdan yaxshimi?

- **Intent:** `roic_vs_deposit` · **Soha:** Investor
- **Variantlar:** «Pulim biznesda yaxshi ishlayaptimi yoki depozit yaxshimi?» · «ROIC qancha?»
- **Parametrlar:** depozit stavkasi (standart: web_lookup yoki 20–24%)
- **Manba:** Foyda-zarar, Balans, Asosiy vositalar
- **Hisoblash:** ROIC = normallashtirilgan yillik EBIT ÷ (asosiy vositalar qoldig'i + aylanma kapital); oxirgi 3 oy × 4 (mavsum tuzatish bilan). Taxmin deb belgilanadi.
- **Hisobot:**
  - Xulosa: «ROIC ~{x}% — depozit ({d}%) va kredit (24%) dan {yuqori/past}.»
  - KPI: ROIC | Normallashtirilgan EBIT | Ishlatilgan kapital
  - Grafik: bar: ROIC vs depozit vs kredit
  - Jadval: hisob qatorlari (EBIT, kapital, formula)
  - Nima qilish kerak: 1) ROIC'ni har chorak hisoblang → 2) Yangi investitsiya ROIC > 24% bo'lsin → 3) 2025 ma'lumotini qo'shing
- **Live:** «Biznesingiz kapitalga bankdan ancha ko'p daromad beryapti — taxminan {x} foiz.»
- **Side:** «Depozitga qo'ysam qancha olaman?» → N13 · «ROIC qanday hisoblandi?» → formula

#### S10 · Foyda sifati qanday — qog'ozdagi foyda haqiqiy pulga aylanyaptimi?

- **Intent:** `earnings_quality` · **Soha:** Investor
- **Variantlar:** «Foyda bor, lekin pul qayerda?» · «Foyda va kassa nega farq qiladi?»
- **Parametrlar:** davr (yil boshidan)
- **Manba:** Pul oqimi, Foyda-zarar, Balans
- **Hisoblash:** Operatsion pul oqimi vs sof foyda; farq: amortizatsiya (+), debitorlik o'zgarishi (−), zaxira (−), kreditorlik (+). Kapital xarajat va kredit to'lovi alohida.
- **Hisobot:**
  - Xulosa: «Foyda sifati {yaxshi/zaif}: operatsion pul oqimi {x} mln, sof foyda {y} mln. Farq — {asosiy sabab}.»
  - KPI: Operatsion pul oqimi | Sof foyda | Asosiy farq
  - Grafik: bridge: sof foyda → operatsion pul oqimi
  - Jadval: oylik foyda vs pul oqimi
  - Nima qilish kerak: 1) Foyda va pul oqimini har oy yonma-yon ko'ring → 2) Debitorlik o'sishini kuzating → 3) Farq kattalashsa sababini tekshiring
- **Live:** «Foydangiz haqiqiy pulga aylanyapti — pul oqimi foydadan ham yuqori, chunki amortizatsiya pul chiqimi emas.»
- **Side:** «Pul qayerga ketdi?» → Pul oqimi moddalar · «Kredit to'lovi foydani yeyaptimi?» → N09

#### S11 · Biznes meni hisobga olmasdan o'zi ishlay oladimi, egasiga bog'liqligi qanday?

- **Intent:** `owner_dependency` · **Soha:** Investor
- **Variantlar:** «Men bir oy yo'q bo'lsam biznes ishlaydimi?» · «Kimga bog'liqmiz?»
- **Parametrlar:** —
- **Manba:** Tekshiruv, Ish haqi, Texkarta
- **Hisoblash:** Tizim (nazoratlar, texkarta, hisobotlar) + kalit xodimlar (menejer, bosh oshpaz: ish haqi ulushi, staj) + o'rinbosar bor/yo'q.
- **Hisobot:**
  - Xulosa: «{Qisman}: tizim kuchli ({n}/27 nazorat OK), lekin {kalit xodimlar}ga bog'liqlik yuqori.»
  - KPI: Nazorat tizimi | Kalit kadrlar | Standartlar
  - Jadval: xavf | daraja | chora
  - Nima qilish kerak: 1) Menejer va oshpaz uchun o'rinbosar → 2) Jarayonlarni hujjatlashtiring → 3) Kalit kadrlarni rasmiylashtiring
- **Live:** «Tizim o'zi ishlaydi, lekin menejer va bosh oshpaz ketsa qiyin bo'ladi — o'rinbosar tayyorlang.»
- **Side:** «Oshpaz ketib qolsa qancha zarar?» → N33 · «Menejerga qancha bonus bersam ushlab qolaman?» → N28 param

#### S12 · Keyingi investor kirganida biznes qanday baholanadi va bahoni nima oshiradi?

- **Intent:** `valuation` · **Soha:** Investor
- **Variantlar:** «Biznesim qancha turadi?» · «Sotsam qancha olaman?»
- **Parametrlar:** multiplikator (standart: EBITDA × 2–3)
- **Manba:** Foyda-zarar, Balans, Fin reja
- **Hisoblash:** Baho = normallashtirilgan yillik EBITDA × (2–3) − sof qarz; sezgirlik: EBITDA +50 mln → baho +100–150 mln.
- **Hisobot:**
  - Xulosa: «Taxminiy baho {a}–{b} mln (EBITDA × 2–3). Bahoni eng ko'p oshiradigan narsa — {dastak}.»
  - KPI: Hozirgi baho | EBITDA +50 mln ta'siri | Asosiy dastak
  - Grafik: bar: past/bazaviy/yuqori baho
  - Jadval: hisob: EBITDA, multiplikator, qarz
  - Nima qilish kerak: 1) 2 chorak barqaror EBITDA ko'rsating → 2) Egaga bog'liqlikni kamaytiring → 3) Yangilangan Fin reja + KPI
- **Live:** «Biznesingiz taxminan {a} dan {b} milliongacha turadi; barqaror o'sish bahoni eng ko'p oshiradi.»
- **Side:** «Sherigim ulushini sotib olsam?» → N19 · «Franshiza bersam?» → N22

#### S13 · Foyda qayta investitsiya qilinsinmi, qarz yopilsinmi yoki dividend berilsinmi?

- **Intent:** `profit_allocation_policy` · **Soha:** Investor
- **Variantlar:** «Foydani nima qilay?» · «Dividend olsam bo'ladimi?»
- **Parametrlar:** oylik bo'sh pul (standart: oxirgi 3 oy o'rtachasi)
- **Manba:** Balans, Investitsiyalar, Pul oqimi
- **Hisoblash:** Tartib: 1) zaxira (7–30 kunlik xarajat) 2) ROIC > 24% loyihalar 3) kredit (24%) 4) dividend; har birining joriy holati.
- **Hisobot:**
  - Xulosa: «Tartib: avval zaxira ({x}/{y} mln), keyin ROIC > 24% loyiha, keyin kredit, oxirida dividend.»
  - KPI: Pul zaxirasi | Eng yaxshi ROIC | Kredit stavkasi
  - Grafik: stacked bar: bo'sh pul taqsimoti
  - Jadval: yo'nalish | summa | daromad | ustuvorlik
  - Nima qilish kerak: 1) Avval zaxirani to'ldiring → 2) Ortiqchasini ROIC yuqori loyihaga → 3) Dividend — oxirida
- **Live:** «Avval zaxira, keyin foydali loyiha, keyin kredit — dividend eng oxirida.»
- **Side:** «Oyiga o'zimga qancha olsam bo'ladi?» → N14 · «Kreditni oldin yopsam?» → N08

#### S14 · Bu biznes qancha qarz ko'tarishi mumkin — kengayishni qarz bilan moliyalashtirsak bo'ladimi?

- **Intent:** `debt_capacity` · **Soha:** Investor
- **Variantlar:** «Yana qancha kredit olsam bo'ladi?» · «Qarz ko'tara olamanmi?»
- **Parametrlar:** chegara (standart: qarz/EBITDA ≤ 1,5x, DSCR ≥ 2x)
- **Manba:** Balans, Foyda-zarar, Kontragentlar
- **Hisoblash:** Qarz/EBITDA, DSCR = EBITDA ÷ yillik qarz xizmati; sig'im = EBITDA × chegara − joriy qarz.
- **Hisobot:**
  - Xulosa: «Joriy qarz {q} mln = EBITDA × {r}. Yana ~{s} mln ko'tarsa bo'ladi (chegara 1,5x).»
  - KPI: Qarz / EBITDA | DSCR | Qarz sig'imi
  - Grafik: gauge: qarz/EBITDA
  - Jadval: stsenariy: +50/+100/+200 mln qarz → DSCR
  - Nima qilish kerak: 1) Kengayish uchun qarz variantini hisoblang → 2) Qarz/EBITDA ≤ 1,5x → 3) Yangi qarzni pul oqimi bilan tasdiqlang
- **Live:** «Qarzingiz kichik — biznes yana ikki yuz millionga yaqin qarz ko'tara oladi.»
- **Side:** «100 mln kredit olsam oyiga qancha?» → N10 · «Filial uchun yetadimi?» → N21

#### S15 · Bu modelni ko'paytirib bo'ladimi — 5 ta filialga arziydigan biznesmi?

- **Intent:** `scalability` · **Soha:** Investor
- **Variantlar:** «Tarmoq qilsa bo'ladimi?» · «Ko'p filial ochishga arziydimi?»
- **Parametrlar:** filiallar soni (standart 5)
- **Manba:** Investitsiyalar, Foyda-zarar, Tekshiruv
- **Hisoblash:** Belgilar: bitta nuqta ROIC, investitsiya qoplanishi, standartlar, tarix uzunligi, kadr bog'liqligi → tayyorlik balli.
- **Hisobot:**
  - Xulosa: «Belgilar {yaxshi}, lekin {cheklov}. Avval {shart}.»
  - KPI: Bitta nuqta ROIC | Tarix | Qoplanish tajribasi
  - Jadval: mezon | holat | shart
  - Nima qilish kerak: 1) Bitta nuqtani 6 oy barqaror ushlang → 2) Filial playbook yozing → 3) 2-filialni pilot qiling
- **Live:** «Model ko'paytirishga arziydi, lekin avval bitta nuqtani barqaror qiling va filialni pilot sifatida oching.»
- **Side:** «2-filialga tayyormanmi?» → N21 · «Franshiza bersam?» → N22

#### S16 · Tashqi auditorsiz bu hisobotlarga qanchalik ishonsam bo'ladi?

- **Intent:** `report_trust` · **Soha:** Investor
- **Variantlar:** «Raqamlar to'g'rimi?» · «Hisobotga ishonsa bo'ladimi?»
- **Parametrlar:** —
- **Manba:** Tekshiruv, Balans, Kassa
- **Hisoblash:** 27 ta avtomatik nazorat holati, balans farqi, cheklovlar (davr, norasmiy xodim, naqd ulushi).
- **Hisobot:**
  - Xulosa: «{Yuqori} darajada: {n}/27 nazorat OK, balans 0 farq. Cheklovlar: {ro'yxat}.»
  - KPI: Avtomatik nazorat | Balans farqi | Tashqi audit
  - Jadval: nazorat | natija | holat
  - Nima qilish kerak: 1) Yiliga 1 marta tashqi audit → 2) Naqdni bank orqali o'tkazing → 3) Xodimlarni rasmiylashtiring
- **Live:** «Ichki nazoratlar hammasi joyida — ishonsa bo'ladi, lekin yiliga bir marta tashqi audit qildiring.»
- **Side:** «Qaysi nazorat eng muhim?» → tushuntirish · «Naqd farqlarni tekshir» → N50

### — CFO —


#### S17 · Pulimiz qancha tez aylanadi — biznesga qancha aylanma mablag' kerak?

- **Intent:** `cash_conversion_cycle` · **Soha:** CFO
- **Variantlar:** «Pul konversiya sikli qancha?» · «Aylanma mablag' qancha kerak?»
- **Parametrlar:** —
- **Manba:** Balans, Kontragentlar, Ombor hisoboti
- **Hisoblash:** DIO (zaxira kunlari) + DSO (debitorlik, asosan agregatorlar) − DPO (kreditorlik) = sikl (kun); kerakli aylanma = sikl × kunlik xarajat.
- **Hisobot:**
  - Xulosa: «Sikl ~{x} kun — aylanma mablag' ehtiyoji {kichik}. Asosiy band qilingan pul — {qayerda}.»
  - KPI: Zaxira (kun) | Debitorlik (kun) | Sikl (kun)
  - Grafik: bar: DIO / DSO / DPO
  - Jadval: komponent | kun | so'm
  - Nima qilish kerak: 1) Debitorlik muddatini qisqartiring → 2) Zaxirani 3–4 kunda ushlang → 3) Bo'shagan pulni zaxiraga
- **Live:** «Pulingiz tez aylanadi — fast food'ning afzalligi; faqat bir qismi to'lov kutib turadi.»
- **Side:** «Yetkazib beruvchiga kech to'lasam?» → N06 · «Zaxira qancha bo'lishi kerak?» → N04

#### S18 · Keyingi 3 oyda pul uzilishi xavfi bormi — eng tang nuqta qachon?

- **Intent:** `cash_risk_3m` · **Soha:** CFO
- **Variantlar:** «Pul qachon eng kam bo'ladi?» · «3 oyda pul yetmay qoladimi?»
- **Parametrlar:** ufq (standart 90 kun)
- **Manba:** Pul oqimi, Ish haqi, Hisoblash, Kassa (takrorlanuvchi to'lovlar)
- **Hisoblash:** Kalendarli kunlik prognoz: retail tushum (hafta kuni profili) + agregator to'lovlari (8/10) − oylik (5) − ijara (3) − soliq (20) − kredit (25) − yetkazib beruvchilar (haftalik). Min nuqta va sana.
- **Hisobot:**
  - Xulosa: «Katta xavf {yo'q/bor}. Eng tang kun — {sana}: qoldiq ~{x} mln (chegara {b} mln).»
  - KPI: Eng tang nuqta | Eng past qoldiq | Xavfsiz chegara
  - Grafik: line: 90 kunlik kunlik kassa + chegara chizig'i
  - Jadval: to'lovlar kalendari (sana, nima, summa)
  - Nima qilish kerak: 1) 13 haftalik kalendar yuriting → 2) Oylikdan oldin tushumni yig'ing → 3) Katta to'lovlarni taqsimlang
- **Live:** «Uch oyda pul uzilmaydi. Eng tang kun — beshinchi dekabr, oylik kuni.»
- **Side:** «O'sha kuni 20 mln xarid qilsam?» → N01 param · «To'lovlar ro'yxatini ber» → kalendar jadvali

#### S19 · Xarajat tuzilmamiz o'sishga qanchalik moslashuvchan — zarba kelsa tez kamaytira olamizmi?

- **Intent:** `cost_flexibility` · **Soha:** CFO
- **Variantlar:** «Xarajatlarning qanchasi doimiy?» · «Inqirozda nimani tez qisqartiraman?»
- **Parametrlar:** —
- **Manba:** Foyda-zarar (oxirgi oy)
- **Hisoblash:** O'zgaruvchan (tannarx, komissiya, qadoq, bank) vs doimiy (ijara, asosiy oylik, kredit); tez kesiladigan ro'yxati va summasi.
- **Hisobot:**
  - Xulosa: «{x}% xarajat o'zgaruvchan; doimiy {y} mln/oy. Tez kesish mumkin: {ro'yxat} — {z} mln.»
  - KPI: O'zgaruvchan % | Doimiy (oyiga) | Tez kesiladigan
  - Grafik: donut: doimiy vs o'zgaruvchan
  - Jadval: modda | turi | summa | kesish tezligi
  - Nima qilish kerak: 1) Byudjetda ajrating → 2) Yangi doimiy xarajatdan oldin 2 marta o'ylang → 3) Inqiroz ro'yxatini tayyorlang
- **Live:** «Xarajatlarning uchdan biri savdo bilan birga kamayadi; zarba kelsa reklama va kunbaylarni tez qisqartirish mumkin.»
- **Side:** «Savdo 20% tushsa nima kesaman?» → S06 + ro'yxat · «Ijara oshsa?» → N35

#### S20 · 2027 byudjetini qaysi 3 ssenariyda tuzishim kerak?

- **Intent:** `budget_scenarios` · **Soha:** CFO
- **Variantlar:** «Kelasi yil rejasi» · «2027 byudjeti»
- **Parametrlar:** ssenariy parametrlari (trafik o'sishi, narx, filial)
- **Manba:** Fin reja, Foyda-zarar, Reja-fakt
- **Hisoblash:** Pessimistik (trafik 0%), bazaviy (+~8 chek), optimistik (+15 chek + filial) — oylik tushum, xarajat, foyda, kassa.
- **Hisobot:**
  - Xulosa: «Pessimistik foyda ~{a}, bazaviy ~{b}, optimistik ~{c} mln. Asosiy byudjet — bazaviy.»
  - KPI: Pessimistik | Bazaviy | Optimistik
  - Grafik: line: 12 oylik tushum (3 ssenariy)
  - Jadval: ssenariy jadvali (tushum, foyda, kassa)
  - Nima qilish kerak: 1) 3 ssenariyni Fin rejaga kiriting → 2) Bazaviyni asosiy qiling → 3) Har oy faktni solishtiring
- **Live:** «Bazaviy ssenariyda kelasi yil taxminan {b} million foyda — byudjetni shunga qurasiz.»
- **Side:** «Filialsiz optimistik?» → param · «Yil oxirigacha qancha foyda?» → N41

#### S22 · Operatsion leverejimiz qanday — o'sishda foyda tushumdan tezroq oshadimi?

- **Intent:** `operating_leverage` · **Soha:** CFO
- **Variantlar:** «Savdo oshsa foyda qancha oshadi?» · «Leverej nima va bizda qancha?»
- **Parametrlar:** —
- **Manba:** Foyda-zarar
- **Hisoblash:** Tushum va EBITDA o'sishi (yanvar → oxirgi oy), marjinal foyda % = (tushum − o'zgaruvchan xarajat) ÷ tushum; DOL = %ΔEBITDA ÷ %Δtushum.
- **Hisobot:**
  - Xulosa: «Ha: tushum +{x}% → EBITDA +{y}%. Har +10 mln tushum ~+{z} mln foyda.»
  - KPI: Tushum o'sishi | EBITDA o'sishi | Marjinal foyda
  - Grafik: line: tushum vs EBITDA (indeks)
  - Jadval: oylar: tushum, EBITDA, marja
  - Nima qilish kerak: 1) O'sishga sarmoya kiriting → 2) Pasayishga zaxira ushlang → 3) Doimiy xarajatni nazorat qiling
- **Live:** «Savdo o'n foiz oshsa, foyda undan ancha tezroq oshadi — lekin pasayishda ham tez tushadi.»
- **Side:** «Savdo 10% tushsa?» → S06 · «Marjinal foyda nima?» → tushuntirish

#### S23 · Marjani eng ko'p qaysi narsa yeb qo'yyapti va uni qayerdan himoya qilamiz?

- **Intent:** `margin_bridge` · **Soha:** CFO
- **Variantlar:** «Foydam qayerga ketyapti?» · «Eng katta xarajatim qaysi?»
- **Parametrlar:** davr
- **Manba:** Foyda-zarar
- **Hisoblash:** Marja zanjiri: yalpi marja → har xarajat guruhi % → sof marja; eng boshqariladigan va maqsaddan chetga chiqqan modda.
- **Hisobot:**
  - Xulosa: «Yalpi marja {g}% dan sof {n}% gacha eng katta yo'qotish — {modda} ({p}%).»
  - KPI: Yalpi marja | Sof marja | Eng katta xarajat
  - Grafik: waterfall: yalpi → sof marja
  - Jadval: modda | % | maqsad | holat
  - Nima qilish kerak: 1) Xodimlar unumdorligini oshiring → 2) Soliq rejimini optimal ushlang → 3) Hajmni zararsizlikdan yuqori saqlang
- **Live:** «Foydani eng ko'p xodimlar xarajati yeydi — u maqsaddan biroz yuqori.»
- **Side:** «Oylikni 10% oshirsam?» → N28 · «Food cost normami?» → S41

#### S24 · Oy yopilmasidan foyda raqamiga ishonib qaror qabul qilsam bo'ladimi?

- **Intent:** `open_month_reliability` · **Soha:** CFO
- **Variantlar:** «Noyabr foydasi nega bunchalik baland?» · «Joriy oy raqamlari to'g'rimi?»
- **Parametrlar:** —
- **Manba:** Foyda-zarar, Bosh sahifa
- **Hisoblash:** Yopilmagan oyda yo'q yozuvlar: ish haqi, foiz, inventarizatsiya, hisoblashlar; run-rate tuzatish (oxirgi oy xarajat ulushlari bilan).
- **Hisobot:**
  - Xulosa: «Yo'q: ekranda {x} mln, tuzatilgan baho ~{y} mln. Qaror uchun — {oxirgi yopilgan oy}.»
  - KPI: Ekrandagi foyda | Tuzatilgan baho | Ishonchli asos
  - Jadval: yo'q yozuv | taxminiy summa
  - Nima qilish kerak: 1) Oxirgi yopilgan oydan foydalaning → 2) Joriy oyni run-rate sifatida ko'ring → 3) Oyni o'z vaqtida yoping
- **Live:** «Joriy oy hali yopilmagan — ish haqi yozilmagan. Qarorni oktyabr raqamiga qarab qiling.»
- **Side:** «Noyabr qanday yopiladi?» → N42 · «Oy yopish tartibi?» → S31

### — Buxgalteriya —


#### S25 · Soliq strategiyamiz optimalmi — qonuniy ravishda qancha soliq tejashimiz mumkin?

- **Intent:** `tax_regime_optimal` · **Soha:** Buxgalteriya
- **Variantlar:** «Qaysi soliq rejimi foydali?» · «Soliqni qonuniy kamaytirsa bo'ladimi?»
- **Parametrlar:** rejim (aylanma / QQS 6% / umumiy)
- **Manba:** Sozlamalar, Foyda-zarar, Ish haqi
- **Hisoblash:** Har rejim bo'yicha yillik soliq: aylanma 4% × tushum; QQS 6% (soddalashtirilgan) va umumiy (12% + 15%) — kirish QQS bilan.
- **Hisobot:**
  - Xulosa: «Hozirgi {rejim} eng arzon: muqobil {+x} mln/yil qimmat. Asosiy xavf — {xavf}.»
  - KPI: Amaldagi rejim | Muqobil farq | Asosiy xavf
  - Grafik: bar: yillik soliq 3 rejimda
  - Jadval: rejim | yillik soliq | shartlar
  - Nima qilish kerak: 1) Joriy rejimda qoling → 2) Norasmiy xodimlarni bosqichma-bosqich rasmiylashtiring → 3) Yiliga soliq maslahatchisi bilan tekshiring
- **Live:** «Aylanma solig'i siz uchun eng arzon variant — boshqa rejim yiliga o'ttiz milliondan ortiq qimmat.»
- **Side:** «Rasmiylashtirsam qancha soliq?» → N30 · «Soliq kalendari» → N55

#### S26 · Agar bugun soliq tekshiruvi kelsa, qayerda muammo chiqadi?

- **Intent:** `tax_audit_readiness` · **Soha:** Buxgalteriya
- **Variantlar:** «Soliq tekshiruviga tayyormizmi?» · «Qayerda jarima xavfi bor?»
- **Parametrlar:** —
- **Manba:** Ish haqi, Kassa, Kirim, Tekshiruv
- **Hisoblash:** Kuchli tomonlar (to'langan soliq, POS savdo, nazoratlar) va zaif joylar (norasmiy xodim soni/fondi, naqd ulushi, hujjatsiz xarid) — har biriga taxminiy xavf.
- **Hisobot:**
  - Xulosa: «Model toza; zaif joylar: {ro'yxat}.»
  - KPI: To'langan soliq (yil) | Hujjatlashtirilgan savdo | Zaif joy
  - Jadval: xavf | dalil | chora
  - Nima qilish kerak: 1) Norasmiylarni rasmiylashtiring → 2) Xaridda hujjat talab qiling → 3) Naqdni bankka o'tkazing
- **Live:** «Hisobot tomoni toza; xavf — norasmiy xodimlar va naqd aylanma.»
- **Side:** «Rasmiylashtirish qancha turadi?» → N30 · «Naqd farqlar bormi?» → N50

#### S27 · Ikkinchi filial ochsak soliq yuki qanday o'zgaradi — QQS to'lovchiga aylanib qolamizmi?

- **Intent:** `tax_threshold_expansion` · **Soha:** Buxgalteriya
- **Variantlar:** «QQS chegarasiga yetamizmi?» · «Filial soliqqa qanday ta'sir qiladi?»
- **Parametrlar:** filial tushumi (standart: joriy nuqtadek)
- **Manba:** Sozlamalar (QQS chegarasi), Fin reja, Tekshiruv
- **Hisoblash:** Yillik tushum sur'ati (×12) vs chegara (4,944 mlrd); filial bilan jami; chegaradan o'tsa 6% QQS ta'siri.
- **Hisobot:**
  - Xulosa: «Sur'at ~{x} mlrd, chegara 4,944 mlrd — {zaxira}. 2 filial bilan ~{y} mlrd — {past/yuqori}.»
  - KPI: Yillik sur'at | Chegara | Filial bilan
  - Grafik: bar: sur'at vs chegara
  - Jadval: stsenariy: 1/2/3 nuqta
  - Nima qilish kerak: 1) Har filialda chegarani tekshiring → 2) 6% QQS ta'sirini oldindan hisoblang → 3) Kengayish rejasiga soliq ssenariysini qo'shing
- **Live:** «Ikki filial bilan ham QQS chegarasidan pastdasiz; uchinchi nuqtada o'tasiz.»
- **Side:** «2-filialga tayyormanmi?» → N21 · «QQS 6% ga o'tsam qancha?» → S25

#### S28 · Moliyaviy hisobotlarga ishonish uchun qaysi nazoratlar ishlashi kerak va ular ishlayaptimi?

- **Intent:** `controls_status` · **Soha:** Buxgalteriya
- **Variantlar:** «Nazoratlar ishlayaptimi?» · «Tekshiruv varag'i nima deydi?»
- **Parametrlar:** —
- **Manba:** Tekshiruv, Balans, Pul oqimi, Inventarizatsiya
- **Hisoblash:** 27 avtomatik nazorat holati + qo'lda nazoratlar (inventarizatsiya, kunlik kassa, bank yarashuvi) — oxirgi bajarilgan sana.
- **Hisobot:**
  - Xulosa: «{n}/27 nazorat OK. Qo'lda kerak: {ro'yxat}.»
  - KPI: Avtomatik nazorat | Balans farqi | Qo'lda nazorat
  - Jadval: nazorat | natija | holat
  - Nima qilish kerak: 1) Oy yopishdan oldin Tekshiruvni ko'ring → 2) Oylik inventarizatsiya, kunlik kassa → 3) Mas'ul belgilang
- **Live:** «Barcha avtomatik nazoratlar joyida; qo'lda faqat inventarizatsiya va kassa yarashuvi kerak.»
- **Side:** «Naqd farqlarini tekshir» → N50 · «Oy yopish tartibi» → S31

#### S29 · Tannarxni o'rtacha narx usulida hisoblayapmiz — bu foyda va soliqqa qanday ta'sir qiladi?

- **Intent:** `costing_method` · **Soha:** Buxgalteriya
- **Variantlar:** «Tannarx qanday hisoblanyapti?» · «FIFO yaxshiroqmi?»
- **Parametrlar:** —
- **Manba:** Zaxira, Foyda-zarar, Texkarta
- **Hisoblash:** Oylik food cost oralig'i, narx tebranishi; muqobil usul ta'siri (taxmin); aylanma solig'iga ta'sir yo'q.
- **Hisobot:**
  - Xulosa: «O'rtacha usul food cost'ni {a}–{b}% da barqaror ushlaydi; soliqqa ta'siri {yo'q}.»
  - KPI: Food cost oralig'i | Usul | Soliqqa ta'sir
  - Grafik: line: oylik food cost %
  - Nima qilish kerak: 1) Usulni izchil qo'llang → 2) Texkartani chorakda yangilang → 3) Yil o'rtasida o'zgartirmang
- **Live:** «Usul to'g'ri va barqaror — soliqqa ta'siri yo'q.»
- **Side:** «Food cost nega o'zgaradi?» → S41 · «Texkarta normalari to'g'rimi?» → S48

#### S31 · Oyni ishonchli yopish uchun qaysi tartib-intizom kerak va eng ko'p xato qayerda bo'ladi?

- **Intent:** `month_close_process` · **Soha:** Buxgalteriya
- **Variantlar:** «Oyni qanday yopaman?» · «Oy yopish checklisti»
- **Parametrlar:** oy
- **Manba:** Qo'llanma, Tekshiruv, Inventarizatsiya
- **Hisoblash:** 5 bosqich: hisoblash → ish haqi → inventarizatsiya → Tekshiruv (XATO=0) → tahlil; har bosqich uchun holat (bajarildi/yo'q) joriy oy bo'yicha.
- **Hisobot:**
  - Xulosa: «{oy} yopish: {n}/5 bosqich bajarildi. Qolgan: {ro'yxat}.»
  - KPI: Yopish bosqichlari | Avtomatik tekshiruv | Ko'p xato
  - Jadval: checklist (bosqich, mas'ul, muddat, holat)
  - Nima qilish kerak: 1) Yopish kalendari + mas'ul → 2) Jurnallarda faqat ro'yxatdan tanlang → 3) Inventarizatsiya majburiy
- **Live:** «Noyabrni yopish uchun ish haqi, inventarizatsiya va tekshiruv qoldi.»
- **Side:** «Eslatma qo'y» → Tasks: oy oxiri · «Inventarizatsiya qanday?» → tushuntirish

#### S32 · Kontragentlar bilan hisob-kitoblar to'g'ri yuritilyaptimi — adashgan to'lov yoki qarz bormi?

- **Intent:** `counterparty_hygiene` · **Soha:** Buxgalteriya
- **Variantlar:** «Adashgan to'lov bormi?» · «Kontragent saldolari to'g'rimi?»
- **Parametrlar:** sana (standart: oxirgi ma'lumot kuni)
- **Manba:** Kontragentlar, Tekshiruv, Balans
- **Hisoblash:** Ro'yxatda yo'q kontragentga to'lov, takror nomlar, nol bo'lmagan saldolar (|saldo| ≥ 1 000) turlar bo'yicha; depozit ≠ qarz.
- **Hisobot:**
  - Xulosa: «Hisob-kitob {toza}: ro'yxatsiz to'lov {0}, takror nom {0}. Ochiq saldolar: {ro'yxat}.»
  - KPI: Ro'yxatsiz to'lov | Takror nom | Ochiq saldolar
  - Jadval: kontragent | turi | saldo | izoh (depozit/kredit/debitor)
  - Nima qilish kerak: 1) Har oy saldoni ko'ring → 2) Yangi kontragentni avval ro'yxatga → 3) Debitor to'lovlarini kuzating
- **Live:** «Hisob-kitoblar toza; ochiq saldolar faqat kredit, ijara depoziti va agregator to'lovlari.»
- **Side:** «Kreditni qachon yopaman?» → N09 · «Agregator to'lovi qachon keladi?» → jadval

### — Savdo —


#### S35 · Menyumiz foyda uchun optimal tuzilganmi — qaysi taomlar bizni boqadi, qaysilari to'sqinlik qiladi?

- **Intent:** `menu_engineering` · **Soha:** Savdo
- **Variantlar:** «Qaysi taom eng foydali?» · «Menyuda nimani o'zgartiray?»
- **Parametrlar:** davr (standart: oxirgi 3 oy)
- **Manba:** Menyu tahlili, Mahsulot rentabelligi
- **Hisoblash:** Menyu muhandisligi: mashhurlik × porsiya foydasi → Yulduz/Ishchi ot/Jumboq/Past; har guruhning foyda ulushi.
- **Hisobot:**
  - Xulosa: «Yulduzlar ({ro'yxat}) foydaning ~{x}% i. Muammo — {taom} (FC {y}%).»
  - KPI: Yulduzlar ulushi | Ishchi ot muammosi | Jumboqlar
  - Grafik: scatter: mashhurlik × porsiya foydasi (4 kvadrant)
  - Jadval: taom | sinf | foyda | harakat
  - Nima qilish kerak: 1) Yulduzlarni birinchi qo'ying → 2) Past marjali tovar narxini tuzating → 3) Jumboqlarni reklama qiling
- **Live:** «Lavashlar va kombo sizni boqadi; gazli ichimlik marjasi past — narxini tuzatish kerak.»
- **Side:** «Yangi taom qo'shsam?» → N26 · «Taomni olib tashlasam?» → S46

#### S37 · Marketing byudjetimiz o'zini oqlayaptimi — qaysi xarajat sotuvga aylanyapti?

- **Intent:** `marketing_roi_past` · **Soha:** Savdo
- **Variantlar:** «Reklama ishlayaptimi?» · «Marketingga qancha sarflayapman?»
- **Parametrlar:** davr
- **Manba:** Foyda-zarar, Pul oqimi
- **Hisoblash:** Marketing (yil, % tushum); kampaniya oyi vs qo'shni oylar (boshqa omillar belgilanadi); o'lchanmasa — o'lchash usuli.
- **Hisobot:**
  - Xulosa: «Marketing {x} mln ({y}% tushum). {kampaniya} oyida tushum {+z}%, lekin {aralash omil}.»
  - KPI: Marketing (yil) | Tushumdagi ulush | O'lchanadimi
  - Grafik: bar: oylik marketing vs tushum
  - Jadval: kampaniya | xarajat | tushum farqi
  - Nima qilish kerak: 1) Har kampaniyaga promo-kod → 2) Natijani 2 haftada o'lchang → 3) Byudjet ~3% tushum
- **Live:** «Reklama byudjeti me'yorida; avgust kampaniyasi ishlagan, lekin aniq o'lchash uchun promo-kod kerak.»
- **Side:** «Aksiya qilsam arziydimi?» → N25 · «Instagram reklamasini qayta qilsam?» → param: kampaniya

#### S40 · Mijozlarimizni qaytib keltirish uchun sodiqlik dasturi kerakmi — raqamlar nima deydi?

- **Intent:** `loyalty_program` · **Soha:** Savdo
- **Variantlar:** «Sodiqlik kartasi kerakmi?» · «Doimiy mijozlarni qanday ushlayman?»
- **Parametrlar:** dastur turi (standart: 10-chi bepul)
- **Manba:** Soatlik savdo, Menyu tahlili
- **Hisoblash:** Mavjud dalil (cheklar o'sishi, o'rtacha chek); dastur xarajati = bepul taom tannarxi ÷ 10 tashrif; zararsizlik: takroriy tashrif +x%.
- **Hisobot:**
  - Xulosa: «Fayl sodiqlikni bevosita ko'rsatmaydi. Dastur {x}% xarajat; takroriy tashrif +{y}% bo'lsa o'zini oqlaydi.»
  - KPI: Kunlik cheklar trendi | O'rtacha chek | Sodiqlik ma'lumoti
  - Jadval: dastur | xarajat | zararsizlik
  - Nima qilish kerak: 1) Oddiy dasturni sinang → 2) POS orqali mijoz ma'lumoti yig'ing → 3) Takroriy tashrifni o'lchang
- **Live:** «Sodiqlik dasturini sinab ko'rishga arziydi — takroriy tashrif bir oz oshsa o'zini oqlaydi.»
- **Side:** «Qanday dastur arzon?» → variantlar · «Natijani qanday o'lchayman?» → KPI

### — Oshxona —


#### S41 · Xom ashyo narxi oshishidan qanchalik himoyalanganmiz — inflyatsiya foydamizni yeb qo'yadimi?

- **Intent:** `input_inflation` · **Soha:** Oshxona
- **Variantlar:** «Go'sht qimmatlasa nima bo'ladi?» · «Inflyatsiya foydani yeydimi?»
- **Parametrlar:** mahsulot, o'zgarish %
- **Manba:** Kirim, Foyda-zarar, Zaxira
- **Hisoblash:** Top-5 xom ashyo ulushi va oylik narx trendi; food cost trendi; har +10% → FC +x punkt → foyda −y mln.
- **Hisobot:**
  - Xulosa: «{Qisman} himoyalangan: FC {a}–{b}%. Asosiy xavf — {mahsulot} ({u}% xarid, oyiga +{t}%).»
  - KPI: Food cost | Asosiy mahsulot ulushi | +10% ta'siri
  - Grafik: line: top-5 mahsulot narxi (oyma-oy)
  - Jadval: mahsulot | ulush | trend | +10% ta'sir
  - Nima qilish kerak: 1) Uzoq muddatli narx kelishuvi → 2) Narx oshganda menyuni moslang → 3) Top-5 narxni haftalik kuzating
- **Live:** «Mol go'shti asosiy xavf — u o'n foiz qimmatlasa, food cost qariyb bir punkt oshadi.»
- **Side:** «Qaysi taom narxini oshiray?» → N24 · «Ulgurji olsam?» → N18

#### S43 · Isrof va kamomad nazoratdami — qayerda, qancha pul yo'qotyapmiz?

- **Intent:** `waste_shrinkage` · **Soha:** Oshxona
- **Variantlar:** «Isrof qancha?» · «Kamomad bormi?»
- **Parametrlar:** davr
- **Manba:** Hisobdan chiqarish, Inventarizatsiya, Foyda-zarar
- **Hisoblash:** Isrof (sabab bo'yicha), inventarizatsiya farqi (mahsulot bo'yicha), xodimlar ovqati; % tushum; top mahsulotlar.
- **Hisobot:**
  - Xulosa: «Nazoratda: isrof {x} mln ({p}%), kamomad {y} mln. Eng ko'p — {top}.»
  - KPI: Isrof (yil) | Kamomad | Xodimlar ovqati
  - Grafik: bar: sabab bo'yicha isrof
  - Jadval: mahsulot | isrof | kamomad
  - Nima qilish kerak: 1) Isrofni sabab bo'yicha yozing → 2) Ichimlik va go'shtni haftalik sanang → 3) Xodim ovqatiga norma
- **Live:** «Isrof past — tushumning yarim foizi; asosiy nazorat nuqtasi go'sht va ichimlik.»
- **Side:** «Xodimlar ovqati ko'pmi?» → N39 · «Muzlatgich isrofni kamaytirdimi?» → Investitsiyalar

#### S44 · Ta'minot uzilib qolish xavfi bormi — bitta yetkazib beruvchiga bog'liqmizmi?

- **Intent:** `supply_risk` · **Soha:** Oshxona
- **Variantlar:** «Yetkazib beruvchi to'xtasa nima bo'ladi?» · «Zaxiram necha kunga yetadi?»
- **Parametrlar:** —
- **Manba:** Kirim, Ombor hisoboti, Mahsulotlar
- **Hisoblash:** Har mahsulot: zaxira kunlari, yetkazib beruvchi soni, xarid ulushi; kritik = 1 yetkazib beruvchi + ulush > 10%.
- **Hisobot:**
  - Xulosa: «Xavf {o'rta}: zaxira ~{x} kun; kritik — {mahsulot} (1 yetkazib beruvchi, {u}%).»
  - KPI: Zaxira (kun) | Kritik mahsulot ulushi | Buyurtma signali
  - Jadval: mahsulot | zaxira kun | yetkazib beruvchilar | xavf
  - Nima qilish kerak: 1) 2-yetkazib beruvchi tayyorlang → 2) Kritik zaxirani 4–5 kun → 3) Ombor signalini kuzating
- **Live:** «Go'sht bitta yetkazib beruvchidan — zaxira uch kunlik. Ikkinchi yetkazib beruvchi tayyorlang.»
- **Side:** «Yetkazib beruvchini almashtirsam?» → N38 · «Ulgurji olsam?» → N18

#### S45 · Energiya samaradorligimiz qanday — tarif oshishiga qanchalik moslashganmiz?

- **Intent:** `energy_efficiency` · **Soha:** Oshxona
- **Variantlar:** «Svet/gaz ko'p ketyaptimi?» · «Elektr tarifi oshsa?»
- **Parametrlar:** tarif o'zgarishi %
- **Manba:** Energiya, Foyda-zarar
- **Hisoblash:** Energiya % tushum, kVt·soat/chek trendi, tarif tarixi (manba bilan); +x% tarif → oyiga −y mln.
- **Hisobot:**
  - Xulosa: «Energiya {p}% tushum; kVt·soat/chek {k}. Tarif +10% → −{y} mln/oy.»
  - KPI: Energiya ulushi | Elektr tarifi | kVt·soat/chek
  - Grafik: line: kVt·soat/chek (kunlik)
  - Jadval: oy | kVt·soat | gaz | suv | hisob
  - Nima qilish kerak: 1) Bo'sh soatlarda jihozni o'chiring → 2) kVt·soat/chek kuzating → 3) Tejamkor jihoz/lampa
- **Live:** «Energiya me'yorida; yozda konditsioner sarfni oshiradi — bo'sh soatlarda jihozlarni o'chiring.»
- **Side:** «Kechki soatlar arziydimi?» → N49 · «24 soat ishlasam?» → N31

#### S46 · Yangi taom qo'shish yoki olib tashlash qarorini qanday raqamlar bilan qilamiz?

- **Intent:** `menu_add_remove_rule` · **Soha:** Oshxona
- **Variantlar:** «Qaysi taomni olib tashlay?» · «Taom qo'shish mezoni»
- **Parametrlar:** taom
- **Manba:** Menyu tahlili, Mahsulot rentabelligi, Menyu
- **Hisoblash:** 3 mezon: hajm, porsiya foydasi, FC; qoida: FC > 45% → tuzat; mashhurlik va foyda past → olib tashla; yangi taom → N26.
- **Hisobot:**
  - Xulosa: «{taom}: hajm {h}, porsiya foydasi {f}, FC {c}% → {qaror}.»
  - KPI: Eng foydali porsiya | Muammoli | Kam sotiladigan
  - Grafik: scatter (S35 bilan bir xil)
  - Jadval: taom | hajm | foyda | FC | qaror
  - Nima qilish kerak: 1) Har taomni 3 mezon bilan baholang → 2) FC > 45% ni tuzating → 3) Har oy yangilang
- **Live:** «Gazli ichimlik ko'p sotiladi, lekin foydasi past — olib tashlamang, narxini tuzating.»
- **Side:** «Donar qo'shsam?» → N26 · «Lavash narxini oshirsam?» → N23

#### S47 · Oshxona xodimlari unumli ishlayaptimi — har bir so'm ish haqi qancha mahsulot beryapti?

- **Intent:** `kitchen_productivity` · **Soha:** Oshxona
- **Variantlar:** «Oshpazlar yetarli ishlayaptimi?» · «Unumdorlik qanday?»
- **Parametrlar:** davr
- **Manba:** Ish haqi, Soatlik savdo, Foyda-zarar
- **Hisoblash:** Oshxona ish haqi, chek/oshpaz/kun, tushum/1 so'm oshxona ish haqi, FC barqarorligi, bo'sh soatlar ulushi.
- **Hisobot:**
  - Xulosa: «{O'rtacha}: oshxona ish haqi {x} mln, har oshpazga ~{y} chek/kun; bo'sh soatlarda ortiqcha xodim.»
  - KPI: Oshxona ish haqi | Chek / oshpaz | Food cost
  - Grafik: heatmap: soatlik yuklama
  - Jadval: oshpaz | smena | yuklama
  - Nima qilish kerak: 1) Smenani soatlik yuklamaga moslang → 2) Bo'sh soatlarda tayyorlov → 3) Shoshilib yangi xodim olmang
- **Live:** «Oshxona yaxshi ishlayapti, faqat kunduzgi bo'sh soatlarda ortiqcha odam turibdi — smenani moslang.»
- **Side:** «Oylikni oshirsam?» → N28 · «Xodim qisqartirsam?» → N29

#### S48 · Qaysi jarayonni yaxshilash eng ko'p tejov beradi — xarid, isrof yoki tannarxmi?

- **Intent:** `savings_priority` · **Soha:** Oshxona
- **Variantlar:** «Qayerdan tejasam bo'ladi?» · «Eng katta tejov qayerda?»
- **Parametrlar:** —
- **Manba:** Kirim, Investitsiyalar, Texkarta
- **Hisoblash:** Har yo'nalish tejov imkoniyati (so'm/oy): xarid (ulgurji/kelishuv), isrof (hozirgi darajadan), tannarx (texkarta normasi) — tarixiy tasdiq bilan.
- **Hisobot:**
  - Xulosa: «Eng katta dastak — {xarid}: ~{x} mln/oy. Isrof allaqachon past ({p}%).»
  - KPI: Xarid tejov imkoni | Isrof | Tarixiy tasdiq
  - Grafik: bar: yo'nalishlar bo'yicha tejov
  - Jadval: yo'nalish | imkoniyat | qiyinlik
  - Nima qilish kerak: 1) Asosiy mahsulotni ulgurji/kelishilgan narxda → 2) Texkartani chorakda tekshiring → 3) Isrofni past ushlang
- **Live:** «Eng ko'p tejov xariddan — go'shtni ulgurji va kelishilgan narxda oling.»
- **Side:** «Ulgurji olsam pul qancha band?» → N18 · «Yetkazib beruvchini almashtirsam?» → N38

### — Kassa —


#### N01 · Bugun qancha pulni bemalol sarflay olaman?

- **Intent:** `safe_to_spend` · **Soha:** Kassa
- **Variantlar:** «Hozir qancha pul ishlatsam bo'ladi?» · «Bo'sh pulim qancha?» · «Majburiy to'lovlarga zarar qilmasdan qancha sarflayman?»
- **Parametrlar:** sana (bugun), ufq (standart: keyingi oylik kunigacha)
- **Manba:** Kassa qoldig'i, kunlik prognoz, Ish haqi, Hisoblash, Kontragentlar (kredit)
- **Hisoblash:** Bemalol summa = min(kunlik prognozdagi qoldiq, ufq ichida) − xavfsiz chegara (7 kunlik qat'iy chiqim). Eng tang kun ko'rsatiladi.
- **Hisobot:**
  - Xulosa: «Bugun {x} mln gacha bemalol sarflay olasiz. Undan ortig'i {sana}da kassani chegaradan pastga tushiradi.»
  - KPI: Bemalol summa | Eng tang kun | Xavfsiz chegara
  - Grafik: line: kunlik kassa (bugun → ufq) + chegara + 'sarflansa' chizig'i
  - Jadval: kelgusi majburiy to'lovlar (sana, nima, summa)
  - Nima qilish kerak: 1) {x} mln gacha — bemalol → 2) Kattaroq xarid → {sana} dan keyin → 3) Yoki bo'lib to'lash (N12)
- **Live:** «Bugun {x} milliongacha bemalol sarflay olasiz; undan ko'pi beshinchi dekabrdagi oylikka xavf soladi.»
- **Side:** «30 mln sarflasam-chi?» → param: summa → chegara testi · «Qachon ko'proq bo'ladi?» → N47

#### N02 · Oylikni (ish haqini) vaqtida to'lay olamanmi?

- **Intent:** `payroll_coverage` · **Soha:** Kassa
- **Variantlar:** «Dekabr oyligiga pul yetadimi?» · «Ish haqi kuni kassa qanday bo'ladi?»
- **Parametrlar:** oylik sanasi (standart: keyingi 5-sana)
- **Manba:** Ish haqi (oxirgi oy netto), kunlik prognoz
- **Hisoblash:** Oylik summasi (oxirgi oy netto + kutilayotgan o'zgarishlar); oylik kunidagi kassa (oldin/keyin); yetmasa — farq va choralar.
- **Hisobot:**
  - Xulosa: «Ha, yetadi: {sana}da kassa {a} mln, oylik {o} mln, keyin {b} mln qoladi (chegara {c}).»
  - KPI: Oylik summasi | Kassa (oylikdan keyin) | Zaxira
  - Grafik: line: kassa oylik kuni atrofida (±7 kun)
  - Jadval: xodim | netto | holat
  - Nima qilish kerak: 1) Oylikdan 3 kun oldin katta xarid qilmang → 2) Agregator to'lovini kuting (8–10) → 3) Avans tizimi (N34)
- **Live:** «Oylikka pul yetadi — beshinchi dekabrda to'lagandan keyin ham qirq milliondan ortiq qoladi.»
- **Side:** «Oylikni 10% oshirsam ham yetadimi?» → N28 · «Avans bersam?» → N34

#### N03 · Kredit to'lovim kuni kassada yetarli pul bo'ladimi?

- **Intent:** `loan_payment_coverage` · **Soha:** Kassa
- **Variantlar:** «25-sanadagi kredit to'loviga pul bormi?» · «Kredit to'lovini o'tkazib yubormaymanmi?»
- **Parametrlar:** to'lov sanasi
- **Manba:** Kontragentlar (Bank krediti), Kassa (Kredit foizi, qaytarildi), prognoz
- **Hisoblash:** To'lov = asosiy qarz + foiz (qoldiq × 24%/12); to'lov kunidagi kassa; keyingi 3 to'lov jadvali.
- **Hisobot:**
  - Xulosa: «Ha: {sana}da to'lov {t} mln (asosiy {a} + foiz {f}), kassa {k} mln.»
  - KPI: Keyingi to'lov | Kassa o'sha kuni | Qolgan qarz
  - Grafik: bar: keyingi 6 oylik to'lovlar
  - Jadval: to'lov jadvali (sana, asosiy, foiz, qoldiq)
  - Nima qilish kerak: 1) To'lov kuni oldidan katta xarajat qilmang → 2) Avtomatik to'lov qo'ying → 3) Oldindan yopishni ko'ring (N08)
- **Live:** «Kredit to'loviga pul yetadi — yigirma beshinchi sanada yetti million atrofida to'laysiz.»
- **Side:** «Oldin yopsam?» → N08 · «Qachon tugaydi?» → N09

#### N04 · Kassa zaxiram (rezerv) qancha bo'lishi kerak?

- **Intent:** `cash_reserve_target` · **Soha:** Kassa
- **Variantlar:** «Qancha pulni tegmay ushlashim kerak?» · «Xavfsiz chegara qancha?»
- **Parametrlar:** zaxira darajasi (7 kun / 1 oy)
- **Manba:** Foyda-zarar (doimiy xarajatlar), Pul oqimi
- **Hisoblash:** Minimal = 7 kunlik qat'iy chiqim; tavsiya = 1 oylik doimiy xarajat (+ eng katta oylik to'lov); hozirgi kassa bilan solishtirish.
- **Hisobot:**
  - Xulosa: «Minimal {a} mln, tavsiya {b} mln. Hozir {k} mln — {yetarli/kam}.»
  - KPI: Minimal zaxira | Tavsiya zaxira | Hozirgi kassa
  - Grafik: bar: minimal / tavsiya / hozir
  - Jadval: doimiy xarajat moddalari
  - Nima qilish kerak: 1) Zaxirani alohida hisobga → 2) Oyiga {x} mln dan to'ldiring → 3) Zaxiraga faqat favqulodda tegining
- **Live:** «Kamida o'n yetti million, yaxshisi oltmish olti million tegmay turishi kerak.»
- **Side:** «Zaxirani qanday to'ldiraman?» → N14 bilan · «Overdraft ochsam?» → N15

#### N05 · Bir oy savdo bo'lmasa (yopilib qolsam) qancha chidayman?

- **Intent:** `shutdown_runway` · **Soha:** Kassa
- **Variantlar:** «Remont uchun 2 hafta yopsam?» · «Savdo to'xtasa pul necha kunga yetadi?»
- **Parametrlar:** yopilish muddati (kun)
- **Manba:** Kassa, doimiy xarajatlar, debitorlik
- **Hisoblash:** Runway = (kassa + kutilayotgan tushumlar) ÷ kunlik doimiy chiqim; yopilish muddati bo'yicha kassa yo'li.
- **Hisobot:**
  - Xulosa: «Savdosiz {d} kun chidaysiz. {n} kun yopilsangiz, kassa {k} mln gacha tushadi.»
  - KPI: Runway (kun) | Kunlik doimiy chiqim | Yopilish oxirida kassa
  - Grafik: line: kassa yopilish davrida
  - Jadval: qaysi to'lovlarni kechiktirsa bo'ladi
  - Nima qilish kerak: 1) Yopilishni oylikdan keyin rejalang → 2) Yetkazib beruvchilar bilan kelishing → 3) Zaxirani oldindan to'plang
- **Live:** «Savdo to'xtasa, pulingiz taxminan {d} kunga yetadi.»
- **Side:** «Remontni qachon qilay?» → N17 + N47 · «Zaxira qancha kerak?» → N04

#### N06 · Yetkazib beruvchiga to'lovni 2 hafta kechiktirsam kassaga qanday ta'sir qiladi?

- **Intent:** `supplier_terms_whatif` · **Soha:** Kassa
- **Variantlar:** «To'lov muddatini uzaytirsam?» · «Yetkazib beruvchidan muddat so'rasam?»
- **Parametrlar:** kechiktirish (kun), yetkazib beruvchi
- **Manba:** Kirim, Kassa (Yetkazib beruvchiga to'lov), Kontragentlar
- **Hisoblash:** Bir martalik kassa bo'shashi = haftalik xarid × hafta; eng tang kunga ta'siri; xavf (narx/munosabat).
- **Hisobot:**
  - Xulosa: «Kassa bir martalik ~{x} mln ga bo'shaydi; eng tang kun {a} → {b} mln.»
  - KPI: Bo'shaydigan pul | Eng tang kun (oldin/keyin) | Xavf
  - Grafik: line: kassa oldin vs keyin
  - Jadval: yetkazib beruvchi | haftalik xarid | yangi muddat
  - Nima qilish kerak: 1) Faqat go'sht/ulgurji bilan kelishing → 2) Kechikish evaziga narx oshmasin → 3) Yozma kelishuv
- **Live:** «Ikki hafta muddat kassangizga bir martalik yigirma millionga yaqin havo beradi.»
- **Side:** «Qaysi yetkazib beruvchi bilan?» → jadval · «Aylanma sikl?» → S17

#### N07 · Past mavsum (yanvar–fevral) uchun pulni qanday rejalashtiray?

- **Intent:** `seasonal_cash_plan` · **Soha:** Kassa
- **Variantlar:** «Qishda savdo tushsa nima qilaman?» · «Fevral qiyin oymi?»
- **Parametrlar:** oylar
- **Manba:** Fin reja (mavsumiylik), Foyda-zarar (o'tgan yil), prognoz
- **Hisoblash:** Mavsum koeffitsientlari (Fin reja) × trend → oylik tushum/foyda; past oylarda kassa yo'li; oldindan yig'ish summasi.
- **Hisobot:**
  - Xulosa: «{oy} eng past: tushum ~{x}% kam, foyda ~{y} mln. Oldindan {z} mln yig'ib qo'ying.»
  - KPI: Eng past oy | Foyda o'sha oyda | Oldindan yig'ish
  - Grafik: bar: oylik tushum (mavsum bilan)
  - Jadval: oy | koeffitsient | tushum | foyda
  - Nima qilish kerak: 1) Dekabrda yig'ing → 2) Past oyda reklama/kombo → 3) Katta xaridlarni yuqori mavsumga
- **Live:** «Fevral eng past oy; dekabrdan o'n millionga yaqin yig'ib qo'ysangiz, bemalol o'tasiz.»
- **Side:** «Fevralda reklama qilsam?» → N25 · «Qaysi oyda xarid qilay?» → N47

### — Moliyalashtirish —


#### N08 · Kreditni muddatidan oldin yopsam qancha tejayman?

- **Intent:** `loan_prepay` · **Soha:** Moliyalashtirish
- **Variantlar:** «Kreditni hozir yopsam-chi?» · «50 mln bilan qarzni qisqartirsam?»
- **Parametrlar:** summa (standart: to'liq), sana
- **Manba:** Kontragentlar (Bank krediti 110 mln, 24%), Kassa
- **Hisoblash:** Tejov = qolgan foizlar (jadval bo'yicha) − yangi jadval foizlari; kassa testi (chegara); muqobil daromad (ROIC) bilan solishtirish.
- **Hisobot:**
  - Xulosa: «{s} mln oldin yopsangiz ~{t} mln foiz tejaysiz; lekin kassa {k} mln ga tushadi.»
  - KPI: Foiz tejovi | Kassa keyin | Muqobil ROIC
  - Grafik: bar: qolgan foiz (hozirgi vs yangi)
  - Jadval: to'lov jadvali oldin/keyin
  - Nima qilish kerak: 1) Avval zaxira → 2) Qisman yopish (har oy qo'shimcha) → 3) ROIC > 24% loyiha bo'lsa — loyiha
- **Live:** «Kreditni oldin yopish foizdan tejaydi, lekin avval zaxirani to'ldiring.»
- **Side:** «Qisman yopsam?» → param · «Kredit qachon tugaydi?» → N09

#### N09 · Joriy grafik bo'yicha kreditni qachon to'liq yopaman?

- **Intent:** `loan_payoff_timeline` · **Soha:** Moliyalashtirish
- **Variantlar:** «Qarzim qachon tugaydi?» · «Kredit qoldig'i qancha?»
- **Parametrlar:** —
- **Manba:** Kontragentlar, Kassa (to'lovlar), Fin reja (kredit shartlari)
- **Hisoblash:** Qoldiq ÷ oylik asosiy to'lov → oxirgi oy; qolgan jami foiz; qo'shimcha to'lov bilan muddat.
- **Hisobot:**
  - Xulosa: «Qoldiq {q} mln; {sana}da yopiladi, yana {f} mln foiz to'laysiz.»
  - KPI: Qoldiq | Yopilish sanasi | Qolgan foiz
  - Grafik: line: qarz qoldig'i (oyma-oy)
  - Jadval: jadval (oy, asosiy, foiz, qoldiq)
  - Nima qilish kerak: 1) Grafik bo'yicha to'lang → 2) Oyiga +x mln qo'shsangiz {n} oy erta → 3) Kechikmang (jarima)
- **Live:** «Kreditingiz {sana}da tugaydi; har oy qo'shimcha besh million bersangiz, ancha erta.»
- **Side:** «Oyiga 10 mln to'lasam?» → param · «Oldin yopsam?» → N08

#### N10 · X mln kredit olsam oyiga qancha to'layman va ko'tara olamanmi?

- **Intent:** `loan_whatif` · **Soha:** Moliyalashtirish
- **Variantlar:** «100 mln kredit olsam?» · «Yangi kredit to'lovi qancha bo'ladi?»
- **Parametrlar:** summa, stavka (standart 24%), muddat (12/24/36)
- **Manba:** Foyda-zarar (EBITDA), Kontragentlar, prognoz
- **Hisoblash:** Annuitet to'lov; DSCR; eng tang kunga ta'siri; kreditga nima olinadi (bo'lmasa — so'ra).
- **Hisobot:**
  - Xulosa: «{s} mln, {m} oy, 24%: oyiga {p} mln. DSCR {d}x — {ko'tara olasiz/xavfli}.»
  - KPI: Oylik to'lov | Jami ortiqcha | DSCR
  - Grafik: bar: muddat bo'yicha to'lov (12/24/36)
  - Jadval: jadval
  - Nima qilish kerak: 1) Kredit maqsadini aniqlang → 2) DSCR ≥ 2x → 3) Eng arzon taklif (web_lookup)
- **Live:** «Yuz million kreditga oyiga to'qqiz millionga yaqin to'laysiz — biznes ko'taradi.»
- **Side:** «Qaysi bank arzon?» → web_lookup jadval · «Lizing arzonmi?» → N11

#### N11 · Kredit, lizing yoki muddatli to'lov — qaysi biri arzon?

- **Intent:** `financing_compare` · **Soha:** Moliyalashtirish
- **Variantlar:** «Bo'lib to'lash yaxshimi yoki kredit?» · «Lizing nima beradi?»
- **Parametrlar:** summa, muddat, takliflar (bo'lmasa — standart stavkalar)
- **Manba:** Kontragentlar, prognoz, web_lookup
- **Hisoblash:** Har variant: boshlang'ich to'lov, oylik, jami ortiqcha, effektiv yillik stavka, kassaga ta'sir.
- **Hisobot:**
  - Xulosa: «Eng arzon — {variant}: jami ortiqcha {x} mln, effektiv {r}%.»
  - KPI: Eng arzon | Ortiqcha to'lov | Effektiv stavka
  - Grafik: bar: jami ortiqcha to'lov
  - Jadval: variant | boshlang'ich | oylik | muddat | ortiqcha | stavka
  - Nima qilish kerak: 1) Effektiv stavkani solishtiring → 2) Kassa chegarasini tekshiring → 3) Shartlarni yozma oling
- **Live:** «Bu summaga eng arzoni {variant} — ortiqcha to'lov eng kam.»
- **Side:** «Muddatli to'lov ustamasi aslida necha foiz?» → N12 · «Kredit to'lovi?» → N10

#### N12 · Muddatli to'lov (bo'lib to'lash) ustamasi haqiqatda necha foiz?

- **Intent:** `installment_true_rate` · **Soha:** Moliyalashtirish
- **Variantlar:** «0% bo'lib to'lash rostdan 0%mi?» · «Do'kon ustamasi qancha?»
- **Parametrlar:** narx (naqd), narx (bo'lib), muddat, boshlang'ich
- **Manba:** — (foydalanuvchi kiritadi)
- **Hisoblash:** Effektiv yillik stavka (IRR) = to'lovlar oqimi bo'yicha; kredit 24% bilan solishtirish.
- **Hisobot:**
  - Xulosa: «Haqiqiy stavka ~{r}% yillik — kredit (24%) dan {arzon/qimmat}.»
  - KPI: Effektiv stavka | Ortiqcha to'lov | Kredit bilan farq
  - Jadval: oy | to'lov | qoldiq
  - Nima qilish kerak: 1) Naqd chegirmani so'rang → 2) Stavkani solishtiring → 3) Muddatni qisqa tanlang
- **Live:** «Bu bo'lib to'lash aslida yillik {r} foiz — kreditdan {arzon/qimmat}.»
- **Side:** «Naqd olsam chegirma?» → hisob · «Qaysi biri arzon?» → N11

#### N13 · Depozitga pul qo'ysam yoki biznesda aylantirsam — qaysi biri foydali?

- **Intent:** `deposit_vs_business` · **Soha:** Moliyalashtirish
- **Variantlar:** «Bo'sh pulni bankka qo'yaymi?» · «Depozit foizi biznesdan yaxshimi?»
- **Parametrlar:** summa, depozit stavkasi (web_lookup)
- **Manba:** S09 ROIC, kassa, zaxira
- **Hisoblash:** Depozit daromadi (soliq bilan) vs biznes ROIC vs kredit yopish (24%); zaxira talabi.
- **Hisobot:**
  - Xulosa: «{x} mln: depozit ~{d} mln/yil, kreditni yopish {k} mln/yil tejaydi, biznes loyihasi ~{b}. Eng yaxshi — {variant}.»
  - KPI: Depozit daromadi | Kredit tejovi | Biznes ROIC
  - Grafik: bar: 3 variant yillik daromadi
  - Nima qilish kerak: 1) Zaxirani depozitda ushlang → 2) Ortiqchasini kreditga → 3) Loyiha ROIC > 24% bo'lsa — loyihaga
- **Live:** «Bo'sh pulni depozitga qo'ygandan ko'ra, kredit qarzini yopish ko'proq foyda beradi.»
- **Side:** «Qaysi bank depoziti yaxshi?» → web_lookup · «Zaxira qancha?» → N04

#### N14 · Har oy o'zimga qancha pul olsam biznesga zarar qilmaydi?

- **Intent:** `owner_withdrawal` · **Soha:** Moliyalashtirish
- **Variantlar:** «Oyiga qancha dividend olaman?» · «Egasiga qancha pul olsa bo'ladi?»
- **Parametrlar:** sheriklar ulushi (Sozlamalar)
- **Manba:** Foyda-zarar, Pul oqimi, Sozlamalar (sheriklar), zaxira
- **Hisoblash:** Bo'sh pul oqimi (operatsion − kredit asosiy − kapital rejasi) − zaxira to'ldirish; sheriklar ulushiga bo'lish.
- **Hisobot:**
  - Xulosa: «Oyiga {x} mln gacha olish xavfsiz (Sherik 1 — {a}, Sherik 2 — {b}).»
  - KPI: Xavfsiz summa | Bo'sh pul oqimi | Zaxira holati
  - Grafik: bar: bo'sh pul oqimi taqsimoti
  - Jadval: sherik | ulush | summa
  - Nima qilish kerak: 1) Avval zaxira → 2) Har oy bir xil sanada → 3) Kapital loyiha oylarida kamaytiring
- **Live:** «Oyiga {x} milliongacha olsangiz biznesga zarar qilmaydi.»
- **Side:** «Sherik bilan qanday bo'lamiz?» → N59 · «Kredit yopilsa ko'proq?» → N09

#### N15 · Overdraft yoki kredit liniya ochib qo'ysam arziydimi?

- **Intent:** `overdraft_line` · **Soha:** Moliyalashtirish
- **Variantlar:** «Zaxira kredit liniyasi kerakmi?» · «Overdraft nima beradi?»
- **Parametrlar:** limit, stavka
- **Manba:** Prognoz (tang kunlar), web_lookup (shartlar)
- **Hisoblash:** Tang kunlardagi yetishmovchilik × kunlar × stavka; komissiya; zaxira bilan solishtirish.
- **Hisobot:**
  - Xulosa: «Yiliga ~{d} kun kerak bo'ladi, xarajati ~{x} mln; {arziydi/arzimaydi}.»
  - KPI: Kerakli kunlar | Yillik xarajat | Muqobil (zaxira)
  - Grafik: line: kassa + overdraft limiti
  - Nima qilish kerak: 1) Limitni eng tang kun ehtiyojiga → 2) Faqat favqulodda → 3) Zaxira bilan birga
- **Live:** «Overdraft faqat bir necha kunda kerak bo'ladi — kichik limit yetarli.»
- **Side:** «Qaysi bankda?» → web_lookup · «Zaxira yetarlimi?» → N04

### — Kapital —


#### N16 · Qo'limda 50 mln bor — qayerga tiksam to'g'ri bo'ladi?

- **Intent:** `capital_allocation` · **Soha:** Kapital
- **Variantlar:** «Bo'sh pulni qayerga ishlataman?» · «50 mln: zaxira, kredit, reklama yoki boshqa?»
- **Parametrlar:** summa, variantlar (bo'lmasa: zaxira, kredit, marketing, ulgurji xarid, depozit)
- **Manba:** N04, N08, N13, N18, S13
- **Hisoblash:** Har variant: yillik daromad (so'm va %), xavf, likvidlik; tartib S13 qoidasi bo'yicha. Jihoz variantini tanlasa → Q3 ga yo'naltir.
- **Hisobot:**
  - Xulosa: «{s} mln: {a} mln zaxiraga, {b} mln kreditga, {c} mln {loyiha}ga — yillik ~{d} mln foyda.»
  - KPI: Eng yuqori daromad | Taqsimot | Yillik natija
  - Grafik: stacked bar: taqsimot
  - Jadval: variant | daromad % | xavf | tavsiya summa
  - Nima qilish kerak: 1) Avval zaxira → 2) Keyin 24% dan qimmat qarz → 3) Qolgani — eng yuqori ROIC
- **Live:** «Ellik millionni bunday bo'ling: zaxira, kredit va eng foydali loyiha.»
- **Side:** «Hammasini kreditga bersam?» → N08 · «Apparatga bersam?» → → Q3 (taqdimot savoli)

#### N17 · Zal ta'miriga (remont) X mln sarflasam o'zini oqlaydimi?

- **Intent:** `renovation_roi` · **Soha:** Kapital
- **Variantlar:** «Remont qilsam savdo oshadimi?» · «Interyerni yangilash arziydimi?»
- **Parametrlar:** summa, yopilish kunlari
- **Manba:** Foyda-zarar (Zal kanali), Soatlik savdo, N05
- **Hisoblash:** Xarajat + yopilish davridagi yo'qotish; foyda: zal savdosi +x% (taxmin, standart 5–8%) × marja; qoplash; eng yaxshi oy.
- **Hisobot:**
  - Xulosa: «{s} mln + yopilish {d} kun ({l} mln yo'qotish); zal +{p}% bo'lsa {m} oyda qoplaydi.»
  - KPI: Jami xarajat | Oylik qo'shimcha foyda | Qoplash
  - Grafik: line: yig'ma natija
  - Jadval: taxminlar (o'zgartirish mumkin)
  - Nima qilish kerak: 1) Past mavsumda qiling → 2) Yopilmasdan bosqichma-bosqich → 3) Natijani 2 oyda o'lchang
- **Live:** «Remont zal savdosini besh foizga oshirsa, taxminan {m} oyda o'zini oqlaydi.»
- **Side:** «Qachon qilay?» → N47 · «Yopilsam qancha chidayman?» → N05

#### N18 · Xom ashyoni ulgurji (oylik) olsam qancha tejayman va pul qancha band bo'ladi?

- **Intent:** `bulk_purchase` · **Soha:** Kapital
- **Variantlar:** «Go'shtni ko'p olsam arzonroqmi?» · «Ulgurji xarid foydalimi?»
- **Parametrlar:** mahsulot, muddat (oy), chegirma %
- **Manba:** Kirim (hajm, narx), Mahsulotlar, muzlatgich tajribasi (Investitsiyalar)
- **Hisoblash:** Tejov = oylik hajm × narx × chegirma; band pul = qo'shimcha zaxira qiymati; saqlash (muzlatgich) va isrof xavfi; kassa testi.
- **Hisobot:**
  - Xulosa: «{mahsulot}ni {m} oylik olsangiz oyiga ~{t} mln tejaysiz, {b} mln pul band bo'ladi.»
  - KPI: Oylik tejov | Band pul | Qoplash (kun)
  - Jadval: mahsulot | hajm | chegirma | tejov | saqlash
  - Nima qilish kerak: 1) Faqat saqlanadigan mahsulot → 2) Muzlatgich sig'imini tekshiring → 3) Oylikdan keyin xarid qiling
- **Live:** «Go'shtni ulgurji olsangiz oyiga bir millionga yaqin tejaysiz.»
- **Side:** «Qaysi mahsulot?» → jadval · «Pul yetadimi?» → N01

#### N19 · Sherigimning ulushini sotib olsam qancha turadi va arziydimi?

- **Intent:** `partner_buyout` · **Soha:** Kapital
- **Variantlar:** «Sherikni chiqarsam?» · «40% ulush narxi?»
- **Parametrlar:** ulush % (Sozlamalar), baho usuli
- **Manba:** Sozlamalar (sheriklar), S12 baho, Pul oqimi
- **Hisoblash:** Ulush narxi = baho × ulush (diapazon); moliyalash (kassa/kredit/bo'lib); qoplash = ulush foydasi.
- **Hisobot:**
  - Xulosa: «{p}% ulush ~{a}–{b} mln; u ulushning foydasi yiliga ~{f} mln → {n} yilda qoplaydi.»
  - KPI: Ulush narxi | Yillik ulush foydasi | Qoplash
  - Jadval: moliyalash variantlari
  - Nima qilish kerak: 1) Baho usulini kelishing → 2) Bosqichma-bosqich to'lov → 3) Huquqiy rasmiylashtirish
- **Live:** «Sherigingiz ulushi taxminan {a} dan {b} milliongacha — {n} yilda qoplaydi.»
- **Side:** «Kreditga olsam?» → N10 · «Biznes bahosi?» → S12

#### N20 · Korporativ buyurtmalar (ofislarga tushlik) yo'nalishini ochsam arziydimi?

- **Intent:** `corporate_catering` · **Soha:** Kapital
- **Variantlar:** «Ofislarga ovqat yetkazsam?» · «Korporativ mijozlar foydalimi?»
- **Parametrlar:** kunlik porsiya, narx, to'lov muddati
- **Manba:** Soatlik savdo (12–14 yuklama), Menyu, Ish haqi
- **Hisoblash:** Qo'shimcha foyda = porsiya × (narx − tannarx − qadoq − yetkazish); quvvat (tushlik piki); to'lov kechikishi (debitorlik).
- **Hisobot:**
  - Xulosa: «Kuniga {n} porsiya → oyiga +{f} mln foyda; tushlik pikida quvvat {yetadi/yetmaydi}.»
  - KPI: Oylik foyda | Quvvat | Debitorlik
  - Jadval: stsenariy: 20/50/100 porsiya
  - Nima qilish kerak: 1) Bitta ofis bilan pilot → 2) Oldindan to'lov → 3) Tushlik pikidan oldin tayyorlov
- **Live:** «Kuniga ellik porsiya korporativ buyurtma oyiga {f} million foyda beradi.»
- **Side:** «Narx qancha qo'yay?» → param · «Kuryer yetadimi?» → → Q1 (taqdimot savoli)

#### N21 · Ikkinchi filial ochishga tayyormanmi?

- **Intent:** `branch_readiness` · **Soha:** Kapital
- **Variantlar:** «2-filial qachon ochsam bo'ladi?» · «Filial ochishga pulim yetadimi?»
- **Parametrlar:** investitsiya (standart: ochilish CAPEX + aylanma), moliyalash
- **Manba:** Fin reja (CAPEX), Investitsiyalar, S14, N04
- **Hisoblash:** Tayyorlik sharti (3 oy foyda ≥ x, zaxira, egaga bog'liqlik), moliyalash (o'z + kredit), filial P&L (ramp-up) va qoplash.
- **Hisobot:**
  - Xulosa: «Hozir {tayyor emas/tayyor}: shart {shart}. Ochish ~{s} mln, qoplash ~{m} oy.»
  - KPI: Investitsiya | Qoplash | Tayyorlik
  - Grafik: line: filial yig'ma natija (ramp-up)
  - Jadval: shart | hozir | kerak
  - Nima qilish kerak: 1) Shartlarga yeting → 2) Joy va moliyalashni tayyorlang → 3) Pilot rejasi
- **Live:** «Ikkinchi filialga hali erta — avval uch oy barqaror foyda va zaxira kerak.»
- **Side:** «Kreditga ochsam?» → N10/S14 · «Soliq o'zgaradimi?» → S27

#### N22 · Franshiza bersam (brendimni boshqalarga sotsam) qancha daromad olaman?

- **Intent:** `franchise_out` · **Soha:** Kapital
- **Variantlar:** «Franshiza sotsam bo'ladimi?» · «Royalti qancha bo'ladi?»
- **Parametrlar:** paushal, royalti %, franshiza soni
- **Manba:** Foyda-zarar (bir nuqta modeli), Tekshiruv/Texkarta (standartlar)
- **Hisoblash:** Daromad = paushal + royalti × franchayzi tushumi; xarajat (qo'llab-quvvatlash); tayyorlik (standartlar, brend).
- **Hisobot:**
  - Xulosa: «Bitta franshiza yiliga ~{x} mln; tayyorlik: {holat}.»
  - KPI: Yillik daromad (1 ta) | Tayyorlik | Xavf
  - Jadval: model: paushal, royalti, soni
  - Nima qilish kerak: 1) Avval playbook → 2) Brendni ro'yxatdan o'tkazing → 3) 1 ta pilot franchayzi
- **Live:** «Bitta franshiza yiliga taxminan {x} million beradi, lekin avval standartlarni hujjatlashtiring.»
- **Side:** «Biznes bahosi?» → S12 · «5 filialga arziydimi?» → S15

### — Narx —


#### N23 · Bitta taom narxini X so'mga oshirsam foydam qancha o'zgaradi?

- **Intent:** `single_item_price` · **Soha:** Narx
- **Variantlar:** «Lavash mol go'shtli narxini 2 000 ga oshirsam?» · «Shaurmani qimmatlashtirsam?»
- **Parametrlar:** taom, yangi narx yoki +so'm, elastiklik (S07 dan)
- **Manba:** Menyu, Sotuv (hajm), S07
- **Hisoblash:** Yangi hajm = hajm × (1 + elastiklik × Δnarx%); foyda = yangi hajm × (yangi narx − tannarx) − eski; substitutsiya (boshqa taomga o'tish) taxmini.
- **Hisobot:**
  - Xulosa: «{taom} {a} → {b}: oyiga {+x} mln foyda, sotuv ~{−y}%.»
  - KPI: Oylik foyda o'zgarishi | Sotuv o'zgarishi | Yangi FC
  - Grafik: bar: narx variantlari (+1/+2/+3 ming)
  - Jadval: variant | hajm | foyda
  - Nima qilish kerak: 1) Avval bitta taomda sinang → 2) 4 hafta kuzating → 3) Kanallar bo'yicha bir xil narx (agregatorni hisobga oling)
- **Live:** «Lavash narxini ikki ming so'mga oshirsangiz, oyiga {x} million ko'proq foyda qoladi.»
- **Side:** «3 000 bo'lsa?» → param · «Narx kuchi?» → S07

#### N24 · Go'sht narxi 15% oshsa, qaysi taom narxini qanchaga oshirishim kerak?

- **Intent:** `cost_pass_through` · **Soha:** Narx
- **Variantlar:** «Xom ashyo qimmatladi, narxni qancha oshiray?» · «Food cost'ni ushlab qolish uchun narx?»
- **Parametrlar:** mahsulot, o'zgarish %
- **Manba:** Texkarta, Menyu, Kirim
- **Hisoblash:** Har taom tannarxi yangi narx bilan; FC ni joriy darajada ushlash uchun kerakli narx = yangi tannarx ÷ FC; yaxlitlash (500/1000).
- **Hisobot:**
  - Xulosa: «Go'sht +15% → {n} taomga ta'sir; FC'ni ushlash uchun {taom} +{x} so'm.»
  - KPI: Ta'sir qilgan taomlar | Oylik zarar (narx o'zgarmasa) | O'rtacha narx o'sishi
  - Jadval: taom | yangi tannarx | kerakli narx | o'zgarish
  - Nima qilish kerak: 1) Faqat ta'sir qilganlarni o'zgartiring → 2) Yaxlit narxlar → 3) Yetkazib beruvchi bilan narx kelishuvi
- **Live:** «Go'sht o'n besh foiz qimmatlasa, lavashlarga bir-ikki ming so'm qo'shish kerak bo'ladi.»
- **Side:** «Narxni oshirmasam qancha yo'qotaman?» → hisob · «Ulgurji olsam?» → N18

#### N25 · Chegirma aksiyasi (masalan, −20% hafta oxiri) o'zini oqlaydimi?

- **Intent:** `discount_promo_roi` · **Soha:** Narx
- **Variantlar:** «Aksiya qilsam foyda bo'ladimi?» · «2+1 aksiya arziydimi?»
- **Parametrlar:** chegirma %, kunlar, taomlar, kutilgan o'sish
- **Manba:** Menyu (marja), Soatlik savdo (yuklama), Sotuv
- **Hisoblash:** Zararsizlik: kerakli hajm o'sishi = chegirma ÷ (marja − chegirma); quvvat (pik kunda chegirma — xato); kannibalizatsiya.
- **Hisobot:**
  - Xulosa: «−{d}% uchun hajm kamida +{z}% oshishi kerak; {kun}da quvvat {yetadi/yo'q} → {tavsiya}.»
  - KPI: Zararsizlik o'sishi | Kutilgan natija | Quvvat
  - Jadval: stsenariy: hajm +10/+25/+50%
  - Nima qilish kerak: 1) Bo'sh soat/kunlarga qo'ying → 2) Chegirma o'rniga bonus taom → 3) Promo-kod bilan o'lchang
- **Live:** «Yigirma foiz chegirma uchun savdo kamida {z} foiz oshishi kerak — buni faqat bo'sh kunlarga qo'ying.»
- **Side:** «Hafta boshida qilsam?» → param kunlar · «Marketing ishlayaptimi?» → S37

#### N26 · Yangi taom (masalan, donar) X so'mga qo'shsam oyiga qancha foyda beradi?

- **Intent:** `new_item_whatif` · **Soha:** Narx
- **Variantlar:** «Menyuga yangi taom qo'shsam?» · «Burrito qo'shsam arziydimi?»
- **Parametrlar:** taom, narx, retsept (bo'lmasa — o'xshash taomdan), kutilgan sotuv
- **Manba:** Texkarta (o'xshash), Kirim narxlari, Menyu tahlili
- **Hisoblash:** Tannarx (retsept × narxlar), porsiya foydasi, sotuv taxmini (o'xshash taom × 50–80%), kannibalizatsiya, uskuna kerakmi.
- **Hisobot:**
  - Xulosa: «{taom} {narx}: porsiya foydasi {p}; oyiga ~{n} porsiya → +{f} mln (kannibalizatsiyadan keyin).»
  - KPI: Porsiya foydasi | Oylik foyda | Food cost
  - Jadval: stsenariy: past/bazaviy/yuqori sotuv
  - Nima qilish kerak: 1) 1 oy sinov → 2) Kassada taklif → 3) Mezon: 30 kunda ≥ n porsiya
- **Live:** «Donar qo'shsangiz, oyiga taxminan {f} million qo'shimcha foyda beradi.»
- **Side:** «Narxini qancha qo'yay?» → FC 30% bo'yicha · «Qaysi taomni olib tashlay?» → S46

#### N27 · Lavashdagi go'shtni 10 g kamaytirsam foyda qancha oshadi va xavfi nima?

- **Intent:** `portion_size_change` · **Soha:** Narx
- **Variantlar:** «Porsiyani kichraytirsam?» · «Retseptni o'zgartirsam qancha tejayman?»
- **Parametrlar:** taom, ingredient, o'zgarish (g)
- **Manba:** Texkarta, Kirim, Sotuv
- **Hisoblash:** Tejov = Δg × narx/kg × oylik hajm; FC o'zgarishi; xavf: sifat → sotuv −x% (zararsizlik).
- **Hisobot:**
  - Xulosa: «−10 g → oyiga +{x} mln; agar sotuv {z}% dan ko'p kamaysa — zarar.»
  - KPI: Oylik tejov | Yangi FC | Xavf chegarasi
  - Jadval: taom | eski/yangi norma | tejov
  - Nima qilish kerak: 1) Kichik o'zgarish → 2) Sifatni sinang → 3) Narx oshirish bilan solishtiring
- **Live:** «O'n gramm kamaytirish oyiga {x} million beradi, lekin mijoz sezsa — zarar.»
- **Side:** «Narxni oshirsam yaxshiroqmi?» → N23 · «Texkarta normasi to'g'rimi?» → S48

### — Xodimlar —


#### N28 · Xodimlarga oylikni 10% (yoki X%) oshirsam foyda qanchaga kamayadi?

- **Intent:** `salary_raise` · **Soha:** Xodimlar
- **Variantlar:** «Oshpazlar oyligini 3 barobar oshirsam?» · «Hammaga +500 ming qo'shsam?»
- **Parametrlar:** kimga, % yoki summa
- **Manba:** Ish haqi (oklad, rasmiy), Foyda-zarar, kassa
- **Hisoblash:** Qo'shimcha xarajat = Δbrutto + ijtimoiy soliq (rasmiy); sof foyda va labor % ta'siri; kassa runway (zarar bo'lsa); alternativa (KPI bonus).
- **Hisobot:**
  - Xulosa: «+{p}% → oyiga +{x} mln xarajat; sof foyda {a} → {b} mln; labor {c}%.»
  - KPI: Qo'shimcha xarajat | Yangi sof foyda | Labor %
  - Grafik: bar: foyda oldin/keyin
  - Jadval: xodim | eski | yangi | farq
  - Nima qilish kerak: 1) Ko'tarish o'rniga KPI bonus → 2) Kalit xodimlarga ustuvorlik → 3) Narx/hajm bilan qoplang
- **Live:** «Hammaga o'n foiz oshirsangiz, oyiga uch yarim million ketadi — foyda o'n to'rt millionga tushadi.»
- **Side:** «Faqat bosh oshpazga?» → param · «KPI bonus qanday?» → tushuntirish

#### N29 · Bitta xodimni ishdan bo'shatsam qancha tejayman va xavfi nima?

- **Intent:** `staff_cut` · **Soha:** Xodimlar
- **Variantlar:** «Xodim qisqartirsam?» · «Kuryerdan voz kechsam?»
- **Parametrlar:** lavozim
- **Manba:** Ish haqi, yuklama (Soatlik savdo / kuryer), Q2 yuklama jadvali
- **Hisoblash:** Tejov = brutto + soliq + ovqat; ta'sir: yuklama qolganlarga (%), xizmat sekinlashishi → yo'qotilgan savdo taxmini.
- **Hisobot:**
  - Xulosa: «{lavozim}: oyiga {x} mln tejov; qolganlar yuklamasi {a}% → {b}%; xavf {past/yuqori}.»
  - KPI: Oylik tejov | Yangi yuklama | Xavf
  - Grafik: progress: bo'lim yuklamasi oldin/keyin
  - Nima qilish kerak: 1) Avval smenani optimallang → 2) Bo'sh soatlarga qisqartiring → 3) Pikda xizmat sifatini kuzating
- **Live:** «Bu xodimsiz oyiga {x} million tejaysiz, lekin pik soatlarda navbat xavfi bor.»
- **Side:** «Yarim stavkaga o'tkazsam?» → param · «Oylikni oshirsam-chi?» → N28

#### N30 · Norasmiy xodimlarni rasmiylashtirsam qancha qo'shimcha soliq to'layman?

- **Intent:** `formalize_staff_tax` · **Soha:** Xodimlar
- **Variantlar:** «Hammani rasmiy qilsam?» · «Ijtimoiy soliq qancha bo'ladi?»
- **Parametrlar:** xodimlar (standart: barcha norasmiy)
- **Manba:** Ish haqi (Rasmiy=Yo'q), Sozlamalar (JShDS 12%, ijtimoiy 12%)
- **Hisoblash:** Ijtimoiy soliq 12% × brutto (ish beruvchi); JShDS 12% (xodimdan — netto saqlash uchun brutto oshirilsa xarajat); jami oylik/yillik; foyda ta'siri.
- **Hisobot:**
  - Xulosa: «{n} xodim: oyiga +{x} mln (ijtimoiy), netto saqlansa +{y} mln. Yillik {z} mln.»
  - KPI: Oylik qo'shimcha | Yillik | Foydaga ta'sir
  - Jadval: xodim | brutto | ijtimoiy | JShDS
  - Nima qilish kerak: 1) Bosqichma-bosqich → 2) Kalit xodimlardan boshlang → 3) Narx/hajm bilan qoplang
- **Live:** «Hamma norasmiylarni rasmiy qilsangiz oyiga taxminan {x} million qo'shimcha soliq.»
- **Side:** «Soliq tekshiruvi xavfi?» → S26 · «Soliq rejimi?» → S25

#### N31 · 24 soat ishlasam arziydimi?

- **Intent:** `extend_hours_24h` · **Soha:** Xodimlar
- **Variantlar:** «Tungi smena ochsam?» · «Ish vaqtini uzaytirsam?»
- **Parametrlar:** yangi soatlar, smena xodimlari
- **Manba:** Soatlik savdo (22–24 trendi), Ish haqi, Energiya
- **Hisoblash:** Tungi tushum taxmini (oxirgi soat sur'ati × pasayish koeffitsienti) × marja − tungi xodimlar − energiya − xavfsizlik.
- **Hisobot:**
  - Xulosa: «Tungi soatlar ~{t} mln tushum, {c} mln xarajat → {+/−}{x} mln/oy.»
  - KPI: Tungi tushum | Tungi xarajat | Natija
  - Grafik: bar: soatlik tushum (+ tungi taxmin)
  - Jadval: soat | tushum | xarajat
  - Nima qilish kerak: 1) Avval dam olish kunlari kechasi sinang → 2) Faqat dostavka rejimida → 3) 2 hafta o'lchang
- **Live:** «Yigirma to'rt soat hozircha zarar beradi; avval juma-shanba tunlarida sinab ko'ring.»
- **Side:** «Faqat dostavka tunda?» → param · «Kechki 22–24 foydalimi?» → N49

#### N32 · Haftada bir kun (masalan, dushanba) yopsam nima bo'ladi?

- **Intent:** `close_one_day` · **Soha:** Xodimlar
- **Variantlar:** «Dushanba dam olsam?» · «Bir kun yopilsa qancha yo'qotaman?»
- **Parametrlar:** kun
- **Manba:** Smena (hafta kuni tushumi), Ish haqi, Energiya
- **Hisoblash:** Yo'qotish = o'sha kun yalpi foydasi × (1 − boshqa kunga o'tish %); tejov = energiya + kunbay + smena; natija.
- **Hisobot:**
  - Xulosa: «{kun} yopilsa: −{a} mln yalpi foyda, +{b} mln tejov → {x} mln/oy.»
  - KPI: Yo'qotilgan foyda | Tejov | Natija
  - Grafik: bar: hafta kunlari tushumi
  - Nima qilish kerak: 1) Yopmang — bo'sh kunni aksiya bilan to'ldiring → 2) Yoki qisqa ish vaqti → 3) Xodimlarga navbatli dam
- **Live:** «Dushanbani yopsangiz oyiga {x} million yo'qotasiz — yopmasdan, ish vaqtini qisqartiring.»
- **Side:** «Ish vaqtini qisqartirsam?» → param · «Bo'sh kunlarni to'ldirish?» → N25

#### N33 · Bosh oshpaz ketib qolsa qancha zarar ko'raman?

- **Intent:** `staff_turnover_cost` · **Soha:** Xodimlar
- **Variantlar:** «Kalit xodim ketsa?» · «Xodim almashishi qancha turadi?»
- **Parametrlar:** lavozim
- **Manba:** Ish haqi, Foyda-zarar, S11
- **Hisoblash:** Bevosita: yollash + o'qitish (1–2 oylik oylik); bilvosita: sifat/sur'at pasayishi → savdo −x% × n oy (taxmin).
- **Hisobot:**
  - Xulosa: «{lavozim} ketsa ~{x} mln (yollash {a} + yo'qotilgan savdo {b}).»
  - KPI: Jami zarar | Yollash xarajati | Tiklanish muddati
  - Jadval: komponent | summa | taxmin
  - Nima qilish kerak: 1) O'rinbosar tayyorlang → 2) Ushlab qolish bonusi (zararning 10–20%) → 3) Retseptlar hujjatda
- **Live:** «Bosh oshpaz ketsa, taxminan {x} million zarar — ushlab qolish bonusi arzonroq.»
- **Side:** «Bonus bersam qancha?» → N28 param · «Egaga bog'liqlik?» → S11

#### N34 · Ish haqini oyda 2 marta (avans bilan) to'lasam kassaga ta'siri qanday?

- **Intent:** `payroll_split` · **Soha:** Xodimlar
- **Variantlar:** «Avans bersam?» · «Oylikni ikkiga bo'lsam?»
- **Parametrlar:** avans % va sana (standart 40%, 20-sana)
- **Manba:** Ish haqi, prognoz
- **Hisoblash:** Kassa yo'li: bitta katta 5-sana vs 20-sana avans + 5-sana qoldiq; eng tang kun o'zgarishi.
- **Hisobot:**
  - Xulosa: «Avans {p}% 20-sanada: eng tang kun {a} → {b} mln; jami summa o'zgarmaydi.»
  - KPI: Eng tang kun (oldin/keyin) | Avans summasi | Xodimlar uchun
  - Grafik: line: kassa (2 variant)
  - Nima qilish kerak: 1) 20-sanadagi soliq bilan to'qnashuvni tekshiring → 2) Avansni tushum yuqori kunga → 3) Xodimlarga oldindan ayting
- **Live:** «Avans tizimi beshinchi sanadagi bosimni kamaytiradi — kassa tekisroq bo'ladi.»
- **Side:** «Qaysi sanada?» → param · «Oylikka yetadimi?» → N02

### — Xarajat —


#### N35 · Ijara 20% oshsa nima qilaman?

- **Intent:** `rent_increase` · **Soha:** Xarajat
- **Variantlar:** «Ijarachi narxni oshirsa?» · «Ijara qimmatlasa foyda qancha?»
- **Parametrlar:** % yoki summa
- **Manba:** Hisoblash (Ijara), Foyda-zarar
- **Hisoblash:** Ijara % tushum (maqsad ≤ 10%); yangi foyda; kompensatsiya uchun kerakli tushum/narx; muzokara dalillari (bozor — web_lookup).
- **Hisobot:**
  - Xulosa: «+{p}% → oyiga −{x} mln; ijara {a}% → {b}% tushum. Qoplash: {chora}.»
  - KPI: Oylik ta'sir | Ijara % tushum | Kerakli kompensatsiya
  - Jadval: variant: qabul / muzokara / ko'chish
  - Nima qilish kerak: 1) Uzoq muddatli shartnoma evaziga muzokara → 2) Bozor narxini keltiring → 3) Qoplash — narx/hajm
- **Live:** «Ijara yigirma foiz oshsa, oyiga ikki million ketadi — uzoq shartnoma evaziga kamroqqa kelishing.»
- **Side:** «Bozor ijarasi qancha?» → web_lookup · «Ko'chsam?» → N17/N05

#### N36 · Qadoqlash xarajatim to'g'ri darajadami?

- **Intent:** `packaging_cost` · **Soha:** Xarajat
- **Variantlar:** «Paket/konteynerga ko'p ketyaptimi?» · «Qadoq xarajati normal mi?»
- **Parametrlar:** —
- **Manba:** Kassa (Qadoqlash materiallari), Sotuv (zaldan tashqari tushum)
- **Hisoblash:** Qadoq % zaldan tashqari tushum, trend; buyurtma boshiga so'm; bozor normasi (2–3%).
- **Hisobot:**
  - Xulosa: «Qadoq {p}% (zaldan tashqari) — {normal/yuqori}; buyurtmaga ~{s} so'm.»
  - KPI: Qadoq % | Buyurtmaga | Trend
  - Grafik: line: oylik qadoq %
  - Nima qilish kerak: 1) Ulgurji qadoq → 2) Standart o'lcham → 3) Agregator qadoq to'lovini tekshiring
- **Live:** «Qadoq xarajati me'yorida — tushumning ikki foiz atrofida.»
- **Side:** «Qayerdan arzon olaman?» → N40 · «Isrof?» → S43

#### N37 · Bank va terminal komissiyalarini qanday kamaytiraman?

- **Intent:** `payment_fees` · **Soha:** Xarajat
- **Variantlar:** «Ekvayring ko'p olyaptimi?» · «Click/Payme komissiyasi?»
- **Parametrlar:** —
- **Manba:** Kassa (Bank komissiyasi), Smena (to'lov turlari)
- **Hisoblash:** Komissiya % karta tushumi; to'lov turlari ulushi; tarif muzokarasi/boshqa bank (web_lookup) tejovi.
- **Hisobot:**
  - Xulosa: «Komissiya {x} mln/oy ({p}%). Tarifni {q}% ga tushirish {t} mln/yil tejaydi.»
  - KPI: Oylik komissiya | % karta tushumi | Tejov imkoni
  - Grafik: donut: to'lov turlari
  - Nima qilish kerak: 1) Bank bilan hajm bo'yicha muzokara → 2) Takliflarni solishtiring → 3) QR-to'lov ulushini oshiring
- **Live:** «Bank komissiyasi oyiga bir millionga yaqin — tarifni kelishib, yiliga bir necha million tejaysiz.»
- **Side:** «Qaysi bank arzon?» → web_lookup · «Naqd ko'proq olsam?» → S26 xavfi

#### N38 · Yetkazib beruvchini almashtirsam qancha tejayman?

- **Intent:** `supplier_switch` · **Soha:** Xarajat
- **Variantlar:** «Boshqa go'sht yetkazib beruvchi arzonmi?» · «Arzonroq ta'minotchi topsam?»
- **Parametrlar:** mahsulot, yangi narx
- **Manba:** Kirim (narx, hajm), Kontragentlar
- **Hisoblash:** Tejov = (eski − yangi narx) × oylik hajm; xavflar (sifat, ishonchlilik, to'lov shartlari); sinov rejasi.
- **Hisobot:**
  - Xulosa: «{mahsulot}: {a} → {b} so'm/kg → oyiga {t} mln tejov.»
  - KPI: Oylik tejov | Yillik | Xavf
  - Jadval: yetkazib beruvchi | narx | shart | sifat
  - Nima qilish kerak: 1) Avval 2 hafta parallel sinov → 2) Sifatni texkarta bilan tekshiring → 3) Eski bilan muzokara
- **Live:** «Go'shtni kilosiga besh ming arzonga olsangiz, oyiga yarim million tejaysiz.»
- **Side:** «Ta'minot xavfi?» → S44 · «Ulgurji?» → N18

#### N39 · Xodimlar ovqati xarajati qancha va normalmi?

- **Intent:** `staff_meals_cost` · **Soha:** Xarajat
- **Variantlar:** «Xodimlar qancha ovqat yeyapti?» · «Personal ovqatiga norma kerakmi?»
- **Parametrlar:** —
- **Manba:** Hisobdan chiqarish (Xodimlar ovqati), Ish haqi
- **Hisoblash:** Oylik summa, xodim boshiga, % tushum; norma (kuniga 1 porsiya) bilan solishtirish.
- **Hisobot:**
  - Xulosa: «Oyiga {x} mln, xodim boshiga {y}; normaga nisbatan {farq}.»
  - KPI: Oylik | Xodim boshiga | % tushum
  - Grafik: line: oylik
  - Nima qilish kerak: 1) Kuniga 1 porsiya normasi → 2) Hisobdan chiqarishga yozish → 3) Arzon taomdan
- **Live:** «Xodimlar ovqati me'yorida — oyiga bir million atrofida.»
- **Side:** «Isrof qancha?» → S43 · «Bonus o'rniga ovqat?» → tushuntirish

#### N40 · Yetkazib beruvchilardan chegirma olish uchun qancha hajm kerak?

- **Intent:** `supplier_volume_discount` · **Soha:** Xarajat
- **Variantlar:** «Ko'p olsam chegirma beradimi?» · «Hajm bo'yicha muzokara»
- **Parametrlar:** yetkazib beruvchi, chegirma %
- **Manba:** Kirim (yillik hajm), Kontragentlar
- **Hisoblash:** Har yetkazib beruvchi yillik hajmi; 2–5% chegirma tejovi; muzokara dalili (hajm, to'lov intizomi).
- **Hisobot:**
  - Xulosa: «{supplier}: yillik {v} mln — 3% chegirma {t} mln/yil.»
  - KPI: Eng katta yetkazib beruvchi | Yillik hajm | Tejov (3%)
  - Grafik: bar: yetkazib beruvchilar hajmi
  - Jadval: yetkazib beruvchi | hajm | 2/3/5% tejov
  - Nima qilish kerak: 1) Eng kattasidan boshlang → 2) Tez to'lov evaziga chegirma → 3) Yillik shartnoma
- **Live:** «Go'sht yetkazib beruvchingiz bilan uch foiz chegirma yiliga bir necha million tejaydi.»
- **Side:** «Ulgurji olsam?» → N18 · «Almashtirsam?» → N38

### — Prognoz —


#### N41 · Yil oxirigacha (dekabr) qancha foyda qilaman?

- **Intent:** `year_end_forecast` · **Soha:** Prognoz
- **Variantlar:** «2026 yil yakuni qanday bo'ladi?» · «Yillik foyda qancha?»
- **Parametrlar:** —
- **Manba:** Foyda-zarar (yil boshidan), prognoz (noyabr–dekabr), Fin reja (mavsum)
- **Hisoblash:** Yil boshidan fakt + noyabr (run-rate, yopilmagan yozuvlar bilan) + dekabr (mavsum × trend); diapazon.
- **Hisobot:**
  - Xulosa: «2026: tushum ~{t} mlrd, sof foyda ~{f} mln ({a}–{b}).»
  - KPI: Yillik tushum | Yillik sof foyda | Dekabr prognozi
  - Grafik: bar: oylik foyda (fakt + prognoz)
  - Jadval: oy | tushum | foyda | turi (fakt/prognoz)
  - Nima qilish kerak: 1) Dekabr bayramlariga tayyorlaning → 2) Noyabrni to'g'ri yoping → 3) Yil yakuniy hisobotini rejalashtiring
- **Live:** «Yil oxirida sof foyda taxminan {f} million bo'ladi.»
- **Side:** «Dekabrda qancha?» → N42 · «Dividend olsam?» → N14

#### N42 · Keyingi oy tushum va foyda qancha bo'ladi?

- **Intent:** `next_month_forecast` · **Soha:** Prognoz
- **Variantlar:** «Dekabr savdosi qanday bo'ladi?» · «Keyingi oy prognozi»
- **Parametrlar:** oy
- **Manba:** Smena (trend, hafta kuni), Fin reja (mavsum), Foyda-zarar (xarajat ulushlari)
- **Hisoblash:** Kunlik prognoz (trend × hafta kuni × mavsum × bayramlar) → tushum; xarajatlar (o'zgaruvchan % + doimiy) → foyda; backtest aniqligi.
- **Hisobot:**
  - Xulosa: «{oy}: tushum ~{t} mln ({a}–{b}), foyda ~{f} mln. Aniqlik: o'tgan oylarda ±{e}%.»
  - KPI: Tushum prognozi | Foyda prognozi | Aniqlik
  - Grafik: line: kunlik tushum prognozi (oraliq bilan)
  - Jadval: hafta | tushum | farq
  - Nima qilish kerak: 1) Kunlik maqsadni belgilang (N48) → 2) Bayram kunlariga tayyorlaning → 3) Haftalik solishtiring
- **Live:** «Dekabrda tushum taxminan {t} million, foyda {f} million bo'ladi.»
- **Side:** «Nega bunday?» → omillar · «Kunlik maqsad?» → N48

#### N43 · Zararsizlik nuqtam qancha — kuniga nechta chek kerak?

- **Intent:** `break_even` · **Soha:** Prognoz
- **Variantlar:** «Zarar qilmaslik uchun qancha sotishim kerak?» · «Minimal savdo?»
- **Parametrlar:** —
- **Manba:** Foyda-zarar (doimiy va o'zgaruvchan), Smena (o'rtacha chek)
- **Hisoblash:** Zararsizlik tushumi = doimiy xarajat ÷ marjinal foyda %; cheklar/kun = ÷ o'rtacha chek ÷ kunlar; xavfsizlik zaxirasi = (joriy − zararsizlik) ÷ joriy.
- **Hisobot:**
  - Xulosa: «Zararsizlik: oyiga {t} mln = kuniga {c} chek. Hozir {h} — {z}% yuqori.»
  - KPI: Zararsizlik (chek/kun) | Hozir | Xavfsizlik zaxirasi
  - Grafik: line: kunlik cheklar + zararsizlik chizig'i
  - Nima qilish kerak: 1) Kunlik cheklarni kuzating → 2) Doimiy xarajatni oshirmang → 3) Pul oqimi zararsizligini ham ko'ring
- **Live:** «Kuniga {c} ta chek zararsizlik; hozir {h} ta — xavfsiz.»
- **Side:** «Ijara oshsa?» → N35 · «30 mln foyda uchun?» → N44

#### N44 · Oyiga X mln sof foyda uchun kuniga nechta chek kerak?

- **Intent:** `target_profit_reverse` · **Soha:** Prognoz
- **Variantlar:** «30 mln foyda qilish uchun qancha sotish kerak?» · «Maqsadli foydaga qanday yetaman?»
- **Parametrlar:** maqsad foyda
- **Manba:** Foyda-zarar, Smena
- **Hisoblash:** Kerakli tushum = (doimiy + maqsad) ÷ marjinal %; chek/kun; hozirgidan farq; quvvat bilan tekshiruv.
- **Hisobot:**
  - Xulosa: «{f} mln foyda uchun kuniga {c} chek (hozir {h}, +{d}). Quvvat: {yetadi/yo'q}.»
  - KPI: Kerakli cheklar/kun | Hozir | Farq
  - Jadval: maqsad: 20/30/40 mln → chek/kun
  - Nima qilish kerak: 1) Kunlik maqsadni qo'ying → 2) Bo'sh soatlarni to'ldiring → 3) Quvvat chegarasini kuzating
- **Live:** «Oyiga o'ttiz million foyda uchun kuniga yana {d} ta chek kerak.»
- **Side:** «Kunlik tushum maqsadi?» → N48 · «Quvvat yetadimi?» → → Q3/Q2 yuklama

#### N45 · Bayramlar (Yangi yil, Navro'z) uchun qancha ko'proq zaxira va xodim kerak?

- **Intent:** `holiday_stock_plan` · **Soha:** Prognoz
- **Variantlar:** «31-dekabrga qancha mahsulot olay?» · «Navro'zda qancha savdo bo'ladi?»
- **Parametrlar:** bayram, sana
- **Manba:** Smena (o'tgan bayram kunlari koeffitsienti), Kirim, Ish haqi
- **Hisoblash:** O'tgan bayram koeffitsienti × bazaviy kun → savdo; mahsulot ehtiyoji (texkarta) − zaxira = xarid; qo'shimcha smena.
- **Hisobot:**
  - Xulosa: «{bayram}: savdo ~{k}x (o'tgan {sana}), tushum ~{t} mln. Xarid: {ro'yxat}; +{n} kunbay.»
  - KPI: Kutilgan savdo | Qo'shimcha xarid | Qo'shimcha xodim
  - Grafik: bar: bayram vs oddiy kun
  - Jadval: mahsulot | kerak | bor | xarid
  - Nima qilish kerak: 1) Xaridni 2 kun oldin → 2) Qo'shimcha smena → 3) Kombo bilan tezlashtiring
- **Live:** «Navro'zda savdo odatdagidan o'ttiz besh foiz ko'p bo'ladi — go'sht va lavashni oldindan oling.»
- **Side:** «Pul yetadimi?» → N01 · «Navbat bo'lmasligi uchun?» → tayyorlov

#### N46 · Shu sur'atda o'ssak 1 yildan keyin biznes qanday bo'ladi?

- **Intent:** `one_year_projection` · **Soha:** Prognoz
- **Variantlar:** «Kelasi yil shu vaqtda qayerda bo'lamiz?» · «1 yillik prognoz»
- **Parametrlar:** o'sish (standart: oxirgi 9 oy)
- **Manba:** Foyda-zarar, Smena, Fin reja
- **Hisoblash:** Trend × mavsum → 12 oylik tushum/foyda/kassa; quvvat chegarasiga yetish sanasi (Q3 bilan muvofiq).
- **Hisobot:**
  - Xulosa: «1 yilda: tushum ~{t} mln/oy, foyda ~{f} mln/oy, kassa ~{k} mln. Quvvat ~{sana}da to'ladi.»
  - KPI: Tushum (12 oy keyin) | Foyda | Quvvat sanasi
  - Grafik: line: 12 oylik tushum + foyda
  - Jadval: oy | tushum | foyda | kassa
  - Nima qilish kerak: 1) Quvvat sanasiga tayyorlaning → 2) Zaxirani oshiring → 3) Filial shartlarini kuzating
- **Live:** «Shu sur'atda bir yildan keyin oyiga {t} million tushum — mayda oshxona quvvati to'ladi.»
- **Side:** «Byudjet ssenariylari?» → S20 · «Quvvat to'lsa?» → → Q3 (taqdimot savoli)

#### N47 · Katta xaridni qaysi oyga rejalashtirsam yaxshi?

- **Intent:** `best_month_big_spend` · **Soha:** Prognoz
- **Variantlar:** «Qachon pul ko'p bo'ladi?» · «Katta xarajat uchun eng yaxshi vaqt?»
- **Parametrlar:** summa
- **Manba:** Prognoz (oylik kassa), Fin reja (mavsum)
- **Hisoblash:** Har oy: eng tang kun − summa ≥ chegara; mavsum (yuqori oydan oldin); eng yaxshi oy va sana.
- **Hisobot:**
  - Xulosa: «{s} mln uchun eng yaxshi vaqt — {oy} {sana} (agregator to'lovidan keyin).»
  - KPI: Eng yaxshi oy | O'sha oyda min kassa | Xavfli oylar
  - Grafik: bar: oylik min kassa − summa
  - Jadval: oy | min kassa | holat
  - Nima qilish kerak: 1) Agregator to'lovidan (8–10) keyin → 2) Oylik kunidan uzoq → 3) Past mavsum oldidan emas
- **Live:** «Bu xaridni eng yaxshisi {oy} o'rtasida qiling.»
- **Side:** «Bugun qancha bemalol?» → N01 · «Bo'lib olsam?» → N11

#### N48 · Kunlik tushum maqsadim qancha bo'lishi kerak?

- **Intent:** `daily_target` · **Soha:** Prognoz
- **Variantlar:** «Har kuni qancha sotishim kerak?» · «Bugungi reja qancha?»
- **Parametrlar:** oylik maqsad (standart: oxirgi oy +trend)
- **Manba:** Smena (hafta kuni profili), N42
- **Hisoblash:** Oylik maqsad × hafta kuni ulushi → har kun uchun reja; bugungi fakt vs reja (real time).
- **Hisobot:**
  - Xulosa: «Bugun ({kun}) maqsad {t} mln; hozirgacha {f} mln ({p}%).»
  - KPI: Bugungi maqsad | Hozirgacha | Bajarilish
  - Grafik: bar: hafta kunlari maqsadi
  - Jadval: kun | maqsad | fakt
  - Nima qilish kerak: 1) Kechki pikda kombo taklif → 2) Bo'sh soatlarda aksiya → 3) Kun oxirida solishtiring
- **Live:** «Bugun shanba — maqsad {t} million; hozircha {p} foiz bajarildi.»
- **Side:** «Oylik maqsad qancha?» → N42 · «Nega bugun past?» → N51

#### N49 · Kechki 22:00–24:00 soatlarda ishlash foydalimi?

- **Intent:** `late_hours_profit` · **Soha:** Prognoz
- **Variantlar:** «Kechqurun ochiq turish arziydimi?» · «Soat 22 dan keyin yopsam?»
- **Parametrlar:** soatlar
- **Manba:** Soatlik savdo, Ish haqi (kechki smena), Energiya
- **Hisoblash:** Soatlik tushum × marja − soatlik xodim xarajati − energiya; hafta kunlari bo'yicha.
- **Hisobot:**
  - Xulosa: «22–24: oyiga {t} mln tushum, {x} mln foyda; {kunlar}da zarar.»
  - KPI: Kechki foyda | Zarar kunlari | Energiya
  - Grafik: heatmap: soat × kun foydasi
  - Jadval: kun | 22–23 | 23–24
  - Nima qilish kerak: 1) Zarar kunlari ertaroq yoping → 2) Kechki kombo → 3) Faqat dostavka rejimi
- **Live:** «Kechki soatlar juma-shanba foydali, hafta boshida esa ertaroq yopish yaxshi.»
- **Side:** «24 soat?» → N31 · «Dushanba yopsam?» → N32

### — Nazorat —


#### N50 · Kassir naqd pulni to'g'ri topshiryaptimi — naqd farqlarini tekshir.

- **Intent:** `cash_discrepancy` · **Soha:** Nazorat
- **Variantlar:** «Kassada kamomad bormi?» · «Naqd pul farqi?»
- **Parametrlar:** davr
- **Manba:** Smena (Naqd POS vs Kassadagi haqiqiy naqd), Kassa (inkassatsiya)
- **Hisoblash:** Har smena: haqiqiy − POS naqd; jami, eng katta, kassir bo'yicha; L bo'sh bo'lsa — inkassatsiya vs POS naqd solishtirish.
- **Hisobot:**
  - Xulosa: «{davr}: naqd farq {x} so'm ({n} kun). {holat}.»
  - KPI: Jami farq | Farqli kunlar | Eng katta
  - Grafik: bar: kunlik farq
  - Jadval: sana | POS | haqiqiy | farq
  - Nima qilish kerak: 1) Har kuni haqiqiy naqdni yozing → 2) Kassir almashinuvida sanash → 3) Farq > 50 000 — tekshiruv
- **Live:** «Naqd farqlar yo'q; lekin haqiqiy naqdni har kuni yozib boring.»
- **Side:** «Terminal tushumi bankka to'liq tushyaptimi?» → N54 · «Nazoratlar?» → S28

#### N51 · Qaysi kunlar savdo g'ayrioddiy past bo'ldi va nega?

- **Intent:** `anomaly_days` · **Soha:** Nazorat
- **Variantlar:** «Nega kecha savdo kam bo'ldi?» · «G'alati kunlar bormi?»
- **Parametrlar:** davr
- **Manba:** Smena (kunlik), Soatlik savdo, izohlar, bayram kalendari
- **Hisoblash:** Kutilgan (trend × hafta kuni) vs fakt; |z| > 2 kunlar; sabab: izoh, bayram, ob-havo (web), soatlik profil.
- **Hisobot:**
  - Xulosa: «{n} ta g'ayrioddiy kun: {sana} ({−x}%) — {sabab}.»
  - KPI: G'ayrioddiy kunlar | Eng katta og'ish | Yo'qotilgan tushum
  - Grafik: line: fakt vs kutilgan + belgilar
  - Jadval: sana | kutilgan | fakt | sabab
  - Nima qilish kerak: 1) Sababi noma'lumlarni tekshiring → 2) Izohga yozib boring → 3) Takrorlansa — chora
- **Live:** «O'tgan oy ikki kun savdo kutilganidan past bo'ldi — sababi bayram oldi.»
- **Side:** «Kecha nega past?» → bitta kun tahlili · «Bugungi maqsad?» → N48

#### N52 · Qaysi mahsulot narxi keskin oshdi?

- **Intent:** `supplier_price_spike` · **Soha:** Nazorat
- **Variantlar:** «Xom ashyo narxlari qanday o'zgardi?» · «Qaysi narx oshgan?»
- **Parametrlar:** davr (standart: oxirgi 30 kun vs oldingi 90)
- **Manba:** Kirim (birlik narxi)
- **Hisoblash:** Har mahsulot: so'nggi narx vs o'rtacha; > +7% belgilash; foyda ta'siri (hajm × farq).
- **Hisobot:**
  - Xulosa: «{n} mahsulot keskin oshdi: {mahsulot} +{p}% (oyiga −{x} mln).»
  - KPI: Oshgan mahsulotlar | Eng katta o'sish | Oylik ta'sir
  - Grafik: line: top mahsulot narxlari
  - Jadval: mahsulot | eski | yangi | % | ta'sir
  - Nima qilish kerak: 1) Yetkazib beruvchi bilan gaplashing → 2) Muqobil taklif so'rang → 3) Kerak bo'lsa narxni moslang (N24)
- **Live:** «Pomidor narxi o'n besh foiz oshdi — mavsumiy; go'sht barqaror.»
- **Side:** «Narxni moslasam?» → N24 · «Almashtirsam?» → N38

#### N53 · Bu hafta qanday o'tdi?

- **Intent:** `weekly_health` · **Soha:** Nazorat
- **Variantlar:** «Haftalik hisobot» · «O'tgan hafta natijalari»
- **Parametrlar:** hafta
- **Manba:** Smena, Kassa, Foyda-zarar (taxmin), prognoz
- **Hisoblash:** Hafta: tushum, cheklar, o'rtacha chek vs o'tgan hafta va maqsad; kassa o'zgarishi; 3 signal; keyingi hafta to'lovlari.
- **Hisobot:**
  - Xulosa: «Hafta: tushum {t} mln ({+/-}{p}% o'tgan haftaga), kassa {k} mln. Diqqat: {signal}.»
  - KPI: Haftalik tushum | O'tgan haftaga | Kassa
  - Grafik: bar: 7 kun tushum
  - Jadval: 3 signal + keyingi hafta to'lovlari
  - Nima qilish kerak: 1) Signal bo'yicha 1 chora → 2) Keyingi hafta to'lovlarini tekshiring → 3) Maqsadni yangilang
- **Live:** «Bu hafta yaxshi o'tdi — tushum o'tgan haftadan {p} foiz yuqori.»
- **Side:** «Har dushanba yuborib tur» → obuna · «Oylik qanday?» → N58

#### N54 · Terminal (Uzcard/Humo) tushumlari bankka to'liq tushyaptimi?

- **Intent:** `terminal_reconciliation` · **Soha:** Nazorat
- **Variantlar:** «Karta tushumi bankka kelyaptimi?» · «Ekvayring yarashuvi»
- **Parametrlar:** davr
- **Manba:** Smena (Terminal), Kassa/bank (Bank hisob raqami kirimlari), Bank komissiyasi
- **Hisoblash:** POS terminal summasi vs bankka tushgan (komissiya bilan); farqli kunlar; kechikish (T+1).
- **Hisobot:**
  - Xulosa: «{davr}: POS {a} mln, bank {b} mln, komissiya {c} — farq {d}.»
  - KPI: POS terminal | Bankka tushgan | Farq
  - Grafik: bar: kunlik farq
  - Jadval: sana | POS | bank | farq
  - Nima qilish kerak: 1) Haftalik yarashtiring → 2) Farq bo'lsa bankka murojaat → 3) Komissiya tarifini tekshiring (N37)
- **Live:** «Terminal tushumlari bankka to'liq tushgan — farq faqat komissiya.»
- **Side:** «Komissiya qancha?» → N37 · «Naqd farq?» → N50

#### N55 · Soliq kalendari: qachon qancha soliq to'layman?

- **Intent:** `tax_calendar` · **Soha:** Nazorat
- **Variantlar:** «Keyingi soliq to'lovi qachon?» · «Soliqqa qancha ajratay?»
- **Parametrlar:** ufq (3 oy)
- **Manba:** Foyda-zarar (aylanma 4%), Ish haqi (JShDS, ijtimoiy), Balans (soliq saldosi)
- **Hisoblash:** Har oy: hisoblangan soliqlar → keyingi oy 20-sanasi to'lov; joriy oy uchun ajratish (kunlik)
- **Hisobot:**
  - Xulosa: «Keyingi to'lov {sana}: ~{x} mln (aylanma {a} + ish haqi soliqlari {b}).»
  - KPI: Keyingi to'lov | Sana | Joriy oy ajratma
  - Grafik: bar: oylik soliqlar
  - Jadval: oy | aylanma | JShDS | ijtimoiy | sana
  - Nima qilish kerak: 1) Har kuni tushumning ~{p}% ini ajrating → 2) 20-sanadan oldin katta xarid qilmang → 3) Soliq rejimi (S25)
- **Live:** «Yigirmanchi dekabrda o'n bir millionga yaqin soliq to'laysiz.»
- **Side:** «Pul yetadimi?» → S18 · «Rasmiylashtirsam?» → N30

#### N56 · Mavsumiylik: qaysi oylarda savdo yuqori va past?

- **Intent:** `seasonality_profile` · **Soha:** Nazorat
- **Variantlar:** «Yozda savdo tushadimi?» · «Qaysi oy eng yaxshi?»
- **Parametrlar:** —
- **Manba:** Smena (oylar), Fin reja (mavsum koeffitsientlari)
- **Hisoblash:** Oylik indeks (trenddan tozalangan) + Fin reja koeffitsientlari; bayram ta'siri.
- **Hisobot:**
  - Xulosa: «Eng yuqori — {oylar}, eng past — {oylar} ({−x}%).»
  - KPI: Eng yuqori oy | Eng past oy | Bayram ta'siri
  - Grafik: bar: oylik indeks
  - Jadval: oy | indeks | sabab
  - Nima qilish kerak: 1) Past oyga aksiya → 2) Yuqori oyga zaxira/xodim → 3) Katta xarajat — yuqori oy oldidan emas
- **Live:** «Dekabr va yoz oylari yuqori, fevral eng past.»
- **Side:** «Fevralga tayyorgarlik?» → N07 · «Xarid qachon?» → N47

### — Egasi —


#### N57 · Ertalabki brifing: bugun nimaga e'tibor berishim kerak?

- **Intent:** `daily_brief` · **Soha:** Egasi
- **Variantlar:** «Bugun nima qilishim kerak?» · «Ertalabki hisobot»
- **Parametrlar:** sana
- **Manba:** Hamma (kecha natijasi, kassa, bugungi to'lovlar, signallar)
- **Hisoblash:** Kecha: tushum vs maqsad; kassa; bugun/ertaga to'lovlar; 1–3 signal (narx, anomaliya, quvvat); bitta harakat.
- **Hisobot:**
  - Xulosa: «Kecha {t} mln ({p}% maqsad). Kassa {k} mln. Bugun: {to'lovlar}. Diqqat: {signal}.»
  - KPI: Kechagi tushum | Kassa | Bugungi to'lovlar
  - Jadval: signallar + 1 harakat
  - Nima qilish kerak: 1) Bitta eng muhim harakat → 2) Signalni tekshiring → 3) Kun oxirida maqsad
- **Live:** «Xayrli tong! Kecha maqsad bajarildi, kassa yetarli; bugun faqat yetkazib beruvchiga to'lov bor.»
- **Side:** «Batafsil» → N53 · «Bugungi maqsad?» → N48

#### N58 · O'tgan oyga nisbatan nima yaxshilandi, nima yomonlashdi?

- **Intent:** `mom_change` · **Soha:** Egasi
- **Variantlar:** «Oktyabr sentyabrdan yaxshimi?» · «Oylik o'zgarishlar»
- **Parametrlar:** oy (standart: oxirgi yopilgan)
- **Manba:** Foyda-zarar, Smena
- **Hisoblash:** Har KPI: tushum, cheklar, o'rtacha chek, FC, labor, foyda — Δ va sabab (hajm/narx/xarajat).
- **Hisobot:**
  - Xulosa: «{oy}: foyda {+x} mln; yaxshi — {ro'yxat}, yomon — {ro'yxat}.»
  - KPI: Foyda o'zgarishi | Eng yaxshi KPI | Eng yomon KPI
  - Grafik: waterfall: foyda o'zgarishi omillari
  - Jadval: KPI | o'tgan | joriy | Δ
  - Nima qilish kerak: 1) Yomonlashgan KPI'ga 1 chora → 2) Yaxshisini mustahkamlang → 3) Keyingi oy maqsadi
- **Live:** «Oktyabr sentyabrdan yaxshi: foyda yetti million oshdi, asosan mijozlar ko'paygani hisobiga.»
- **Side:** «Nega foyda oshdi?» → S02 · «Keyingi oy?» → N42

#### N59 · Sherigim bilan foydani qanday bo'lamiz?

- **Intent:** `partner_profit_split` · **Soha:** Egasi
- **Variantlar:** «Foyda ulushlari» · «Sherikka qancha tushadi?»
- **Parametrlar:** davr
- **Manba:** Sozlamalar (ulushlar 60/40), Foyda-zarar (sheriklar qatori), Kassa (dividend, kiritma)
- **Hisoblash:** Har sherik: foyda ulushi, kiritmalar, olingan dividend, qoldiq (yil boshidan).
- **Hisobot:**
  - Xulosa: «Sherik 1: {a} mln, Sherik 2: {b} mln (yil boshidan, kiritma va dividend bilan).»
  - KPI: Sherik 1 qoldig'i | Sherik 2 qoldig'i | Olingan dividend
  - Grafik: bar: sheriklar
  - Jadval: sherik | ulush | foyda | kiritma | dividend | qoldiq
  - Nima qilish kerak: 1) Dividendni xavfsiz summada (N14) → 2) Kiritmalarni hisobga oling → 3) Yozma kelishuv
- **Live:** «Yil boshidan Sherik 1 ga {a}, Sherik 2 ga {b} million to'g'ri keladi.»
- **Side:** «Qancha olsak bo'ladi?» → N14 · «Ulush sotib olsam?» → N19

#### N60 · Biznesimni nima qulatishi mumkin?

- **Intent:** `risk_map` · **Soha:** Egasi
- **Variantlar:** «Eng katta xavflarim qaysi?» · «Nima bizni sindirishi mumkin?»
- **Parametrlar:** —
- **Manba:** S06, S18, S44, S11, S41, Kontragentlar
- **Hisoblash:** 6 xavf: kassa tang kuni, kalit kadr, ta'minot, xom ashyo narxi, kanalga bog'liqlik, kredit — ehtimol × ta'sir (so'm) + himoya.
- **Hisobot:**
  - Xulosa: «Top-3 xavf: {x1}, {x2}, {x3}. Eng katta zarar — {x1} ({s} mln).»
  - KPI: Eng katta xavf | Ehtimol | Ta'sir
  - Grafik: matrix: ehtimol × ta'sir
  - Jadval: xavf | ehtimol | ta'sir | himoya
  - Nima qilish kerak: 1) Har xavfga 1 himoya → 2) Zaxira (N04) → 3) Choraklik qayta ko'rib chiqish
- **Live:** «Eng katta xavf — mijozlar oqimining keskin tushishi; bir oylik zaxira sizni himoya qiladi.»
- **Side:** «Zaxira qancha?» → N04 · «Savdo 20% tushsa?» → S06

#### N61 · Biznesni sug'urta qilsam arziydimi?

- **Intent:** `insurance` · **Soha:** Egasi
- **Variantlar:** «Mol-mulk sug'urtasi kerakmi?» · «Yong'in/sug'urta»
- **Parametrlar:** turi, yillik badal (web_lookup yoki foydalanuvchi)
- **Manba:** Asosiy vositalar (qoldiq qiymat), N05 (to'xtash zarari)
- **Hisoblash:** Himoyalanadigan qiymat (asosiy vositalar + zaxira + to'xtash zarari) vs badal; badal % qiymat.
- **Hisobot:**
  - Xulosa: «Himoya qiymati ~{v} mln; badal ~{b} mln/yil ({p}%) — {arziydi}.»
  - KPI: Himoya qiymati | Yillik badal | Badal %
  - Jadval: xavf | zarar | qoplanadimi
  - Nima qilish kerak: 1) Asosiy vositalarni sug'urtalang → 2) To'xtash zararini qo'shing → 3) Takliflarni solishtiring
- **Live:** «Uskunalaringiz uch yuz milliondan ortiq turadi — yillik badal arzon bo'lsa, sug'urta arziydi.»
- **Side:** «Qaysi kompaniya?» → web_lookup · «Yopilsam qancha chidayman?» → N05

#### N62 · Eng shoshilinch 3 ishim qaysi?

- **Intent:** `urgent_actions` · **Soha:** Egasi
- **Variantlar:** «Hozir nimadan boshlay?» · «Ustuvor vazifalar»
- **Parametrlar:** —
- **Manba:** Barcha signallar, prognoz, tasdiqlangan rejalar (Tasks)
- **Hisoblash:** Signallarni muddat × pul ta'siri bo'yicha saralash; top-3 (sana, so'm, qadam).
- **Hisobot:**
  - Xulosa: «1) {ish} — {sana}, {so'm}. 2) … 3) …»
  - KPI: 1-ish | Muddat | Pul ta'siri
  - Jadval: ish | muddat | ta'sir | holat
  - Nima qilish kerak: 1) Birinchisini bugun → 2) Qolganlarini Tasks'ga → 3) Haftalik qayta ko'rib chiqish
- **Live:** «Birinchi navbatda — beshinchi dekabrgacha katta xarid qilmaslik.»
- **Side:** «Ertalabki brifing» → N57 · «Haftalik» → N53

### — Narx —


#### N63 · Bozorda (raqobatchilarda) lavash va burger narxi qancha — menikiga solishtir.

- **Intent:** `market_price_compare` · **Soha:** Narx
- **Variantlar:** «Raqobatchilar narxi?» · «Mening narxlarim bozordan qimmatmi?»
- **Parametrlar:** taomlar, shahar
- **Manba:** Menyu + web_lookup (manbalar, sana)
- **Hisoblash:** Har taom: mening narx vs bozor past/o'rtacha/yuqori (manbalar bilan); pozitsiya (%); manba topilmasa — 'manba topilmadi'.
- **Hisobot:**
  - Xulosa: «{taom}: siz {a}, bozor {l}–{h} (o'rtacha {m}) — {pozitsiya}.»
  - KPI: Pozitsiya | Eng qimmat taom | Manbalar soni
  - Grafik: bar: mening vs bozor
  - Jadval: taom | mening | past | o'rtacha | yuqori | manba
  - Nima qilish kerak: 1) Bozordan past taomni oshiring (N23) → 2) Yuqorisini qiymat bilan oqlang → 3) Choraklik kuzating
- **Live:** «Lavashingiz bozor o'rtachasiga yaqin; burger biroz arzon — oshirishga joy bor.»
- **Side:** «Narx oshirsam?» → N23 · «Narx kuchi?» → S07


---

## 5. Agent uchun implementatsiya eslatmasi

1. Har intent uchun bitta deterministik tool (`<intent>(params)`), natija JSON → ReportCard. LLM faqat xulosa matnini payload'dan yozadi.
2. Umumiy tool'lar (qayta ishlatiladi): `cash_forecast_daily`, `obligations_calendar`, `pnl_month`, `capacity_load`,
   `menu_economics`, `staff_costs`, `price_elasticity`, `loan_schedule`, `web_lookup` (manba + sana bilan).
3. Router: Q1–Q4 (ustuvor) → katalog 100 intent → to'liq-kontekst chat. Ishonch < 0,5 → bitta aniqlashtiruvchi savol.
4. Test: har intent uchun 2 variant + 1 parametrli so'rov; Q1–Q4 golden testlari har commit'da o'tishi shart
   (katalog qo'shilgandan keyin ham raqamlar o'zgarmasin).
5. Bosqichma-bosqich: avval S18, N01, N02, N43, N42, N57, N53 (kassa va prognoz — demo uchun eng foydali), keyin qolganlari.
