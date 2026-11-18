import googlemaps
from decimal import Decimal
from django.conf import settings
from .models import LocationDetail


class GoogleGeocodingService:
    """
    Implements SRS Section 11:
    - Resolves raw location strings via Google Geocoding API.
    - Handles single results (GEOCODED), multiple results (AMBIGUOUS), and no match (NO_MATCH).
    - Preserves original entered text without loss.
    """

    @classmethod
    def get_client(cls):
        api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        if not api_key:
            return None
        return googlemaps.Client(key=api_key)

    @classmethod
    def geocode_location(cls, location_instance: LocationDetail) -> dict:
        """
        Geocodes a LocationDetail instance based on original_location.
        Returns a dict containing:
          - 'status': updated LocationDetail status
          - 'candidates': list of formatted candidates (empty if <= 1 or error)
        """
        raw_text = (location_instance.original_location or '').strip()
        if not raw_text:
            location_instance.status = 'NOT_PROVIDED'
            location_instance.save(update_fields=['status', 'modified_by', 'modified_on'])
            return {'status': 'NOT_PROVIDED', 'candidates': []}

        gmaps = cls.get_client()
        if not gmaps:
            location_instance.status = 'GEOCODING_ERROR'
            location_instance.save(update_fields=['status', 'modified_by', 'modified_on'])
            return {'status': 'GEOCODING_ERROR', 'candidates': []}

        try:
            results = gmaps.geocode(raw_text)
        except Exception:
            location_instance.status = 'GEOCODING_ERROR'
            location_instance.save(update_fields=['status', 'modified_by', 'modified_on'])
            return {'status': 'GEOCODING_ERROR', 'candidates': []}

        # Case 1: No match
        if not results:
            location_instance.status = 'NO_MATCH'
            location_instance.save(update_fields=['status', 'modified_by', 'modified_on'])
            return {'status': 'NO_MATCH', 'candidates': []}

        # Case 2: Exactly one deterministic match
        if len(results) == 1:
            cls.apply_result_to_instance(location_instance, results[0], status='GEOCODED')
            return {'status': 'GEOCODED', 'candidates': []}

        # Case 3: Multiple candidates (SRS Section 11.4: AMBIGUOUS, requires explicit selection)
        location_instance.status = 'AMBIGUOUS'
        location_instance.save(update_fields=['status', 'modified_by', 'modified_on'])

        candidates = []
        for item in results:
            loc = item.get('geometry', {}).get('location', {})
            candidates.append({
                'place_id': item.get('place_id'),
                'formatted_address': item.get('formatted_address'),
                'lat': loc.get('lat'),
                'lng': loc.get('lng'),
                'address_components': item.get('address_components'),
                'location_type': item.get('geometry', {}).get('location_type', ''),
            })

        return {'status': 'AMBIGUOUS', 'candidates': candidates}

    @classmethod
    def apply_result_to_instance(cls, location_instance: LocationDetail, result_dict: dict, status: str = 'USER_CONFIRMED'):
        """
        Applies a confirmed or deterministic result to the LocationDetail entity.
        Preserves original_location text intact.
        """
        geometry_loc = result_dict.get('geometry', {}).get('location', {}) if 'geometry' in result_dict else {}
        lat_val = geometry_loc.get('lat') if geometry_loc else result_dict.get('lat')
        lng_val = geometry_loc.get('lng') if geometry_loc else result_dict.get('lng')

        location_instance.google_place_id = result_dict.get('place_id')
        location_instance.google_formatted_address = result_dict.get('formatted_address')
        location_instance.latitude = Decimal(str(lat_val)) if lat_val is not None else None
        location_instance.longitude = Decimal(str(lng_val)) if lng_val is not None else None
        location_instance.status = status
        
        # Save address components JSON if supported on model
        if hasattr(location_instance, 'address_components'):
            location_instance.address_components = result_dict.get('address_components')
        if hasattr(location_instance, 'location_type'):
            location_instance.location_type = result_dict.get('location_type')

        location_instance.save()