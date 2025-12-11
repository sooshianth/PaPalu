"""
Management command برای اصلاح داده‌های Decimal نامعتبر
"""
from django.core.management.base import BaseCommand
from decimal import Decimal, InvalidOperation
from core.OrderFolder.OrderItemModel import OrderItem
from core.OrderFolder.OrderModel import Order
from django.db import transaction


class Command(BaseCommand):
    help = 'اصلاح داده‌های Decimal نامعتبر در دیتابیس'

    def handle(self, *args, **options):
        self.stdout.write('Starting to fix Decimal data...')
        fixed_count = 0
        
        with transaction.atomic():
            # بررسی OrderItem
            for item in OrderItem.objects.all():
                try:
                    # بررسی و اصلاح فیلدهای Decimal
                    if item.quantity is not None:
                        try:
                            Decimal(str(item.quantity))
                        except (InvalidOperation, ValueError, TypeError):
                            item.quantity = Decimal('0')
                            fixed_count += 1
                    
                    if item.unit_price is not None:
                        try:
                            Decimal(str(item.unit_price))
                        except (InvalidOperation, ValueError, TypeError):
                            item.unit_price = Decimal('0')
                            fixed_count += 1
                    
                    if item.discount is not None:
                        try:
                            Decimal(str(item.discount))
                        except (InvalidOperation, ValueError, TypeError):
                            item.discount = Decimal('0')
                            fixed_count += 1
                    
                    if item.additional_charges is not None:
                        try:
                            Decimal(str(item.additional_charges))
                        except (InvalidOperation, ValueError, TypeError):
                            item.additional_charges = Decimal('0')
                            fixed_count += 1
                    
                    if item.bag_weight is not None:
                        try:
                            Decimal(str(item.bag_weight))
                        except (InvalidOperation, ValueError, TypeError):
                            item.bag_weight = None
                            fixed_count += 1
                    
                    item.save()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error fixing OrderItem {item.id}: {e}'))
            
            # بررسی Order
            for order in Order.objects.all():
                try:
                    if order.total_shipment_weight is not None:
                        try:
                            Decimal(str(order.total_shipment_weight))
                        except (InvalidOperation, ValueError, TypeError):
                            order.total_shipment_weight = Decimal('0')
                            fixed_count += 1
                    
                    if order.total_delivery_weight is not None:
                        try:
                            Decimal(str(order.total_delivery_weight))
                        except (InvalidOperation, ValueError, TypeError):
                            order.total_delivery_weight = Decimal('0')
                            fixed_count += 1
                    
                    order.save()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error fixing Order {order.id}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} fields.'))

