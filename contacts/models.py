from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from common.models import TimeStampedModel, DateDetail, LocationDetail
from genealogy.models import IndividualDetail


class IndividualAddress(TimeStampedModel):
    """
    Physical Table: Individual_Address
    Enforces maximum 2 active addresses and the strict Primary flag rule.
    """
    individual_address_id = models.BigAutoField(primary_key=True, db_column='Individual_Address_Id')
    individual = models.ForeignKey(
        IndividualDetail,
        on_delete=models.RESTRICT,
        db_column='Individual_Id',
        related_name='addresses'
    )
    location = models.ForeignKey(
        LocationDetail,
        on_delete=models.RESTRICT,
        db_column='Location_Id',
        related_name='individual_addresses'
    )
    from_date = models.ForeignKey(
        DateDetail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='From_Date_Id',
        related_name='address_from_events'
    )
    to_date = models.ForeignKey(
        DateDetail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='To_Date_Id',
        related_name='address_to_events'
    )
    is_primary = models.BooleanField(default=False, db_column='Is_Primary')
    is_active = models.BooleanField(default=True, db_column='Is_Active')

    class Meta:
        db_table = 'Individual_Address'
        indexes = [
            models.Index(fields=['individual', 'is_active'], name='ix_addr_ind_active'),
        ]

    def clean(self):
        # Validate date interval bounds if available
        if self.from_date and self.to_date:
            from_min, _ = self.from_date.get_bounds()
            _, to_max = self.to_date.get_bounds()
            if to_max < from_min:
                raise ValidationError("To_Date cannot precede From_Date.")

    def save(self, *args, **kwargs):
        self.clean()
        with transaction.atomic():
            if self.is_active:
                active_qs = IndividualAddress.objects.select_for_update().filter(
                    individual=self.individual,
                    is_active=True
                ).exclude(pk=self.pk)
                
                count = active_qs.count()
                if count >= 2:
                    raise ValidationError("An individual cannot have more than 2 active physical addresses.")

                # If this is the only active address, it must be Primary
                if count == 0:
                    self.is_primary = True
                elif count == 1:
                    # Exactly one must be primary between the two
                    other_addr = active_qs.first()
                    if self.is_primary:
                        other_addr.is_primary = False
                        other_addr.save(update_fields=['is_primary'])
                    else:
                        if not other_addr.is_primary:
                            other_addr.is_primary = True
                            other_addr.save(update_fields=['is_primary'])
            else:
                self.is_primary = False

            super().save(*args, **kwargs)


class IndividualPhone(TimeStampedModel):
    """
    Physical Table: Individual_Phone
    Max 3 active numbers; country code required; no Primary flag.
    """
    PHONE_TYPES = [
        ('MOBILE', 'Mobile'),
        ('HOME', 'Home'),
        ('WORK', 'Work'),
        ('OTHER', 'Other'),
    ]

    individual_phone_id = models.BigAutoField(primary_key=True, db_column='Individual_Phone_Id')
    individual = models.ForeignKey(
        IndividualDetail,
        on_delete=models.RESTRICT,
        db_column='Individual_Id',
        related_name='phones'
    )
    country_code = models.CharField(max_length=10, db_column='Country_Code')
    phone_number = models.CharField(max_length=30, db_column='Phone_Number')
    phone_type = models.CharField(max_length=15, choices=PHONE_TYPES, default='MOBILE', db_column='Phone_Type')
    is_active = models.BooleanField(default=True, db_column='Is_Active')

    class Meta:
        db_table = 'Individual_Phone'

    def clean(self):
        if not self.country_code or not self.country_code.strip():
            raise ValidationError("Country code is required.")
        if not self.phone_number or not self.phone_number.strip():
            raise ValidationError("Phone number is required.")

    def save(self, *args, **kwargs):
        self.clean()
        with transaction.atomic():
            if self.is_active:
                active_count = IndividualPhone.objects.select_for_update().filter(
                    individual=self.individual,
                    is_active=True
                ).exclude(pk=self.pk).count()
                if active_count >= 3:
                    raise ValidationError("An individual cannot have more than 3 active phone numbers.")
            super().save(*args, **kwargs)


class IndividualEmail(TimeStampedModel):
    """
    Physical Table: Individual_Email
    Max 3 active emails; RFC validation; no Primary flag.
    """
    individual_email_id = models.BigAutoField(primary_key=True, db_column='Individual_Email_Id')
    individual = models.ForeignKey(
        IndividualDetail,
        on_delete=models.RESTRICT,
        db_column='Individual_Id',
        related_name='emails'
    )
    email_address = models.CharField(
        max_length=255,
        validators=[EmailValidator(message="Enter a valid email address.")],
        db_column='Email_Address'
    )
    is_active = models.BooleanField(default=True, db_column='Is_Active')

    class Meta:
        db_table = 'Individual_Email'

    def clean(self):
        if self.email_address:
            self.email_address = self.email_address.strip().lower()

    def save(self, *args, **kwargs):
        self.clean()
        with transaction.atomic():
            if self.is_active:
                active_count = IndividualEmail.objects.select_for_update().filter(
                    individual=self.individual,
                    is_active=True
                ).exclude(pk=self.pk).count()
                if active_count >= 3:
                    raise ValidationError("An individual cannot have more than 3 active email addresses.")
            super().save(*args, **kwargs)