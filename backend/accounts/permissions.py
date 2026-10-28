from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasBusiness(BasePermission):
    """The user is logged in and belongs to a business."""

    message = 'Your account is not linked to a business.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.business_id)


def can(read=None, create=None, change=None, delete=None):
    """A permission class: which accounts.models.Permission a user needs to view (GET), add (POST),
    change (PUT/PATCH) and delete. None means any user of the business; a tuple means all of them.

    Example: permission_classes = [HasBusiness, can(read='sales', create='sales', delete='manage')]
    """
    by_method = {'POST': create, 'PUT': change, 'PATCH': change, 'DELETE': delete}

    class CanPermission(BasePermission):
        message = 'You are not allowed to do this. Ask the shop owner.'

        def has_permission(self, request, view):
            needed = read if request.method in SAFE_METHODS else by_method.get(request.method)
            if needed is None:
                return True
            needed = (needed,) if isinstance(needed, str) else needed
            return all(request.user.can(permission) for permission in needed)

    return CanPermission


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
