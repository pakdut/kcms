from django.contrib import admin
from .models import BlacklistedPerson, CaseRecord


@admin.register(CaseRecord)
class CaseRecordAdmin(admin.ModelAdmin):
    # List fields let the admin quickly review recent records.
    list_display = ("case_id", "complainant_name", "respondent_name", "case_title", "status", "created_on")
    search_fields = ("complainant_name", "respondent_name", "case_title")
    list_filter = ("status", "created_on")


@admin.register(BlacklistedPerson)
class BlacklistedPersonAdmin(admin.ModelAdmin):
    list_display = ("blacklisted_id", "blacklisted_name", "case_title", "created_on")
    search_fields = ("blacklisted_name", "case_title")
    list_filter = ("created_on",)
