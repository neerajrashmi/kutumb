# apps/genealogy/forms.py
from datetime import date
from decimal import Decimal
from django import forms
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError

from common.models import DateDetail, LocationDetail
from genealogy.models import IndividualDetail, MarriageDetail
from genealogy.validators import validate_individual_name
from media_mgmt.models import PhotoDetail


def _parse_full_name_parts(raw_name: str):
    """
    Splits a full name string into (first_name, middle_name, last_name)
    preserving all middle words instead of ignoring them.
    """
    parts = [p for p in (raw_name or "").strip().split() if p]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


class DescriptiveIndividualChoiceField(forms.ModelChoiceField):
    """Renders full name, ID, and gender in dropdown options."""
    def label_from_instance(self, obj):
        name = " ".join(p for p in [obj.first_name, obj.middle_name, obj.last_name] if p).strip() or "Unnamed"
        gender_icon = "♂" if obj.gender == 'M' else ("♀" if obj.gender == 'F' else "?")
        return f"{name} ({obj.individual_id}, {gender_icon})"


class DescriptiveMarriageChoiceField(forms.ModelChoiceField):
    """Renders parent union names in dropdown options."""
    def label_from_instance(self, obj):
        m_name = (" ".join(p for p in [obj.male_member.first_name, obj.male_member.middle_name, obj.male_member.last_name] if p).strip() or obj.male_member.individual_id) if obj.male_member else "Unknown"
        f_name = (" ".join(p for p in [obj.female_member.first_name, obj.female_member.middle_name, obj.female_member.last_name] if p).strip() or obj.female_member.individual_id) if obj.female_member else "Unknown"
        return f"{obj.marriage_id}: {m_name} & {f_name}"


class IndividualCompositeForm(forms.ModelForm):
    # 1. Demographics
    first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'First Name', 'id': 'id_first_name'}))
    middle_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Middle Name', 'id': 'id_middle_name'}))
    last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Last Name', 'id': 'id_last_name'}))
    gender = forms.ChoiceField(choices=IndividualDetail.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_gender'}))
    parent_marriage = DescriptiveMarriageChoiceField(queryset=MarriageDetail.objects.all(), required=False, label="Lineage Union", widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_parent_marriage'}))

    # Parents Quick-Assign / Create (supports First, Middle, Last names)
    assign_father = DescriptiveIndividualChoiceField(queryset=IndividualDetail.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_assign_father'}))
    new_father_name = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'New Father (First Middle Last)', 'id': 'id_new_father_name'}))
    assign_mother = DescriptiveIndividualChoiceField(queryset=IndividualDetail.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_assign_mother'}))
    new_mother_name = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'New Mother (First Middle Last)', 'id': 'id_new_mother_name'}))

    # Profile Photo
    profile_photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control form-control-sm', 'accept': 'image/*'}))

    # 2. Birth Date Block
    birth_date_precision = forms.ChoiceField(choices=DateDetail.PRECISION_CHOICES, initial='EXACT', widget=forms.Select(attrs={'class': 'form-select form-select-sm date-precision-select', 'data-prefix': 'birth'}))
    birth_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-start-input'}))
    birth_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-end-input'}))
    birth_year_val = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm date-year-input', 'placeholder': 'YYYY', 'min': 1000, 'max': 2100}))
    birth_year_month = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control form-control-sm date-month-input'}))
    birth_date_text = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light date-display-text', 'readonly': 'readonly', 'placeholder': 'Auto-generated date display'}))

    # Birth Location
    birth_place = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place or click map', 'id': 'id_birth_place', 'autocomplete': 'off'}))
    birth_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_birth_place_id'}))
    birth_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_birth_formatted_address'}))
    birth_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_birth_lat'}))
    birth_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_birth_lng'}))

    # 3. Death Date Block
    death_date_precision = forms.ChoiceField(choices=DateDetail.PRECISION_CHOICES, initial='EXACT', widget=forms.Select(attrs={'class': 'form-select form-select-sm date-precision-select', 'data-prefix': 'death'}))
    death_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-start-input'}))
    death_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-end-input'}))
    death_year_val = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm date-year-input', 'placeholder': 'YYYY', 'min': 1000, 'max': 2100}))
    death_year_month = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control form-control-sm date-month-input'}))
    death_date_text = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light date-display-text', 'readonly': 'readonly', 'placeholder': 'Auto-generated date display'}))

    # Death Location
    death_place = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place or click map', 'id': 'id_death_place', 'autocomplete': 'off'}))
    death_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_death_place_id'}))
    death_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_death_formatted_address'}))
    death_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_death_lat'}))
    death_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_death_lng'}))

    # 4. Spouse & Marriage Block
    target_spouse_marriage_id = forms.CharField(required=False, widget=forms.HiddenInput(attrs={'id': 'id_target_spouse_marriage_id'}))
    edit_marriage_id = forms.CharField(required=False, widget=forms.HiddenInput(attrs={'id': 'id_edit_marriage_id'}))
    add_spouse_mode = forms.ChoiceField(choices=[('NONE', 'None'), ('EXISTING', 'Existing Member'), ('NEW', 'Quick-Add New Spouse')], initial='NONE', widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_spouse_mode'}))
    existing_spouse = DescriptiveIndividualChoiceField(queryset=IndividualDetail.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_existing_spouse'}))
    new_spouse_first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse First Name'}))
    new_spouse_middle_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse Middle Name'}))
    new_spouse_last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse Last Name'}))

    marriage_date_precision = forms.ChoiceField(choices=DateDetail.PRECISION_CHOICES, initial='EXACT', widget=forms.Select(attrs={'class': 'form-select form-select-sm date-precision-select', 'data-prefix': 'marriage', 'id': 'id_marriage_date_precision'}))
    marriage_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-start-input', 'id': 'id_marriage_date_start'}))
    marriage_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm date-end-input', 'id': 'id_marriage_date_end'}))
    marriage_year_val = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm date-year-input', 'placeholder': 'YYYY', 'min': 1000, 'max': 2100, 'id': 'id_marriage_year_val'}))
    marriage_year_month = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month', 'class': 'form-control form-control-sm date-month-input', 'id': 'id_marriage_year_month'}))
    marriage_date_text = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light date-display-text', 'readonly': 'readonly', 'placeholder': 'Auto-generated date display', 'id': 'id_marriage_date_text'}))

    marriage_place = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place or click map', 'id': 'id_marriage_place', 'autocomplete': 'off'}))
    marriage_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_marriage_place_id'}))
    marriage_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_marriage_formatted_address'}))
    marriage_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_marriage_lat'}))
    marriage_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'd-none', 'id': 'id_marriage_lng'}))

    class Meta:
        model = IndividualDetail
        fields = ['first_name', 'middle_name', 'last_name', 'gender', 'parent_marriage']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        all_inds = IndividualDetail.objects.all().order_by('first_name', 'last_name')
        self.is_gender_locked = False
        self._original_parent_marriage_id = None
        self.has_existing_father = False
        self.has_existing_mother = False
        current_gender = None

        if self.instance and self.instance.pk:
																																												
            self._original_parent_marriage_id = self.instance.parent_marriage_id
            all_inds = all_inds.exclude(pk=self.instance.pk)
            current_gender = self.instance.gender
            has_marriage = MarriageDetail.objects.filter(
                Q(male_member_id=self.instance.pk) | Q(female_member_id=self.instance.pk)
            ).exists()
            if has_marriage:
                self.is_gender_locked = True
                self.fields['gender'].disabled = True

																							 
            if self.instance.parent_marriage:
                if self.instance.parent_marriage.male_member:
                    self.has_existing_father = True
                    self.fields['assign_father'].initial = self.instance.parent_marriage.male_member
                    self.fields['assign_father'].disabled = True
                    self.fields['new_father_name'].disabled = True
                if self.instance.parent_marriage.female_member:
                    self.has_existing_mother = True
                    self.fields['assign_mother'].initial = self.instance.parent_marriage.female_member
                    self.fields['assign_mother'].disabled = True
                    self.fields['new_mother_name'].disabled = True

        self.fields['assign_father'].queryset = all_inds.filter(gender='M')
        self.fields['assign_mother'].queryset = all_inds.filter(gender='F')

															 
        if current_gender == 'M':
            self.fields['existing_spouse'].queryset = all_inds.filter(gender='F')
        elif current_gender == 'F':
            self.fields['existing_spouse'].queryset = all_inds.filter(gender='M')
        else:
            self.fields['existing_spouse'].queryset = all_inds

								  
        if self.instance and self.instance.pk:
            self._prefill_date('birth', self.instance.birth_date, self.instance.birth_location)
            self._prefill_date('death', self.instance.death_date, self.instance.death_location)

    def _prefill_date(self, prefix, date_obj, loc_obj):
        if date_obj:
            self.fields[f'{prefix}_date_precision'].initial = date_obj.precision
            self.fields[f'{prefix}_date_start'].initial = date_obj.start_date
            self.fields[f'{prefix}_date_end'].initial = date_obj.end_date
            self.fields[f'{prefix}_year_val'].initial = date_obj.year_val or (date_obj.start_date.year if date_obj.start_date else None)
            if date_obj.start_date:
                self.fields[f'{prefix}_year_month'].initial = date_obj.start_date.strftime("%Y-%m")
            self.fields[f'{prefix}_date_text'].initial = date_obj.original_text
        if loc_obj:
            self.fields[f'{prefix}_place'].initial = loc_obj.original_location
            self.fields[f'{prefix}_place_id'].initial = loc_obj.google_place_id
            self.fields[f'{prefix}_formatted_address'].initial = loc_obj.google_formatted_address
            self.fields[f'{prefix}_lat'].initial = str(loc_obj.latitude) if loc_obj.latitude else ''
            self.fields[f'{prefix}_lng'].initial = str(loc_obj.longitude) if loc_obj.longitude else ''

    def clean(self):
        cleaned_data = super().clean()
        validate_individual_name(
            cleaned_data.get('first_name', ''),
            cleaned_data.get('middle_name', ''),
            cleaned_data.get('last_name', '')
        )

        # Requirement 1: An individual cannot have more than one Father or more than one Mother
        if self.has_existing_father and (cleaned_data.get('new_father_name') or '').strip():
            raise ValidationError("This individual already has a Father recorded and cannot have more than one Father.")
        if self.has_existing_mother and (cleaned_data.get('new_mother_name') or '').strip():
            raise ValidationError("This individual already has a Mother recorded and cannot have more than one Mother.")

        # Requirement 2: Validate new Father/Mother names (including middle name) before creating records
        new_f = (cleaned_data.get('new_father_name') or '').strip()
        if new_f and not cleaned_data.get('assign_father'):
            f_fn, f_mn, f_ln = _parse_full_name_parts(new_f)
            validate_individual_name(f_fn, f_mn, f_ln)

        new_m = (cleaned_data.get('new_mother_name') or '').strip()
        if new_m and not cleaned_data.get('assign_mother'):
            m_fn, m_mn, m_ln = _parse_full_name_parts(new_m)
            validate_individual_name(m_fn, m_mn, m_ln)

        ind_gender = self.instance.gender if (self.instance and self.instance.pk and self.is_gender_locked) else cleaned_data.get('gender')
        ex_spouse = cleaned_data.get('existing_spouse')
        if cleaned_data.get('add_spouse_mode') == 'EXISTING' and ex_spouse and ind_gender:
            if ex_spouse.gender == ind_gender:
                raise ValidationError("Marriages must be between male and female members only.")

        for prefix in ['birth', 'death', 'marriage']:
            prec = cleaned_data.get(f'{prefix}_date_precision')
            if prec == 'BETWEEN':
                if cleaned_data.get(f'{prefix}_date_start') and not cleaned_data.get(f'{prefix}_date_end'):
                    raise ValidationError(f"Both Start Date and End Date are required for 'Between' in {prefix.capitalize()} Date.")

        # Connectivity validation: an individual cannot be saved hanging/orphan
        total_individuals = IndividualDetail.objects.count()
        if total_individuals == 0 and not (self.instance and self.instance.pk):
            return cleaned_data

        if self.instance and self.instance.pk:
            is_already_connected = (
                self._original_parent_marriage_id is not None or
                self.instance.parent_marriage_id is not None or
                MarriageDetail.objects.filter(
                    Q(male_member_id=self.instance.pk) | Q(female_member_id=self.instance.pk)
                ).exists()
            )
            if is_already_connected:
                return cleaned_data

        p_marriage = cleaned_data.get('parent_marriage')
        father = cleaned_data.get('assign_father') or new_f
        mother = cleaned_data.get('assign_mother') or new_m
        spouse = (cleaned_data.get('add_spouse_mode') != 'NONE')

        if not (p_marriage or father or mother or spouse):
            raise ValidationError(
                "An individual cannot exist disconnected from the tree. You must connect this member "
                "to a Parent Marriage Union, assign Father/Mother, or connect as a Spouse."
            )

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True, user_id=None, locked_parent_marriage=None):
																										  
        existing_pm = None
        if self._original_parent_marriage_id:
            existing_pm = MarriageDetail.objects.filter(pk=self._original_parent_marriage_id).first()

        individual = super().save(commit=False)
        if self.instance and self.instance.pk and self.is_gender_locked:
            individual.gender = self.instance.gender

        # 1. Sync Birth Date & Location
        individual.birth_date = self._sync_date_entity('birth', individual.birth_date)
        b_place = self.cleaned_data.get('birth_place')
        if b_place:
            bl = individual.birth_location or LocationDetail()
            bl.original_location = b_place
            bl.google_place_id = self.cleaned_data.get('birth_place_id') or None
            bl.google_formatted_address = self.cleaned_data.get('birth_formatted_address') or None
            lat_str = self.cleaned_data.get('birth_lat')
            lng_str = self.cleaned_data.get('birth_lng')
            bl.latitude = Decimal(lat_str) if lat_str else None
            bl.longitude = Decimal(lng_str) if lng_str else None
            bl.save()
            individual.birth_location = bl
        elif individual.birth_location and not b_place:
            individual.birth_location = None

        # 2. Sync Death Date & Location
        individual.death_date = self._sync_date_entity('death', individual.death_date)
        d_place = self.cleaned_data.get('death_place')
        if d_place:
            dl = individual.death_location or LocationDetail()
            dl.original_location = d_place
            dl.google_place_id = self.cleaned_data.get('death_place_id') or None
            dl.google_formatted_address = self.cleaned_data.get('death_formatted_address') or None
            lat_str = self.cleaned_data.get('death_lat')
            lng_str = self.cleaned_data.get('death_lng')
            dl.latitude = Decimal(lat_str) if lat_str else None
            dl.longitude = Decimal(lng_str) if lng_str else None
            dl.save()
            individual.death_location = dl
        elif individual.death_location and not d_place:
            individual.death_location = None

        # 3. Direct Father / Mother Assignment (Requirement 1 & Requirement 2)
        if existing_pm and existing_pm.male_member:
            father = existing_pm.male_member
        else:
            father = self.cleaned_data.get('assign_father')
            new_f_name = (self.cleaned_data.get('new_father_name') or '').strip()
            if not father and new_f_name:
                f_fn, f_mn, f_ln = _parse_full_name_parts(new_f_name)
                father = IndividualDetail.objects.create(
                    first_name=f_fn,
                    middle_name=f_mn,
                    last_name=f_ln,
                    gender='M'
                )

        if existing_pm and existing_pm.female_member:
            mother = existing_pm.female_member
        else:
            mother = self.cleaned_data.get('assign_mother')
            new_m_name = (self.cleaned_data.get('new_mother_name') or '').strip()
            if not mother and new_m_name:
                m_fn, m_mn, m_ln = _parse_full_name_parts(new_m_name)
                mother = IndividualDetail.objects.create(
                    first_name=m_fn,
                    middle_name=m_mn,
                    last_name=m_ln,
                    gender='F'
                )

																						   
        submitted_pm = None if existing_pm else self.cleaned_data.get('parent_marriage')
        target_pm = locked_parent_marriage or existing_pm or submitted_pm

        if father or mother:
            pm = None

																							 
            if target_pm:
                father_matches = (not target_pm.male_member_id) or (not father) or (target_pm.male_member_id == father.pk)
                mother_matches = (not target_pm.female_member_id) or (not mother) or (target_pm.female_member_id == mother.pk)

                if father_matches and mother_matches:
                    effective_father = father or target_pm.male_member
                    effective_mother = mother or target_pm.female_member

                    full_dup = None
                    if effective_father and effective_mother:
                        full_dup = MarriageDetail.objects.filter(
                            male_member=effective_father,
                            female_member=effective_mother
                        ).exclude(pk=target_pm.pk).first()

                    if full_dup:
                        pm = full_dup
                        if not target_pm.children.exclude(pk=individual.pk).exists():
                            target_pm.delete()
                    else:
                        updated = False
                        if father and not target_pm.male_member_id:
                            target_pm.male_member = father
                            updated = True
                        if mother and not target_pm.female_member_id:
                            target_pm.female_member = mother
                            updated = True
                        if updated:
                            target_pm.save()
                        pm = target_pm

            # Requirement 3: Creates or reuses single-parent MarriageDetail (e.g., Mar1 with Ind1 + null second parent)
            if not pm:
                if father and mother:
                    pm = MarriageDetail.objects.filter(male_member=father, female_member=mother).first()
                    if not pm:
                        pm = (
                            MarriageDetail.objects.filter(male_member=father, female_member__isnull=True).first()
                            or MarriageDetail.objects.filter(female_member=mother, male_member__isnull=True).first()
                        )
                        if pm:
                            pm.male_member = father
                            pm.female_member = mother
                            pm.save()
                        else:
                            pm = MarriageDetail.objects.create(male_member=father, female_member=mother)
                elif father:
                    pm = MarriageDetail.objects.filter(male_member=father, female_member__isnull=True).first() or MarriageDetail.objects.create(male_member=father)
                elif mother:
                    pm = MarriageDetail.objects.filter(female_member=mother, male_member__isnull=True).first() or MarriageDetail.objects.create(female_member=mother)

            individual.parent_marriage = pm
        elif target_pm:
            individual.parent_marriage = target_pm

        if commit:
            individual.save()

        # 4. Profile Photo
        photo_file = self.cleaned_data.get('profile_photo')
        if photo_file and commit:
            PhotoDetail.objects.create(
                individual=individual,
                image_file=photo_file,
                caption="Profile Photo",
                owner_uploader_id=user_id or individual.individual_id,
                mime_type=getattr(photo_file, 'content_type', 'image/jpeg'),
                file_size_bytes=photo_file.size
            )

        # 5. Edit existing marriage date and/or location in place
        edit_m_id = (self.cleaned_data.get('edit_marriage_id') or '').strip()
        if edit_m_id and commit:
            m_obj = MarriageDetail.objects.filter(pk=edit_m_id).first()
            if m_obj and (m_obj.male_member_id == individual.pk or m_obj.female_member_id == individual.pk):
                m_obj.marriage_date = self._sync_date_entity('marriage', m_obj.marriage_date)
                m_place = (self.cleaned_data.get('marriage_place') or '').strip()
                if m_place:
                    m_loc = m_obj.marriage_location or LocationDetail()
                    m_loc.original_location = m_place
                    m_loc.google_place_id = self.cleaned_data.get('marriage_place_id') or None
                    m_loc.google_formatted_address = self.cleaned_data.get('marriage_formatted_address') or None
                    m_loc.latitude = Decimal(self.cleaned_data.get('marriage_lat')) if self.cleaned_data.get('marriage_lat') else None
                    m_loc.longitude = Decimal(self.cleaned_data.get('marriage_lng')) if self.cleaned_data.get('marriage_lng') else None
                    m_loc.save()
                    m_obj.marriage_location = m_loc
                else:
                    m_obj.marriage_location = None
                m_obj.save()

        # 6. Spouse & Marriage
        spouse_obj = None
        spouse_mode = self.cleaned_data.get('add_spouse_mode')
        if spouse_mode == 'EXISTING':
            spouse_obj = self.cleaned_data.get('existing_spouse')
        elif spouse_mode == 'NEW':
            fn = self.cleaned_data.get('new_spouse_first_name', '').strip()
            mn = self.cleaned_data.get('new_spouse_middle_name', '').strip()
            ln = self.cleaned_data.get('new_spouse_last_name', '').strip()
            if fn or mn or ln:
                spouse_obj = IndividualDetail.objects.create(
                    first_name=fn, middle_name=mn, last_name=ln,
                    gender='F' if individual.gender == 'M' else 'M'
                )

        if spouse_obj and commit:
            m_date = self._sync_date_entity('marriage', None)
            m_loc = None
            m_place = self.cleaned_data.get('marriage_place')
            if m_place:
                m_loc = LocationDetail.objects.create(
                    original_location=m_place,
                    google_place_id=self.cleaned_data.get('marriage_place_id') or None,
                    google_formatted_address=self.cleaned_data.get('marriage_formatted_address') or None,
                    latitude=Decimal(self.cleaned_data.get('marriage_lat')) if self.cleaned_data.get('marriage_lat') else None,
                    longitude=Decimal(self.cleaned_data.get('marriage_lng')) if self.cleaned_data.get('marriage_lng') else None
                )

            male = individual if individual.gender == 'M' else spouse_obj
            female = spouse_obj if individual.gender == 'M' else individual

            target_m_id = (self.cleaned_data.get('target_spouse_marriage_id') or '').strip()
            target_marriage = MarriageDetail.objects.filter(pk=target_m_id).first() if target_m_id else None

            if target_marriage and (
                (target_marriage.male_member_id == individual.pk and not target_marriage.female_member_id) or
                (target_marriage.female_member_id == individual.pk and not target_marriage.male_member_id)
            ):
																			
                existing_pair = MarriageDetail.objects.filter(
                    male_member=male, female_member=female
                ).exclude(pk=target_marriage.pk).first()

                if existing_pair:
                    IndividualDetail.objects.filter(parent_marriage=target_marriage).update(parent_marriage=existing_pair)
                    target_marriage.delete()
                else:
                    target_marriage.male_member = male
                    target_marriage.female_member = female
                    if m_date:
                        target_marriage.marriage_date = m_date
                    if m_loc:
                        target_marriage.marriage_location = m_loc
                    target_marriage.save()
            else:
                if not MarriageDetail.objects.filter(male_member=male, female_member=female).exists():
                    MarriageDetail.objects.create(
                        male_member=male,
                        female_member=female,
                        marriage_date=m_date,
                        marriage_location=m_loc
                    )

        return individual

    def _sync_date_entity(self, prefix, existing_date_obj):
        prec = self.cleaned_data.get(f'{prefix}_date_precision')
        start_d = self.cleaned_data.get(f'{prefix}_date_start')
        end_d = self.cleaned_data.get(f'{prefix}_date_end')
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