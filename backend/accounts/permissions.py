from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasBusiness(BasePermission):
    """The user is logged in and belongs to a business."""

    message = 'Your account is not linked to a business.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.business_id)


class IsOwner(BasePermission):
    """Only the business owner."""

    message = 'Only the business owner can do this.'

    def has_permission(self, request, view):
        return request.user.is_owner


class IsOwnerOrReadOnly(BasePermission):
    """Staff can view; only the owner can add, change or delete."""

    message = 'Only the business owner can do this.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_owner


class IsOwnerOrCreateOnly(BasePermission):
    """Staff can view and add (e.g. record a sale); only the owner can change or delete."""

    message = 'Only the business owner can change or delete records.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.method == 'POST' or request.user.is_owner
