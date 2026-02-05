"""
Management command to run makemigrations for all installed apps
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Run makemigrations for all installed apps that have models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what migrations would be made without actually creating them',
        )
        parser.add_argument(
            '--merge',
            action='store_true',
            help='Enable fixing of migration conflicts',
        )
        parser.add_argument(
            '--empty',
            action='store_true',
            help='Create an empty migration file',
        )
        parser.add_argument(
            '--noinput',
            '--no-input',
            action='store_true',
            help='Tells Django to NOT prompt the user for input of any kind.',
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Use this name for migration file(s)',
        )
    
    def handle(self, *args, **options):
        # Get all installed apps (excluding Django's built-in apps and third-party apps)
        django_apps = {
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
        }
        
        # Get all installed apps from settings
        installed_apps = []
        for app in settings.INSTALLED_APPS:
            # Skip Django's built-in apps (check full path)
            if app in django_apps:
                continue
            
            # Skip any app that starts with 'django.' (all Django contrib apps)
            if app.startswith('django.'):
                continue
            
            # Skip third-party apps that don't need migrations
            if app.startswith('django_jalali') or app.startswith('django_tables2'):
                continue
            
            # Extract app name (handle both 'app_name' and 'app_name.apps.AppConfig')
            if '.' in app:
                app_name = app.split('.')[0]
            else:
                app_name = app
            
            # Only add if not already in the list (avoid duplicates)
            if app_name not in installed_apps:
                installed_apps.append(app_name)
        
        self.stdout.write(
            self.style.SUCCESS(f'Running makemigrations for {len(installed_apps)} apps...')
        )
        self.stdout.write('')
        
        # Prepare options for makemigrations
        makemigrations_options = {}
        if options.get('dry_run'):
            makemigrations_options['dry_run'] = True
        if options.get('merge'):
            makemigrations_options['merge'] = True
        if options.get('empty'):
            makemigrations_options['empty'] = True
        if options.get('noinput'):
            makemigrations_options['interactive'] = False
        if options.get('name'):
            makemigrations_options['name'] = options['name']
        
        # Run makemigrations for all apps
        for app_name in installed_apps:
            self.stdout.write(f'Processing {app_name}...', ending=' ')
            try:
                # Run makemigrations for this app
                call_command('makemigrations', app_name, **makemigrations_options)
                self.stdout.write(self.style.SUCCESS('✓'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('Done! All apps have been processed.')
        )

