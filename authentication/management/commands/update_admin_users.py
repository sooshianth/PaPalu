from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from authentication.models import UserPhoneNumber

class Command(BaseCommand):
    help = 'تبدیل کاربران با شماره ادمین به superuser'

    def handle(self, *args, **options):
        self.stdout.write(f"شماره‌های ادمین تعریف شده: {settings.ADMIN_PHONE_NUMBERS}")
        
        if not settings.ADMIN_PHONE_NUMBERS:
            self.stdout.write(self.style.WARNING('هیچ شماره ادمینی تعریف نشده است!'))
            return
        
        updated_count = 0
        for admin_phone in settings.ADMIN_PHONE_NUMBERS:
            try:
                user_phone = UserPhoneNumber.objects.get(phone_number=admin_phone)
                user = user_phone.user
                
                if not user.is_superuser or not user.is_staff:
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'کاربر {user.username} ({admin_phone}) به superuser تبدیل شد'
                        )
                    )
                else:
                    self.stdout.write(
                        f'کاربر {user.username} ({admin_phone}) از قبل superuser است'
                    )
                    
            except UserPhoneNumber.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'کاربری با شماره {admin_phone} یافت نشد'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'تعداد {updated_count} کاربر به‌روزرسانی شد')
        )
