# apps/common/forms.py
from django import forms
from .models import LocationDetail


class LocationDetailAdminForm(forms.ModelForm):
    # Render Google-verified metadata as disabled/read-only inputs
    google_place_id = forms.CharField(
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'readonly-input',
            'style': 'background-color: #f1f5f9; cursor: not-allowed; width: 100%; max-width: 600px;',
            'placeholder': 'Auto-populated via Google Places'
        })
    )
    google_formatted_address = forms.CharField(
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'readonly-input',
            'style': 'background-color: #f1f5f9; cursor: not-allowed; width: 100%; max-width: 600px;',
            'placeholder': 'Auto-populated via Google Places'
        })
    )
    latitude = forms.DecimalField(
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'readonly-input',
            'style': 'background-color: #f1f5f9; cursor: not-allowed; width: 250px;',
            'placeholder': 'Auto-populated'
        })
    )
    longitude = forms.DecimalField(
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'readonly-input',
            'style': 'background-color: #f1f5f9; cursor: not-allowed; width: 250px;',
            'placeholder': 'Auto-populated'
        })
    )

    class Meta:
        model = LocationDetail
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        # Because disabled fields are ignored by standard POST in HTML,
        # read the raw submitted POST data so Google-populated values persist
        for field_name in ('google_place_id', 'google_formatted_address', 'latitude', 'longitude'):
            submitted_val = self.data.get(field_name)
            if submitted_val:
                cleaned_data[field_name] = submitted_val
        return cleaned_data