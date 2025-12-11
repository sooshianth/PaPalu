"""
Management command برای پاک کردن داده‌های فیک
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from core.OrderFolder.OrderItemModel import OrderItem
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.InvoiceModel import Invoice
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.AllocationFolder.AllocationModel import Allocation
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder, ProcurementPurchaseOrderMaterial
from core.StockEntryFolder.StockEntryModel import StockEntry
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PersonModel import Person
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.WarehouseFolder.WarehouseModel import Warehouse


class Command(BaseCommand):
    help = 'Clear all fake data from database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion (required)'
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.ERROR('Please use --confirm to delete all fake data'))
            return
        
        self.stdout.write('Clearing fake data...')
        
        with transaction.atomic():
            # حذف به ترتیب وابستگی‌ها
            OrderItem.objects.all().delete()
            self.stdout.write('Deleted OrderItems')
            
            Proforma.objects.all().delete()
            self.stdout.write('Deleted Proformas')
            
            Invoice.objects.all().delete()
            self.stdout.write('Deleted Invoices')
            
            Order.objects.all().delete()
            self.stdout.write('Deleted Orders')
            
            ProcurementPurchaseOrderMaterial.objects.all().delete()
            self.stdout.write('Deleted ProcurementPurchaseOrderMaterials')
            
            ProcurementPurchaseOrder.objects.all().delete()
            self.stdout.write('Deleted ProcurementPurchaseOrders')
            
            StockEntry.objects.all().delete()
            self.stdout.write('Deleted StockEntries')
            
            TruckInfo.objects.all().delete()
            self.stdout.write('Deleted TruckInfos')
            
            Transport.objects.all().delete()
            self.stdout.write('Deleted Transports')
            
            Allocation.objects.all().delete()
            self.stdout.write('Deleted Allocations')
            
            ProductionProgram.objects.all().delete()
            self.stdout.write('Deleted ProductionPrograms')
            
            PhoneNumber.objects.all().delete()
            self.stdout.write('Deleted PhoneNumbers')
            
            DeliveryAddress.objects.all().delete()
            self.stdout.write('Deleted DeliveryAddresses')
            
            BankAccount.objects.all().delete()
            self.stdout.write('Deleted BankAccounts')
            
            FinancialBanking.objects.all().delete()
            self.stdout.write('Deleted FinancialBankings')
            
            Person.objects.all().delete()
            self.stdout.write('Deleted Persons')
            
            Product.objects.all().delete()
            self.stdout.write('Deleted Products')
            
            RawMaterial.objects.all().delete()
            self.stdout.write('Deleted RawMaterials')
            
            Warehouse.objects.all().delete()
            self.stdout.write('Deleted Warehouses')
        
        self.stdout.write(self.style.SUCCESS('All fake data cleared!'))

