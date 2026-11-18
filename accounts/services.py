# apps/accounts/services.py
from typing import Set, Tuple
from django.db.models import Q
from genealogy.models import IndividualDetail, MarriageDetail
from accounts.models import UserAccess, UserAccessScope


class AuthorizationService:
    @staticmethod
    def get_direct_ancestor_ids(individual_id: str) -> Set[str]:
        """Recursively retrieves all direct ancestor Individual_Ids without generation limit."""
        ancestors = set()
        queue = [individual_id]
        while queue:
            curr_id = queue.pop(0)
            curr = IndividualDetail.objects.filter(pk=curr_id).select_related('parent_marriage').first()
            if curr and curr.parent_marriage:
                pm = curr.parent_marriage
                if pm.male_member_id and pm.male_member_id not in ancestors:
                    ancestors.add(pm.male_member_id)
                    queue.append(pm.male_member_id)
                if pm.female_member_id and pm.female_member_id not in ancestors:
                    ancestors.add(pm.female_member_id)
                    queue.append(pm.female_member_id)
        return ancestors

    @staticmethod
    def get_direct_descendant_ids(individual_id: str) -> Set[str]:
        """Recursively retrieves all direct descendant Individual_Ids without generation limit."""
        descendants = set()
        queue = [individual_id]
        while queue:
            curr_id = queue.pop(0)
            marriage_ids = MarriageDetail.objects.filter(
                Q(male_member_id=curr_id) | Q(female_member_id=curr_id)
            ).values_list('marriage_id', flat=True)
            child_ids = IndividualDetail.objects.filter(
                parent_marriage_id__in=marriage_ids
            ).values_list('individual_id', flat=True)
            for cid in child_ids:
                if cid not in descendants:
                    descendants.add(cid)
                    queue.append(cid)
        return descendants

    @classmethod
    def evaluate_9_degree_lineage(cls, logged_in_user_id: str, target_individual_id: str) -> bool:
        """
        SRS Section 10.1: Automatic read-only visibility for protected dates and contacts.
        """
        # 1. Logged-in user themselves
        if logged_in_user_id == target_individual_id:
            return True

        # 2 & 3: Direct descendants and ancestors of user
        if target_individual_id in cls.get_direct_descendant_ids(logged_in_user_id):
            return True
        if target_individual_id in cls.get_direct_ancestor_ids(logged_in_user_id):
            return True

        # Get all spouses of user
        spouses = MarriageDetail.objects.filter(
            Q(male_member_id=logged_in_user_id) | Q(female_member_id=logged_in_user_id)
        ).values_list('male_member_id', 'female_member_id')
        spouse_ids = {m if m != logged_in_user_id else f for m, f in spouses if (m or f)} - {None, logged_in_user_id}

        # 4 & 5: Direct descendants and ancestors of spouses
        for s_id in spouse_ids:
            if target_individual_id == s_id:
                return True
            if target_individual_id in cls.get_direct_descendant_ids(s_id):
                return True
            if target_individual_id in cls.get_direct_ancestor_ids(s_id):
                return True

        # Parents of logged-in user
        user_node = IndividualDetail.objects.filter(pk=logged_in_user_id).select_related('parent_marriage').first()
        father_id = user_node.parent_marriage.male_member_id if user_node and user_node.parent_marriage else None
        mother_id = user_node.parent_marriage.female_member_id if user_node and user_node.parent_marriage else None

        # 6 & 7: Direct descendants of user's father and mother (siblings, nephews, nieces)
        if father_id and target_individual_id in cls.get_direct_descendant_ids(father_id):
            return True
        if mother_id and target_individual_id in cls.get_direct_descendant_ids(mother_id):
            return True

        # 8 & 9: Direct descendants of spouse's father and mother
        for s_id in spouse_ids:
            s_node = IndividualDetail.objects.filter(pk=s_id).select_related('parent_marriage').first()
            s_father_id = s_node.parent_marriage.male_member_id if s_node and s_node.parent_marriage else None
            s_mother_id = s_node.parent_marriage.female_member_id if s_node and s_node.parent_marriage else None
            if s_father_id and target_individual_id in cls.get_direct_descendant_ids(s_father_id):
                return True
            if s_mother_id and target_individual_id in cls.get_direct_descendant_ids(s_mother_id):
                return True

        return False

    @classmethod
    def get_user_permissions(cls, requesting_user_id: str, target_individual: IndividualDetail) -> Tuple[bool, bool]:
        """
        Calculates (can_view_protected, can_edit) for requesting_user on target_individual.
        Enforces SRS Sections 8, 10, 23, and 25.
        """
        if not requesting_user_id:
            return False, False

        # Superusers have full maintenance access
        from accounts.models import UserDetail
        user_acct = UserDetail.objects.filter(pk=requesting_user_id).first()
        if user_acct and user_acct.is_superuser:
            return True, True

        target_id = target_individual.individual_id

        # Creator check (SRS Section 8.3)
        if target_individual.created_by == requesting_user_id:
            return True, True

        # Check explicit active User_Access grants
        # Excludes REVOKED access immediately (SRS Section 25)
        active_grants = UserAccess.objects.filter(
            granted_to_user_id=requesting_user_id,
            access_status='ACTIVE'
        ).prefetch_related('scopes')

        can_view = False
        can_edit = False

        for grant in active_grants:
            for scope in grant.scopes.all():
                in_scope = False
                if scope.scope_mode == 'INDIVIDUAL_ONLY':
                    in_scope = (scope.scope_individual_id == target_id)
                elif scope.scope_mode == 'INDIVIDUAL_AND_BRANCH':
                    if scope.scope_individual_id == target_id:
                        in_scope = True
                    else:
                        in_scope = (
                            target_id in cls.get_direct_descendant_ids(scope.scope_individual_id) or
                            target_id in cls.get_direct_ancestor_ids(scope.scope_individual_id)
                        )

                if in_scope:
                    can_view = True
                    if grant.access_type == 'EDIT':
                        can_edit = True
                        break
            if can_edit:
                break

        # Check automatic 9-degree lineage for protected read-only data (SRS 10.1)
        if not can_view and cls.evaluate_9_degree_lineage(requesting_user_id, target_id):
            can_view = True

        return can_view, can_edit