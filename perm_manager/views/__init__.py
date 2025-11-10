# Import all views for backward compatibility
from .home import permissions_home_view
from .task_permissions import (
    task_permissions_view,
    save_task_permissions,
    add_task_permission,
    delete_task_permission
)
from .roles import (
    roles_view,
    add_role,
    update_role,
    delete_role
)
from .users import (
    users_view,
    save_user_assignments
)

__all__ = [
    'permissions_home_view',
    'task_permissions_view',
    'save_task_permissions',
    'add_task_permission',
    'delete_task_permission',
    'roles_view',
    'add_role',
    'update_role',
    'delete_role',
    'users_view',
    'save_user_assignments',
]

