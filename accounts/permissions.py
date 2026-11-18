# apps/accounts/permissions.py
from typing import Tuple, Set
from django.db.models import Q
from accounts.models import UserAccess, UserAccessScope
from genealogy.models import IndividualDetail, MarriageDetail


def get_direct_ancestor_ids(individual_id: str) -> Set[str]:
    """Recursively retrieves all ancestor individual IDs across unlimited generations."""
    ancestors = set()
    to_visit = [individual_id]
    while to_visit:
        curr_id = to_visit.pop(0)
        curr = IndividualDetail.objects.filter(pk=curr_id).select_related('parent_marriage').first()
        if curr and curr.parent_marriage:
            pm = curr.parent_marriage
            if pm.male_member_id and pm.male_member_id not in ancestors:
                ancestors.add(pm.male_member_id)
                to_visit.append(pm.male_member_id)
            if pm.female_member_id and pm.female_member_id not in ancestors:
                ancestors.add(pm.female_member_id)
                to_visit.append(pm.female_member_id)
    return ancestors


def get_direct_descendant_ids(individual_id: str) -> Set[str]:
    """Recursively retrieves all descendant individual IDs across unlimited generations."""
    descendants = set()
    to_visit = [individual_id]
    while to_visit:
        curr_id = to_visit.pop(0)
        marriages = MarriageDetail.objects.filter(
            Q(male_member_id=curr_id) | Q(female_member_id=curr_id)
        ).values_list('marriage_id', flat=True)
        children = IndividualDetail.objects.filter(parent_marriage_id__in=marriages).values_list('individual_id', flat=True)
        for child_id in children:
            if child_id not in descendants:
                descendants.add(child_id)
                to_visit.append(child_id)
    return descendants


def evaluate_9_degree_lineage(logged_in_user_id: str, target_individual_id: str) -> bool:
    """Evaluates automatic 9-degree direct lineage rule (SRS 10.1)."""
    if not logged_in_user_id or not target_individual_id:
        return False
    if logged_in_user_id == target_individual_id:
        return True

    # 2 & 3: Direct descendants & ancestors of logged-in user
    if target_individual_id in get_direct_descendant_ids(logged_in_user_id):
        return True
    if target_individual_id in get_direct_ancestor_ids(logged_in_user_id):
        return True

    # Spouses
    spouses = MarriageDetail.objects.filter(
        Q(male_member_id=logged_in_user_id) | Q(female_member_id=logged_in_user_id)
    ).values_list('male_member_id', 'female_member_id')
    spouse_ids = {m if m != logged_in_user_id else f for m, f in spouses if (m or f)} - {None, logged_in_user_id}

    # 4 & 5: Direct descendants & ancestors of spouse
    for s_id in spouse_ids:
        if target_individual_id == s_id:
            return True
        if target_individual_id in get_direct_descendant_ids(s_id):
            return True
        if target_individual_id in get_direct_ancestor_ids(s_id):
            return True

    # Parents of logged-in user
    user_ind = IndividualDetail.objects.filter(pk=logged_in_user_id).select_related('parent_marriage').first()
    father_id = user_ind.parent_marriage.male_member_id if user_ind and user_ind.parent_marriage else None
    mother_id = user_ind.parent_marriage.female_member_id if user_ind and user_ind.parent_marriage else None

    # 6 & 7: Direct descendants of father and mother (siblings, nephews, nieces)
    if father_id and target_individual_id in get_direct_descendant_ids(father_id):
        return True
    if mother_id and target_individual_id in get_direct_descendant_ids(mother_id):
        return True

    # 8 & 9: Direct descendants of spouse's father and mother
    for s_id in spouse_ids:
        s_ind = IndividualDetail.objects.filter(pk=s_id).select_related('parent_marriage').first()
        s_father_id = s_ind.parent_marriage.male_member_id if s_ind and s_ind.parent_marriage else None
        s_mother_id = s_ind.parent_marriage.female_member_id if s_ind and s_ind.parent_marriage else None
        if s_father_id and target_individual_id in get_direct_descendant_ids(s_father_id):
            return True
        if s_mother_id and target_individual_id in get_direct_descendant_ids(s_mother_id):
            return True

    return False


def get_user_individual_permissions(requesting_user_id: str, target_individual_id: str) -> Tuple[bool, bool]:
    """
    Returns (can_view, can_edit) for requesting_user on target_individual.
    Enforces:
      1. Anchored self-editing.
      2. Creator view & edit rights.
      3. Active UserAccess EDIT & VIEW grants (non-cascading).
      4. Automatic 9-degree read-only lineage.
    """
    if not requesting_user_id:
        return False, False

    # 1. Anchored self: A user always has full view and edit on their own record
    if requesting_user_id == target_individual_id:
        return True, True

    # 2. Record Creator: SRS 8.3 grants view & edit to the creator
    target = IndividualDetail.objects.filter(pk=target_individual_id).first()
    if target and target.created_by == requesting_user_id:
        return True, True

    can_view = False
    can_edit = False

    # 3. Check Explicit Active UserAccess Grants (SRS 8.4, 8.5, 8.8)
    active_grants = UserAccess.objects.filter(
        granted_to_user_id=requesting_user_id,
        access_status='ACTIVE'
    )

    for grant in active_grants:
        scopes = UserAccessScope.objects.filter(access=grant)
        in_scope = False
        for sc in scopes:
            if sc.scope_mode == 'INDIVIDUAL_ONLY' and sc.scope_individual_id == target_individual_id:
                in_scope = True
                break
            elif sc.scope_mode == 'INDIVIDUAL_AND_BRANCH':
                if sc.scope_individual_id == target_individual_id:
                    in_scope = True
                    break
                branch_desc = get_direct_descendant_ids(sc.scope_individual_id)
                branch_anc = get_direct_ancestor_ids(sc.scope_individual_id)
                if target_individual_id in branch_desc or target_individual_id in branch_anc:
                    in_scope = True
                    break

        if in_scope:
            can_view = True
            if grant.access_type == 'EDIT':
                can_edit = True
                break  # Maximum permission attained

    # 4. Check Automatic 9-Degree Lineage (Read-Only)
    if not can_view and evaluate_9_degree_lineage(requesting_user_id, target_individual_id):
        can_view = True

    return can_view, can_edit


def has_protected_read_access(requesting_user_id: str, target_individual_id: str) -> bool:
    """Helper returning whether requesting_user has read access to protected dates/locations."""
    can_view, _ = get_user_individual_permissions(requesting_user_id, target_individual_id)
    return can_view