from django.urls import path

from . import views

app_name = "kcms_app"

urlpatterns = [
    path("", views.home, name="home"),
    path("assets/logo/", views.logo_image, name="logo_image"),
    path("assets/hero/", views.hero_image, name="hero_image"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("dashboard/report/", views.dashboard_report, name="dashboard_report"),
    path("exports/case-records.csv", views.export_case_records_csv, name="export_case_records_csv"),
    path("exports/blacklisted-records.csv", views.export_blacklisted_csv, name="export_blacklisted_csv"),
    path("kp-form-7/", views.kp_form_7, name="kp_form_7"),
    path("kp-form-9/", views.kp_form_9, name="kp_form_9"),
    path("kp-form-14/", views.kp_form_14, name="kp_form_14"),
    path("kp-form-20/", views.kp_form_20, name="kp_form_20"),
    path("case/<int:case_id>/toggle-status/", views.toggle_case_status, name="toggle_case_status"),
    path("case/<int:case_id>/add-blacklist/", views.add_case_to_blacklist, name="add_case_to_blacklist"),
    path("logout/", views.logout_view, name="logout"),
]
