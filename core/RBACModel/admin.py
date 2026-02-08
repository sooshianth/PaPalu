from django.contrib import admin
from django import forms
from . import TaskPermission, Role, UserTaskPermission, TaskChoices, FieldPermission, FieldChoice, UserFieldPermission, ManagedField


class TaskPermissionForm(forms.ModelForm):
    tasks = forms.MultipleChoiceField(
        choices=TaskChoices.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select tasks for this permission set"
    )
    
    class Meta:
        model = TaskPermission
        fields = ['name', 'tasks']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.tasks:
            self.initial['tasks'] = self.instance.tasks
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tasks = self.cleaned_data['tasks']
        if commit:
            instance.save()
        return instance


@admin.register(TaskPermission)
class TaskPermissionAdmin(admin.ModelAdmin):
    form = TaskPermissionForm
    list_display = ['name', 'get_tasks_display']
    search_fields = ['name']
    
    def get_tasks_display(self, obj):
        return ', '.join([TaskChoices(task).label for task in obj.tasks if task in TaskChoices.values])
    get_tasks_display.short_description = 'Tasks'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    list_filter = ['name']
    filter_horizontal = ['users']
    search_fields = ['name', 'description']


@admin.register(UserTaskPermission)
class UserTaskPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'task_permission']
    search_fields = ['user__username', 'task_permission__name']
    list_filter = ['task_permission']


class FieldChoiceInline(admin.TabularInline):
    model = FieldChoice
    extra = 1
    fields = ['content_type', 'field_name', 'access_type', 'allowed']


@admin.register(FieldPermission)
class FieldPermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'description', 'created_at', 'updated_at']
    list_filter = ['role']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [FieldChoiceInline]
    autocomplete_fields = ['role']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'description')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FieldChoice)
class FieldChoiceAdmin(admin.ModelAdmin):
    list_display = [
        'field_permission',
        'content_type', 
        'field_name', 
        'access_type', 
        'allowed',
        'created_at'
    ]
    
    list_filter = [
        'access_type', 
        'allowed', 
        'content_type',
        'field_permission'
    ]
    
    search_fields = [
        'field_permission__name',
        'field_name'
    ]
    
    autocomplete_fields = ['field_permission']
    
    fieldsets = (
        ('اطلاعات مجوز', {
            'fields': ('field_permission',)
        }),
        ('اطلاعات مدل و فیلد', {
            'fields': ('content_type', 'field_name')
        }),
        ('تنظیمات دسترسی', {
            'fields': ('access_type', 'allowed')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('field_permission', 'content_type')


@admin.register(UserFieldPermission)
class UserFieldPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'field_permission']
    search_fields = ['user__username', 'user__email', 'field_permission__name']
    autocomplete_fields = ['user', 'field_permission']
    
    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('user',)
        }),
        ('مجوز دسترسی فیلد', {
            'fields': ('field_permission',)
        }),
    )


@admin.register(ManagedField)
class ManagedFieldAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'field_name', 'field_label', 'created_at']
    list_filter = ['content_type']
    search_fields = ['field_name', 'field_label']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('اطلاعات فیلد', {
            'fields': ('content_type', 'field_name', 'field_label')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
