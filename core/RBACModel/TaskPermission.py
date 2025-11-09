from django.db import models


class TaskChoices(models.TextChoices):
    VIEW_DASHBOARD = 'view_dashboard', 'View Dashboard'
    MANAGE_ORDERS = 'manage_orders', 'Manage Orders'
    MANAGE_PRODUCTS = 'manage_products', 'Manage Products'
    MANAGE_INVENTORY = 'manage_inventory', 'Manage Inventory'
    MANAGE_TRANSPORT = 'manage_transport', 'Manage Transport'
    MANAGE_RAW_MATERIALS = 'manage_raw_materials', 'Manage Raw Materials'
    MANAGE_ALLOCATION = 'manage_allocation', 'Manage Allocation'
    MANAGE_SETTLEMENT = 'manage_settlement', 'Manage Settlement'
    MANAGE_WAREHOUSE = 'manage_warehouse', 'Manage Warehouse'
    MANAGE_STOCK_ENTRY = 'manage_stock_entry', 'Manage Stock Entry'
    MANAGE_USERS = 'manage_users', 'Manage Users'
    VIEW_REPORTS = 'view_reports', 'View Reports'


class TaskPermission(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tasks = models.JSONField(default=list)

    def __str__(self):
        return self.name
