/* apps/common/static/common/js/google_places_admin.js */

(function () {
    window.initGoogleAdminMap = function () {
        const origInput = document.getElementById('id_original_location');
        const placeIdInput = document.getElementById('id_google_place_id');
        const formattedAddrInput = document.getElementById('id_google_formatted_address');
        const latInput = document.getElementById('id_latitude');
        const lngInput = document.getElementById('id_longitude');
        const statusSelect = document.getElementById('id_status');

        if (!origInput) return;

        if (!window.google || !google.maps || !google.maps.places || !google.maps.places.Autocomplete) {
            console.error("Google Places Autocomplete is not available.");
            return;
        }

        // 1. Create or retrieve Map container
        let mapDiv = document.getElementById('admin_location_map');
        if (!mapDiv) {
            mapDiv = document.createElement('div');
            mapDiv.id = 'admin_location_map';
            mapDiv.style.width = '100%';
            mapDiv.style.height = '340px';
            mapDiv.style.marginTop = '12px';
            mapDiv.style.marginBottom = '16px';
            mapDiv.style.borderRadius = '6px';
            mapDiv.style.border = '1px solid #ccc';
            origInput.parentNode.appendChild(mapDiv);
        }

        const curLat = latInput && latInput.value ? parseFloat(latInput.value) : 20.0;
        const curLng = lngInput && lngInput.value ? parseFloat(lngInput.value) : 0.0;
        const hasCoords = Boolean(latInput && latInput.value && lngInput && lngInput.value);

        const map = new google.maps.Map(mapDiv, {
            center: { lat: curLat, lng: curLng },
            zoom: hasCoords ? 14 : 2,
            mapTypeControl: false,
            streetViewControl: false
        });

        const marker = new google.maps.Marker({
            position: { lat: curLat, lng: curLng },
            map: map,
            draggable: true,
            visible: hasCoords
        });

        // 2. Attach Places Autocomplete
        const autocomplete = new google.maps.places.Autocomplete(origInput, {
            fields: ['place_id', 'formatted_address', 'geometry', 'name']
        });

        origInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
            }
        });

        // 3. Selection handler
        autocomplete.addListener('place_changed', function () {
            const place = autocomplete.getPlace();
            if (!place || !place.geometry || !place.geometry.location) {
                return;
            }

            const latVal = place.geometry.location.lat().toFixed(7);
            const lngVal = place.geometry.location.lng().toFixed(7);

            if (placeIdInput) placeIdInput.value = place.place_id || '';
            if (formattedAddrInput) formattedAddrInput.value = place.formatted_address || '';
            if (latInput) latInput.value = latVal;
            if (lngInput) lngInput.value = lngVal;
            if (statusSelect) statusSelect.value = 'USER_CONFIRMED';

            map.setCenter(place.geometry.location);
            map.setZoom(15);
            marker.setPosition(place.geometry.location);
            marker.setVisible(true);
        });

        // 4. Pin drag handler
        marker.addListener('dragend', function () {
            const pos = marker.getPosition();
            const latVal = pos.lat().toFixed(7);
            const lngVal = pos.lng().toFixed(7);

            if (latInput) latInput.value = latVal;
            if (lngInput) lngInput.value = lngVal;
            if (statusSelect) statusSelect.value = 'USER_CONFIRMED';
        });

        // 5. Ensure disabled fields are enabled right at form submission so values submit
        const formElement = origInput.closest('form');
        if (formElement) {
            formElement.addEventListener('submit', function () {
                if (placeIdInput) placeIdInput.disabled = false;
                if (formattedAddrInput) formattedAddrInput.disabled = false;
                if (latInput) latInput.disabled = false;
                if (lngInput) lngInput.disabled = false;
            });
        }
    };

    function loadGoogleMapsAsync() {
        if (window.google && window.google.maps && window.google.maps.places) {
            window.initGoogleAdminMap();
            return;
        }

        const apiKeyMeta = document.querySelector('meta[name="google-maps-api-key"]');
        const apiKey = (apiKeyMeta ? apiKeyMeta.getAttribute('content') : '') || window.GOOGLE_MAPS_API_KEY;

        if (!apiKey) {
            console.error("GOOGLE_MAPS_API_KEY is missing.");
            return;
        }

        const script = document.createElement('script');
        //script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places,marker&callback=initAddressMap`;
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&loading=async&callback=initAddressMap`;
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadGoogleMapsAsync);
    } else {
        loadGoogleMapsAsync();
    }
})();