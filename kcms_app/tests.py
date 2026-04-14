from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BlacklistedPerson, CaseRecord


class KCMSCoreFlowTests(TestCase):
    def setUp(self):
        # One-admin setup used by all system tests.
        self.user = get_user_model().objects.create_superuser(
            username="joy",
            email="joy@example.com",
            password="1234",
        )

    def _login(self):
        self.client.post(
            reverse("kcms_app:login"),
            {"username": "joy", "password": "1234"},
            follow=True,
        )

    def test_admin_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("kcms_app:login"),
            {"username": "joy", "password": "1234"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("kcms_app:dashboard"))

    def test_kp7_blacklist_confirmation_then_save(self):
        self._login()
        BlacklistedPerson.objects.create(blacklisted_name="Juan Dela Cruz", case_title="Physical Injury")

        warning_response = self.client.post(
            reverse("kcms_app:kp_form_7"),
            {
                "complainant_name": "Maria",
                "respondent_name": "juan dela cruz",
                "case_title": "Physical Injury",
                "confirm_continue": "0",
            },
        )
        self.assertContains(warning_response, "already in Blacklisted Record")
        self.assertEqual(CaseRecord.objects.count(), 0)

        save_response = self.client.post(
            reverse("kcms_app:kp_form_7"),
            {
                "complainant_name": "Maria",
                "respondent_name": "juan dela cruz",
                "case_title": "Physical Injury",
                "confirm_continue": "1",
            },
            follow=True,
        )
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(CaseRecord.objects.count(), 1)

    def test_csv_export_returns_expected_header(self):
        self._login()
        CaseRecord.objects.create(
            complainant_name="Maria",
            respondent_name="Pedro",
            case_title="Noise Complaint",
        )
        response = self.client.get(reverse("kcms_app:export_case_records_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("Case ID", response.content.decode("utf-8"))

    def test_settings_rejects_weak_password(self):
        self._login()
        response = self.client.post(
            reverse("kcms_app:settings"),
            {
                "current_password": "1234",
                "new_username": "joy",
                "new_password": "1234",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("1234"))
