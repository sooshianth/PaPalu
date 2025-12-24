import os
import django
from django.utils import timezone
from decimal import Decimal
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PaPalu.settings')
django.setup()

from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.StockEntryFolder.StockEntryParentModel import StockEntryParent
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

def run_verification():
    print("Starting M2M Tracing verification...")
    
    # Clean previous test data? No, let's just make new distinct items
    suffix = datetime.datetime.now().strftime("%H%M%S")
    
    # Setup Data
    supplier_wh, _ = Warehouse.objects.get_or_create(name="Supplier WH Test", warehouse_type='supplier', defaults={'code': f'WHS{suffix}'})
    raw_wh, _ = Warehouse.objects.get_or_create(name="Raw Material WH Test", warehouse_type='primary', defaults={'code': f'WHR{suffix}'})
    production_wh, _ = Warehouse.objects.get_or_create(name="Production WH Test", warehouse_type='production', defaults={'code': f'WHP{suffix}'})
    
    raw_material, _ = RawMaterial.objects.get_or_create(name=f"Iron Ore {suffix}", raw_material_id=f"RM{suffix}")
    rm_ct = ContentType.objects.get_for_model(RawMaterial)
    
    # ----------------------------------------------------------------
    # Scenario 1: Split Trace (1 Purchase -> 2 Consumptions)
    # ----------------------------------------------------------------
    print("\n[Scenario 1] Split Trace: 1 Purchase (100t) -> Consume 40t, Consume 60t")
    
    # 1. Purchase 100t
    purchase_entry = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.PURCHASE,
        notes=f"Purchase Split Test {suffix}",
        is_committed=True
    )
    TargetStock.objects.create(
        stock_entry=purchase_entry,
        to_content_type=rm_ct,
        to_object_id=raw_material.id,
        to_warehouse=raw_wh,
        quantity=100
    )
    
    # Simulate Consumption Logic for Batch 1 (40t)
    needed = Decimal('40')
    consumption_1 = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.CONSUMPTION,
        notes=f"Consumption 1 {suffix}",
        is_committed=True
    )
    # Manual FIFO simulation (mirroring view logic)
    available = purchase_entry.get_remaining_quantity()
    take = min(needed, available)
    StockEntryParent.objects.create(parent=purchase_entry, child=consumption_1, quantity=take)
    
    print(f"  Consumed {take}t for Consumption 1. Remaining in Purchase: {purchase_entry.get_remaining_quantity()}")
    
    # Simulate Consumption Logic for Batch 2 (60t)
    needed = Decimal('60')
    consumption_2 = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.CONSUMPTION,
        notes=f"Consumption 2 {suffix}",
        is_committed=True
    )
    available = purchase_entry.get_remaining_quantity()
    take = min(needed, available)
    StockEntryParent.objects.create(parent=purchase_entry, child=consumption_2, quantity=take)
    
    print(f"  Consumed {take}t for Consumption 2. Remaining in Purchase: {purchase_entry.get_remaining_quantity()}")
    
    # Verify
    if purchase_entry.get_remaining_quantity() == 0:
        print("  SUCCESS: Purchase fully consumed correctly.")
    else:
        print(f"  FAILURE: Purchase remaining {purchase_entry.get_remaining_quantity()} != 0")
        
    trace1 = consumption_1.get_upstream_trace()
    if purchase_entry in trace1:
        print("  SUCCESS: Consumption 1 traces back to Purchase.")
    else:
         print("  FAILURE: Link missing.")

    # ----------------------------------------------------------------
    # Scenario 2: Merge Trace (2 Purchases -> 1 Consumption)
    # user example: 3 logs of 20 tons -> consume 50 tons
    # ----------------------------------------------------------------
    print("\n[Scenario 2] Merge Trace: P1(20t) + P2(20t) + P3(20t) -> Consume 50t")
    
    p1 = StockEntry.objects.create(transaction_date=timezone.now() - datetime.timedelta(days=3), entry_type=StockEntry.StockEntryType.PURCHASE, notes=f"P1 {suffix}", is_committed=True)
    TargetStock.objects.create(stock_entry=p1, to_content_type=rm_ct, to_object_id=raw_material.id, to_warehouse=raw_wh, quantity=20)
    
    p2 = StockEntry.objects.create(transaction_date=timezone.now() - datetime.timedelta(days=2), entry_type=StockEntry.StockEntryType.PURCHASE, notes=f"P2 {suffix}", is_committed=True)
    TargetStock.objects.create(stock_entry=p2, to_content_type=rm_ct, to_object_id=raw_material.id, to_warehouse=raw_wh, quantity=20)
    
    p3 = StockEntry.objects.create(transaction_date=timezone.now() - datetime.timedelta(days=1), entry_type=StockEntry.StockEntryType.PURCHASE, notes=f"P3 {suffix}", is_committed=True)
    TargetStock.objects.create(stock_entry=p3, to_content_type=rm_ct, to_object_id=raw_material.id, to_warehouse=raw_wh, quantity=20)
    
    # Consume 50t
    consumption_merge = StockEntry.objects.create(
        transaction_date=timezone.now(),
        entry_type=StockEntry.StockEntryType.CONSUMPTION,
        notes=f"Consumption Merge {suffix}",
        is_committed=True
    )
    
    needed = Decimal('50')
    candidates = [p1, p2, p3] # Ordered by date
    
    for cand in candidates:
        if needed <= 0: break
        avail = cand.get_remaining_quantity()
        if avail > 0:
            take = min(needed, avail)
            StockEntryParent.objects.create(parent=cand, child=consumption_merge, quantity=take)
            needed -= take
            print(f"  Took {take} from {cand.notes}")
            
    # Verify
    # P1: 20 used (Rem: 0)
    # P2: 20 used (Rem: 0)
    # P3: 10 used (Rem: 10)
    print(f"  P1 Rem: {p1.get_remaining_quantity()}")
    print(f"  P2 Rem: {p2.get_remaining_quantity()}")
    print(f"  P3 Rem: {p3.get_remaining_quantity()}")
    
    if p1.get_remaining_quantity() == 0 and p2.get_remaining_quantity() == 0 and p3.get_remaining_quantity() == 10:
        print("  SUCCESS: FIFO logic worked perfectly.")
    else:
        print("  FAILURE: FIFO logic math mismatch.")
        
    trace_merge = consumption_merge.get_upstream_trace()
    if len(trace_merge) >= 4: # Self + 3 parents
         print("  SUCCESS: Trace contains all parents.")
    else:
         print(f"  FAILURE: Trace length {len(trace_merge)} (expected >= 4)")

if __name__ == '__main__':
    run_verification()
