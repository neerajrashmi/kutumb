/* apps/contacts/static/contacts/js/address_places.js */

(function () {
    window.initAddressMap = function () {
        const addressInput = document.getElementById('id_address_location');
        if (!addressInput) return;

        if (!window.google || !google.maps || !google.maps.places || !google.maps.places.Autocomplete) {
            console.error("Google Places Autocomplete library is not loaded.");
            return;
        }

        // 1. Create or bind Map container under the address field
        let mapDiv = document.getElementById('frontend_address_map');
        if (!mapDiv) {
            mapDiv = document.createElement('div');
            mapDiv.id = 'frontend_address_map';
            mapDiv.style.width = '100%';
            mapDiv.style.height = '280px';
            mapDiv.style.marginTop = '10px';
            mapDiv.style.marginBottom = '15px';
            mapDiv.style.borderRadius = '6px';
            mapDiv.style.border = '1px solid #ced4da';
            addressInput.parentNode.appendChild(mapDiv);
        }

        // Default viewport
        const defaultLat = 20.0;
        const defaultLng = 0.0;

        const map = new google.maps.Map(mapDiv, {
            center: { lat: defaultLat, lng: defaultLng },
            zoom: 2,
            mapTypeControl: false,
            streetViewControl: false
        });

        const marker = new google.maps.Marker({
            position: { lat: defaultLat, lng: defaultLng },
            map: map,
            draggable: false,
            visible: false
        });

        // 2. Attach Places Autocomplete
        const autocomplete = new google.maps.places.Autocomplete(addressInput, {
            fields: ['place_id', 'formatted_address', 'geometry', 'name']
        });

        // Prevent pressing "Enter" from submitting the form prematurely
        addressInput.addEventListener('keydown', function (e) {
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

            // Fill input with the standardized address or formatted name
            if (place.formatted_address) {
                addressInput.value = place.formatted_address;
            }

            // Adjust map view and drop pin
            map.setCenter(place.geometry.location);
            map.setZoom(15);
            marker.setPosition(place.geometry.location);
            marker.setVisible(true);
        });
    };

    // 4. Asynchronous Google Maps loader
    function loadGoogleMaps() {
        if (window.google && window.google.maps && window.google.maps.places) {
            window.initAddressMap();
            return;
        }

        const apiKeyMeta = document.querySelector('meta[name="google-maps-api-key"]');
        const apiKey = apiKeyMeta ? apiKeyMeta.getAttribute('content') : '';

        if (!apiKey) {
            console.warn("Google Maps API Key not supplied to the page.");
            return;
        }

        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&loading=async&callback=initAddressMap`;
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadGoogleMaps);
    } else {
        loadGoogleMaps();
    }
})();