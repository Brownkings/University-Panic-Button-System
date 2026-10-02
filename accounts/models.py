from django.db import models
from django.contrib.auth.models import AbstractUser


class Role(models.Model):
    """
    Role entity as specified in Phase 3 ERD Section 3.3 & 3.4.
    Defines system access levels: STUDENT, STAFF, SECURITY, ADMIN.
    """
    STUDENT = 'STUDENT'
    STAFF = 'STAFF'
    SECURITY = 'SECURITY'
    ADMIN = 'ADMIN'

    ROLE_CHOICES = [
        (STUDENT, 'Student'),
        (STAFF, 'Staff Member'),
        (SECURITY, 'Security Personnel'),
        (ADMIN, 'System Administrator'),
    ]

    role_name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.get_role_name_display()


class User(AbstractUser):
    """
    User entity as specified in Phase 3 Section 3.4.
    Fields:
    - id: Primary Key
    - full_name: VARCHAR(100)
    - institutional_id: VARCHAR(20) [Student/Staff ID]
    - email: VARCHAR(100)
    - contact_number: VARCHAR(15)
    - role: Foreign Key to Role (1:M)
    - is_verified: Verification status flag
    """
    full_name = models.CharField(max_length=100, help_text="User's full name")
    institutional_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Institutional Student or Staff Number (e.g., 202474004)"
    )
    email = models.EmailField(unique=True, help_text="University institutional email")
    contact_number = models.CharField(max_length=15, help_text="Mobile contact number for emergency callbacks")
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        help_text="Assigned system role"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether account has completed identity/OTP verification"
    )
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    REQUIRED_FIELDS = ['email', 'full_name', 'institutional_id', 'contact_number']

    @property
    def is_student(self):
        return bool(self.role and self.role.role_name == Role.STUDENT)

    @property
    def is_security(self):
        return bool(self.role and self.role.role_name == Role.SECURITY)

    @property
    def is_admin_user(self):
        return bool(self.is_superuser or (self.role and self.role.role_name == Role.ADMIN))

    def save(self, *args, **kwargs):
        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.institutional_id})"
