from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', User.Role.ADMIN)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
        BVG = 'bvg', 'BVG Staff'
        SHOP = 'shop', 'Photocopy Shop'
        ADMIN = 'admin', 'Admin'

    # Roles a person can pick on the public sign-up page. Staff, shops and
    # admins are created by an admin.
    SELF_SIGNUP_ROLES = (Role.STUDENT, Role.TEACHER)

    username = None
    first_name = None
    last_name = None
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    department = models.CharField(max_length=80, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    def __str__(self):
        return f'{self.name} <{self.email}>'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split(' ')[0] if self.name else self.email

    @property
    def is_requester(self):
        return self.role in (self.Role.STUDENT, self.Role.TEACHER)

    @property
    def is_bvg(self):
        return self.role == self.Role.BVG

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser


class EmailOTP(models.Model):
    """A one-time code sent to prove ownership of a COEP email at sign-up."""

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
