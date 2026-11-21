"""Money facts: transactions, planned payments, counterparties, opening cash."""

from __future__ import annotations

from django.db import models

from apps.tenancy.managers import TenantScopedModel


class Counterparty(TenantScopedModel):
    class Kind(models.TextChoices):
        SUPPLIER = "supplier", "Ta'minotchi"
        BANK = "bank", "Bank"
        LANDLORD = "landlord", "Ijara beruvchi"
        STATE = "state", "Davlat"
        EMPLOYEE = "employee", "Xodim"
        CUSTOMER = "customer", "Mijoz"
        OTHER = "other", "Boshqa"

    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "name"], name="uniq_counterparty_name")
        ]

    def __str__(self) -> str:
        return self.name


class Transaction(TenantScopedModel):
    class Direction(models.TextChoices):
        IN = "in", "Kirim"
        OUT = "out", "Chiqim"

    amount = models.DecimalField(
        max_digits=18, decimal_places=2
    )  # always positive; direction gives the sign
    direction = models.CharField(max_length=3, choices=Direction.choices)
    category = models.CharField(max_length=64, blank=True)
    counterparty = models.ForeignKey(Counterparty, null=True, blank=True, on_delete=models.SET_NULL)
    txn_date = models.DateField()
    method = models.CharField(max_length=32, blank=True)
    note = models.CharField(max_length=255, blank=True)
    raw_row = models.ForeignKey(
        "ingestion.RawRow", null=True, blank=True, on_delete=models.SET_NULL
    )
    is_actual = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "txn_date"], name="txn_business_date")]


class Obligation(TenantScopedModel):
    class Priority(models.TextChoices):
        CRITICAL = "critical", "Muhim"
        DEFERRABLE = "deferrable", "Kechiktirsa bo'ladi"
        DISCRETIONARY = "discretionary", "Ixtiyoriy"

    class Status(models.TextChoices):
        PLANNED = "planned", "Rejada"
        PAID = "paid", "To'landi"
        CANCELLED = "cancelled", "Bekor"

    class Source(models.TextChoices):
        SHEET = "sheet", "Jadval"
        RULE = "rule", "Qoida"
        MANUAL = "manual", "Qo'lda"

    title = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    due_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.CRITICAL)
    category = models.CharField(max_length=32, blank=True)  # payroll|loan|rent|tax|supplier|...
    recurrence = models.JSONField(null=True, blank=True)
    counterparty = models.ForeignKey(Counterparty, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.SHEET)
    raw_row = models.ForeignKey(
        "ingestion.RawRow", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "status", "due_date"], name="oblig_business_due")
        ]


class CashAccount(TenantScopedModel):
    """Cash at the end of `as_of_date` (asked once at onboarding if the sheet lacks it)."""

    opening_balance = models.DecimalField(max_digits=18, decimal_places=2)
    as_of_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "-as_of_date"], name="cash_business_asof")]
