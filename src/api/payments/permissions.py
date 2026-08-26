from rest_framework.permissions import BasePermission

from shop_epower.accounts.models import Role


class IsAdmin(BasePermission):

    def has_permission(
        self,
        request,
        view,
    ):

        return (
            request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsManagerOrAdmin(BasePermission):
    """
    Разрешает доступ только менеджерам и администраторам.
    """

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role in (
                Role.MANAGER,
                Role.ADMIN,
            )
        )