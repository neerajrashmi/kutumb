"""
apps/genealogy/views.py
Controller views for interactive tree visualization, JSON API streaming,
combobox member searching, and contextual family member creation/editing.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q

from genealogy.models import IndividualDetail, MarriageDetail
from media_mgmt.models import PhotoDetail
from accounts.permissions import (
    get_user_individual_permissions,
    has_protected_read_access,
)
from .forms import IndividualCompositeForm
from .services import GenealogyTreeService


@login_required
def executive_dashboard_view(request):
    """
    Renders the executive overview dashboard summarizing the user's
    family branch, active quotas, and recent genealogy records.
    """
    user_ind_id = str(request.user.pk)
    user_individual = IndividualDetail.objects.filter(pk=user_ind_id).first()

    total_individuals = IndividualDetail.objects.count()
    total_marriages = MarriageDetail.objects.count()

    if hasattr(PhotoDetail, 'active_flag'):
        total_photos = PhotoDetail.objects.filter(active_flag=True).count()
    elif hasattr(PhotoDetail, 'is_active'):
        total_photos = PhotoDetail.objects.filter(is_active=True).count()
    else:
        total_photos = PhotoDetail.objects.count()

    recent_members = IndividualDetail.objects.order_by('-created_on')[:5]

    return render(request, 'genealogy/dashboard.html', {
        'anchor_person': user_individual,
        'user_individual': user_individual,
        'current_user_id': user_ind_id,
        'total_individuals': total_individuals,
        'total_marriages': total_marriages,
        'total_photos': total_photos,
        'recent_members': recent_members,
    })


@login_required
def tree_view(request, individual_id=None):
    """
    Renders the interactive SVG/D3 pedigree visualizer container.
    """
    if not individual_id or individual_id in ('undefined', 'None', ''):
        individual_id = str(request.user.pk)
        return redirect('genealogy:individual_tree', individual_id=individual_id)

    focus_person = get_object_or_404(IndividualDetail, pk=individual_id)
    return render(request, 'genealogy/tree.html', {'focus_person': focus_person})


@login_required
def tree_data_api(request, individual_id):
    """
    API endpoint delivering unified multi-generational graph payload:
    Focus person, all spouses, recursive ancestors, parental siblings, and descendants.
    """
    req_user = str(request.user.pk)
    unified = GenealogyTreeService.get_unified_tree(individual_id, requesting_user_id=req_user)
    
    return JsonResponse({
        'root_id': individual_id,
        'unified': unified,
        'can_view_protected': has_protected_read_access(req_user, individual_id)
    })


@login_required
def individual_search_api(request):
    """
    API endpoint for TomSelect combobox searches.
    Searches by name or Individual ID, with optional gender and self-exclusion filters.
    """
    query = request.GET.get('q', '').strip()
    gender = request.GET.get('gender', '').strip()
    exclude_id = request.GET.get('exclude_id', '').strip()

    qs = IndividualDetail.objects.all()

    if gender:
        qs = qs.filter(gender=gender)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)

    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(individual_id__icontains=query)
        )
    else:
        qs = qs.order_by('first_name', 'last_name')

    results = []
    for ind in qs[:30]:
        gender_icon = "♂" if ind.gender == 'M' else ("♀" if ind.gender == 'F' else "?")
        name = " ".join(p for p in [ind.first_name, ind.middle_name, ind.last_name] if p).strip() or "Unnamed"
        results.append({
            'id': ind.individual_id,
            'text': f"{name} ({ind.individual_id}, {gender_icon})"
        })

    return JsonResponse({'results': results})


@login_required
def individual_create_view(request):
    """
    Handles contextual creation of a child linked to a specific parent marriage union.
    Direct/isolated creation is blocked unless creating the initial root ancestor.
    """
    parent_marriage_id = request.POST.get('parent_marriage_id') or request.GET.get('parent_marriage')
    pm_instance = None
    if parent_marriage_id:
        pm_instance = MarriageDetail.objects.filter(pk=parent_marriage_id).first()

    # Integrity Guard: Block unlinked creations if the tree already has members
    total_individuals = IndividualDetail.objects.count()
    if total_individuals > 0 and not pm_instance and request.method == 'GET':
        messages.warning(
            request, 
            "Members cannot be created without a family connection. "
            "Please select a member from the Family Tree to add a child or spouse."
        )
        return redirect('genealogy:my_tree')

    initial_data = {}
    if pm_instance:
        initial_data['parent_marriage'] = pm_instance
        if pm_instance.male_member:
            initial_data['assign_father'] = pm_instance.male_member
        if pm_instance.female_member:
            initial_data['assign_mother'] = pm_instance.female_member

    if request.method == 'POST':
        form = IndividualCompositeForm(request.POST, request.FILES, initial=initial_data)
        if form.is_valid():
            individual = form.save(user_id=str(request.user.pk), locked_parent_marriage=pm_instance)
            messages.success(request, f"Individual {individual.name} ({individual.individual_id}) created successfully.")
            return redirect('genealogy:individual_tree', individual_id=individual.individual_id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = IndividualCompositeForm(initial=initial_data)

    return render(request, 'genealogy/individual_form.html', {
        'form': form,
        'title': 'Add Child to Family Union' if pm_instance else 'Add Initial Family Member',
        'locked_parent_marriage': pm_instance,
        'parent_marriage_id': parent_marriage_id or '',
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    })


@login_required
def individual_edit_view(request, individual_id):
    """
    Handles composite editing of an existing member, providing the complete
    Direct Family Network Dashboard (Parents, all spouses, and children by marriage).
    """
    individual = get_object_or_404(IndividualDetail, pk=individual_id)
    req_user = str(request.user.pk)

    # Permission check: disallow unauthorized editing
    can_view, can_edit = get_user_individual_permissions(req_user, individual_id)
    if not can_edit:
        return HttpResponseForbidden(
            f"Access Denied: You do not possess Edit Rights on member {individual.name} ({individual.individual_id})."
        )

    # 1. Parents serialized as full tree card nodes
    father_card = None
    mother_card = None
    if individual.parent_marriage:
        pm = individual.parent_marriage
        if pm.male_member:
            father_card = GenealogyTreeService._serialize_person(pm.male_member, req_user)
        if pm.female_member:
            mother_card = GenealogyTreeService._serialize_person(pm.female_member, req_user)

    # 2. All Marriages, Spouses, and Children serialized as full tree card nodes
    marriages_data = []
    marriages = MarriageDetail.objects.filter(
        Q(male_member_id=individual_id) | Q(female_member_id=individual_id)
    ).select_related('male_member', 'female_member', 'marriage_date', 'marriage_location')

    for m in marriages:
        spouse = m.female_member if m.male_member_id == individual_id else m.male_member
        spouse_card = GenealogyTreeService._serialize_person(spouse, req_user) if spouse else None

        children_qs = IndividualDetail.objects.filter(
            parent_marriage_id=m.marriage_id
        ).select_related('birth_date', 'birth_location', 'death_date', 'death_location')

        sorted_children = sorted(children_qs, key=lambda ch: GenealogyTreeService._get_date_min_bound(ch.birth_date))
        children_cards = [GenealogyTreeService._serialize_person(child, req_user) for child in sorted_children]

        marriages_data.append({
            'marriage': m,
            'spouse': spouse_card,
            'children': children_cards
        })

    # 3. Active Profile Photo
    current_photo = None
    photo_qs = PhotoDetail.objects.filter(individual=individual)
    if hasattr(PhotoDetail, 'is_profile_photo'):
        current_photo = photo_qs.filter(is_profile_photo=True, active_flag=True).order_by('-created_on').first()
    if not current_photo:
        current_photo = photo_qs.filter(active_flag=True).order_by('-created_on').first()

    if request.method == 'POST':
        form = IndividualCompositeForm(request.POST, request.FILES, instance=individual)
        if form.is_valid():
            form.save(user_id=str(request.user.pk))
            messages.success(request, f"Details for {individual.name} ({individual.individual_id}) successfully updated.")
            return redirect('genealogy:individual_tree', individual_id=individual.individual_id)
    else:
        form = IndividualCompositeForm(instance=individual)

    return render(request, 'genealogy/individual_form.html', {
        'form': form,
        'title': f'Edit Member: {individual.name} ({individual.individual_id})',
        'individual': individual,
        'father': father_card,
        'mother': mother_card,
        'marriages_data': marriages_data,
        'current_photo': current_photo,
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    })