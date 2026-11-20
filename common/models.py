# apps/common/models.py
from datetime import date
from django.db import models
from django.utils import timezone
from common.middleware import get_current_user_id

class TimeStampedModel(models.Model):
    created_by = models.CharField(max_length=8, null=True, blank=True)
    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_by = models.CharField(max_length=8, null=True, blank=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        current_user_id = get_current_user_id()

        if current_user_id:
            if self._state.adding or not self.created_by:
                self.created_by = current_user_id
            self.modified_by = current_user_id

        super().save(*args, **kwargs)

class IdSequence(models.Model):
    sequence_type = models.CharField(max_length=20, primary_key=True, db_column='Sequence_Type')
    next_val = models.BigIntegerField(default=1, db_column='Next_Val')

    class Meta:
        db_table = 'id_sequence'

    @classmethod
    def get_next_id(cls, prefix='I', seq_type='INDIVIDUAL'):
        from django.db import transaction
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                sequence_type=seq_type,
                defaults={'next_val': 1}
            )
            val = seq.next_val
            seq.next_val += 1
            seq.save(update_fields=['next_val'])
            return f"{prefix}{val:07d}"


class DateDetail(TimeStampedModel):
    PRECISION_CHOICES = [
        ('EXACT', 'Exact Date'),
        ('YEAR', 'Year Only'),
        ('YEAR_MONTH', 'Year-Month'),
        ('BEFORE', 'Before Date'),
        ('AFTER', 'After Date'),
        ('BETWEEN', 'Between Dates'),
    ]

    date_id = models.BigAutoField(primary_key=True, db_column='Date_Id')
    precision = models.CharField(
        max_length=15, 
        choices=PRECISION_CHOICES, 
        default='EXACT', 
        db_column='Precision'
    )
    qualifier = models.CharField(max_length=10, default='NONE', db_column='Qualifier')
    original_text = models.CharField(max_length=255, db_column='Original_Text')
    
    start_date = models.DateField(null=True, blank=True, db_column='Start_Date')
    end_date = models.DateField(null=True, blank=True, db_column='End_Date')
    year_val = models.PositiveSmallIntegerField(null=True, blank=True, db_column='Year_Val')

    class Meta:
        db_table = 'Date_Detail'

    @staticmethod
    def generate_display_text(precision, start_date=None, end_date=None, year_val=None):
        """Constructs canonical standardized date text (DD-Mon-YYYY)."""
        if precision == 'EXACT' and start_date:
            return start_date.strftime("%d-%b-%Y")
        elif precision == 'YEAR' and year_val:
            return str(year_val)
        elif precision == 'YEAR' and start_date:
            return str(start_date.year)
        elif precision == 'YEAR_MONTH' and start_date:
            return start_date.strftime("%b-%Y")
        elif precision == 'BEFORE' and start_date:
            return f"Before {start_date.strftime('%d-%b-%Y')}"
        elif precision == 'AFTER' and start_date:
            return f"After {start_date.strftime('%d-%b-%Y')}"
        elif precision == 'BETWEEN':
            s_str = start_date.strftime("%d-%b-%Y") if start_date else "?"
            e_str = end_date.strftime("%d-%b-%Y") if end_date else "?"
            return f"Between {s_str} and {e_str}"
        elif start_date:
            return start_date.strftime("%d-%b-%Y")
        return ""

    def get_bounds(self):
        """Calculates (min_date, max_date) for chronological sorting."""
        if self.precision == 'EXACT' and self.start_date:
            return (self.start_date, self.start_date)
        elif self.precision == 'YEAR' and self.year_val:
            return (date(self.year_val, 1, 1), date(self.year_val, 12, 31))
        elif self.precision == 'YEAR_MONTH' and self.start_date:
            y, m = self.start_date.year, self.start_date.month
            next_m = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
            return (date(y, m, 1), next_m)
        elif self.precision == 'BEFORE' and self.start_date:
            return (date.min, self.start_date)
        elif self.precision == 'AFTER' and self.start_date:
            return (self.start_date, date.max)
        elif self.precision == 'BETWEEN':
            return (self.start_date or date.min, self.end_date or date.max)
        return (self.start_date or date.min, self.end_date or self.start_date or date.max)

    def get_comparison_bounds(self):
        return self.get_bounds()

    def __str__(self):
        return self.original_text or f"Date #{self.date_id}"


class LocationDetail(TimeStampedModel):
    STATUS_CHOICES = [
        ('ENTERED', 'Entered'),
        ('GEOCODED_AUTO', 'Geocoded Automatic'),
        ('USER_CONFIRMED', 'User Confirmed'),
    ]

    location_id = models.BigAutoField(primary_key=True, db_column='Location_Id')
    original_location = models.CharField(max_length=500, db_column='Original_Location')
    google_place_id = models.CharField(max_length=255, null=True, blank=True, db_column='Google_Place_Id')
    google_formatted_address = models.CharField(max_length=500, null=True, blank=True, db_column='Google_Formatted_Address')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, db_column='Latitude')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, db_column='Longitude')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ENTERED', db_column='Status')

    class Meta:
        db_table = 'Location_Detail'

    def __str__(self):
        return self.google_formatted_address or self.original_location