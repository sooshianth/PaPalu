import logging

from django.db import transaction
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver
from .AllocationModel import Allocation
from .AllocationSchedulingInfoModel import AllocationSchedulingInfo


bug_logger = logging.getLogger("bugs")


@receiver(post_save, sender=Allocation)
def create_allocation_scheduling_info(sender, instance, created, **kwargs):
    """
    Signal handler برای ایجاد خودکار AllocationSchedulingInfo 
    هنگام ایجاد یک Allocation جدید
    """
    if created:
        def _create_scheduling_info():
            try:
                AllocationSchedulingInfo.objects.get_or_create(
                    allocation_id=instance.pk,
                    defaults={'allocation_received_time': instance.created_at}
                )
            except IntegrityError as exc:
                bug_logger.warning(
                    f"ایجاد AllocationSchedulingInfo برای allocation={instance.pk} با خطای FK مواجه شد: {exc}"
                )
            except Exception as exc:
                bug_logger.warning(
                    f"ایجاد AllocationSchedulingInfo برای allocation={instance.pk} ناموفق بود: {exc}"
                )

        # در برخی دیتابیس‌ها مثل SQLite، ایجاد رکورد وابسته داخل همان post_save
        # در اولین ثبت می‌تواند به FK race بخورد. ایجاد را تا بعد از commit عقب می‌اندازیم.
        transaction.on_commit(_create_scheduling_info, robust=True)

