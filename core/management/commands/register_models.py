"""
Management command to register all core models in ContentType
"""
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Register all core models in Django ContentType system'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Registering core models in ContentType...'))
        
        # Import all models - this will trigger their registration
        from core.ProductFolder import (
            Product, ProductionInfo, BOM, QualityControl, ProductSales
        )
        from core.ProductFolder.ProductModel import PhysicalShape
        
        from core.PersonFolder import (
            Person, PhoneNumber, PurchasePreference, PaymentPreference,
            Attachment, SocialNetwork, FinancialBanking, BankAccount,
            Representative, DeliveryAddress
        )
        
        from core.OrderFolder import (
            Order, OrderItem, ApprovalInfo, DocumentRelation, OrderDocument
        )
        
        from core.AllocationFolder import (
            Allocation, AllocationProductInfo, AllocationSchedulingInfo
        )
        
        from core.TransportFolder import (
            Transport, ProductInfo, TruckInfo, Fare, LoadingScheduleInfo
        )
        
        from core.WarehouseFolder import (
            InventoryItem, Warehouse, DefaultItem
        )
        
        from core.RawMaterialFolder import (
            Supplier, QualityParameter, RawMaterialPurchaseInfo,
            RawMaterialQualityControl, RawMaterial
        )
        
        from core.StockEntryFolder import (
            StockEntry, SourceStock, TargetStock
        )
        
        from core.SettlementFolder import (
            Settlement, TransactionDocument
        )
        
        from core.RBACModel import (
            TaskPermission, FieldPermission, FieldChoice, Role, UserTaskPermission, UserFieldPermission
        )
        
        # List of all model classes
        models = [
            # Product
            Product, PhysicalShape, ProductionInfo, BOM, QualityControl, ProductSales,
            # Person
            Person, PhoneNumber, PurchasePreference, PaymentPreference,
            Attachment, SocialNetwork, FinancialBanking, BankAccount,
            Representative, DeliveryAddress,
            # Order
            Order, OrderItem, ApprovalInfo, DocumentRelation, OrderDocument,
            # Allocation
            Allocation, AllocationProductInfo, AllocationSchedulingInfo,
            # Transport
            Transport, ProductInfo, TruckInfo, Fare, LoadingScheduleInfo,
            # Warehouse
            InventoryItem, Warehouse, DefaultItem,
            # Raw Material
            Supplier, QualityParameter, RawMaterialPurchaseInfo,
            RawMaterialQualityControl, RawMaterial,
            # Stock Entry
            StockEntry, SourceStock, TargetStock,
            # Settlement
            Settlement, TransactionDocument,
            # RBAC
            TaskPermission, FieldPermission, FieldChoice, Role, UserTaskPermission, UserFieldPermission,
        ]
        
        registered_count = 0
        for model in models:
            try:
                ct, created = ContentType.objects.get_or_create(
                    app_label='core',
                    model=model._meta.model_name,
                    defaults={'model': model._meta.model_name}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'  + Registered: {model._meta.model_name}')
                    )
                    registered_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  - Already exists: {model._meta.model_name}')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  x Error registering {model._meta.model_name}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nTotal models registered: {registered_count}')
        )
        self.stdout.write(
            self.style.SUCCESS('Done! All core models are now registered in ContentType.')
        )

