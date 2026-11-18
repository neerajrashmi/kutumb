# apps/contacts/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.services import AuthorizationService
from contacts.forms import (
    IndividualAddressCompositeForm,
    IndividualEmailForm,
    IndividualPhoneForm,
)
from contacts.models import IndividualAddress, IndividualEmail, IndividualPhone
from genealogy.models import IndividualDetail


@login_required
def individual_contacts_manage_view(request, individual_id):
    """
    Main contact management hub for an individual.
    Verifies lineage or permission grants (SRS 8, 10, 12, 13, 14) and
    manages Addresses, Phones, and Emails.
    """
    person = get_object_or_404(IndividualDetail, pk=individual_id)
    requesting_user_id = str(request.user.pk)

    can_view, can_edit = AuthorizationService.get_user_permissions(requesting_user_id, person)
    if not can_view:
        return HttpResponseForbidden("You are not authorized to view contact information for this member.")

    addresses = person.addresses.select_related('location', 'from_date', 'to_date').order_by('-is_active', '-is_primary', '-created_on')
    phones = person.phones.all().order_by('-is_active', '-created_on')
    emails = person.emails.all().order_by('-is_active', '-created_on')

    address_form = IndividualAddressCompositeForm()
    phone_form = IndividualPhoneForm()
    email_form = IndividualEmailForm()

    maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')

    return render(request, 'contacts/manage_contacts.html', {
        'person': person,
        'addresses': addresses,
        'phones': phones,
        'emails': emails,
        'address_form': address_form,
        'phone_form': phone_form,
        'email_form': email_form,
        'can_edit': can_edit,
        'GOOGLE_MAPS_API_KEY': maps_api_key,
        'google_maps_api_key': maps_api_key,
    })


@login_required
def add_physical_address(request, individual_id):
    """
    Adds a new physical address with Google Place ID and geocoding coordinates.
    Enforces maximum 2 active addresses and the primary rule.
    """
    person = get_object_or_404(IndividualDetail, pk=individual_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to add addresses for this member.")

    if request.method == 'POST':
        form = IndividualAddressCompositeForm(request.POST)
        if form.is_valid():
            try:
                form.save(individual=person)
                messages.success(request, "Physical address successfully recorded.")
            except Exception as e:
                messages.error(request, f"Error saving address: {e}")
        else:
            error_msgs = [f"{field}: {errs[0]}" for field, errs in form.errors.items()]
            messages.error(request, "Validation error: " + " | ".join(error_msgs))

    return redirect('contacts:manage_contacts', individual_id=individual_id)


@login_required
def edit_address_view(request, address_id):
    """
    Updates an existing physical address.
    """
    addr = get_object_or_404(IndividualAddress, pk=address_id)
    person = addr.individual
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to edit addresses for this member.")

    if request.method == 'POST':
        form = IndividualAddressCompositeForm(request.POST, instance=addr)
        if form.is_valid():
            try:
                form.save(individual=person)
                messages.success(request, "Address updated successfully.")
                return redirect('contacts:manage_contacts', individual_id=person.individual_id)
            except Exception as e:
                messages.error(request, f"Error updating address: {e}")
        else:
            error_msgs = [f"{field}: {errs[0]}" for field, errs in form.errors.items()]
            messages.error(request, "Validation error: " + " | ".join(error_msgs))
    else:
        form = IndividualAddressCompositeForm(instance=addr)

    maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    return render(request, 'contacts/edit_address.html', {
        'form': form,
        'person': person,
        'address': addr,
        'GOOGLE_MAPS_API_KEY': maps_api_key,
        'google_maps_api_key': maps_api_key,
    })


@login_required
def toggle_address_primary_view(request, address_id):
    """
    Designates an active address as primary and adjusts other active addresses.
    """
    addr = get_object_or_404(IndividualAddress, pk=address_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), addr.individual)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to modify addresses for this member.")

    if not addr.is_active:
        messages.warning(request, "Cannot set an inactive address as primary.")
    else:
        # Demote existing active primary addresses
        IndividualAddress.objects.filter(
            individual=addr.individual,
            is_active=True
        ).exclude(pk=addr.pk).update(is_primary=False)

        addr.is_primary = True
        addr.save(update_fields=['is_primary'])
        messages.success(request, "Primary address updated.")

    return redirect('contacts:manage_contacts', individual_id=addr.individual_id)


@login_required
def add_phone(request, individual_id):
    """
    Adds a phone number with country code, enforcing maximum 3 active items.
    """
    person = get_object_or_404(IndividualDetail, pk=individual_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to add phone numbers for this member.")

    if request.method == 'POST':
        form = IndividualPhoneForm(request.POST)
        if form.is_valid():
            active_count = person.phones.filter(is_active=True).count()
            if form.cleaned_data.get('is_active') and active_count >= 3:
                messages.error(request, "Maximum of 3 active phone numbers permitted.")
            else:
                phone = form.save(commit=False)
                phone.individual = person
                phone.save()
                messages.success(request, f"Phone {phone.country_code} {phone.phone_number} added.")
        else:
            messages.error(request, "Invalid phone number input.")

    return redirect('contacts:manage_contacts', individual_id=individual_id)


@login_required
def edit_phone_view(request, phone_id):
    """
    Updates an existing phone number.
    """
    phone = get_object_or_404(IndividualPhone, pk=phone_id)
    person = phone.individual
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to edit phone numbers for this member.")

    if request.method == 'POST':
        form = IndividualPhoneForm(request.POST, instance=phone)
        if form.is_valid():
            form.save()
            messages.success(request, "Phone record updated.")
            return redirect('contacts:manage_contacts', individual_id=person.individual_id)
        else:
            messages.error(request, "Invalid phone input.")
    else:
        form = IndividualPhoneForm(instance=phone)

    return render(request, 'contacts/edit_contact.html', {
        'form': form,
        'person': person,
        'title': f"Edit Phone for {person}",
        'item_type': 'Phone'
    })


@login_required
def toggle_phone_status_view(request, phone_id):
    """
    Toggles phone active status while maintaining the max 3 limit.
    """
    phone = get_object_or_404(IndividualPhone, pk=phone_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), phone.individual)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to modify this phone record.")

    if not phone.is_active:
        active_count = phone.individual.phones.filter(is_active=True).count()
        if active_count >= 3:
            messages.error(request, "Cannot activate: Maximum 3 active phone numbers reached.")
            return redirect('contacts:manage_contacts', individual_id=phone.individual_id)

    phone.is_active = not phone.is_active
    phone.save(update_fields=['is_active'])
    messages.success(request, f"Phone status updated to {'Active' if phone.is_active else 'Inactive'}.")
    return redirect('contacts:manage_contacts', individual_id=phone.individual_id)


@login_required
def add_email(request, individual_id):
    """
    Adds an email address, enforcing maximum 3 active items.
    """
    person = get_object_or_404(IndividualDetail, pk=individual_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to add email addresses for this member.")

    if request.method == 'POST':
        form = IndividualEmailForm(request.POST)
        if form.is_valid():
            active_count = person.emails.filter(is_active=True).count()
            if form.cleaned_data.get('is_active') and active_count >= 3:
                messages.error(request, "Maximum of 3 active email addresses permitted.")
            else:
                email = form.save(commit=False)
                email.individual = person
                email.save()
                messages.success(request, f"Email {email.email_address} added.")
        else:
            messages.error(request, "Invalid email address format.")

    return redirect('contacts:manage_contacts', individual_id=individual_id)


@login_required
def edit_email_view(request, email_id):
    """
    Updates an existing email address.
    """
    email = get_object_or_404(IndividualEmail, pk=email_id)
    person = email.individual
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), person)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to edit email addresses for this member.")

    if request.method == 'POST':
        form = IndividualEmailForm(request.POST, instance=email)
        if form.is_valid():
            form.save()
            messages.success(request, "Email record updated.")
            return redirect('contacts:manage_contacts', individual_id=person.individual_id)
        else:
            messages.error(request, "Invalid email format.")
    else:
        form = IndividualEmailForm(instance=email)

    return render(request, 'contacts/edit_contact.html', {
        'form': form,
        'person': person,
        'title': f"Edit Email for {person}",
        'item_type': 'Email'
    })


@login_required
def toggle_email_status_view(request, email_id):
    """
    Toggles email active status while maintaining the max 3 limit.
    """
    email = get_object_or_404(IndividualEmail, pk=email_id)
    _, can_edit = AuthorizationService.get_user_permissions(str(request.user.pk), email.individual)
    if not can_edit:
        return HttpResponseForbidden("You do not have permission to modify this email record.")

    if not email.is_active:
        active_count = email.individual.emails.filter(is_active=True).count()
        if active_count >= 3:
            messages.error(request, "Cannot activate: Maximum 3 active email addresses reached.")
            return redirect('contacts:manage_contacts', individual_id=email.individual_id)

    email.is_active = not email.is_active
    email.save(update_fields=['is_active'])
    messages.success(request, f"Email status updated to {'Active' if email.is_active else 'Inactive'}.")
    return redirect('contacts:manage_contacts', individual_id=email.individual_id)