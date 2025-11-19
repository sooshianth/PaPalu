from django.db.models.signals import post_save
from django.dispatch import receiver
from .AllocationModel import Allocation
from .AllocationSchedulingInfoModel import AllocationSchedulingInfo


@receiver(post_save, sender=Allocation)
def create_allocation_scheduling_info(sender, instance, created, **kwargs):
    """
    Signal handler برای ایجاد خودکار AllocationSchedulingInfo 
    هنگام ایجاد یک Allocation جدید
    """
    if created:
        # ایجاد AllocationSchedulingInfo برای تخصیص جدید
        # allocation_received_time با created_at تخصیص تنظیم می‌شود
        AllocationSchedulingInfo.objects.create(
            allocation=instance,
            allocation_received_time=instance.created_at
        )

