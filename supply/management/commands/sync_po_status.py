from django.core.management.base import BaseCommand
from django.db import transaction

from core.SupplyFolder.ProcurementPurchaseOrderModel import (
    ProcurementPurchaseOrder,
)
from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport


class Command(BaseCommand):
    help = "Sync ProcurementPurchaseOrder status from related PurchaseTransport states. Use --order to target one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--order",
            dest="order_number",
            type=str,
            help="Specific order number to sync (e.g., PO-0000001)",
        )

    def handle(self, *args, **options):
        order_number = options.get("order_number")

        qs = ProcurementPurchaseOrder.objects.all()
        if order_number:
            qs = qs.filter(order_number=order_number)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No purchase orders found to sync."))
            return

        po_rank = {
            ProcurementPurchaseOrder.STATUS_DRAFT: 0,
            ProcurementPurchaseOrder.STATUS_AWAITING_TRANSPORT_DEFINITION: 1,
            ProcurementPurchaseOrder.STATUS_AWAITING_VEHICLE_ENTRY: 2,
            ProcurementPurchaseOrder.STATUS_AWAITING_DELIVERY: 3,
            ProcurementPurchaseOrder.STATUS_AWAITING_WAREHOUSE_RECONCILIATION: 4,
            ProcurementPurchaseOrder.STATUS_AWAITING_FINAL_SETTLEMENT: 5,
            ProcurementPurchaseOrder.STATUS_COMPLETED: 6,
        }

        # Map observed PT states to suggested PO status progression
        pt_to_po_rank = {
            PurchaseTransport.STATUS_AWAITING_VEHICLE_ENTRY: 2,
            PurchaseTransport.STATUS_VEHICLE_ENTERED: 3,  # push PO to awaiting_delivery
            PurchaseTransport.STATUS_AWAITING_UNLOADING: 3,  # unloading implies PO awaiting_delivery stage
            PurchaseTransport.STATUS_AWAITING_DELIVERY: 3,
            PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION: 4,
            # We intentionally do not auto-push to final settlement/completed here
        }

        updated = 0
        with transaction.atomic():
            for po in qs.select_related("supplier").prefetch_related("transports"):
                current_rank = po_rank.get(po.status, 0)

                # Determine suggested rank from related transports
                suggested_rank = None
                for pt in po.transports.all():
                    rank = pt_to_po_rank.get(pt.status)
                    if rank is not None:
                        suggested_rank = max(suggested_rank or 0, rank)

                if suggested_rank is None:
                    continue  # no transports or unrelated statuses; skip

                if suggested_rank > current_rank:
                    if suggested_rank == 4:
                        new_status = ProcurementPurchaseOrder.STATUS_AWAITING_WAREHOUSE_RECONCILIATION
                    elif suggested_rank == 3:
                        new_status = ProcurementPurchaseOrder.STATUS_AWAITING_DELIVERY
                    elif suggested_rank == 2:
                        new_status = ProcurementPurchaseOrder.STATUS_AWAITING_VEHICLE_ENTRY
                    else:
                        continue

                    old = po.status
                    po.status = new_status
                    po.save(update_fields=["status"])
                    updated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{po.order_number}: {old} -> {new_status} (synced from transports)"
                        )
                    )

        self.stdout.write(self.style.NOTICE(f"Sync complete. Updated: {updated}"))
