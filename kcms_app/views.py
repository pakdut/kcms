from datetime import timedelta
from pathlib import Path
import csv

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.password_validation import validate_password
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.conf import settings

from .models import BlacklistedPerson, CaseRecord

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 5


def _is_admin(user):
    # The whole app is restricted to the admin account only.
    return user.is_authenticated and user.is_superuser


def home(request):
    return render(request, "kcms_app/index.html")


def _serve_template_image(filename):
    # Images were provided inside the templates tree, so we expose read-only endpoints for them.
    image_path = Path(settings.BASE_DIR) / "kcms_app" / "templates" / "kcms_app" / "images" / filename
    if not image_path.exists():
        raise Http404("Image not found.")
    return FileResponse(open(image_path, "rb"))


def logo_image(request):
    return _serve_template_image("kinasang-an_logo.jpeg")


def hero_image(request):
    return _serve_template_image("kinasang-an.jpeg")


def _parse_date_filters(request):
    # Shared date filter parser for dashboard, report, and CSV exports.
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    return start_date, end_date


def _apply_date_range(queryset, start_date, end_date):
    if start_date:
        queryset = queryset.filter(created_on__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_on__date__lte=end_date)
    return queryset


def login_view(request):
    lock_until = request.session.get("lock_until")
    if lock_until:
        lock_until_dt = timezone.datetime.fromisoformat(lock_until)
        if timezone.now() < lock_until_dt:
            messages.error(request, "Too many failed attempts. Please try again in a few minutes.")
            return render(request, "kcms_app/login.html")
        request.session.pop("lock_until", None)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user and user.is_superuser:
            login(request, user)
            # Reset lockout counters on successful admin login.
            request.session.pop("login_attempts", None)
            request.session.pop("lock_until", None)
            return redirect("kcms_app:dashboard")

        attempts = int(request.session.get("login_attempts", 0)) + 1
        request.session["login_attempts"] = attempts
        if attempts >= MAX_LOGIN_ATTEMPTS:
            lock_until_time = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
            request.session["lock_until"] = lock_until_time.isoformat()
            request.session["login_attempts"] = 0
            messages.error(request, "Login locked due to repeated failed attempts.")
        else:
            messages.error(request, "Invalid admin credentials.")

    return render(request, "kcms_app/login.html")


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def dashboard(request):
    start_date, end_date = _parse_date_filters(request)
    case_records = _apply_date_range(CaseRecord.objects.all(), start_date, end_date)
    blacklisted_records = _apply_date_range(BlacklistedPerson.objects.all(), start_date, end_date)
    monthly_summary = (
        CaseRecord.objects.filter(created_on__month=timezone.now().month, created_on__year=timezone.now().year)
        .values("status")
        .annotate(total=Count("case_id"))
    )
    summary_lookup = {row["status"]: row["total"] for row in monthly_summary}

    context = {
        "case_records": case_records,
        "blacklisted_records": blacklisted_records,
        "total_cases": case_records.count(),
        "pending_cases": summary_lookup.get(CaseRecord.STATUS_PENDING, 0),
        "settled_cases": summary_lookup.get(CaseRecord.STATUS_SETTLED, 0),
        "total_blacklisted": blacklisted_records.count(),
        "recent_cases": case_records[:5],
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "kcms_app/dashboard.html", context)


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def toggle_case_status(request, case_id):
    # Allow quick status workflow directly from the table.
    if request.method != "POST":
        return redirect("kcms_app:dashboard")

    record = get_object_or_404(CaseRecord, case_id=case_id)
    record.status = (
        CaseRecord.STATUS_SETTLED
        if record.status == CaseRecord.STATUS_PENDING
        else CaseRecord.STATUS_PENDING
    )
    record.save(update_fields=["status"])
    messages.success(request, f"Case #{record.case_id} status updated to {record.get_status_display()}.")
    return redirect("kcms_app:dashboard")


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def add_case_to_blacklist(request, case_id):
    # Adds respondent into blacklisted records if not existing yet.
    if request.method != "POST":
        return redirect("kcms_app:dashboard")

    record = get_object_or_404(CaseRecord, case_id=case_id)
    exists = BlacklistedPerson.objects.filter(blacklisted_name__iexact=record.respondent_name).exists()
    if exists:
        messages.error(request, "This respondent already exists in blacklisted records.")
        return redirect("kcms_app:dashboard")

    BlacklistedPerson.objects.create(
        blacklisted_name=record.respondent_name,
        case_title=record.case_title,
    )
    messages.success(request, f"{record.respondent_name} added to blacklisted records.")
    return redirect("kcms_app:dashboard")


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def export_case_records_csv(request):
    start_date, end_date = _parse_date_filters(request)
    records = _apply_date_range(CaseRecord.objects.all(), start_date, end_date)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="case_records.csv"'
    writer = csv.writer(response)
    writer.writerow(["Case ID", "Complainant Name", "Case Title", "Respondent Name", "Status", "Created On"])
    for row in records:
        writer.writerow(
            [row.case_id, row.complainant_name, row.case_title, row.respondent_name, row.get_status_display(), row.created_on]
        )
    return response


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def export_blacklisted_csv(request):
    start_date, end_date = _parse_date_filters(request)
    records = _apply_date_range(BlacklistedPerson.objects.all(), start_date, end_date)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="blacklisted_records.csv"'
    writer = csv.writer(response)
    writer.writerow(["Blacklist ID", "Blacklisted Name", "Case Title", "Created On"])
    for row in records:
        writer.writerow([row.blacklisted_id, row.blacklisted_name, row.case_title, row.created_on])
    return response


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def dashboard_report(request):
    # Printable summary report used for quick review or defense/demo presentation.
    start_date, end_date = _parse_date_filters(request)
    case_records = _apply_date_range(CaseRecord.objects.all(), start_date, end_date)
    blacklisted_records = _apply_date_range(BlacklistedPerson.objects.all(), start_date, end_date)
    return render(
        request,
        "kcms_app/report.html",
        {
            "case_records": case_records[:20],
            "total_cases": case_records.count(),
            "pending_cases": case_records.filter(status=CaseRecord.STATUS_PENDING).count(),
            "settled_cases": case_records.filter(status=CaseRecord.STATUS_SETTLED).count(),
            "total_blacklisted": blacklisted_records.count(),
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def settings_view(request):
    # Settings is scoped for one admin account; this page manages account credentials.
    if request.method == "POST":
        current_password = request.POST.get("current_password", "")
        new_username = request.POST.get("new_username", "").strip()
        new_password = request.POST.get("new_password", "").strip()

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
        else:
            if new_username:
                request.user.username = new_username
            if new_password:
                try:
                    # Enforce Django strong-password rules before saving.
                    validate_password(new_password, user=request.user)
                    request.user.set_password(new_password)
                except ValidationError as exc:
                    messages.error(request, " ".join(exc.messages))
                    return render(request, "kcms_app/settings.html")
            request.user.save()
            messages.success(request, "Account settings updated. Please log in again.")
            logout(request)
            return redirect("kcms_app:login")

    return render(request, "kcms_app/settings.html")


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def kp_form_7(request):
    context = {}
    if request.method == "POST":
        # Keep all posted fields so the printed page preserves every typed blank line.
        context["form_data"] = request.POST.dict()
        complainant_name = request.POST.get("complainant_name", "").strip()
        respondent_name = request.POST.get("respondent_name", "").strip()
        case_title = request.POST.get("case_title", "").strip()
        confirm_continue = request.POST.get("confirm_continue") == "1"

        if complainant_name and respondent_name and case_title:
            is_blacklisted = BlacklistedPerson.objects.filter(blacklisted_name__iexact=respondent_name).exists()

            # Ask for explicit confirmation before printing if respondent is blacklisted.
            if is_blacklisted and not confirm_continue:
                context["show_blacklist_warning"] = True
                return render(request, "kcms_app/kp-form-7.html", context)

            CaseRecord.objects.create(
                complainant_name=complainant_name,
                respondent_name=respondent_name,
                case_title=case_title,
            )
            context["trigger_print"] = True
            messages.success(request, "Case record saved. You can now print this form.")
        else:
            messages.error(request, "Please fill in complainant name, respondent name, and case title.")

    return render(request, "kcms_app/kp-form-7.html", context)


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def kp_form_9(request):
    context = {"trigger_print": request.method == "POST"}
    return render(request, "kcms_app/kp-form-9.html", context)


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def kp_form_14(request):
    context = {"trigger_print": request.method == "POST"}
    return render(request, "kcms_app/kp-form-14.html", context)


@login_required(login_url="kcms_app:login")
@user_passes_test(_is_admin, login_url="kcms_app:login")
def kp_form_20(request):
    context = {}
    if request.method == "POST":
        # Preserve all printable form inputs after submit.
        context["form_data"] = request.POST.dict()
        blacklisted_name = request.POST.get("blacklisted_name", "").strip()
        case_title = request.POST.get("case_title", "").strip()

        if blacklisted_name and case_title:
            BlacklistedPerson.objects.create(blacklisted_name=blacklisted_name, case_title=case_title)
            context["trigger_print"] = True
            messages.success(request, "Blacklisted record saved. You can now print this form.")
        else:
            messages.error(request, "Please fill in respondent name and case title.")

    return render(request, "kcms_app/kp-form-20.html", context)


@login_required(login_url="kcms_app:login")
def logout_view(request):
    logout(request)
    return redirect("kcms_app:login")


def denied(request, exception=None):
    return HttpResponseForbidden("Forbidden")
