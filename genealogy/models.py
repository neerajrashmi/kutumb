# apps/genealogy/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from common.models import TimeStampedModel, DateDetail, LocationDetail, IdSequence
from .validators import validate_individual_name


class IndividualDetail(TimeStampedModel):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]

    individual_id = models.CharField(max_length=8, primary_key=True, editable=False)
    first_name = models.CharField(max_length=100, blank=True, default='')
    middle_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, default='')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    birth_date = models.ForeignKey('common.DateDetail', related_name='birth_individuals', on_delete=models.SET_NULL, null=True, blank=True)
    birth_location = models.ForeignKey('common.LocationDetail', related_name='birth_individuals', on_delete=models.SET_NULL, null=True, blank=True)
    death_date = models.ForeignKey('common.DateDetail', related_name='death_individuals', on_delete=models.SET_NULL, null=True, blank=True)
    death_location = models.ForeignKey('common.LocationDetail', related_name='death_individuals', on_delete=models.SET_NULL, null=True, blank=True)

    parent_marriage = models.ForeignKey('MarriageDetail', related_name='children', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'Individual_Detail'

    @property
    def name(self):
        """Constructs full name string with first, middle, and last name."""
        full = " ".join(part for part in [self.first_name, self.middle_name, self.last_name] if part).strip()
        return full or self.individual_id

    def clean(self):
        validate_individual_name(self.first_name, self.middle_name, self.last_name)

    def save(self, *args, **kwargs):
        self.clean()
        if not self.individual_id:
            self.individual_id = IdSequence.get_next_id(prefix='I', seq_type='INDIVIDUAL')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.individual_id} - {self.name}"


class MarriageDetail(TimeStampedModel):
    SEPARATION_REASONS = [
        ('DIVORCE', 'Divorce'),
        ('DEATH_OF_PARTNER', 'Death of Partner'),
        ('OTHER', 'Other'),
        ('UNKNOWN', 'Unknown'),
    ]

    marriage_id = models.CharField(max_length=8, primary_key=True, editable=False)
    male_member = models.ForeignKey(IndividualDetail, related_name='male_marriages', on_delete=models.RESTRICT, null=True, blank=True)
    female_member = models.ForeignKey(IndividualDetail, related_name='female_marriages', on_delete=models.RESTRICT, null=True, blank=True)

    marriage_date = models.ForeignKey(DateDetail, related_name='marriage_events', on_delete=models.SET_NULL, null=True, blank=True)
    marriage_location = models.ForeignKey(LocationDetail, related_name='marriage_events', on_delete=models.SET_NULL, null=True, blank=True)

    separation_date = models.ForeignKey(DateDetail, related_name='separation_events', on_delete=models.SET_NULL, null=True, blank=True)
    separation_reason = models.CharField(max_length=20, choices=SEPARATION_REASONS, null=True, blank=True)

    class Meta:
        db_table = 'Marriage_Detail'

    def clean(self):
        if not self.male_member and not self.female_member:
            raise ValidationError("At least one participant must be populated in a marriage.")

        # Requirement 4: Prohibit duplicate marriages with the same individuals
        if self.male_member and self.female_member:
            dup_qs = MarriageDetail.objects.filter(
                male_member=self.male_member,
                female_member=self.female_member
            )
            if self.pk:
                dup_qs = dup_qs.exclude(pk=self.pk)
            if dup_qs.exists():
                raise ValidationError(
                    f"A marriage union already exists between {self.male_member.name} and {self.female_member.name}."
                )
        elif self.male_member and not self.female_member:
            single_qs = MarriageDetail.objects.filter(
                male_member=self.male_member,
                female_member__isnull=True
            )
            if self.pk:
                single_qs = single_qs.exclude(pk=self.pk)
            if single_qs.exists():
                raise ValidationError(
                    f"A single-participant union already exists for {self.male_member.name}."
                )
        elif self.female_member and not self.male_member:
            single_qs = MarriageDetail.objects.filter(
                female_member=self.female_member,
                male_member__isnull=True
            )
            if self.pk:
                single_qs = single_qs.exclude(pk=self.pk)
            if single_qs.exists():
                raise ValidationError(
                    f"A single-participant union already exists for {self.female_member.name}."
                )

        # Separation date must not precede marriage date
        if self.marriage_date and self.separation_date:
            m_min, _ = self.marriage_date.get_bounds()
            _, s_max = self.separation_date.get_bounds()
            if s_max < m_min:
                raise ValidationError("Separation date cannot precede marriage date.")

    def save(self, *args, **kwargs):
        self.clean()
        if not self.marriage_id:
            self.marriage_id = IdSequence.get_next_id(prefix='M', seq_type='MARRIAGE')
        super().save(*args, **kwargs)

    def __str__(self):
        m_str = self.male_member.name if self.male_member else "Unknown"
        f_str = self.female_member.name if self.female_member else "Unknown"
        return f"{self.marriage_id}: {m_str} & {f_str}"