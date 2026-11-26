"""
apps/genealogy/services.py
Comprehensive Genealogy Tree Service for ancestry traversal, multi-spouse serialization,
collateral paternal/maternal uncle & aunt branches, and privacy-aware graph generation.
"""
from datetime import date
import re
from typing import List, Optional
import urllib.parse
import urllib.request
import json

from django.conf import settings
from django.db.models import Q

from genealogy.models import IndividualDetail, MarriageDetail
from accounts.permissions import has_protected_read_access
from media_mgmt.models import PhotoDetail


class GenealogyTreeService:
    """
    Core graph traversal engine for ancestry, descendants, and tree rendering.
    Enforces SRS Section 5 (unbounded recursion), Section 10.1 (lineage privacy),
    and Section 10.2 (relative age ordering).
    """

    @staticmethod
    def _extract_city_state_country(formatted_addr: Optional[str]) -> Optional[str]:
        """
        Extracts strictly 'City, State, Country' from a Google formatted address string,
        stripping street lines and postal/ZIP codes.
        """
        if not formatted_addr:
            return None

        parts = [p.strip() for p in formatted_addr.split(',') if p.strip()]
        if not parts:
            return None

        cleaned_parts = []
        for part in parts:
            # Strip numeric postal/ZIP codes (e.g., 'NE 68102' -> 'NE', '110001' -> '')
            token = re.sub(r'\b\d{4,6}(?:-\d{4})?\b', '', part).strip()
            # Strip UK/Canadian alphanumeric postal codes if present
            token = re.sub(r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', '', token, flags=re.IGNORECASE).strip()
            token = re.sub(r'\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b', '', token, flags=re.IGNORECASE).strip()
            if token and not token.isdigit():
                cleaned_parts.append(token)

        if len(cleaned_parts) >= 3:
            return ", ".join(cleaned_parts[-3:])
        return ", ".join(cleaned_parts) if cleaned_parts else None

    @classmethod
    def _get_card_place_display(cls, location_obj, can_view: bool) -> Optional[str]:
        """
        Bug 3 Fix: Returns 'City, State, Country' extracted from google_formatted_address,
        or reverse-geocoded from latitude/longitude if google_formatted_address is null.
        """
        if not location_obj or not can_view:
            return None

        # 1. Extract from Google Formatted Address if available
        if location_obj.google_formatted_address:
            return cls._extract_city_state_country(location_obj.google_formatted_address)

        # 2. Reverse-geocode from Latitude / Longitude if formatted address is missing
        if location_obj.latitude is not None and location_obj.longitude is not None:
            api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
            if api_key:
                try:
                    params = urllib.parse.urlencode({
                        'latlng': f"{location_obj.latitude},{location_obj.longitude}",
                        'result_type': 'locality|administrative_area_level_1|country',
                        'key': api_key,
                    })
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
                    with urllib.request.urlopen(url, timeout=3) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data.get('status') == 'OK' and data.get('results'):
                            fmt = data['results'][0].get('formatted_address')
                            if fmt:
                                location_obj.google_formatted_address = fmt
                                location_obj.save(update_fields=['google_formatted_address'])
                                return cls._extract_city_state_country(fmt)
                except Exception:
                    pass

        # 3. Fallback if neither Google formatted address nor coordinates are available
        return cls._extract_city_state_country(location_obj.original_location)

    @staticmethod
    def _get_photo_url(individual_id: str) -> Optional[str]:
        """Retrieves active profile photo URL for an individual."""
        try:
            qs = PhotoDetail.objects.filter(individual_id=individual_id)
            if hasattr(PhotoDetail, 'active_flag'):
                qs = qs.filter(active_flag=True)
            elif hasattr(PhotoDetail, 'is_active'):
                qs = qs.filter(is_active=True)
            photo = qs.order_by('-created_on').first()
            if photo and photo.image_file:
                return photo.image_file.url
        except Exception:
            return None
        return None

    @staticmethod
    def _get_safe_date_display(date_obj, can_view: bool) -> Optional[str]:
        if date_obj and can_view:
            return getattr(date_obj, 'original_text', str(date_obj))
        return None

    @staticmethod
    def _get_date_min_bound(date_obj) -> date:
        if not date_obj:
            return date.max
        if hasattr(date_obj, 'get_bounds'):
            bounds = date_obj.get_bounds()
            return bounds[0] if bounds and bounds[0] else date.max
        if hasattr(date_obj, 'get_comparison_bounds'):
            bounds = date_obj.get_comparison_bounds()
            return bounds[0] if bounds and bounds[0] else date.max
        if hasattr(date_obj, 'start_date') and date_obj.start_date:
            return date_obj.start_date
        return date.max

    @classmethod
    def _serialize_person(cls, person, requesting_user_id: Optional[str] = None) -> Optional[dict]:
        """Converts an IndividualDetail model instance into a standard JSON card payload."""
        if not person:
            return None
        can_view = has_protected_read_access(requesting_user_id, person.individual_id) if requesting_user_id else False
        full_name = " ".join(p for p in [person.first_name, person.middle_name, person.last_name] if p).strip() or person.individual_id
        is_dec = bool(person.death_date_id or person.death_location_id)

        return {
            'individual_id': person.individual_id,
            'first_name': person.first_name,
            'middle_name': person.middle_name,
            'last_name': person.last_name,
            'name': full_name,
            'gender': person.gender,
            'photo_url': cls._get_photo_url(person.individual_id),
            'is_deceased': is_dec,
            'can_edit': can_view,
            'birth_date_display': cls._get_safe_date_display(person.birth_date, can_view),
            'birth_place_display': cls._get_card_place_display(person.birth_location, can_view),
            'death_date_display': cls._get_safe_date_display(person.death_date, can_view),
            'death_place_display': cls._get_card_place_display(person.death_location, can_view),
        }

    @classmethod
    def _get_spouses_for_person(cls, individual_id: str, requesting_user_id: Optional[str] = None) -> List[dict]:
        """Fetches all spouses serialized for an individual."""
        marriages = MarriageDetail.objects.filter(
            Q(male_member_id=individual_id) | Q(female_member_id=individual_id)
        ).select_related('male_member', 'female_member', 'marriage_date')

        spouses = []
        for m in marriages:
            spouse_obj = m.female_member if m.male_member_id == individual_id else m.male_member
            if spouse_obj:
                card = cls._serialize_person(spouse_obj, requesting_user_id)
                card['marriage_id'] = m.marriage_id
                spouses.append(card)
        return spouses

    @classmethod
    def get_ancestor_tree(cls, individual_id: str, max_generations: Optional[int] = None, requesting_user_id: Optional[str] = None) -> Optional[dict]:
        """Recursively builds the ancestral tree (parents, grandparents) moving upward."""
        person = IndividualDetail.objects.filter(pk=individual_id).select_related('birth_date', 'birth_location', 'death_date', 'death_location').first()
        if not person:
            return None

        node = cls._serialize_person(person, requesting_user_id)
        node['father'] = None
        node['mother'] = None
        node['spouses'] = cls._get_spouses_for_person(person.individual_id, requesting_user_id)

        if person.parent_marriage_id:
            pm = MarriageDetail.objects.filter(pk=person.parent_marriage_id).first()
            if pm:
                next_gen = max_generations - 1 if max_generations is not None else None
                if pm.male_member_id and (max_generations is None or max_generations > 1):
                    node['father'] = cls.get_ancestor_tree(pm.male_member_id, next_gen, requesting_user_id)
                if pm.female_member_id and (max_generations is None or max_generations > 1):
                    node['mother'] = cls.get_ancestor_tree(pm.female_member_id, next_gen, requesting_user_id)

        return node

    @classmethod
    def get_descendant_tree(cls, individual_id: str, requesting_user_id: Optional[str] = None) -> Optional[dict]:
        """Recursively builds downward descendant branches with chronological sibling sorting."""
        person = IndividualDetail.objects.filter(pk=individual_id).select_related('birth_date', 'birth_location', 'death_date', 'death_location').first()
        if not person:
            return None

        node = cls._serialize_person(person, requesting_user_id)
        node['marriages'] = []
        node['children'] = []
        node['spouses'] = []

        marriages = MarriageDetail.objects.filter(
            Q(male_member_id=individual_id) | Q(female_member_id=individual_id)
        ).select_related('male_member', 'female_member', 'marriage_date')

        for m in marriages:
            spouse_obj = m.female_member if m.male_member_id == individual_id else m.male_member
            spouse_card = cls._serialize_person(spouse_obj, requesting_user_id) if spouse_obj else None
            if spouse_card:
                spouse_card['marriage_id'] = m.marriage_id
                node['spouses'].append(spouse_card)

            children_qs = IndividualDetail.objects.filter(parent_marriage_id=m.marriage_id).select_related('birth_date', 'birth_location', 'death_date', 'death_location')
            sorted_children = sorted(children_qs, key=lambda ch: cls._get_date_min_bound(ch.birth_date))

            children_nodes = [cls.get_descendant_tree(ch.individual_id, requesting_user_id) for ch in sorted_children]

            for ch_node in children_nodes:
                if ch_node and ch_node not in node['children']:
                    node['children'].append(ch_node)

            node['marriages'].append({
                'marriage_id': m.marriage_id,
                'spouse_id': spouse_obj.individual_id if spouse_obj else None,
                'spouse_name': spouse_card['name'] if spouse_card else 'Unknown',
                'spouse': spouse_card,
                'children': children_nodes
            })

        return node

    @classmethod
    def get_collateral_uncles_aunts(cls, parent_id: Optional[str], requesting_user_id: Optional[str] = None) -> List[dict]:
        """Retrieves brothers and sisters of a parent (Uncles & Aunts) with their spouses and descendants."""
        if not parent_id:
            return []

        parent = IndividualDetail.objects.filter(pk=parent_id).first()
        if not parent or not parent.parent_marriage_id:
            return []

        uncles_qs = IndividualDetail.objects.filter(
            parent_marriage_id=parent.parent_marriage_id
        ).exclude(pk=parent.pk).select_related('birth_date', 'birth_location', 'death_date', 'death_location')

        sorted_uncles = sorted(uncles_qs, key=lambda u: cls._get_date_min_bound(u.birth_date))

        results = []
        for u in sorted_uncles:
            u_node = cls.get_descendant_tree(u.individual_id, requesting_user_id)
            if u_node:
                results.append(u_node)

        return results

    @classmethod
    def get_unified_tree(cls, individual_id: str, requesting_user_id: Optional[str] = None) -> Optional[dict]:
        """Packages the complete multi-generational family tree graph safely."""
        person = IndividualDetail.objects.filter(pk=individual_id).first()
        if not person:
            return None

        node = cls.get_descendant_tree(individual_id, requesting_user_id)
        node['is_focus'] = True
        node['parents'] = []
        node['ancestors'] = None
        node['ancestor_tree'] = None
        node['siblings'] = []
        node['paternal_uncles_aunts'] = []
        node['maternal_uncles_aunts'] = []

        # Attach Recursive Ancestors to Each Spouse
        for sp in node.get('spouses', []):
            sp['ancestor_tree'] = cls.get_ancestor_tree(sp['individual_id'], max_generations=4, requesting_user_id=requesting_user_id)

        # Parents, Ancestors, Uncles & Aunts (Safely queried via PK lookup)
        if person.parent_marriage_id:
            pm = MarriageDetail.objects.filter(pk=person.parent_marriage_id).first()
            if pm:
                anc = {'father': None, 'mother': None}

                # Father Branch
                if pm.male_member_id:
                    father_obj = IndividualDetail.objects.filter(pk=pm.male_member_id).first()
                    if father_obj:
                        anc['father'] = cls.get_ancestor_tree(father_obj.individual_id, max_generations=4, requesting_user_id=requesting_user_id)
                        if anc['father']:
                            anc['father']['role'] = 'Father'
                            node['parents'].append(anc['father'])
                        node['paternal_uncles_aunts'] = cls.get_collateral_uncles_aunts(father_obj.individual_id, requesting_user_id)

                # Mother Branch
                if pm.female_member_id:
                    mother_obj = IndividualDetail.objects.filter(pk=pm.female_member_id).first()
                    if mother_obj:
                        anc['mother'] = cls.get_ancestor_tree(mother_obj.individual_id, max_generations=4, requesting_user_id=requesting_user_id)
                        if anc['mother']:
                            anc['mother']['role'] = 'Mother'
                            node['parents'].append(anc['mother'])
                        node['maternal_uncles_aunts'] = cls.get_collateral_uncles_aunts(mother_obj.individual_id, requesting_user_id)

                node['ancestor_tree'] = anc
                node['ancestors'] = anc

                # Focus Person's Siblings
                sib_qs = IndividualDetail.objects.filter(
                    parent_marriage_id=person.parent_marriage_id
                ).exclude(pk=person.pk).select_related('birth_date', 'birth_location', 'death_date', 'death_location')

                sorted_sibs = sorted(sib_qs, key=lambda s: cls._get_date_min_bound(s.birth_date))
                for s in sorted_sibs:
                    sib_tree = cls.get_descendant_tree(s.individual_id, requesting_user_id)
                    if sib_tree:
                        node['siblings'].append(sib_tree)

        return node

    @classmethod
    def get_chronologically_ordered_siblings(cls, individual_id: str) -> List[dict]:
        """Returns ordered sibling cards without date disclosure."""
        person = IndividualDetail.objects.filter(pk=individual_id).first()
        if not person or not person.parent_marriage_id:
            return []

        siblings = IndividualDetail.objects.filter(
            parent_marriage_id=person.parent_marriage_id
        ).select_related('birth_date', 'birth_location')

        sorted_sibs = sorted(siblings, key=lambda s: cls._get_date_min_bound(s.birth_date))
        return [cls._serialize_person(s) for s in sorted_sibs]