from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django_jalali.db import models as jmodels


class StockEntry(models.Model):
    """
    Main model representing stock entry/movement transaction in the warehouse.
    """
    
    transaction_date = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ تراکنش'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='یادداشت‌ها'
    )
    
    is_committed = models.BooleanField(
        default=False,
        verbose_name='تأیید شده',
        help_text='آیا این تراکنش انبار تأیید و اعمال شده است؟'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ به‌روزرسانی'
    )
    
    class Meta:
        verbose_name = 'انبار | لاگ انبار'
        verbose_name_plural = 'انبار | لاگ‌های انبار'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['transaction_date']),
        ]
    
    def __str__(self):
        status = "تأیید شده" if self.is_committed else "در انتظار تأیید"
        date_str = self.transaction_date.strftime('%Y-%m-%d %H:%M') if self.transaction_date else 'بدون تاریخ'
        return f"تراکنش انبار - {date_str} ({status})"
    
    def commit(self):
        """
        تأیید و اعمال تراکنش انبار
        این عملیات موجودی انبارها را بر اساس تغییرات مشخص شده به‌روزرسانی می‌کند
        """
        if self.is_committed:
            raise ValidationError('این تراکنش قبلاً تأیید شده است.')
        
        with transaction.atomic():
            # Process source stocks (decrease inventory)
            for source in self.source_stocks.all():
                self._process_source_stock(source)
            
            # Process target stocks (increase inventory)  
            for target in self.target_stocks.all():
                self._process_target_stock(target)
            
            # Mark as committed
            self.is_committed = True
            self.save(update_fields=['is_committed'])
    
    def _process_source_stock(self, source_stock):
        """پردازش موجودی منبع (کاهش از انبار)"""
        from core.WarehouseFolder.InventoryItemModel import InventoryItem
        
        warehouse = source_stock.from_warehouse
        quantity = source_stock.quantity or 0
        
        if source_stock.from_item:
            # Handle generic item (product or raw material)
            self._update_inventory_item(
                warehouse=warehouse,
                item=source_stock.from_item,
                quantity_change=-quantity,  # Negative for source (decrease)
                is_product=source_stock.is_product
            )
    
    def _process_target_stock(self, target_stock):
        """پردازش موجودی مقصد (افزایش به انبار)"""
        from core.WarehouseFolder.InventoryItemModel import InventoryItem
        
        warehouse = target_stock.to_warehouse
        quantity = target_stock.quantity or 0
        
        if target_stock.to_item:
            # Handle generic item (product or raw material)
            self._update_inventory_item(
                warehouse=warehouse,
                item=target_stock.to_item,
                quantity_change=quantity,  # Positive for target (increase)
                is_product=target_stock.is_product
            )
    
    def _update_inventory_item(self, warehouse, item, quantity_change, is_product=True):
        """
        به‌روزرسانی یا ایجاد آیتم موجودی انبار
        """
        from core.WarehouseFolder.InventoryItemModel import InventoryItem
        from core.ProductFolder.ProductModel import Product
        from core.RawMaterialFolder.RawMaterialModel import RawMaterial
        
        # Get appropriate content type
        if is_product:
            content_type = ContentType.objects.get_for_model(Product)
            item_identifier = str(item.id)  # Use primary key for object_id
        else:
            content_type = ContentType.objects.get_for_model(RawMaterial)
            item_identifier = str(item.id)  # Use primary key for object_id
        
        # Try to find existing inventory item
        inventory_item, created = InventoryItem.objects.get_or_create(
            warehouse=warehouse,
            content_type=content_type,
            object_id=item_identifier,
            defaults={
                'quantity': 0
            }
        )
        
        # Update quantity (can be negative)
        new_quantity = (inventory_item.quantity or 0) + quantity_change
        inventory_item.quantity = new_quantity
        inventory_item.save(update_fields=['quantity', 'updated_at'])
