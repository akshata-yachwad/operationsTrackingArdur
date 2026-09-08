"""Master data serializers.

Every name field carries an explicit ``max_length`` matched to the column and
a non-blank validator — the two failures these tables historically had were
whitespace-only names and silent truncation.
"""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.masters.models import ClientCode, Project, Shift, WorkType
from core.validators import validate_safe_name


class WorkTypeSerializer(serializers.ModelSerializer):
    work_type = serializers.CharField(
        max_length=100,
        validators=[validate_safe_name, UniqueValidator(
            queryset=WorkType.objects.all(),
            message="A work type with this name already exists.",
        )],
    )
    # Legacy alias fields — keep the JS working during migration
    wt_id = serializers.CharField(required=False, default="", allow_blank=True)
    class Meta:
        model = WorkType
        fields = [
            "id", "wt_id",
            "work_type", "description", "standard_rate",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        max_length=150,
        validators=[validate_safe_name, UniqueValidator(
            queryset=Project.objects.all(),
            message="A project with this name already exists.",
        )],
    )
    # Legacy alias fields — keep the JS working during migration
    project_id = serializers.CharField(required=False, default="", allow_blank=True)
    client_code = serializers.CharField(required=False, default="", allow_blank=True)
    worktypes = serializers.CharField(required=False, default="", allow_blank=True)

    class Meta:
        model = Project
        fields = [
            "id", "project_id", "project_name", "project_code", "client_name",
            "client_code", "worktypes",
            "start_date", "end_date", "requires_attendance", "is_simplified_project", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and start > end:
            raise serializers.ValidationError(
                {"end_date": "The end date must be on or after the start date."}
            )
        return attrs


class ClientCodeSerializer(serializers.ModelSerializer):
    client_code = serializers.CharField(
        max_length=50,
        validators=[validate_safe_name, UniqueValidator(
            queryset=ClientCode.objects.all(),
            message="This client code already exists.",
        )],
    )
    # Legacy alias fields — keep the JS working during migration
    cc_id = serializers.CharField(required=False, default="", allow_blank=True)
    worktypes = serializers.CharField(required=False, default="", allow_blank=True)

    class Meta:
        model = ClientCode
        fields = [
            "id", "cc_id", "client_code", "client_name", "project",
            "worktypes", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ShiftSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(
        max_length=50,
        validators=[validate_safe_name, UniqueValidator(
            queryset=Shift.objects.all(),
            message="A shift with this name already exists.",
        )],
    )
    is_overnight = serializers.BooleanField(read_only=True)

    class Meta:
        model = Shift
        fields = [
            "id", "shift_name", "start_time", "end_time", "break_minutes",
            "is_overnight", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_overnight"]

    def validate_break_minutes(self, value: int) -> int:
        if value < 0 or value > 240:
            raise serializers.ValidationError("Break minutes must be between 0 and 240.")
        return value


class MasterBundleSerializer(serializers.Serializer):
    """Everything a page needs to populate its dropdowns, in one request.

    Saves four round-trips on every screen load; the result is cached, so it
    usually costs no queries at all.
    """

    work_types = WorkTypeSerializer(many=True, read_only=True)
    projects = ProjectSerializer(many=True, read_only=True)
    client_codes = ClientCodeSerializer(many=True, read_only=True)
    shifts = ShiftSerializer(many=True, read_only=True)
