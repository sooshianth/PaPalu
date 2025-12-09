from django import template
from core.RBACModel.Roles import user_has_task

register = template.Library()


@register.simple_tag
def has_task_permission(user, task_code):
    """
    بررسی اینکه آیا کاربر دسترسی به task خاصی دارد یا نه
    
    استفاده در template:
    {% load rbac_tags %}
    {% has_task_permission user 'sales.create_order' as can_create_order %}
    {% if can_create_order %}
        <!-- نمایش محتوا -->
    {% endif %}
    """
    return user_has_task(user, task_code)


@register.filter
def has_task(user, task_code):
    """
    بررسی دسترسی به task به صورت filter
    
    استفاده در template:
    {% load rbac_tags %}
    {% if user|has_task:'sales.create_order' %}
        <!-- نمایش محتوا -->
    {% endif %}
    """
    return user_has_task(user, task_code)

