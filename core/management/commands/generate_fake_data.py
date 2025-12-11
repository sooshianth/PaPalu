"""
Management command برای تولید داده‌های فیک برای توسعه
استفاده: python manage.py generate_fake_data [--count=10]
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
import jdatetime
import random
import string
from decimal import Decimal
from datetime import datetime, timedelta

# Import مدل‌ها
from core.PersonFolder.PersonModel import Person, ActivityField
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
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
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'تولید داده‌های فیک برای توسعه سیستم'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='تعداد رکوردهای تولید شده برای هر مدل (پیش‌فرض: 10)'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='رد کردن اگر داده‌های موجود وجود دارد'
        )

    def handle(self, *args, **options):
        count = options['count']
        skip_existing = options['skip_existing']

        self.stdout.write(self.style.SUCCESS('شروع تولید داده‌های فیک...'))

        # بررسی داده‌های موجود
        if skip_existing:
            if Person.objects.exists():
                self.stdout.write(self.style.WARNING('داده‌های موجود یافت شد. رد کردن...'))
                return

        try:
            with transaction.atomic():
                # 1. ایجاد ActivityField ها
                self.stdout.write('ایجاد حیطه‌های فعالیت...')
                activity_fields = self.create_activity_fields()

                # 2. ایجاد انبارها
                self.stdout.write('ایجاد انبارها...')
                warehouses = self.create_warehouses(count)

                # 3. ایجاد کاربران (اگر وجود ندارند)
                self.stdout.write('ایجاد کاربران...')
                users = self.create_users(count)

                # 4. ایجاد اشخاص (مشتریان، تامین‌کنندگان، رانندگان)
                self.stdout.write('ایجاد اشخاص...')
                customers = self.create_persons('customer', count, warehouses, users, activity_fields)
                suppliers = self.create_persons('supplier', count, warehouses, users, activity_fields)
                drivers = self.create_persons('driver', count, warehouses, users, activity_fields)
                
                # 4.1. ایجاد اطلاعات تکمیلی اشخاص
                self.stdout.write('ایجاد اطلاعات تکمیلی اشخاص (تلفن، آدرس، حساب بانکی)...')
                self.create_person_details(customers + suppliers)

                # 5. ایجاد محصولات
                self.stdout.write('ایجاد محصولات...')
                products = self.create_products(count, warehouses)

                # 6. ایجاد مواد اولیه
                self.stdout.write('ایجاد مواد اولیه...')
                raw_materials = self.create_raw_materials(count, suppliers)

                # 7. ایجاد سفارش‌های فروش
                self.stdout.write('ایجاد سفارش‌های فروش...')
                orders = self.create_orders('sale', count, customers, users, products)

                # 8. ایجاد سفارش‌های خرید
                self.stdout.write('ایجاد سفارش‌های خرید...')
                purchase_orders = self.create_orders('purchase', count, suppliers, users, products)

                # 9. ایجاد پیش فاکتورها
                self.stdout.write('ایجاد پیش فاکتورها...')
                proformas = self.create_proformas(count, orders)

                # 10. ایجاد فاکتورها
                self.stdout.write('ایجاد فاکتورها...')
                invoices = self.create_invoices(count, orders)

                # 11. ایجاد برنامه‌های تولید
                self.stdout.write('ایجاد برنامه‌های تولید...')
                production_programs = self.create_production_programs(count, products)

                # 12. ایجاد تخصیص‌ها
                self.stdout.write('ایجاد تخصیص‌ها...')
                allocations = self.create_allocations(count, orders, products)

                # 13. ایجاد حمل‌ها (قبل از خودروها، چون TruckInfo به Transport نیاز دارد)
                self.stdout.write('ایجاد حمل‌ها...')
                transports = self.create_transports(count, allocations)

                # 14. ایجاد خودروها (بعد از transports)
                self.stdout.write('ایجاد خودروها...')
                trucks = self.create_trucks(count, transports)

                # 15. ایجاد سفارش‌های خرید تامین
                self.stdout.write('ایجاد سفارش‌های خرید تامین...')
                procurement_orders = self.create_procurement_orders(count, suppliers, raw_materials, users)

                # 16. ایجاد ورودی‌های انبار
                self.stdout.write('ایجاد ورودی‌های انبار...')
                stock_entries = self.create_stock_entries(count, warehouses, products, raw_materials)

                self.stdout.write(self.style.SUCCESS(f'\n✅ تولید داده‌های فیک با موفقیت انجام شد!'))
                self.stdout.write(f'📊 خلاصه:')
                self.stdout.write(f'   👥 اشخاص: {Person.objects.count()} (مشتری: {Person.objects.filter(type="customer").count()}, تامین: {Person.objects.filter(type="supplier").count()}, راننده: {Person.objects.filter(type="driver").count()})')
                self.stdout.write(f'   📞 شماره تلفن‌ها: {PhoneNumber.objects.count()}')
                self.stdout.write(f'   📍 آدرس‌های تحویل: {DeliveryAddress.objects.count()}')
                self.stdout.write(f'   💰 اطلاعات مالی: {FinancialBanking.objects.count()}')
                self.stdout.write(f'   🏦 حساب‌های بانکی: {BankAccount.objects.count()}')
                self.stdout.write(f'   📦 انبارها: {Warehouse.objects.count()}')
                self.stdout.write(f'   🛍️ محصولات: {Product.objects.count()}')
                self.stdout.write(f'   🌾 مواد اولیه: {RawMaterial.objects.count()}')
                self.stdout.write(f'   📋 سفارش‌ها: {Order.objects.count()} (فروش: {Order.objects.filter(order_type="sale").count()}, خرید: {Order.objects.filter(order_type="purchase").count()})')
                self.stdout.write(f'   📄 اقلام سفارش: {OrderItem.objects.count()}')
                self.stdout.write(f'   📝 پیش فاکتورها: {Proforma.objects.count()}')
                self.stdout.write(f'   🧾 فاکتورها: {Invoice.objects.count()}')
                self.stdout.write(f'   🏭 برنامه‌های تولید: {ProductionProgram.objects.count()}')
                self.stdout.write(f'   🚚 تخصیص‌ها: {Allocation.objects.count()}')
                self.stdout.write(f'   🚛 حمل‌ها: {Transport.objects.count()}')
                self.stdout.write(f'   🚗 خودروها: {TruckInfo.objects.count()}')
                self.stdout.write(f'   📦 سفارش‌های خرید تامین: {ProcurementPurchaseOrder.objects.count()}')
                self.stdout.write(f'   📥 ورودی‌های انبار: {StockEntry.objects.count()}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ خطا در تولید داده: {str(e)}'))
            import traceback
            traceback.print_exc()
            raise

    def create_activity_fields(self):
        """ایجاد حیطه‌های فعالیت"""
        fields = []
        for code, name in [
            ('chicken', 'مرغدار'),
            ('livestock', 'دامدار'),
            ('factory', 'کارخانه خوراک'),
            ('fish', 'پرورش آبزیان'),
            ('corporation', 'تعاونی'),
            ('association', 'اتحادیه'),
            ('dealer', 'دلال'),
        ]:
            field, created = ActivityField.objects.get_or_create(code=code)
            if created:
                fields.append(field)
        return fields

    def create_warehouses(self, count):
        """ایجاد انبارها"""
        warehouses = []
        types = ['supplier', 'primary', 'production', 'secondary', 'consumer']
        
        for i in range(count):
            warehouse_type = random.choice(types)
            warehouse = Warehouse.objects.create(
                warehouse_id=f'WH-{1000 + i:04d}',
                name=f'انبار {self.get_persian_name()}',
                warehouse_type=warehouse_type,
                warehouse_capacity=self.safe_decimal(1000, 50000),
                remaining_capacity=self.safe_decimal(500, 20000),
                used_capacity=self.safe_decimal(100, 15000),
            )
            warehouses.append(warehouse)
        return warehouses

    def create_users(self, count):
        """ایجاد کاربران"""
        users = []
        existing_count = User.objects.count()
        
        if existing_count == 0:
            # ایجاد superuser
            admin = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123',
                first_name='ادمین',
                last_name='سیستم'
            )
            users.append(admin)
        
        for i in range(count):
            username = f'user{i+1}'
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'user{i+1}@example.com',
                    password='123456',
                    first_name=self.get_persian_name(),
                    last_name=self.get_persian_name()
                )
                users.append(user)
        
        return users if users else list(User.objects.all()[:count])

    def create_persons(self, person_type, count, warehouses, users, activity_fields):
        """ایجاد اشخاص"""
        persons = []
        natures = ['legal', 'natural']
        
        consumer_warehouses = [w for w in warehouses if w.warehouse_type == 'consumer']
        
        for i in range(count):
            nature = random.choice(natures)
            national_id = self.generate_national_id()
            
            # برای مشتریان، انبار باید consumer باشد
            warehouse = None
            if person_type == 'customer' and consumer_warehouses:
                warehouse = random.choice(consumer_warehouses)
            elif person_type != 'customer':
                warehouse = random.choice(warehouses) if warehouses else None
            
            person = Person.objects.create(
                national_id=national_id,
                type=person_type,
                name=self.get_company_name() if nature == 'legal' else self.get_persian_name(),
                nature=nature,
                registration_number=f'{random.randint(10000, 99999)}' if nature == 'legal' else None,
                accounting_code=f'ACC-{random.randint(1000, 9999)}',
                phone_number=self.generate_phone_number(),
                warehouse=warehouse,
                sales_expert=random.choice(users) if users else None,
                is_active=random.choice([True, True, True, False]),  # 75% فعال
                description=f'توضیحات برای {person_type}',
            )
            
            # اضافه کردن حیطه فعالیت
            if activity_fields:
                selected_fields = random.sample(activity_fields, k=min(3, len(activity_fields)))
                person.activity_fields.set(selected_fields)
            
            persons.append(person)
        
        return persons

    def create_person_details(self, persons):
        """ایجاد اطلاعات تکمیلی اشخاص (تلفن، آدرس، حساب بانکی)"""
        provinces = ['تهران', 'اصفهان', 'فارس', 'خراسان رضوی', 'آذربایجان شرقی', 'خوزستان', 'مازندران', 'گیلان']
        cities = {
            'تهران': ['تهران', 'کرج', 'ورامین'],
            'اصفهان': ['اصفهان', 'کاشان', 'نجف‌آباد'],
            'فارس': ['شیراز', 'مرودشت', 'کازرون'],
            'خراسان رضوی': ['مشهد', 'نیشابور', 'سبزوار'],
            'آذربایجان شرقی': ['تبریز', 'مراغه', 'میانه'],
            'خوزستان': ['اهواز', 'آبادان', 'دزفول'],
            'مازندران': ['ساری', 'بابل', 'آمل'],
            'گیلان': ['رشت', 'انزلی', 'لاهیجان'],
        }
        banks = ['ملی', 'صادرات', 'ملت', 'تجارت', 'پارسیان', 'سامان', 'پاسارگاد']
        
        person_ct = ContentType.objects.get_for_model(Person)
        
        for person in persons:
            # ایجاد شماره تلفن
            if random.choice([True, True, False]):  # 66% احتمال
                PhoneNumber.objects.create(
                    content_type=person_ct,
                    object_id=person.id,
                    phone_type='mobile',
                    number=self.generate_phone_number(),
                    is_primary=True,
                )
                # شماره ثابت (اختیاری)
                if random.choice([True, False]):
                    PhoneNumber.objects.create(
                        content_type=person_ct,
                        object_id=person.id,
                        phone_type='landline',
                        number=f'0{random.randint(20, 99)}-{random.randint(1000000, 9999999)}',
                        is_primary=False,
                    )
            
            # ایجاد آدرس تحویل (فقط برای مشتریان)
            if person.type == 'customer' and random.choice([True, True, False]):  # 66% احتمال
                province = random.choice(provinces)
                city = random.choice(cities.get(province, [province]))
                postal_code = f'{random.randint(1000000000, 9999999999)}'
                
                DeliveryAddress.objects.create(
                    person=person,
                    postal_code=postal_code,
                    recipient_name=person.name or 'تحویل گیرنده',
                    recipient_national_id=self.generate_national_id(),
                    province=province,
                    city=city,
                    address=f'خیابان {self.get_persian_name()}، کوچه {random.randint(1, 50)}، پلاک {random.randint(1, 200)}',
                    recipient_type=random.choice(['person', 'company', 'warehouse']),
                )
            
            # ایجاد اطلاعات مالی بانکی و حساب بانکی
            if random.choice([True, True, False]):  # 66% احتمال
                province = random.choice(provinces)
                city = random.choice(cities.get(province, [province]))
                financial = FinancialBanking.objects.create(
                    person=person,
                    tax_group=random.choice(['type1', 'type2', 'type3']),
                    account_balance=self.safe_decimal(-10000000, 50000000),
                    economic_code=f'{random.randint(100000000, 999999999)}' if person.nature == 'legal' else None,
                    tax_postal_code=f'{random.randint(1000000000, 9999999999)}',
                    tax_province=province,
                    tax_city=city,
                    tax_address=f'آدرس مالیاتی: {city}، {province}',
                )
                
                # ایجاد حساب بانکی
                if random.choice([True, True, False]):  # 66% احتمال
                    BankAccount.objects.create(
                        financial_banking=financial,
                        account_number=f'{random.randint(1000000000, 9999999999)}',
                        shaba_number=f'IR{random.randint(1000000000000000000000, 9999999999999999999999)}',
                        bank_name=random.choice(banks),
                    )

    def create_products(self, count, warehouses):
        """ایجاد محصولات"""
        products = []
        categories = ['خوراک مرغ', 'خوراک دام', 'خوراک آبزیان', 'پیش‌میکس', 'مکمل']
        subcategories = ['استارتر', 'رشد', 'پایان', 'تخم‌گذار', 'گوشتی']
        grades = ['A', 'B', 'C', 'Premium']
        applications = ['chicken_layer', 'chicken_broiler', 'cow_dairy', 'cow_beef', 'sheep_dairy']
        shapes = ['پلت', 'مش', 'پودر', 'گرانول']
        
        for i in range(count):
            product = Product.objects.create(
                code=f'PRD-{1000 + i:04d}',
                name=f'{random.choice(categories)} {random.choice(subcategories)} {random.choice(grades)}',
                category=random.choice(categories),
                subcategory=random.choice(subcategories),
                grade=random.choice(grades),
                physical_shape=random.choice(shapes),
                main_application=random.choice(applications),
                main_unit='kg',
                secondary_unit='ton',
                conversion_coefficient=Decimal('0.001'),
                min_sales_amount=self.safe_decimal(100, 1000),
                tax_percentage=Decimal(str(random.choice([0, 9]))),
                accounting_code=f'ACC-PRD-{random.randint(100, 999)}',
                min_inventory=self.safe_decimal(500, 5000),
                production_order_point=self.safe_decimal(1000, 10000),
                default_warehouse=random.choice(warehouses) if warehouses else None,
                expiration_date=f'{random.randint(6, 24)} ماه',
                full_description=f'توضیحات کامل محصول {i+1}',
                is_custom=random.choice([True, False]),
            )
            products.append(product)
        
        return products

    def create_raw_materials(self, count, suppliers):
        """ایجاد مواد اولیه"""
        raw_materials = []
        names = ['ذرت', 'سویا', 'گندم', 'جو', 'پنبه دانه', 'کنجاله سویا', 'کنجاله آفتابگردان', 
                 'روغن سویا', 'روغن پالم', 'نمک', 'کربنات کلسیم', 'فسفات دی‌کلسیم']
        forms = ['solid', 'liquid', 'powder', 'granular']
        units = ['kg', 'ton', 'gr']
        
        for i in range(count):
            raw_material = RawMaterial.objects.create(
                name=f'{random.choice(names)} {i+1}',
                physical_form=random.choice(forms),
                primary_unit=random.choice(units),
                secondary_unit=random.choice(units),
                conversion_factor=self.safe_decimal(0.001, 1000, 3),
                status=random.choice(['active', 'active', 'active', 'inactive']),
                main_supplier=random.choice(suppliers) if suppliers else None,
                technical_description=f'توضیحات فنی ماده اولیه {i+1}',
                standard_loss_percentage=self.safe_decimal(0.5, 5, 2),
                expiration_date=f'Q{random.randint(1, 4)}-{random.randint(1403, 1405)}',
            )
            raw_materials.append(raw_material)
        
        return raw_materials

    def create_orders(self, order_type, count, persons, users, products):
        """ایجاد سفارش‌ها"""
        orders = []
        statuses = [
            'pending_proforma_issue',
            'pending_allocation',
            'pending_allocation_approval',
            'pending_factory',
            'pending_unloading_approval',
        ]
        freight_types = ['seller', 'buyer', 'shared']
        
        for i in range(count):
            order_number = Order.generate_order_number()
            order = Order.objects.create(
                order_number=order_number,
                customer=random.choice(persons) if persons else None,
                order_type=order_type,
                registration_source=random.choice(['api', 'expert']),
                status=random.choice(statuses),
                creation_date=jdatetime.date.today() - jdatetime.timedelta(days=random.randint(0, 90)),
                registered_by=random.choice(users) if users else None,
                freight_payment_type=random.choice(freight_types),
            )
            
            # ایجاد اقلام سفارش (بین 2 تا 8 قلم)
            num_items = random.randint(2, min(8, len(products)))
            selected_products = random.sample(products, k=num_items) if len(products) >= num_items else products
            
            total_weight = Decimal('0')
            for product in selected_products:
                weight_unit = random.choice(['kg', 'ton', 'bag'])
                if weight_unit == 'ton':
                    quantity = self.safe_decimal(1, 50)
                elif weight_unit == 'bag':
                    quantity = Decimal(str(random.randint(10, 500)))
                else:
                    quantity = self.safe_decimal(100, 5000)
                
                unit_price = self.safe_decimal(10000, 500000)
                vat_percent = Decimal(str(random.choice([0, 9])))
                discount = self.safe_decimal(0, 100000) if random.choice([True, False]) else Decimal('0')
                additional_charges = self.safe_decimal(0, 50000) if random.choice([True, False]) else Decimal('0')
                
                bag_weight = self.safe_decimal(20, 50) if weight_unit == 'bag' else None
                
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    weight_unit=weight_unit,
                    quantity=quantity,
                    unit_price=unit_price,
                    vat_percent=vat_percent,
                    discount=discount,
                    additional_charges=additional_charges,
                    bag_weight=bag_weight,
                )
                # محاسبه وزن به کیلوگرم
                weight_kg = 0
                if item.quantity:
                    if item.weight_unit == 'kg':
                        weight_kg = float(item.quantity)
                    elif item.weight_unit == 'ton':
                        weight_kg = float(item.quantity) * 1000
                    elif item.weight_unit == 'bag' and item.bag_weight:
                        weight_kg = float(item.quantity) * float(item.bag_weight)
                    elif item.weight_unit == 'piece':
                        weight_kg = float(item.quantity)
                
                if weight_kg > 0:
                    total_weight += Decimal(str(round(weight_kg, 2)))
            
            # به‌روزرسانی وزن کل سفارش
            if total_weight > 0:
                order.total_shipment_weight = total_weight
                delivery_factor = self.safe_decimal(0.95, 1.0, 4)
                order.total_delivery_weight = (total_weight * delivery_factor).quantize(Decimal('0.01'))
            else:
                order.total_shipment_weight = Decimal('0')
                order.total_delivery_weight = Decimal('0')
            order.save()
            
            orders.append(order)
        
        return orders

    def create_proformas(self, count, orders):
        """ایجاد پیش فاکتورها"""
        proformas = []
        
        selected_orders = random.sample(orders, k=min(count, len(orders))) if orders else []
        
        for order in selected_orders:
            proforma = Proforma.objects.create(
                order=order,
                proforma_number=f'PRO-{random.randint(10000, 99999)}',
                validity_date=jdatetime.date.today() + jdatetime.timedelta(days=random.randint(7, 30)),
                customer=order.customer,
            )
            proformas.append(proforma)
        
        return proformas

    def create_invoices(self, count, orders):
        """ایجاد فاکتورها"""
        invoices = []
        tax_types = ['type1', 'type2', 'type3']
        
        selected_orders = random.sample(orders, k=min(count, len(orders))) if orders else []
        
        for order in selected_orders:
            invoice = Invoice.objects.create(
                order=order,
                tax_invoice_number=f'INV-{random.randint(10000, 99999)}',
                issue_date=jdatetime.date.today() - jdatetime.timedelta(days=random.randint(0, 30)),
                customer_tax_type=random.choice(tax_types),
            )
            invoices.append(invoice)
        
        return invoices

    def create_production_programs(self, count, products):
        """ایجاد برنامه‌های تولید"""
        programs = []
        statuses = ['draft', 'confirmed', 'in_progress', 'completed']
        packaging_types = ['bulk', 'bag', 'carton']
        
        for i in range(count):
            start_date = jdatetime.date.today() + jdatetime.timedelta(days=random.randint(1, 30))
            end_date = start_date + jdatetime.timedelta(days=random.randint(1, 7))
            
            program = ProductionProgram.objects.create(
                program_id=f'PRG-{random.randint(10000, 99999)}',
                product=random.choice(products) if products else None,
                planned_weight_ton=self.safe_decimal(10, 100),
                predicted_start_date=start_date,
                predicted_end_date=end_date,
                packaging_type=random.choice(packaging_types),
                status=random.choice(statuses),
                extra_description=f'توضیحات برنامه تولید {i+1}',
                produced_weight_ton=self.safe_decimal(8, 95) if random.choice([True, False]) else None,
            )
            programs.append(program)
        
        return programs

    def create_allocations(self, count, orders, products):
        """ایجاد تخصیص‌ها"""
        allocations = []
        statuses = ['planned', 'pending_approval', 'pending_shipping', 'completed', 'canceled']
        shipping_methods = ['customer_vehicle', 'carrier']
        
        selected_orders = random.sample(orders, k=min(count, len(orders))) if orders else []
        
        for order in selected_orders:
            allocation = Allocation.objects.create(
                allocation_number=f'ALLOC-{random.randint(10000, 99999)}',
                order=order,
                allocation_status=random.choice(statuses),
                allocation_priority=random.randint(1, 10),
                shipping_announcement_method=random.choice(shipping_methods),
                delivery_postal_code=f'{random.randint(1000000000, 9999999999)}',
                requested_machine=f'ماشین {random.choice(["کامیون", "تریلی", "کامیونت"])}',
            )
            allocations.append(allocation)
        
        return allocations

    def create_trucks(self, count, transports):
        """ایجاد خودروها"""
        trucks = []
        vehicle_types = ['truck', 'trailer', 'van', 'pickup', 'other']
        loading_types = ['open', 'closed', 'refrigerated', 'tank', 'flatbed', 'other']
        manufacturers = ['بنز', 'وولو', 'اسکانیا', 'مک', 'کاترپیلار', 'کماز', 'ایران‌خودرو']
        
        selected_transports = random.sample(transports, k=min(count, len(transports))) if transports else []
        
        for i in range(count):
            transport = random.choice(selected_transports) if selected_transports else None
            truck = TruckInfo.objects.create(
                plate_number=f'{random.randint(10, 99)}-{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}-{random.randint(100, 999)}-{random.randint(10, 99)}',
                transport=transport,
                vehicle_type=random.choice(vehicle_types),
                loading_type=random.choice(loading_types),
                manufacturer=random.choice(manufacturers),
                is_smart_truck=random.choice([True, False]),
            )
            trucks.append(truck)
        
        return trucks

    def create_transports(self, count, allocations):
        """ایجاد حمل‌ها"""
        transports = []
        statuses = ['pending_recruitment_completion', 'pending_vehicle_entry', 'vehicle_entered', 
                    'loading', 'loaded', 'in_transit', 'delivered', 'completed']
        directions = ['inbound', 'outbound']
        
        selected_allocations = random.sample(allocations, k=min(count, len(allocations))) if allocations else []
        drivers = list(Person.objects.filter(type='driver')[:count])
        
        for i in range(count):
            allocation = random.choice(selected_allocations) if selected_allocations else None
            transport = Transport.objects.create(
                waybill_number=f'TRANS-{random.randint(10000, 99999)}',
                allocation=allocation,
                driver=random.choice(drivers) if drivers else None,
                status=random.choice(statuses),
                direction=random.choice(directions),
                loading_date=jdatetime.date.today() - jdatetime.timedelta(days=random.randint(0, 15)),
                unloading_date=jdatetime.date.today() - jdatetime.timedelta(days=random.randint(0, 10)) if random.choice([True, False]) else None,
                waybill_date=jdatetime.date.today() - jdatetime.timedelta(days=random.randint(0, 5)),
            )
            transports.append(transport)
        
        return transports

    def create_procurement_orders(self, count, suppliers, raw_materials, users):
        """ایجاد سفارش‌های خرید تامین"""
        orders = []
        statuses = ['draft', 'awaiting_transport_def', 'awaiting_vehicle_entry', 
                    'awaiting_delivery', 'awaiting_wh_reconciliation', 'completed']
        freight_payment_types = ['cash', 'credit', 'included', 'separate']
        
        for i in range(count):
            order = ProcurementPurchaseOrder.objects.create(
                supplier=random.choice(suppliers) if suppliers else None,
                status=random.choice(statuses),
                freight_payment_type=random.choice(freight_payment_types),
                subtotal_without_freight=self.safe_decimal(1000000, 50000000),
                freight_cost=self.safe_decimal(100000, 5000000),
                vat_percentage=Decimal(str(random.choice([0, 9]))),
                created_by=random.choice(users) if users else None,
            )
            
            # ایجاد مواد اولیه برای این سفارش
            num_materials = random.randint(1, min(5, len(raw_materials)))
            selected_materials = random.sample(raw_materials, k=num_materials) if raw_materials else []
            
            total_subtotal = Decimal(0)
            for raw_material in selected_materials:
                quantity = self.safe_decimal(100, 5000, 3)
                unit_price = self.safe_decimal(5000, 50000)
                total_price = quantity * unit_price
                total_subtotal += total_price
                
                ProcurementPurchaseOrderMaterial.objects.create(
                    purchase_order=order,
                    raw_material=raw_material,
                    quantity=quantity,
                    unit=raw_material.primary_unit or 'kg',
                    unit_price=unit_price,
                    total_price=total_price,
                    freight_included=random.choice([True, False]),
                )
            
            # به‌روزرسانی subtotal سفارش
            if total_subtotal > 0:
                order.subtotal_without_freight = total_subtotal
                order.save()
            
            orders.append(order)
        
        return orders

    def create_stock_entries(self, count, warehouses, products, raw_materials):
        """ایجاد ورودی‌های انبار"""
        entries = []
        
        for i in range(count):
            # برای jDateTimeField باید از datetime استفاده کنیم
            transaction_datetime = timezone.now() - timedelta(days=random.randint(0, 30))
            entry = StockEntry.objects.create(
                transaction_date=transaction_datetime,
                notes=f'یادداشت ورودی انبار {i+1}',
                is_committed=random.choice([True, True, False]),  # 66% committed
            )
            entries.append(entry)
        
        return entries

    # Helper methods
    def generate_national_id(self):
        """تولید کد ملی فیک"""
        return ''.join([str(random.randint(0, 9)) for _ in range(10)])

    def generate_phone_number(self):
        """تولید شماره تلفن فیک"""
        prefixes = ['0912', '0913', '0914', '0915', '0916', '0917', '0918', '0919', '0921', '0935', '0936', '0937', '0938', '0939']
        return f'{random.choice(prefixes)}{random.randint(1000000, 9999999)}'

    def get_persian_name(self):
        """تولید نام فارسی فیک"""
        first_names = ['علی', 'محمد', 'حسن', 'حسین', 'رضا', 'امیر', 'سعید', 'مهدی', 'احمد', 'حامد', 
                      'فاطمه', 'زهرا', 'مریم', 'سارا', 'نرگس', 'لیلا', 'سمیرا', 'نیلوفر']
        last_names = ['احمدی', 'محمدی', 'حسینی', 'رضایی', 'کریمی', 'موسوی', 'نوری', 'صادقی', 
                     'جعفری', 'عباسی', 'اکبری', 'امینی', 'حیدری', 'کاظمی']
        return f'{random.choice(first_names)} {random.choice(last_names)}'
    
    def safe_decimal(self, min_val, max_val, decimal_places=2):
        """ایجاد مقدار Decimal معتبر از یک محدوده"""
        value = random.uniform(min_val, max_val)
        return Decimal(str(round(value, decimal_places)))

    def get_company_name(self):
        """تولید نام شرکت فیک"""
        prefixes = ['شرکت', 'مجتمع', 'کارخانه', 'تعاونی']
        suffixes = ['کشت و صنعت', 'دامپروری', 'تولیدی', 'صنعتی', 'کشاورزی', 'خوراک دام']
        names = ['پارس', 'ایران', 'گلستان', 'شیراز', 'اصفهان', 'تبریز', 'مشهد', 'تهران', 'یزد', 'کرمان']
        return f'{random.choice(prefixes)} {random.choice(names)} {random.choice(suffixes)}'

