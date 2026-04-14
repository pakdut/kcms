from django.db import models


class CaseRecord(models.Model):
    # Choices are restricted to the two states requested by the system rules.
    STATUS_PENDING = "pending"
    STATUS_SETTLED = "settled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SETTLED, "Settled"),
    ]

    case_id = models.AutoField(primary_key=True)
    complainant_name = models.CharField(max_length=255)
    case_title = models.CharField(max_length=255)
    respondent_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        return f"{self.case_title} ({self.complainant_name} vs {self.respondent_name})"


class BlacklistedPerson(models.Model):
    blacklisted_id = models.AutoField(primary_key=True)
    blacklisted_name = models.CharField(max_length=255)
    case_title = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        return f"{self.blacklisted_name} - {self.case_title}"
