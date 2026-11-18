# apps/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponseForbidden
from django.urls import reverse

from accounts.models import UserAccess, UserAccessScope, UserDetail
from accounts.forms import GrantAccessForm, SendInvitationForm, RegisterInvitedUserForm, MemberLoginForm
from accounts.tokens import InvitationTokenService


def landing_view(request):
    """
    Public landing page showing platform capabilities and the login portal.
    If already authenticated, redirects directly to the main dashboard.
    """
    if request.user.is_authenticated:
        return redirect('genealogy:dashboard')

    form = MemberLoginForm()
    return render(request, 'landing.html', {'form': form})

def login_view(request):
    """Handles submission of member credentials."""
    if request.user.is_authenticated:
        return redirect('genealogy:dashboard')

    if request.method == 'POST':
        form = MemberLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.pk}!")
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'genealogy:my_tree')
        else:
            messages.error(request, "Invalid Member ID or password. Please try again.")
    else:
        form = MemberLoginForm()

    return render(request, 'landing.html', {'form': form})

def logout_view(request):
    """Terminates session and returns to the public landing page."""
    logout(request)
    messages.info(request, "You have been safely signed out.")
    return redirect('accounts:login')

@login_required
def access_dashboard_view(request):
    """
    SRS Section 8 & Option B Dashboard:
    - Lists access grants issued by the logged-in user.
    - Lists access grants received by the logged-in user.
    - Form to create new grants with scope.
    """
    current_user = request.user

    # Grants issued by current user
    issued_grants = UserAccess.objects.filter(
        host_user=current_user
    ).select_related('granted_to_user__user_id', 'granted_by_user').prefetch_related('scopes__scope_individual')

    # Grants received by current user
    received_grants = UserAccess.objects.filter(
        granted_to_user=current_user
    ).select_related('host_user__user_id').prefetch_related('scopes__scope_individual')

    if request.method == 'POST':
        form = GrantAccessForm(request.POST, request_user=current_user)
        if form.is_valid():
            with transaction.atomic():
                grantee = form.cleaned_data['granted_to_user']
                acc_type = form.cleaned_data['access_type']
                anchor_ind = form.cleaned_data['scope_individual']
                mode = form.cleaned_data['scope_mode']

                # Create master grant
                access_grant = UserAccess.objects.create(
                    host_user=current_user,
                    granted_to_user=grantee,
                    access_type=acc_type,
                    access_status='ACTIVE',
                    granted_by_user=current_user,
                    granted_on=timezone.now()
                )

                # Create normalized scope
                UserAccessScope.objects.create(
                    access=access_grant,
                    scope_individual=anchor_ind,
                    scope_mode=mode
                )

            messages.success(request, f"Successfully granted {acc_type} access to {grantee.user_id}.")
            return redirect('accounts:access_dashboard')
    else:
        form = GrantAccessForm(request_user=current_user)

    return render(request, 'accounts/access_dashboard.html', {
        'form': form,
        'issued_grants': issued_grants,
        'received_grants': received_grants,
    })


@login_required
def revoke_access_view(request, access_id):
    """
    SRS Section 25: Immediately revokes an access grant.
    """
    grant = get_object_or_404(UserAccess, pk=access_id)

    # Security check: Only the host user or superuser may revoke
    if grant.host_user != request.user and not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to revoke this grant.")

    if request.method == 'POST':
        grant.access_status = 'REVOKED'
        grant.revoked_on = timezone.now()
        grant.save(update_fields=['access_status', 'revoked_on', 'modified_on'])

        messages.warning(request, f"Access grant #{grant.access_id} has been revoked immediately.")
        return redirect('accounts:access_dashboard')

    return render(request, 'accounts/confirm_revoke.html', {'grant': grant})

@login_required
def invite_member_view(request):
    """
    SRS Section 7.2: Existing user generates a tokenized invitation
    for an unlinked Individual node.
    """
    generated_invite = None

    if request.method == 'POST':
        form = SendInvitationForm(request.POST)
        if form.is_valid():
            target_person = form.cleaned_data['target_individual']
            token = InvitationTokenService.generate_token(
                individual_id=target_person.individual_id,
                host_user_id=str(request.user.pk)
            )

            relative_url = reverse('accounts:register_invited_user', kwargs={'token': token})
            full_invite_link = request.build_absolute_uri(relative_url)

            # Retrieve available contact channels
            primary_email = target_person.emails.filter(is_active=True).first()
            primary_phone = target_person.phones.filter(is_active=True).first()

            generated_invite = {
                'person': target_person,
                'link': full_invite_link,
                'email': primary_email.email_address if primary_email else None,
                'phone': f"{primary_phone.country_code} {primary_phone.phone_number}" if primary_phone else None,
            }
            messages.success(request, f"Invitation link generated for {target_person.first_name} {target_person.last_name}.")
    else:
        form = SendInvitationForm()

    return render(request, 'accounts/invite_member.html', {
        'form': form,
        'generated_invite': generated_invite,
    })


def register_invited_user_view(request, token):
    """
    SRS Section 7.1 & 7.2: Recipient clicks token link, confirms identity,
    sets their password, and creates their UserDetail record (User_Id == Individual_Id).
    """
    # 1. Validate cryptographic token & single-use constraints
    try:
        individual, host_user = InvitationTokenService.validate_token(token)
    except ValueError as err:
        return render(request, 'accounts/registration_error.html', {'error_message': str(err)})

    # 2. Process account creation
    if request.method == 'POST':
        form = RegisterInvitedUserForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                password = form.cleaned_data['password']

                # Create UserDetail with PK == Individual_Id
                new_user = UserDetail.objects.create(
                    user_id=individual,
                    invited_by_user=host_user,
                    user_status='ACTIVE',
                    is_active=True,
                    created_by=str(host_user.pk) if host_user else individual.individual_id,
                    modified_by=individual.individual_id,
                )
                new_user.set_password(password)
                new_user.save()

            messages.success(request, f"Welcome to the family tree, {individual.first_name}! Your account is now active.")
            login(request, new_user)
            return redirect('accounts:access_dashboard')
    else:
        form = RegisterInvitedUserForm()

    return render(request, 'accounts/register_invited.html', {
        'form': form,
        'individual': individual,
        'host_user': host_user,
        'token': token,
    })