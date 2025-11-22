# Generated manually for warehouse production declaration fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '__first__'),  # Replace with actual last migration if exists
    ]

    operations = [
        migrations.AddField(
            model_name='productionprogram',
            name='confirmed_by_warehouseman',
            field=models.BooleanField(default=False, help_text='آیا این برنامه تولید توسط انباردار تایید شده است؟', verbose_name='تایید شده توسط انبار'),
        ),
        migrations.AddField(
            model_name='productionprogram',
            name='sent_to_manager_for_revalidation',
            field=models.BooleanField(default=False, help_text='آیا این برنامه برای بررسی مجدد به مدیر ارسال شده است؟', verbose_name='ارسال شده به مدیر برای بررسی مجدد'),
        ),
        migrations.AddField(
            model_name='productionprogram',
            name='reason_for_warehouse_disapprove',
            field=models.TextField(blank=True, help_text='دلیل رد کردن برنامه تولید توسط انباردار', null=True, verbose_name='دلیل عدم تایید توسط انبار'),
        ),
    ]
