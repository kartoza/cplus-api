from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


class UserRoleType(models.Model):
    """User role type (Base users, admins ..etc.) model."""

    name = models.CharField(unique=True, max_length=50)
    description = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'User role'
        verbose_name_plural = 'User roles'
        db_table = 'user_role'


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        unique=True,
        related_name='user_profile',
        on_delete=models.CASCADE
    )
    role = models.ForeignKey(
        UserRoleType,
        on_delete=models.CASCADE,
        related_name='role_profile',
        null=True
    )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, created, **kwargs):
    """
    Handle Profile creation creating saving User
    """
    if created:
        external_role, created = UserRoleType.objects.get_or_create(
            name='External'
        )
        UserProfile.objects.create(
            user=instance,
            role=external_role
        )
