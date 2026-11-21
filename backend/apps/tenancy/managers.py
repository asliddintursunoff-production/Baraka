"""Tenant isolation at the ORM level (spec §5.2)."""

from __future__ import annotations

from typing import Any, ClassVar

from django.db import models
from django.db.models import Q

from .context import TenantContextMissing, current_business_id, require_business_id


class TenantScopedManager(models.Manager[Any]):
    """`Model.objects`: always filtered to the current business; raises without one."""

    def get_queryset(self) -> models.QuerySet[Any]:
        return super().get_queryset().filter(business_id=require_business_id())


class TenantOrGlobalManager(models.Manager[Any]):
    """For rows that may be global (business IS NULL), e.g. anonymous segment insights."""

    def get_queryset(self) -> models.QuerySet[Any]:
        bid = require_business_id()
        return super().get_queryset().filter(Q(business_id=bid) | Q(business__isnull=True))


class TenantScopedModel(models.Model):
    """Abstract base: `business` FK + scoped `objects` + explicit `unscoped`."""

    business = models.ForeignKey("tenancy.Business", on_delete=models.CASCADE, db_index=True)

    objects: ClassVar[TenantScopedManager] = TenantScopedManager()
    unscoped: ClassVar[models.Manager[Any]] = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        bid = current_business_id()
        if bid is not None and self.business_id != bid:
            raise TenantContextMissing(
                f"refusing to save {type(self).__name__} of business {self.business_id} "
                f"inside the context of business {bid}"
            )
        super().save(*args, **kwargs)
