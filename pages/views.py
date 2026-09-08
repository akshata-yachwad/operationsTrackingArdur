"""Page views.

Thin by design: render a shell, hand it the bootstrap context, and let the
JavaScript fetch its data from /api/v1/. No queryset ever reaches a template.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from pages.context import base_context


@method_decorator(never_cache, name='dispatch')
class BasePage(LoginRequiredMixin, TemplateView):
    """Every page except login requires a session."""

    login_url = "/login/"
    redirect_field_name = None
    page_title = "OpsTracking"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not getattr(request.user, 'is_super_admin', False):
            from apps.accounts.models import Employee
            emp = Employee.objects.filter(employee_id=request.user.emp_id).first()
            if emp:
                # Mandatory fields required for completion
                if not emp.email or not emp.phone or not emp.department or not emp.shift or not emp.date_of_joining:
                    return redirect(reverse("pages:profile_setup"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(base_context(self.request, page_title=self.page_title))
        return context

class ProfileSetupPage(LoginRequiredMixin, TemplateView):
    """GET /profile-setup/ — mandatory profile completion on first login."""

    template_name = "profile_setup.html"
    login_url = "/login/"
    redirect_field_name = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.accounts.models import Employee
        emp = Employee.objects.filter(employee_id=self.request.user.emp_id).first()
        context.update(base_context(self.request, page_title="Complete Your Profile"))
        context['employee'] = emp
        return context

    def post(self, request, *args, **kwargs):
        from apps.accounts.models import Employee
        emp = Employee.objects.filter(employee_id=request.user.emp_id).first()
        if not emp:
            return redirect(reverse("pages:home"))

        # Save the mandatory fields
        emp.email = request.POST.get("email", "").strip()
        emp.phone = request.POST.get("phone", "").strip()
        emp.alternate_phone = request.POST.get("alternate_phone", "").strip()
        emp.shift = request.POST.get("shift", "").strip()
        emp.department = request.POST.get("department", "").strip()
        
        emp_type = request.POST.get("employee_type")
        if emp_type:
            emp.employee_type = emp_type
            
        doj = request.POST.get("date_of_joining")
        if doj:
            emp.date_of_joining = doj
            
        emp.save()
        
        # After saving, redirect to home which will route them to their dashboard
        return redirect(reverse("pages:home"))



class LoginPage(TemplateView):
    """GET /login/ — the only unauthenticated page."""

    template_name = "login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_home_for(request.user))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            base_context(
                self.request,
                page_title="Sign in",
                reason=self.request.GET.get("reason", ""),
                next_url=self.request.GET.get("next", ""),
            )
        )
        return context


class SignupPage(TemplateView):
    """GET /signup/ — registration page."""

    template_name = "signup.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_home_for(request.user))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            base_context(
                self.request,
                page_title="Sign Up",
            )
        )
        return context


class HomeRedirect(LoginRequiredMixin, TemplateView):
    """GET / — send people to the right dashboard for their role."""

    login_url = "/login/"
    redirect_field_name = None

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(_home_for(request.user))


class DashboardPage(BasePage):
    """Supervisor and admin dashboard."""

    template_name = "dashboard.html"
    page_title = "Dashboard"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not getattr(request.user, 'is_team_lead', False):
            return redirect(reverse("pages:userdashboard"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        is_title_indexing_only = False
        if getattr(user, 'is_team_lead', False) and not getattr(user, 'is_super_admin', False):
            authorized = user.get_authorized_projects()
            if authorized:
                from django.apps import apps
                Project = apps.get_model('masters', 'Project')
                from django.db.models import Q
                q_objs = Q()
                for p in authorized:
                    q_objs |= Q(project_id__iexact=p) | Q(project_name__iexact=p)
                projects = Project.objects.filter(q_objs)
                
                has_title_indexing = False
                has_other = False
                for proj in projects:
                    if "title indexing" in proj.project_name.lower():
                        has_title_indexing = True
                    else:
                        has_other = True
                if has_title_indexing and not has_other:
                    is_title_indexing_only = True
                    
        context["is_title_indexing_only"] = is_title_indexing_only
        return context


class UserDashboardPage(BasePage):
    """The employee's own screen: work timer, breaks, tasks, feedback."""

    template_name = "userdashboard.html"
    page_title = "User Dashboard"

    def get(self, request, *args, **kwargs):
        self.is_simplified = False
        user = request.user
        if hasattr(user, 'employee') and user.employee and user.employee.project:
            import re
            project_ids = [p.strip() for p in re.split(r'[,|]', user.employee.project) if p.strip()]
            from django.apps import apps
            Project = apps.get_model('masters', 'Project')
            projects = Project.objects.filter(project_id__in=project_ids)
            for proj in projects:
                if getattr(proj, 'is_simplified_project', False):
                    self.is_simplified = True
                    break
        return super().get(request, *args, **kwargs)

    

    def get_context_data(self, **kwargs):
        from datetime import date
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["username"] = getattr(user, "name", "") or getattr(user, "emp_id", "") or str(user)
        context["role"] = getattr(user, "role", "employee")
        context["current_date"] = date.today().strftime("%Y-%m-%d")
        context["emp_id"] = getattr(user, "emp_id", "")
        context["is_simplified"] = getattr(self, 'is_simplified', False)
        
        is_title_indexing = False
        if hasattr(user, 'employee') and user.employee and user.employee.project:
            import re
            project_ids = [p.strip() for p in re.split(r'[,|]', user.employee.project) if p.strip()]
            from django.apps import apps
            Project = apps.get_model('masters', 'Project')
            projects = Project.objects.filter(project_id__in=project_ids)
            for proj in projects:
                if "title indexing" in getattr(proj, 'project_name', '').lower():
                    is_title_indexing = True
                    break
        context["is_title_indexing"] = is_title_indexing
        
        return context



class SettingsPage(BasePage):
    """Application settings. Admin only."""

    template_name = "settings.html"
    page_title = "Settings"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_admin:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["username"] = getattr(user, "name", "") or getattr(user, "emp_id", "") or str(user)
        context["role"] = getattr(user, "role", "admin")
        context["emp_id"] = getattr(user, "emp_id", "")
        return context


class ChatPage(BasePage):
    """Chat — reachable only when FEATURE_CHAT is on.

    Returns 404 rather than a "coming soon" page: an unfinished feature should
    be invisible, not advertised.
    """

    template_name = "chat.html"
    page_title = "Chat"

    def dispatch(self, request, *args, **kwargs):
        if not settings.FEATURE_CHAT:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def _home_for(user) -> str:
    return reverse("pages:dashboard") if user.is_supervisor else reverse("pages:userdashboard")
