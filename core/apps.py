from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'هسته سامانه'
    
    def ready(self):
        """
        این متد بعد از آماده شدن اپلیکیشن اجرا می‌شود
        و مطمئن می‌شود که همه مدل‌ها در ContentType ثبت شوند
        """
        # Import all models to ensure they are registered with ContentType
        # This allows FieldAccessRule to reference any model in the system
        
        # Product models
        from .ProductFolder import (
            Product, ProductionInfo, BOM, QualityControl, ProductSales
        )
        from .ProductFolder.ProductModel import PhysicalShape
        
        # Person models
        from .PersonFolder import (
            Person, PhoneNumber, PurchasePreference, PaymentPreference,
            Attachment, SocialNetwork, FinancialBanking, BankAccount,
            Representative, DeliveryAddress
        )
        
        # Order models
        from .OrderFolder import (
            Order, OrderItem, ApprovalInfo, DocumentRelation, OrderDocument
        )
        
        # Allocation models
        from .AllocationFolder import (
            Allocation, AllocationProductInfo, AllocationSchedulingInfo
        )
        
        # Transport models
        from .TransportFolder import (
            Transport, ProductInfo, TruckInfo, Fare, LoadingScheduleInfo
        )
        
        # Warehouse models
        from .WarehouseFolder import (
            Inventory, InventoryProduct, Warehouse, DefaultItem
        )
        
        # Raw Material models
        from .RawMaterialFolder import (
            Supplier, QualityParameter, RawMaterialPurchaseInfo,
            RawMaterialQualityControl, RawMaterial
        )
        
        # Stock Entry models
        from .StockEntryFolder import (
            StockEntry, SourceStock, TargetStock
        )
        
        # Settlement models
        from .SettlementFolder import (
            Settlement, TransactionDocument
        )
        
        # RBAC models
        from .RBACModel import (
            TaskPermission, TaskChoices, Role, UserTaskPermission, user_has_task
        )