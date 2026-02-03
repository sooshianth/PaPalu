"""
Supply Tables Module
"""

# Import legacy tables
from .tables_legacy import (
    convert_to_persian_numbers,
    format_number_persian,
    SupplierTable,
    ProcurementPurchaseOrderTable,
    RepresentativeTable,
    BankAccountTable,
    PaymentPreferenceTable,
    SocialNetworkTable,
    AttachmentTable,
    TransportTable,
    TransportStatusLogTable,
    ProcurementPurchaseOrderStatusLogTable,
    GuardExitTable,
    WarehouseDeliveryTable,
    RawMaterialTable,
    LogisticConfirmationTable,
    UploadFarePaymentDocsTable,
    AwaitingPurchaseOrderTable,
    PurchaseOrderMaterialTable,
    PurchaseOrderTransportTable,
)

# Import settlement tables
from .tables_supply_settlement import (
    PendingSupplySettlementOrderTable,
    PendingSupplySettlementApprovalOrderTable,
)

__all__ = [
    'convert_to_persian_numbers',
    'format_number_persian',
    'SupplierTable',
    'ProcurementPurchaseOrderTable',
    'RepresentativeTable',
    'BankAccountTable',
    'PaymentPreferenceTable',
    'SocialNetworkTable',
    'AttachmentTable',
    'TransportTable',
    'TransportStatusLogTable',
    'ProcurementPurchaseOrderStatusLogTable',
    'GuardExitTable',
    'WarehouseDeliveryTable',
    'RawMaterialTable',
    'LogisticConfirmationTable',
    'UploadFarePaymentDocsTable',
    'AwaitingPurchaseOrderTable',
    'PurchaseOrderMaterialTable',
    'PurchaseOrderTransportTable',
    'PendingSupplySettlementOrderTable',
    'PendingSupplySettlementApprovalOrderTable',
]
