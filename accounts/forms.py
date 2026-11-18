# apps/accounts/forms.py
from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import AuthenticationForm
from accounts.models import UserAccess, UserAccessScope, UserDetail
from genealogy.models import IndividualDetail

class SendInvitationForm(forms.Form):
    target_individual = forms.ModelChoiceField(
        queryset=IndividualDetail.objects.none(),
        label="Select Family Member to Invite",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Only family members with an active email or phone number and no existing account are eligible."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude individuals who already have a registered UserDetail account
        existing_user_ids = UserDetail.objects.values_list('user_id', flat=True)
        
        # Filter for members who have at least one active phone OR email
        eligible_individuals = IndividualDetail.objects.exclude(
            individual_id__in=existing_user_ids
        ).filter(
            Q(emails__is_active=True) | Q(phones__is_active=True)
        ).distinct()

        self.fields['target_individual'].queryset = eligible_individuals


class RegisterInvitedUserForm(forms.Form):
    password = forms.CharField(
        label="Create Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter strong password'}),
        help_text="Must contain at least 8 characters and satisfy password complexity rules."
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match. Please re-enter both fields.")
        return cleaned_data


class GrantAccessForm(forms.Form):
    granted_to_user = forms.ModelChoiceField(
        queryset=UserDetail.objects.filter(is_active=True),
        label="Select Registered User",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Choose which registered family member will receive permissions."
    )
    access_type = forms.ChoiceField(
        choices=UserAccess.ACCESS_TYPES,
        initial='VIEW',
        label="Permission Level",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="ViewAccess allows reading protected dates and contacts. EditAccess also permits modifications."
    )
    scope_individual = forms.ModelChoiceField(
        queryset=IndividualDetail.objects.all(),
        label="Anchor Individual",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the root individual for this permission grant."
    )
    scope_mode = forms.ChoiceField(
        choices=UserAccessScope.SCOPE_MODES,
        initial='INDIVIDUAL_AND_BRANCH',
        label="Scope Mode",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Choose whether this permission applies solely to this person or propagates recursively."
    )

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        if self.request_user:
            self.fields['granted_to_user'].queryset = UserDetail.objects.filter(
                is_active=True
            ).exclude(pk=self.request_user.pk)

    def clean(self):
        cleaned_data = super().clean()
        grantee = cleaned_data.get('granted_to_user')
        if grantee and self.request_user and grantee.pk == self.request_user.pk:
            raise ValidationError("You cannot grant access to yourself.")
        return cleaned_data

    
class MemberLoginForm(AuthenticationForm):
    """
    Standard authentication form using Individual_Id / User_Id (e.g. I0000001)
    and secure hashed passwords.
    """
    username = forms.CharField(
        label="Member ID / User ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. I0000001',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
        })
    )