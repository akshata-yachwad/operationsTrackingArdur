"""Shared API query serializers."""

from __future__ import annotations

from datetime import date

from rest_framework import serializers


class DateRangeQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "The end date must be on or after the start date."}
            )
        return attrs


def parse_date_range(query_params) -> tuple[date | None, date | None]:
    """Parse optional ``from``/``to`` query parameters, rejecting bad ranges."""
    serializer = DateRangeQuerySerializer(
        data={
            "date_from": query_params.get("from") or None,
            "date_to": query_params.get("to") or None,
        }
    )
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data.get("date_from"), serializer.validated_data.get("date_to")
