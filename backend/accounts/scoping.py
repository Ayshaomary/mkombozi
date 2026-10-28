"""Tools that keep each business's data separate from every other business."""

import uuid

from rest_framework import serializers


def find_by_client_id(queryset, client_id):
    """The record a phone already sent with this client_id, if any.

    Phones that record sales or expenses offline may send the same one twice (for example when the
    network drops before the answer arrives), so the second time we return the first record.
    """
    try:
        client_id = uuid.UUID(str(client_id))
    except (TypeError, ValueError, AttributeError):
        return None
    return queryset.filter(client_id=client_id).first()


class BusinessScopedMixin:
    """For ViewSets: only show records of the user's business, and attach new records to it."""

    def get_queryset(self):
        return super().get_queryset().filter(business=self.request.user.business)

    def perform_create(self, serializer):
        extra = {'business': self.request.user.business}
        if any(f.name == 'created_by' for f in serializer.Meta.model._meta.fields):
            extra['created_by'] = self.request.user
        serializer.save(**extra)


class BusinessScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A foreign-key field that only accepts objects from the user's own business."""

    def get_queryset(self):
        request = self.context['request']
        return super().get_queryset().filter(business=request.user.business)
