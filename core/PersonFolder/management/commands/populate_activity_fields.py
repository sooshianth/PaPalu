from django.core.management.base import BaseCommand
from core.PersonFolder.PersonModel import ActivityField, FIELD_OF_ACTIVITY


class Command(BaseCommand):
    help = 'ایجاد حیطه‌های فعالیت از لیست تعریف شده'

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0
        
        for code, label in FIELD_OF_ACTIVITY:
            activity_field, created = ActivityField.objects.get_or_create(
                code=code
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ حیطه فعالیت "{label}" ({code}) ایجاد شد')
                )
            else:
                existing_count += 1
                self.stdout.write(
                    self.style.WARNING(f'- حیطه فعالیت "{label}" ({code}) قبلاً وجود داشت')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ تعداد {created_count} حیطه فعالیت جدید ایجاد شد'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f'- تعداد {existing_count} حیطه فعالیت قبلاً وجود داشت'
            )
        )

