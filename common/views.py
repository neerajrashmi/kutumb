from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import LocationDetail
from .services import GoogleGeocodingService


@login_required
def geocode_location_view(request, location_id):
    """
    Triggers geocoding for a location record.
    If ambiguous, renders the candidate selection list.
    """
    location = get_object_or_404(LocationDetail, pk=location_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # User confirmed a specific candidate
        if action == 'confirm_candidate':
            candidate_place_id = request.POST.get('place_id')
            formatted_addr = request.POST.get('formatted_address')
            lat = request.POST.get('lat')
            lng = request.POST.get('lng')
            
            result_payload = {
                'place_id': candidate_place_id,
                'formatted_address': formatted_addr,
                'lat': lat,
                'lng': lng,
            }
            GoogleGeocodingService.apply_result_to_instance(location, result_payload, status='USER_CONFIRMED')
            messages.success(request, f"Location confirmed as: {formatted_addr}")
            
            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
            return redirect(next_url)

    # Trigger resolution
    geocoding_result = GoogleGeocodingService.geocode_location(location)
    
    if geocoding_result['status'] == 'GEOCODED':
        messages.success(request, f"Geocoded successfully: {location.google_formatted_address}")
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    elif geocoding_result['status'] == 'NO_MATCH':
        messages.warning(request, f"No geocoding match found for '{location.original_location}'.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    elif geocoding_result['status'] == 'GEOCODING_ERROR':
        messages.error(request, "Geocoding service unavailable or API key invalid.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # If AMBIGUOUS, display candidates for user selection (SRS Section 11.4)
    return render(request, 'common/location_disambiguation.html', {
        'location': location,
        'candidates': geocoding_result['candidates'],
        'next': request.META.get('HTTP_REFERER', '/')
    })