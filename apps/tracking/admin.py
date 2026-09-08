from django.contrib import admin

from apps.tracking.models import Target, WorkSession, Attendance


@admin.register(WorkSession)
class WorkSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "emp_id", "project", "work_type", "start_time",
        "end_time", "total_time", "is_started",
    )
    list_filter = ("is_started", "is_paused", "project", "work_type")
    search_fields = ("emp_id", "name", "project", "batch", "allocation_id")
    # date_hierarchy = "start_time"
    ordering = ("-start_time",)
    readonly_fields = ("total_time", "paused_elapsed")


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = (
        "emp_id", "project", "target_date", "target_units",
        "achieved_units", "completion_percent",
    )
    list_filter = ("target_date", "project")
    search_fields = ("emp_id", "project")
    # date_hierarchy = "target_date"


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "emp_id", "date", "status", "first_login", "last_logout", "total_break_time"
    )
    list_filter = ("status", "date")
    search_fields = ("emp_id",)
    ordering = ("-date",)
