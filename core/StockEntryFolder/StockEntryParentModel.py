from django.db import models
from django.core.exceptions import ValidationError

class StockEntryParent(models.Model):
    """
    Through model for StockEntry parent-child relationship.
    Tracks how much quantity from a specific parent entry was used in a child entry.
    """
    parent = models.ForeignKey(
        'core.StockEntry',
        on_delete=models.CASCADE,
        related_name='child_links',
        verbose_name='تراکنش والد'
    )
    child = models.ForeignKey(
        'core.StockEntry',
        on_delete=models.CASCADE,
        related_name='parent_links',
        verbose_name='تراکنش فرزند'
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name='مقدار مصرف شده از والد',
        help_text='مقداری که از این والد خاص در این فرزند استفاده شده است'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رابطه والد-فرزند انبار'
        verbose_name_plural = 'روابط والد-فرزند انبار'
        unique_together = ('parent', 'child')

    def __str__(self):
        return f"{self.child.id} <- {self.parent.id} ({self.quantity})"
