import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, **extra_fields):
        user = self.model(**extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return str(self.id)
