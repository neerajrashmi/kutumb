# apps/genealogy/privacy.py
from typing import Optional, Dict, Any
from genealogy.models import IndividualDetail
from accounts.services import AuthorizationService


class MaskedIndividual:
    """
    SRS Section 8.1, 8.2, 10, 23:
    Exposes Name, Photo, and Gender publicly.
    Masks birth/death dates, locations, addresses, phones, and emails
    unless the requesting user has authorized access.
    """
    def __init__(self, individual: IndividualDetail, requesting_user_id: Optional[str]):
        self._raw = individual
        self.individual_id = individual.individual_id
        # Public demographic attributes (SRS 8.1 & 4.4)
        self.first_name = individual.first_name
        self.middle_name = individual.middle_name
        self.last_name = individual.last_name
        self.gender = individual.gender
        self.gender_display = individual.get_gender_display()
        
        # Profile photo association
        primary_photo = individual.photos.filter(active_flag=True).first()
        self.photo_url = primary_photo.image_file.url if primary_photo and primary_photo.image_file else None

        # Resolve authorization capabilities
        self.can_view_protected, self.can_edit = AuthorizationService.get_user_permissions(
            requesting_user_id, individual
        )

        # Protected demographic events (SRS Section 10)
        if self.can_view_protected:
            self.birth_date = individual.birth_date.original_text if individual.birth_date else None
            self.birth_location = individual.birth_location.original_location if individual.birth_location else None
            self.death_date = individual.death_date.original_text if individual.death_date else None
            self.death_location = individual.death_location.original_location if individual.death_location else None
            
            # Protected contact relationships (SRS Sections 12, 13, 14)
            self.addresses = list(individual.addresses.filter(is_active=True).select_related('location'))
            self.phones = list(individual.phones.filter(is_active=True))
            self.emails = list(individual.emails.filter(is_active=True))
        else:
            self.birth_date = None
            self.birth_location = None
            self.death_date = None
            self.death_location = None
            self.addresses = []
            self.phones = []
            self.emails = []

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    def __str__(self):
        return f"{self.full_name} ({self.individual_id})"