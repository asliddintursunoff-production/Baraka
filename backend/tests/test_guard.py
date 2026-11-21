from apps.ai.guard import violations

ALLOWED = [
    "Yo'q, hozir olmang. Agar hozir olsangiz, 10-dekabrda oylikka 6,2 mln yetmay qoladi.",
    '{"recommended_date": "2027-01-12", "spend_limit": "8000000.00", "amount": "25000000.00"}',
    "Agar 25 million so'mga jihoz olsam, 3 oyga bo'lib to'lasam?",
]


def test_grounded_answer_passes():
    ans = [
        "Yo'q, hozir olmang.",
        "Agar hozir 25 million sarflasangiz, **10-dekabrda** oylikka 6,2 million so'm yetmay qoladi.",
        "Jihozni **12-yanvarda** oling.",
        "10-dekabrgacha **8 million so'mdan katta** xarid qilmang.",
        "3 oyga bo'lib to'lash ham mumkin.",
    ]
    assert violations(ans, ALLOWED) == []


def test_invented_amount_and_date_are_caught():
    assert violations(["Sizda 7,4 mln yetmaydi."], ALLOWED) == ["amount 7400000.0"]
    assert violations(["15-yanvarda oling."], ALLOWED) == ["date 15-1"]
    assert violations(["12 kun kuting."], ALLOWED) == ["number 12"]


def test_words_amounts_are_checked_too():
    assert violations(["olti million ikki yuz ming so'm yetmaydi"], ALLOWED) == []
    assert violations(["to'qqiz million so'm qoladi"], ALLOWED)
