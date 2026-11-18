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


class DescriptiveIndividualChoiceField(forms.ModelChoiceField):
    """Renders full name, ID, and gender in dropdown options."""
    def label_from_instance(self, obj):
        name = " ".join(p for p in [obj.first_name, obj.middle_name, obj.last_name] if p).strip() or "Unnamed"
        gender_icon = "♂" if obj.gender == 'M' else ("♀" if obj.gender == 'F' else "?")
        return f"{name} ({obj.individual_id}, {gender_icon})"


class DescriptiveMarriageChoiceField(forms.ModelChoiceField):
    """Renders parent union names in dropdown options."""
    def label_from_instance(self, obj):
        m_name = (" ".join(p for p in [obj.male_member.first_name, obj.male_member.last_name] if p).strip() or obj.male_member.individual_id) if obj.male_member else "Unknown"
        f_name = (" ".join(p for p in [obj.female_member.first_name, obj.female_member.last_name] if p).strip() or obj.female_member.individual_id) if obj.female_member else "Unknown"
        return f"{obj.marriage_id}: {m_name} & {f_name}"


class IndividualCompositeForm(forms.ModelForm):
    RELATION_CHOICES = [
        ('CHILD', 'Child — Add as son/daughter of an existing marriage union'),
        ('SPOUSE', 'Spouse — Add as husband/wife to an existing member'),
        ('PARENT', 'Parent — Add as father/mother to an existing member'),
    ]

    relation_type = forms.ChoiceField(
        choices=RELATION_CHOICES,
        initial='CHILD',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_relation_type'})
    )
    target_marriage = DescriptiveMarriageChoiceField(
        queryset=MarriageDetail.objects.all(),
        required=False,
        label="Parents' Marriage Union (M000000X)",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_target_marriage'})
    )
    parent_marriage = DescriptiveMarriageChoiceField(
        queryset=MarriageDetail.objects.all(),
        required=False,
        label="Parents / Lineage Union",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_parent_marriage'})
    )
    target_individual = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.all(),
        required=False,
        label="Target Family Member",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_target_individual'})
    )

    # 1. Demographics
    first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'First Name', 'id': 'id_first_name'}))
    middle_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Middle Name', 'id': 'id_middle_name'}))
    last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Last Name', 'id': 'id_last_name'}))
    gender = forms.ChoiceField(choices=IndividualDetail.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_gender'}))

    # Parents Direct Selection / Quick Add
    assign_father = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.none(),
        required=False,
        label="Father",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_assign_father'})
    )
    new_father_name = forms.CharField(max_length=100, required=False, label="Or Create New Father (Full Name)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. Robert Smith'}))

    assign_mother = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.none(),
        required=False,
        label="Mother",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_assign_mother'})
    )
    new_mother_name = forms.CharField(max_length=100, required=False, label="Or Create New Mother (Full Name)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. Mary Davis'}))

    # 2. Birth Event
    birth_date_text = forms.CharField(max_length=255, required=False, label="Birth Date (Text)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. 14 July 1942, Circa 1940'}))
    birth_date_precision = forms.ChoiceField(choices=getattr(DateDetail, 'PRECISION_CHOICES', [('EXACT', 'Exact'), ('MONTH', 'Month'), ('YEAR', 'Year'), ('UNKNOWN', 'Unknown')]), initial='EXACT', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    birth_date_qualifier = forms.ChoiceField(choices=getattr(DateDetail, 'QUALIFIER_CHOICES', [('NONE', 'None'), ('BEFORE', 'Before'), ('AFTER', 'After'), ('CIRCA', 'Circa'), ('BETWEEN', 'Between')]), initial='NONE', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_birth_qualifier'}))
    birth_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    birth_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm', 'id': 'id_birth_end'}))
    
    birth_place = forms.CharField(max_length=500, required=False, label="Birth Place", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place', 'id': 'id_birth_place', 'autocomplete': 'off'}))
    birth_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_birth_place_id'}))
    birth_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_birth_formatted_address'}))
    birth_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_birth_lat'}))
    birth_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_birth_lng'}))

    # 3. Death Event
    death_date_text = forms.CharField(max_length=255, required=False, label="Death Date (Text)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. November 1995'}))
    death_date_precision = forms.ChoiceField(choices=getattr(DateDetail, 'PRECISION_CHOICES', [('EXACT', 'Exact'), ('MONTH', 'Month'), ('YEAR', 'Year'), ('UNKNOWN', 'Unknown')]), initial='EXACT', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    death_date_qualifier = forms.ChoiceField(choices=getattr(DateDetail, 'QUALIFIER_CHOICES', [('NONE', 'None'), ('BEFORE', 'Before'), ('AFTER', 'After'), ('CIRCA', 'Circa'), ('BETWEEN', 'Between')]), initial='NONE', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_death_qualifier'}))
    death_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    death_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm', 'id': 'id_death_end'}))
    
    death_place = forms.CharField(max_length=500, required=False, label="Death Place", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place', 'id': 'id_death_place', 'autocomplete': 'off'}))
    death_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_death_place_id'}))
    death_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_death_formatted_address'}))
    death_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_death_lat'}))
    death_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_death_lng'}))

    # 4. Profile Photo
    profile_photo = forms.ImageField(required=False, label="Upload Profile Photo", widget=forms.FileInput(attrs={'class': 'form-control form-control-sm', 'accept': 'image/*'}))

    # 5. Spouse & Marriage Entry (Opposite-gender strict filtering)
    add_spouse_mode = forms.ChoiceField(
        choices=[('NONE', 'None'), ('EXISTING', 'Existing Member'), ('NEW', 'Quick-Add New Spouse')],
        initial='NONE',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_spouse_mode'})
    )
    existing_spouse = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.none(),
        required=False,
        label="Select Existing Member",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_existing_spouse'})
    )
    
    new_spouse_first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse First Name'}))
    new_spouse_middle_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse Middle Name'}))
    new_spouse_last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Spouse Last Name'}))

    # Standard genealogical date fields for marriage
    marriage_date_text = forms.CharField(max_length=255, required=False, label="Marriage Date (Text)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. 12 June 1970, Circa 1968'}))
    marriage_date_precision = forms.ChoiceField(choices=getattr(DateDetail, 'PRECISION_CHOICES', [('EXACT', 'Exact'), ('MONTH', 'Month'), ('YEAR', 'Year'), ('UNKNOWN', 'Unknown')]), initial='EXACT', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    marriage_date_qualifier = forms.ChoiceField(choices=getattr(DateDetail, 'QUALIFIER_CHOICES', [('NONE', 'None'), ('BEFORE', 'Before'), ('AFTER', 'After'), ('CIRCA', 'Circa'), ('BETWEEN', 'Between')]), initial='NONE', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_marriage_qualifier'}))
    marriage_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    marriage_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm', 'id': 'id_marriage_end'}))

    marriage_place = forms.CharField(max_length=500, required=False, label="Marriage Place", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search place or click map', 'id': 'id_marriage_place', 'autocomplete': 'off'}))
    marriage_place_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_marriage_place_id'}))
    marriage_formatted_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_marriage_formatted_address'}))
    marriage_lat = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_marriage_lat'}))
    marriage_lng = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm bg-light', 'readonly': 'readonly', 'id': 'id_marriage_lng'}))

    # Backward compatibility fields
    add_spouse = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    new_spouse_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Full Name'}))

    class Meta:
        model = IndividualDetail
        fields = ['first_name', 'middle_name', 'last_name', 'gender', 'parent_marriage']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        all_inds = IndividualDetail.objects.all().order_by('first_name', 'last_name')
        
        self.is_gender_locked = False
        current_gender = None

        if self.instance and self.instance.pk:
            all_inds = all_inds.exclude(pk=self.instance.pk)
            current_gender = self.instance.gender
            has_marriage = MarriageDetail.objects.filter(
                Q(male_member_id=self.instance.pk) | Q(female_member_id=self.instance.pk)
            ).exists()
            if has_marriage:
                self.is_gender_locked = True
                self.fields['gender'].disabled = True
                self.fields['gender'].help_text = "Gender is locked because this member is recorded in a marriage union."
        elif self.data and self.data.get('gender'):
            current_gender = self.data.get('gender')
        elif self.initial.get('gender'):
            current_gender = self.initial.get('gender')

        marriages_qs = MarriageDetail.objects.all().select_related('male_member', 'female_member').order_by('marriage_id')

        self.fields['target_individual'].queryset = all_inds
        self.fields['assign_father'].queryset = all_inds.filter(gender='M')
        self.fields['assign_mother'].queryset = all_inds.filter(gender='F')
        self.fields['add_spouse'].queryset = all_inds
        self.fields['target_marriage'].queryset = marriages_qs
        self.fields['parent_marriage'].queryset = marriages_qs

        # GENDER-STRICT SPOUSE FILTERING (SRS Section 6 & 34 Rule 10)
        if current_gender == 'M':
            # A male individual can only marry female members
            self.fields['existing_spouse'].queryset = all_inds.filter(gender='F')
        elif current_gender == 'F':
            # A female individual can only marry male members
            self.fields['existing_spouse'].queryset = all_inds.filter(gender='M')
        else:
            # Fallback if gender not yet established: exclude neither, client JS handles live switch
            self.fields['existing_spouse'].queryset = all_inds

        if self.instance and self.instance.pk:
            pm = self.instance.parent_marriage
            if pm:
                self.fields['parent_marriage'].initial = pm
                self.fields['target_marriage'].initial = pm
                if pm.male_member:
                    self.fields['assign_father'].initial = pm.male_member
                if pm.female_member:
                    self.fields['assign_mother'].initial = pm.female_member

            # Birth
            if self.instance.birth_date:
                bd = self.instance.birth_date
                self.fields['birth_date_text'].initial = bd.original_text
                self.fields['birth_date_precision'].initial = getattr(bd, 'precision', getattr(bd, 'precision_type', 'EXACT'))
                self.fields['birth_date_qualifier'].initial = bd.qualifier
                self.fields['birth_date_start'].initial = bd.start_date
                self.fields['birth_date_end'].initial = bd.end_date
            if self.instance.birth_location:
                bl = self.instance.birth_location
                self.fields['birth_place'].initial = bl.original_location
                self.fields['birth_place_id'].initial = bl.google_place_id
                self.fields['birth_formatted_address'].initial = bl.google_formatted_address
                self.fields['birth_lat'].initial = str(bl.latitude) if bl.latitude else ''
                self.fields['birth_lng'].initial = str(bl.longitude) if bl.longitude else ''

            # Death
            if self.instance.death_date:
                dd = self.instance.death_date
                self.fields['death_date_text'].initial = dd.original_text
                self.fields['death_date_precision'].initial = getattr(dd, 'precision', getattr(dd, 'precision_type', 'EXACT'))
                self.fields['death_date_qualifier'].initial = dd.qualifier
                self.fields['death_date_start'].initial = dd.start_date
                self.fields['death_date_end'].initial = dd.end_date
            if self.instance.death_location:
                dl = self.instance.death_location
                self.fields['death_place'].initial = dl.original_location
                self.fields['death_place_id'].initial = dl.google_place_id
                self.fields['death_formatted_address'].initial = dl.google_formatted_address
                self.fields['death_lat'].initial = str(dl.latitude) if dl.latitude else ''
                self.fields['death_lng'].initial = str(dl.longitude) if dl.longitude else ''

    def clean(self):
        cleaned_data = super().clean()
        validate_individual_name(
            cleaned_data.get('first_name', ''),
            cleaned_data.get('middle_name', ''),
            cleaned_data.get('last_name', '')
        )

        ind_gender = cleaned_data.get('gender')
        if self.instance and self.instance.pk and self.is_gender_locked:
            ind_gender = self.instance.gender
            cleaned_data['gender'] = ind_gender

        # Validation: Verify that existing spouse is strictly opposite gender
        spouse_mode = cleaned_data.get('add_spouse_mode')
        ex_spouse = cleaned_data.get('existing_spouse')
        if spouse_mode == 'EXISTING' and ex_spouse:
            if ind_gender and ex_spouse.gender == ind_gender:
                raise ValidationError(
                    f"Invalid marriage: Both partners cannot be {dict(IndividualDetail.GENDER_CHOICES).get(ind_gender)}. "
                    "Marriages must be between male and female members only."
                )

        if cleaned_data.get('birth_date_qualifier') == 'BETWEEN':
            if not cleaned_data.get('birth_date_start') or not cleaned_data.get('birth_date_end'):
                raise ValidationError("Both Start Date and End Date are required when using the 'Between' date qualifier for Birth.")

        if cleaned_data.get('death_date_qualifier') == 'BETWEEN':
            if not cleaned_data.get('death_date_start') or not cleaned_data.get('death_date_end'):
                raise ValidationError("Both Start Date and End Date are required when using the 'Between' date qualifier for Death.")

        if cleaned_data.get('marriage_date_qualifier') == 'BETWEEN':
            if not cleaned_data.get('marriage_date_start') or not cleaned_data.get('marriage_date_end'):
                raise ValidationError("Both Start Date and End Date are required when using the 'Between' date qualifier for Marriage.")

        total_individuals = IndividualDetail.objects.count()
        if total_individuals == 0 and not (self.instance and self.instance.pk):
            return cleaned_data

        if self.instance and self.instance.pk:
            is_already_connected = (
                self.instance.parent_marriage_id is not None or
                MarriageDetail.objects.filter(
                    Q(male_member_id=self.instance.pk) | Q(female_member_id=self.instance.pk)
                ).exists()
            )
            if is_already_connected:
                return cleaned_data

        p_marriage = cleaned_data.get('parent_marriage') or cleaned_data.get('target_marriage')
        t_individual = cleaned_data.get('target_individual')
        father = cleaned_data.get('assign_father') or cleaned_data.get('new_father_name')
        mother = cleaned_data.get('assign_mother') or cleaned_data.get('new_mother_name')
        spouse = (
            cleaned_data.get('add_spouse') or 
            cleaned_data.get('new_spouse_name') or 
            (cleaned_data.get('add_spouse_mode') != 'NONE')
        )

        if not (p_marriage or t_individual or father or mother or spouse):
            raise ValidationError(
                "An individual cannot exist disconnected from the tree. You must choose a relationship: "
                "attach to a Parent Marriage Union, assign Father/Mother, or connect as a Spouse."
            )

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True, user_id=None, locked_parent_marriage=None):
        individual = super().save(commit=False)
        is_new_record = not bool(individual.pk)

        if not is_new_record and self.is_gender_locked:
            individual.gender = self.instance.gender

        # 1. Birth Date & Location
        b_text = self.cleaned_data.get('birth_date_text')
        b_start = self.cleaned_data.get('birth_date_start')
        if b_text or b_start:
            bd = individual.birth_date or DateDetail()
            bd.original_text = b_text or str(b_start)
            prec = self.cleaned_data.get('birth_date_precision', 'EXACT')
            if hasattr(bd, 'precision'):
                bd.precision = prec
            else:
                bd.precision_type = prec
            bd.qualifier = self.cleaned_data.get('birth_date_qualifier', 'NONE')
            bd.start_date = b_start
            bd.end_date = self.cleaned_data.get('birth_date_end')
            bd.save()
            individual.birth_date = bd
        elif individual.birth_date and not b_text and not b_start:
            individual.birth_date = None

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
            bl.status = 'USER_CONFIRMED' if bl.google_place_id else 'ENTERED'
            bl.save()
            individual.birth_location = bl
        elif individual.birth_location and not b_place:
            individual.birth_location = None

        # 2. Death Date & Location
        d_text = self.cleaned_data.get('death_date_text')
        d_start = self.cleaned_data.get('death_date_start')
        if d_text or d_start:
            dd = individual.death_date or DateDetail()
            dd.original_text = d_text or str(d_start)
            prec = self.cleaned_data.get('death_date_precision', 'EXACT')
            if hasattr(dd, 'precision'):
                dd.precision = prec
            else:
                dd.precision_type = prec
            dd.qualifier = self.cleaned_data.get('death_date_qualifier', 'NONE')
            dd.start_date = d_start
            dd.end_date = self.cleaned_data.get('death_date_end')
            dd.save()
            individual.death_date = dd
        elif individual.death_date and not d_text and not d_start:
            individual.death_date = None

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
            dl.status = 'USER_CONFIRMED' if dl.google_place_id else 'ENTERED'
            dl.save()
            individual.death_location = dl
        elif individual.death_location and not d_place:
            individual.death_location = None

        # 3. Direct Father and Mother Assignment or Creation
        father = self.cleaned_data.get('assign_father')
        new_f_name = self.cleaned_data.get('new_father_name')
        if not father and new_f_name:
            parts = new_f_name.strip().split()
            fn = parts[0] if len(parts) > 0 else "Father"
            ln = parts[-1] if len(parts) > 1 else ""
            father = IndividualDetail.objects.create(first_name=fn, last_name=ln, gender='M')

        mother = self.cleaned_data.get('assign_mother')
        new_m_name = self.cleaned_data.get('new_mother_name')
        if not mother and new_m_name:
            parts = new_m_name.strip().split()
            fn = parts[0] if len(parts) > 0 else "Mother"
            ln = parts[-1] if len(parts) > 1 else ""
            mother = IndividualDetail.objects.create(first_name=fn, last_name=ln, gender='F')

        p_marriage = locked_parent_marriage or self.cleaned_data.get('parent_marriage') or self.cleaned_data.get('target_marriage')

        if p_marriage:
            individual.parent_marriage = p_marriage
        elif father or mother:
            pm = individual.parent_marriage
            if pm:
                fields_to_update = []
                if father and pm.male_member_id != father.pk:
                    pm.male_member = father
                    fields_to_update.append('male_member')
                if mother and pm.female_member_id != mother.pk:
                    pm.female_member = mother
                    fields_to_update.append('female_member')
                if fields_to_update:
                    pm.save(update_fields=fields_to_update)
            else:
                if father and mother:
                    pm = MarriageDetail.objects.filter(male_member=father, female_member=mother).first()
                    if not pm:
                        pm = MarriageDetail.objects.create(male_member=father, female_member=mother)
                elif father:
                    pm = MarriageDetail.objects.filter(male_member=father, female_member__isnull=True).first()
                    if not pm:
                        pm = MarriageDetail.objects.create(male_member=father)
                elif mother:
                    pm = MarriageDetail.objects.filter(female_member=mother, male_member__isnull=True).first()
                    if not pm:
                        pm = MarriageDetail.objects.create(female_member=mother)
                individual.parent_marriage = pm

        if commit:
            individual.save()

        # 4. Handle Kinship setup if added via Wizard
        if is_new_record and commit:
            rel_type = self.cleaned_data.get('relation_type')
            t_ind = self.cleaned_data.get('target_individual')
            if rel_type == 'SPOUSE' and t_ind:
                male = individual if individual.gender == 'M' else t_ind
                female = t_ind if individual.gender == 'M' else individual
                if not MarriageDetail.objects.filter(male_member=male, female_member=female).exists():
                    MarriageDetail.objects.create(male_member=male, female_member=female)
            elif rel_type == 'PARENT' and t_ind:
                t_pm = t_ind.parent_marriage
                if t_pm:
                    if individual.gender == 'M' and not t_pm.male_member_id:
                        t_pm.male_member = individual
                        t_pm.save(update_fields=['male_member'])
                    elif individual.gender == 'F' and not t_pm.female_member_id:
                        t_pm.female_member = individual
                        t_pm.save(update_fields=['female_member'])
                else:
                    if individual.gender == 'M':
                        new_pm = MarriageDetail.objects.create(male_member=individual)
                    else:
                        new_pm = MarriageDetail.objects.create(female_member=individual)
                    t_ind.parent_marriage = new_pm
                    t_ind.save(update_fields=['parent_marriage'])

        # 5. Handle Spouse Assignment via Form (Strict Male-Female Mapping)
        spouse_obj = None
        spouse_mode = self.cleaned_data.get('add_spouse_mode')

        if spouse_mode == 'EXISTING':
            spouse_obj = self.cleaned_data.get('existing_spouse')
        elif spouse_mode == 'NEW':
            fn = self.cleaned_data.get('new_spouse_first_name', '').strip()
            mn = self.cleaned_data.get('new_spouse_middle_name', '').strip()
            ln = self.cleaned_data.get('new_spouse_last_name', '').strip()
            if fn or mn or ln:
                # Automatically assign opposite gender
                spouse_gender = 'F' if individual.gender == 'M' else 'M'
                spouse_obj = IndividualDetail.objects.create(
                    first_name=fn,
                    middle_name=mn,
                    last_name=ln,
                    gender=spouse_gender
                )
        else:
            add_sp = self.cleaned_data.get('add_spouse')
            new_sp_name = self.cleaned_data.get('new_spouse_name')
            if add_sp:
                spouse_obj = add_sp
            elif new_sp_name:
                parts = new_sp_name.strip().split()
                fn = parts[0] if len(parts) > 0 else "Spouse"
                ln = parts[-1] if len(parts) > 1 else ""
                spouse_gender = 'F' if individual.gender == 'M' else 'M'
                spouse_obj = IndividualDetail.objects.create(first_name=fn, last_name=ln, gender=spouse_gender)

        if spouse_obj and commit:
            m_date_obj = None
            m_text = self.cleaned_data.get('marriage_date_text')
            m_start = self.cleaned_data.get('marriage_date_start')
            if m_text or m_start:
                m_date_obj = DateDetail.objects.create(
                    original_text=m_text or str(m_start),
                    precision=self.cleaned_data.get('marriage_date_precision', 'EXACT'),
                    qualifier=self.cleaned_data.get('marriage_date_qualifier', 'NONE'),
                    start_date=m_start,
                    end_date=self.cleaned_data.get('marriage_date_end')
                )

            m_loc_obj = None
            m_place = self.cleaned_data.get('marriage_place')
            if m_place:
                m_lat = self.cleaned_data.get('marriage_lat')
                m_lng = self.cleaned_data.get('marriage_lng')
                m_loc_obj = LocationDetail.objects.create(
                    original_location=m_place,
                    google_place_id=self.cleaned_data.get('marriage_place_id') or None,
                    google_formatted_address=self.cleaned_data.get('marriage_formatted_address') or None,
                    latitude=Decimal(m_lat) if m_lat else None,
                    longitude=Decimal(m_lng) if m_lng else None,
                    status='USER_CONFIRMED' if self.cleaned_data.get('marriage_place_id') else 'ENTERED'
                )

            # Strictly assign male to male_member and female to female_member
            male = individual if individual.gender == 'M' else spouse_obj
            female = spouse_obj if individual.gender == 'M' else individual

            if not MarriageDetail.objects.filter(male_member=male, female_member=female).exists():
                MarriageDetail.objects.create(
                    male_member=male,
                    female_member=female,
                    marriage_date=m_date_obj,
                    marriage_location=m_loc_obj
                )

        # 6. Profile Photo
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

        return individual


class MarriageCompositeForm(forms.ModelForm):
    marriage_date_text = forms.CharField(max_length=255, required=False, label="Marriage Date (Text)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. 12 June 1970, Circa 1968'}))
    marriage_date_precision = forms.ChoiceField(choices=getattr(DateDetail, 'PRECISION_CHOICES', [('EXACT', 'Exact'), ('MONTH', 'Month'), ('YEAR', 'Year'), ('UNKNOWN', 'Unknown')]), initial='EXACT', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    marriage_date_qualifier = forms.ChoiceField(choices=getattr(DateDetail, 'QUALIFIER_CHOICES', [('NONE', 'None'), ('BEFORE', 'Before'), ('AFTER', 'After'), ('CIRCA', 'Circa'), ('BETWEEN', 'Between')]), initial='NONE', required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_marriage_qualifier'}))
    marriage_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    marriage_date_end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm', 'id': 'id_marriage_end'}))
    
    marriage_location_text = forms.CharField(max_length=500, required=False, label="Marriage Place", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'City, State, Country', 'id': 'id_marriage_location_text', 'autocomplete': 'off'}))
    separation_date_text = forms.CharField(max_length=255, required=False, label="Separation Date (Text)", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. 1985'}))
    separation_date_start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    separation_reason = forms.ChoiceField(choices=[('', '---------')] + getattr(MarriageDetail, 'SEPARATION_REASONS', []), required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))

    male_member = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.filter(gender='M'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    female_member = DescriptiveIndividualChoiceField(
        queryset=IndividualDetail.objects.filter(gender='F'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    class Meta:
        model = MarriageDetail
        fields = ['male_member', 'female_member', 'separation_reason']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.marriage_date:
                md = self.instance.marriage_date
                self.fields['marriage_date_text'].initial = md.original_text
                prec = getattr(md, 'precision', getattr(md, 'precision_type', 'EXACT'))
                self.fields['marriage_date_precision'].initial = prec
                self.fields['marriage_date_qualifier'].initial = md.qualifier
                self.fields['marriage_date_start'].initial = md.start_date
                self.fields['marriage_date_end'].initial = md.end_date

            if self.instance.marriage_location:
                self.fields['marriage_location_text'].initial = self.instance.marriage_location.original_location

            if self.instance.separation_date:
                sd = self.instance.separation_date
                self.fields['separation_date_text'].initial = sd.original_text
                self.fields['separation_date_start'].initial = sd.start_date

    @transaction.atomic
    def save(self, commit=True):
        marriage = super().save(commit=False)
        m_text = self.cleaned_data.get('marriage_date_text')
        m_start = self.cleaned_data.get('marriage_date_start')
        if m_text or m_start:
            md = marriage.marriage_date or DateDetail()
            md.original_text = m_text or str(m_start)
            prec = self.cleaned_data.get('marriage_date_precision', 'EXACT')
            if hasattr(md, 'precision'):
                md.precision = prec
            else:
                md.precision_type = prec
            md.qualifier = self.cleaned_data.get('marriage_date_qualifier', 'NONE')
            md.start_date = m_start
            md.end_date = self.cleaned_data.get('marriage_date_end')
            md.save()
            marriage.marriage_date = md
        elif marriage.marriage_date and not m_text and not m_start:
            marriage.marriage_date = None

        m_loc_text = self.cleaned_data.get('marriage_location_text')
        if m_loc_text:
            ml = marriage.marriage_location or LocationDetail()
            ml.original_location = m_loc_text
            ml.save()
            marriage.marriage_location = ml
        elif marriage.marriage_location and not m_loc_text:
            marriage.marriage_location = None

        s_text = self.cleaned_data.get('separation_date_text')
        s_start = self.cleaned_data.get('separation_date_start')
        if s_text or s_start:
            sd = marriage.separation_date or DateDetail()
            sd.original_text = s_text or str(s_start)
            sd.start_date = s_start
            sd.save()
            marriage.separation_date = sd
        elif marriage.separation_date and not s_text and not s_start:
            marriage.separation_date = None

        if commit:
            marriage.save()
        return marriage