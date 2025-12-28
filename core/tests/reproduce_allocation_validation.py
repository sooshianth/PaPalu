
import os
import django
import sys
from decimal import Decimal

# تنظیم محیط جنگو
sys.path.append('c:\\Users\\soosh\\Desktop\\Karam\\SimurghAfzar\\PaPalu')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PaPalu.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Product
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from sales.models import Allocation, AllocationProductInfo
from sales.views.allocation_list_view import (
    calculate_order_product_quantities,
    calculate_existing_allocation_product_quantities
)

User = get_user_model()

def run_test():
    print("--- Starting Granular Allocation Validation Test ---")

    # 1. Setup Data
    try:
        user = User.objects.first()
        if not user:
            print("No user found, creating one.")
            user = User.objects.create_superuser('admin_test', 'admin@example.com', 'password')

        # Create Products
        p1, _ = Product.objects.get_or_create(name="Product A Test", defaults={'code': 'P-A'})
        p2, _ = Product.objects.get_or_create(name="Product B Test", defaults={'code': 'P-B'})

        # Create Order
        order = Order.objects.create(
            customer=user, # Using user as customer for simplicity
            order_number="ORD-TEST-001",
            status='pending',
            registrar=user
        )

        # Create Order Items
        # Product A: 100kg
        OrderItem.objects.create(
            order=order,
            product=p1,
            quantity=100,
            weight_unit='kg'
        )
        # Product B: 100kg
        OrderItem.objects.create(
            order=order,
            product=p2,
            quantity=100,
            weight_unit='kg'
        )
        
        print("Created Order with:")
        print(f"  - {p1.name}: 100kg")
        print(f"  - {p2.name}: 100kg")

        # 2. Test Helper Functions
        ordered_qty = calculate_order_product_quantities(order)
        print("\nCalculated Ordered Quantities:", ordered_qty)
        assert ordered_qty[p1.id] == 100
        assert ordered_qty[p2.id] == 100

        # Create an existing allocation
        alloc1 = Allocation.objects.create(
            order=order,
            allocation_number="ALL-TEST-001",
            registrar=user
        )
        AllocationProductInfo.objects.create(
            allocation=alloc1,
            product=p1,
            quantity=50,
            unit='kg'
        )
        
        print("\nCreated Existing Allocation:")
        print(f"  - {p1.name}: 50kg")

        existing_qty = calculate_existing_allocation_product_quantities(order)
        print("Calculated Existing Allocation Quantities:", existing_qty)
        assert existing_qty[p1.id] == 50
        assert existing_qty.get(p2.id, 0) == 0

        # 3. Simulate Validation Logic

        # Scenario A: Valid Allocation
        # Allocate remaining 50kg of A, and 100kg of B. Total: 150kg.
        # Order Total: 200kg. Existing: 50kg. Remaining: 150kg.
        print("\n--- Scenario A: Valid Allocation ---")
        new_allocation_valid = {
            p1.id: 50,
            p2.id: 100
        }
        print(f"Attempting to allocate: {p1.name}=50, {p2.name}=100")
        
        valid = True
        for pid, qty in new_allocation_valid.items():
            ord_q = ordered_qty.get(pid, 0)
            ex_q = existing_qty.get(pid, 0)
            if ex_q + qty > ord_q + 0.001:
                print(f"ERROR: {pid} over-allocated!")
                valid = False
        
        if valid:
            print("SUCCESS: Allocation passed validation.")
        else:
            print("FAILURE: Allocation failed validation unexpectedly.")


        # Scenario B: Granular Over-allocation
        # Allocate 10kg of A (total 60/100 -> OK), but 110kg of B (total 110/100 -> FAIL).
        # Total Allocation: 120kg.
        # Order Total: 200kg. Existing: 50kg.
        # Total Check: 50 + 120 = 170 <= 200. (Would pass old validation)
        print("\n--- Scenario B: Granular Over-allocation ---")
        new_allocation_invalid_granular = {
            p1.id: 10,
            p2.id: 110
        }
        print(f"Attempting to allocate: {p1.name}=10, {p2.name}=110")
        print("Note: Total allocation (170) is LESS than Order Total (200), so old validation would pass.")
        
        validation_error = None
        for pid, qty in new_allocation_invalid_granular.items():
            ord_q = ordered_qty.get(pid, 0)
            ex_q = existing_qty.get(pid, 0)
            if ex_q + qty > ord_q + 0.001:
                 validation_error = f"Product {pid} over-allocated"
                 break
        
        if validation_error:
            print(f"SUCCESS: Caught expected error: {validation_error}")
        else:
            print("FAILURE: New validation logic FAILED to catch the error!")

    except Exception as e:
        print(f"\nEXCEPTION OCCURRED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            if 'alloc1' in locals():
                alloc1.delete()
            if 'order' in locals():
                order.delete()
            # Don't delete products as they might be used elsewhere or just leave them
        except:
            pass
        print("Done.")

if __name__ == "__main__":
    run_test()
