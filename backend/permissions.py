from rest_framework.permissions import BasePermission


class IsVendor(BasePermission):
    message = "You must be a vendor to access this resource."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type == 'shop'






