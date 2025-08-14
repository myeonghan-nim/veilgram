from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnlyProfile(BasePermission):
    def has_permission(self, request, view):
        if view.action in ("create", "me", "availability"):
            return request.user and request.user.is_authenticated
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, "user_id", None) == getattr(request.user, "id", None)
