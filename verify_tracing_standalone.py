import os
import django
from django.utils import timezone
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PaPalu.settings')
django.setup()

from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from django.contrib.contenttypes.models import ContentType

def run_verification():
    print("Starting verification...")
    # Setup Data
    supplier_wh, _ = Warehouse.objects.get_or_create(name="Supplier WH Test", warehouse_type='supplier', defaults={'code': 'WHT01'})
    raw_wh, _ = Warehouse.objects.get_or_create(name="Raw Material WH Test", warehouse_type='primary', defaults={'code': 'WHT02'})
    production_wh, _ = Warehouse.objects.get_or_create(name="Production WH Test", warehouse_type='production', defaults={'code': 'WHT03'})
    product_wh, _ = Warehouse.objects.get_or_create(name="Product WH Test", warehouse_type='primary', defaults={'code': 'WHT04'})
    
    raw_material, _ = RawMaterial.objects.get_or_create(name="Iron Ore Test", raw_material_id="RM001T")
    product, _ = Product.objects.get_or_create(name="Steel Beam Test", code="P001T")
    
    rm_ct = ContentType.objects.get_for_model(RawMaterial)
    p_ct = ContentType.objects.get_for_model(Product)
    
    # 1. Purchase
    print("1. Creating Purchase Entry...")
    purchase_entry = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.PURCHASE,
        notes="Purchase Test",
        is_committed=True
    )
    TargetStock.objects.create(
        stock_entry=purchase_entry,
        to_content_type=rm_ct,
        to_object_id=raw_material.id,
        to_warehouse=raw_wh,
        quantity=100
    )
    
    # 2. Consumption
    print("2. Creating Consumption Entry...")
    prog = ProductionProgram.objects.create(
        program_id="PROG-TEST-001",
        product=product,
        planned_weight_ton=10,
        production_warehouse=production_wh
    )
    
    consumption_entry = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.CONSUMPTION,
        notes=f'شروع تولید برنامه {prog.program_id}', 
        is_committed=True
    )
    
    TargetStock.objects.create(
        stock_entry=consumption_entry,
        to_content_type=rm_ct,
        to_object_id=raw_material.id,
        to_warehouse=production_wh, 
        quantity=50
    )
    
    # 3. Production (Completion)
    print("3. Creating Completion Entry...")
    found_consumption = StockEntry.objects.filter(
        notes__contains=f'شروع تولید برنامه {prog.program_id}',
        is_committed=True
    ).order_by('-created_at').first()
    
    completion_entry = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.PRODUCTION,
        notes=f'تکمیل تولید برنامه {prog.program_id}',
        parent=found_consumption,
        is_committed=True
    )
    
    TargetStock.objects.create(
        stock_entry=completion_entry,
        to_content_type=p_ct,
        to_object_id=product.id,
        to_warehouse=product_wh,
        quantity=10
    )
    
    # 4. Sale
    print("4. Creating Sale Entry...")
    sale_entry = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.SALE,
        notes="Sale Test",
        is_committed=False
    )
    
    if not sale_entry.parent:
        parent_entry = StockEntry.objects.filter(
            target_stocks__to_content_type=p_ct,
            target_stocks__to_object_id=product.id,
            target_stocks__to_warehouse=product_wh,
            entry_type__in=[
                StockEntry.StockEntryType.PRODUCTION, 
                StockEntry.StockEntryType.PURCHASE,
                StockEntry.StockEntryType.OPENING
            ],
            is_committed=True
        ).order_by('-transaction_date').first()
        
        if parent_entry:
            sale_entry.parent = parent_entry
            sale_entry.save()
            
    # Link check
    print(f"Sale Parent ID: {sale_entry.parent.id if sale_entry.parent else 'None'}")
    print(f"Completion Parent ID: {completion_entry.parent.id if completion_entry.parent else 'None'}")
    
    trace = sale_entry.get_upstream_trace()
    print("\nTrace Result:")
    for t in trace:
        print(f" -> {t.entry_type} (ID: {t.id})")
        
    if len(trace) >= 3 and trace[-1] == sale_entry and trace[-2] == completion_entry:
         print("\nSUCCESS: Trace verified!")
    else:
         print("\nFAILURE: Trace mismatch.")

if __name__ == '__main__':
    run_verification()
