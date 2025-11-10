from django.contrib import admin
from django import forms
from . import TaskPermission, Role, UserTaskPermission, TaskChoices


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
    list_display = ['name', 'task_permission', 'description']
    list_filter = ['name']
    filter_horizontal = ['users']
    search_fields = ['name', 'description']


@admin.register(UserTaskPermission)
class UserTaskPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'task_permission']
    search_fields = ['user__username', 'task_permission__name']
    list_filter = ['task_permission']
