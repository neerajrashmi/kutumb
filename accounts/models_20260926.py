from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.utils import timezone
from common.models import TimeStampedModel
from genealogy.models import IndividualDetail


class UserDetailManager(BaseUserManager):
    def create_user(self, individual_id, password=None, **extra_fields):
        if not individual_id:
            raise ValueError("The Individual_Id is required to create a User account.")
        
        # Enforce that the individual exists
        individual = IndividualDetail.objects.get(individual_id=individual_id)
        
        user = self.model(
            user_id=individual,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, individual_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_status', 'ACTIVE')
        return self.create_user(individual_id, password, **extra_fields)


class UserDetail(AbstractBaseUser, PermissionsMixin):
    """
    Physical Table: User_Detail
    User_Id is exactly the same value as Individual_Detail.Individual_Id (1:1 PK/FK)
    """
    STATUS_CHOICES = [
        ('INVITED', 'Invited'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('DEACTIVATED', 'Deactivated'),
    ]

    # PK is also FK to Individual_Detail
    user_id = models.OneToOneField(
        IndividualDetail,
        on_delete=models.RESTRICT,
        primary_key=True,
        db_column='User_Id',
        related_name='user_account'
    )
    
    # Invitation chain provenance (A -> B -> C)
    invited_by_user = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='Invited_By_User_Id',
        related_name='invitees'
    )
    
    user_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INVITED')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # UTC audit columns
    created_by = models.CharField(max_length=8, null=True, blank=True)
    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_by = models.CharField(max_length=8, null=True, blank=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = UserDetailManager()

    USERNAME_FIELD = 'user_id'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'User_Detail'

    def __str__(self):
        return f"User {self.user_id_id} [{self.user_status}]"


class UserAccess(TimeStampedModel):
    """
    Physical Table: User_Access
    Maintains explicit View/Edit grants separate from invitations.
    """
    ACCESS_TYPE_CHOICES = [
        ('VIEW', 'View Access'),
        ('EDIT', 'Edit Access'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('REVOKED', 'Revoked'),
    ]

    access_id = models.BigAutoField(primary_key=True, db_column='Access_Id')
    host_user = models.ForeignKey(
        UserDetail,
        on_delete=models.CASCADE,
        db_column='Host_User_Id',
        related_name='hosted_grants'
    )
    granted_to_user = models.ForeignKey(
        UserDetail,
        on_delete=models.CASCADE,
        db_column='Granted_To_User_Id',
        related_name='received_grants'
    )
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPE_CHOICES, db_column='Access_Type')
    access_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE', db_column='Access_Status')
    
    granted_on = models.DateTimeField(default=timezone.now, db_column='Granted_On')
    revoked_on = models.DateTimeField(null=True, blank=True, db_column='Revoked_On')
    granted_by_user = models.ForeignKey(
        UserDetail,
        on_delete=models.RESTRICT,
        db_column='Granted_By_User_Id',
        related_name='authorized_grants'
    )

    class Meta:
        db_table = 'User_Access'

    def clean(self):
        if self.host_user == self.granted_to_user:
            raise ValidationError("Users cannot grant explicit access to themselves.")


class UserAccessScope(TimeStampedModel):
    """
    Physical Table: User_Access_Scope
    Implements recursive scope anchoring without cascading through invitations.
    """
    SCOPE_MODE_CHOICES = [
        ('INDIVIDUAL_ONLY', 'Individual Only'),
        ('INDIVIDUAL_AND_BRANCH', 'Individual and Branch (Recursive)'),
    ]

    access_scope_id = models.BigAutoField(primary_key=True, db_column='Access_Scope_Id')
    access = models.ForeignKey(
        UserAccess,
        on_delete=models.CASCADE,
        db_column='Access_Id',
        related_name='scopes'
    )
    scope_individual = models.ForeignKey(
        IndividualDetail,
        on_delete=models.RESTRICT,
        db_column='Scope_Individual_Id',
        related_name='access_scopes'
    )
    scope_mode = models.CharField(
        max_length=30,
        choices=SCOPE_MODE_CHOICES,
        default='INDIVIDUAL_AND_BRANCH',
        db_column='Scope_Mode'
    )

    class Meta:
        db_table = 'User_Access_Scope'
        constraints = [
            models.UniqueConstraint(fields=['access', 'scope_individual'], name='uk_access_scope_individual')
        ]