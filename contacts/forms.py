# apps/contacts/forms.py
from datetime import date
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import transaction

from common.models import LocationDetail, DateDetail
from contacts.models import IndividualAddress, IndividualPhone, IndividualEmail


class IndividualPhoneForm(forms.ModelForm):
    country_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 or +91'})
    )
    phone_number = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    phone_type = forms.ChoiceField(
        choices=IndividualPhone.PHONE_TYPES,
        initial='MOBILE',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = IndividualPhone
        fields = ['country_code', 'phone_number', 'phone_type', 'is_active']

    def clean_country_code(self):
        cc = (self.cleaned_data.get('country_code') or '').strip()
        if not cc:
            raise ValidationError("Country code is required.")
        if not cc.startswith('+'):
            cc = '+' + cc
        return cc

    def clean_phone_number(self):
        num = (self.cleaned_data.get('phone_number') or '').strip()
        if not num:
            raise ValidationError("Phone number is required.")
        return num


class IndividualEmailForm(forms.ModelForm):
    email_address = forms.CharField(
        max_length=255,
        validators=[EmailValidator(message="Enter a valid email address.")],
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@domain.com'})
    )
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = IndividualEmail
        fields = ['email_address', 'is_active']

    def clean_email_address(self):
        email = (self.cleaned_data.get('email_address') or '').strip().lower()
        if not email:
            raise ValidationError("Email address is required.")
        return email


class IndividualAddressCompositeForm(forms.ModelForm):
    # Location text & Google Geocoded Metadata
    location_text = forms.CharField(
        max_length=500,
        label="Address / Location",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type address or click on map...',
            'id': 'id_address_location',
            'autocomplete': 'off'
        })
    )
    place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_addr_place_id'}))
    formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_addr_formatted_address'}))
    lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_addr_lat'}))
    lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_addr_lng'}))

    # --- 1. Residing From Date Block (Precision First, Auto-generated Read-Only text) ---
    from_date_precision = forms.ChoiceField(
        choices=DateDetail.PRECISION_CHOICES,
        initial='EXACT',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm date-precision-select', 'data-prefix': 'from_date'})
    )
    from_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-start-input'}))
    from_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-end-input'}))
    from_date_year_val = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm date-year-input', 'placeholder': 'YYYY', 'min': 1000, 'max': 2100}))
    from_date_year_month = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control form-control-sm date-month-input'}))
    from_date_text = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light date-display-text', 'readonly': 'readonly', 'placeholder': 'Auto-generated date display'}))

    # --- 2. Residing To Date Block (Precision First, Auto-generated Read-Only text) ---
    to_date_precision = forms.ChoiceField(
        choices=DateDetail.PRECISION_CHOICES,
        initial='EXACT',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm date-precision-select', 'data-prefix': 'to_date'})
    )
    to_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-start-input'}))
    to_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-end-input'}))
    to_date_year_val = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm date-year-input', 'placeholder': 'YYYY', 'min': 1000, 'max': 2100}))
    to_date_year_month = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control form-control-sm date-month-input'}))
    to_date_text = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light date-display-text', 'readonly': 'readonly', 'placeholder': 'Leave empty if current residence'}))

    is_primary = forms.BooleanField(required=False, label="Mark as Primary Address", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_active = forms.BooleanField(required=False, initial=True, label="Active Address", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = IndividualAddress
        fields = ['is_primary', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.location:
                loc = self.instance.location
                self.fields['location_text'].initial = loc.original_location
                self.fields['place_id'].initial = loc.google_place_id
                self.fields['formatted_address'].initial = loc.google_formatted_address
                self.fields['lat'].initial = str(loc.latitude) if loc.latitude else ''
                self.fields['lng'].initial = str(loc.longitude) if loc.longitude else ''
            
            # Pre-populate From Date
            if self.instance.from_date:
                fd = self.instance.from_date
                self.fields['from_date_precision'].initial = fd.precision
                self.fields['from_date_start'].initial = fd.start_date
                self.fields['from_date_end'].initial = fd.end_date
                self.fields['from_date_year_val'].initial = fd.year_val or (fd.start_date.year if fd.start_date else None)
                if fd.start_date:
                    self.fields['from_date_year_month'].initial = fd.start_date.strftime("%Y-%m")
                self.fields['from_date_text'].initial = fd.original_text

            # Pre-populate To Date
            if self.instance.to_date:
                td = self.instance.to_date
                self.fields['to_date_precision'].initial = td.precision
                self.fields['to_date_start'].initial = td.start_date
                self.fields['to_date_end'].initial = td.end_date
                self.fields['to_date_year_val'].initial = td.year_val or (td.start_date.year if td.start_date else None)
                if td.start_date:
                    self.fields['to_date_year_month'].initial = td.start_date.strftime("%Y-%m")
                self.fields['to_date_text'].initial = td.original_text

    def clean(self):
        cleaned_data = super().clean()

        # Helper to extract an effective lower-bound date for comparison
        def get_effective_date(prefix):
            prec = cleaned_data.get(f'{prefix}_precision')
            start_d = cleaned_data.get(f'{prefix}_start')
            y_val = cleaned_data.get(f'{prefix}_year_val')
            ym_str = cleaned_data.get(f'{prefix}_year_month')

            if prec == 'YEAR_MONTH' and ym_str:
                try:
                    y, m = ym_str.split('-')
                    return date(int(y), int(m), 1)
                except Exception:
                    pass
            elif prec == 'YEAR' and y_val:
                return date(int(y_val), 1, 1)
            return start_d

        from_d = get_effective_date('from_date')
        to_d = get_effective_date('to_date')

        if from_d and to_d and to_d < from_d:
            raise ValidationError("Residency To date cannot precede From date.")

        for prefix in ['from_date', 'to_date']:
            prec = cleaned_data.get(f'{prefix}_precision')
            if prec == 'BETWEEN':
                if cleaned_data.get(f'{prefix}_start') and not cleaned_data.get(f'{prefix}_end'):
                    name = "From" if prefix == 'from_date' else "To"
                    raise ValidationError(f"Both Start Date and End Date are required for 'Between' in Residing {name} Date.")

        return cleaned_data

    def _sync_date_entity(self, prefix, existing_date_obj):
        prec = self.cleaned_data.get(f'{prefix}_precision')
        start_d = self.cleaned_data.get(f'{prefix}_start')
        end_d = self.cleaned_data.get(f'{prefix}_end')
        year_v = self.cleaned_data.get(f'{prefix}_year_val')
        ym_str = self.cleaned_data.get(f'{prefix}_year_month')

        if prec == 'YEAR_MONTH' and ym_str:
            try:
                y, m = ym_str.split('-')
                start_d = date(int(y), int(m), 1)
            except Exception:
                pass
        elif prec == 'YEAR' and year_v:
            start_d = date(int(year_v), 1, 1)

        disp_text = DateDetail.generate_display_text(prec, start_d, end_d, year_v)

        if not disp_text and not start_d and not year_v:
            return None

        date_obj = existing_date_obj or DateDetail()
        date_obj.precision = prec
        date_obj.start_date = start_d
        date_obj.end_date = end_d
        date_obj.year_val = year_v
        date_obj.original_text = disp_text
        date_obj.save()
        return date_obj

    @transaction.atomic
    def save(self, commit=True, individual=None):
        addr_instance = super().save(commit=False)
        if individual:
            addr_instance.individual = individual

        # 1. Synchronize LocationDetail with Google Metadata
        loc_text = self.cleaned_data.get('location_text')
        if loc_text:
            loc = addr_instance.location or LocationDetail()
            loc.original_location = loc_text
            loc.google_place_id = self.cleaned_data.get('place_id') or None
            loc.google_formatted_address = self.cleaned_data.get('formatted_address') or None
            lat_str = self.cleaned_data.get('lat')
            lng_str = self.cleaned_data.get('lng')
            loc.latitude = Decimal(lat_str) if lat_str else None
            loc.longitude = Decimal(lng_str) if lng_str else None
            loc.status = 'USER_CONFIRMED' if loc.google_place_id else 'ENTERED'
            loc.save()
            addr_instance.location = loc

        # 2. Synchronize Residing From Date
        addr_instance.from_date = self._sync_date_entity('from_date', addr_instance.from_date)

        # 3. Synchronize Residing To Date
        addr_instance.to_date = self._sync_date_entity('to_date', addr_instance.to_date)

        # 4. Enforce Address Active & Primary Rules (SRS 12)
        active_flag = self.cleaned_data.get('is_active', True)
        primary_flag = self.cleaned_data.get('is_primary', False)
        target_ind = addr_instance.individual

        if active_flag:
            existing_active = IndividualAddress.objects.filter(
                individual=target_ind, is_active=True
            ).exclude(pk=addr_instance.pk)
            
            if existing_active.count() >= 2:
                raise ValidationError("Maximum of 2 active physical addresses permitted per individual.")

            # If this is the only active address, it must be primary
            if existing_active.count() == 0:
                addr_instance.is_primary = True
            elif primary_flag:
                existing_active.update(is_primary=False)
            elif not any(a.is_primary for a in existing_active):
                addr_instance.is_primary = True

        if commit:
            addr_instance.save()
        return addr_instance