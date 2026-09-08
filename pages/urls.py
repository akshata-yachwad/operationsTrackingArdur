from django.urls import path

from pages.views import (
    ChatPage,
    DashboardPage,
    HomeRedirect,
    LoginPage,
    SignupPage,
    SettingsPage,
    UserDashboardPage,
    ProfileSetupPage,
)

app_name = "pages"

urlpatterns = [
    path("", HomeRedirect.as_view(), name="home"),
    path("login/", LoginPage.as_view(), name="login"),
    path("signup/", SignupPage.as_view(), name="signup"),
    path("dashboard/", DashboardPage.as_view(), name="dashboard"),
    path("userdashboard/", UserDashboardPage.as_view(), name="userdashboard"),
    path("profile-setup/", ProfileSetupPage.as_view(), name="profile_setup"),
    path("settings/", SettingsPage.as_view(), name="settings"),
    path("chat/", ChatPage.as_view(), name="chat"),
]
