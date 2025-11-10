from django.db import models


class TaskChoices(models.TextChoices):
    # General
    GENERAL_VIEW_DASHBOARD = 'general.view_dashboard', 'View Dashboard'
    
    # Sales
    SALES_MANAGE_ORDERS = 'sales.manage_orders', 'Manage Orders'
    SALES_MANAGE_ALLOCATION = 'sales.manage_allocation', 'Manage Allocation'
    SALES_MANAGE_SETTLEMENT = 'sales.manage_settlement', 'Manage Settlement'
    SALES_VIEW_REPORTS = 'sales.view_reports', 'View Sales Reports'
    
    # Production
    PRODUCTION_MANAGE_PRODUCTS = 'production.manage_products', 'Manage Products'
    PRODUCTION_MANAGE_RAW_MATERIALS = 'production.manage_raw_materials', 'Manage Raw Materials'
    PRODUCTION_VIEW_REPORTS = 'production.view_reports', 'View Production Reports'
    
    # Warehouse
    WAREHOUSE_MANAGE_INVENTORY = 'warehouse.manage_inventory', 'Manage Inventory'
    WAREHOUSE_MANAGE_WAREHOUSE = 'warehouse.manage_warehouse', 'Manage Warehouse'
    WAREHOUSE_MANAGE_STOCK_ENTRY = 'warehouse.manage_stock_entry', 'Manage Stock Entry'
    WAREHOUSE_VIEW_REPORTS = 'warehouse.view_reports', 'View Warehouse Reports'
    
    # Financial
    FINANCIAL_MANAGE_TRANSPORT = 'financial.manage_transport', 'Manage Transport'
    FINANCIAL_VIEW_REPORTS = 'financial.view_reports', 'View Financial Reports'
    
    # Administration
    ADMIN_MANAGE_USERS = 'administration.manage_users', 'Manage Users'
    ADMIN_VIEW_REPORTS = 'administration.view_reports', 'View Admin Reports'


class TaskPermission(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tasks = models.JSONField(default=list)

    def __str__(self):
        return self.name
