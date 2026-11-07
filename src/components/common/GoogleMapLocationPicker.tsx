/**
 * GoogleMapLocationPicker Component
 * Production-ready Google Maps Platform integration for CloudKitchen.
 * Utilizes @googlemaps/js-api-loader with Maps JavaScript API + Places API (New).
 * Features:
 *  - Google Places Autocomplete (Search places, addresses, areas like "Kondapur", "Jubilee Hills")
 *  - Interactive map with AdvancedMarkerElement
 *  - Drag/click to pinpoint coordinates
 *  - "Use current location" with browser Geolocation API
 *  - Graceful fallback when VITE_GOOGLE_MAPS_API_KEY is not configured
 */

import React, { useEffect, useRef, useState } from 'react';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import { MapPin, Navigation, Search, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import KitchenMap from './KitchenMap';

export interface LocationSelected {
  address: string;
  latitude: number;
  longitude: number;
  placeId?: string;
}

interface GoogleMapLocationPickerProps {
  label?: string;
  initialAddress?: string;
  initialLatitude?: number | null;
  initialLongitude?: number | null;
  onLocationSelect: (location: LocationSelected) => void;
  height?: string;
  className?: string;
}

export default function GoogleMapLocationPicker({
  label = 'Kitchen Location',
  initialAddress = '',
  initialLatitude = null,
  initialLongitude = null,
  onLocationSelect,
  height = '340px',
  className = '',
}: GoogleMapLocationPickerProps) {
  const apiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim();
  const [address, setAddress] = useState(initialAddress);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(
    initialLatitude && initialLongitude
      ? { lat: initialLatitude, lng: initialLongitude }
      : null
  );
  const [geoLoading, setGeoLoading] = useState(false);
  const [mapsLoaded, setMapsLoaded] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const autocompleteInputRef = useRef<HTMLInputElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<any>(null);

  // Sync coords from parent if changed externally
  useEffect(() => {
    if (initialLatitude && initialLongitude) {
      setCoords({ lat: initialLatitude, lng: initialLongitude });
    }
    if (initialAddress) {
      setAddress(initialAddress);
    }
  }, [initialLatitude, initialLongitude, initialAddress]);

  // Load Google Maps JavaScript API
  useEffect(() => {
    if (!apiKey) {
      return;
    }

    let isMounted = true;
    try {
      setOptions({
        key: apiKey,
        v: 'weekly',
      });
    } catch {
      // Options may already be set
    }

    Promise.all([
      importLibrary('maps'),
      importLibrary('marker'),
      importLibrary('places'),
    ])
      .then(async () => {
        if (!isMounted) return;
        const { Map } = (await google.maps.importLibrary('maps')) as google.maps.MapsLibrary;
        const { AdvancedMarkerElement } = (await google.maps.importLibrary('marker')) as google.maps.MarkerLibrary;
        const { Autocomplete } = (await google.maps.importLibrary('places')) as google.maps.PlacesLibrary;

        if (!mapContainerRef.current) return;

        const defaultCenter = coords || { lat: 17.448293, lng: 78.374187 }; // Default Hyderabad center

        const map = new Map(mapContainerRef.current, {
          center: defaultCenter,
          zoom: coords ? 15 : 12,
          mapId: 'DEMO_MAP_ID',
          fullscreenControl: false,
          streetViewControl: false,
          mapTypeControl: false,
        });
        mapInstanceRef.current = map;

        // Create marker
        const marker = new AdvancedMarkerElement({
          map,
          position: coords || defaultCenter,
          gmpDraggable: true,
          title: 'Selected Kitchen Location',
        });
        markerRef.current = marker;

        // Handle marker drag end
        marker.addListener('dragend', () => {
          const pos = marker.position;
          if (pos) {
            const lat = typeof pos.lat === 'function' ? (pos.lat as any)() : (pos as any).lat;
            const lng = typeof pos.lng === 'function' ? (pos.lng as any)() : (pos as any).lng;
            updateLocation(lat, lng, address);
          }
        });

        // Click on map to move marker
        map.addListener('click', (e: google.maps.MapMouseEvent) => {
          if (e.latLng) {
            const lat = e.latLng.lat();
            const lng = e.latLng.lng();
            marker.position = { lat, lng };
            updateLocation(lat, lng, address);
          }
        });

        // Setup Autocomplete
        if (autocompleteInputRef.current) {
          const autocomplete = new Autocomplete(autocompleteInputRef.current, {
            fields: ['formatted_address', 'geometry', 'name', 'place_id'],
          });
          autocomplete.bindTo('bounds', map);

          autocomplete.addListener('place_changed', () => {
            const place = autocomplete.getPlace();
            if (!place.geometry || !place.geometry.location) {
              return;
            }

            const lat = place.geometry.location.lat();
            const lng = place.geometry.location.lng();
            const formatted = place.formatted_address || place.name || '';

            map.setCenter({ lat, lng });
            map.setZoom(16);
            marker.position = { lat, lng };

            setAddress(formatted);
            setCoords({ lat, lng });
            onLocationSelect({
              address: formatted,
              latitude: lat,
              longitude: lng,
              placeId: place.place_id,
            });
          });
        }

        setMapsLoaded(true);
      })
      .catch((err: any) => {
        console.error('Google Maps Loader error:', err);
        if (isMounted) {
          setMapError('Failed to load Google Maps JavaScript API. Falling back to coordinate picker.');
        }
      });

    return () => {
      isMounted = false;
    };
  }, [apiKey]);

  const updateLocation = (lat: number, lng: number, addr: string) => {
    setCoords({ lat, lng });
    onLocationSelect({
      address: addr,
      latitude: lat,
      longitude: lng,
    });
  };

  // Browser Geolocation: "Use current location"
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        setCoords({ lat, lng });

        if (mapInstanceRef.current && markerRef.current) {
          mapInstanceRef.current.setCenter({ lat, lng });
          mapInstanceRef.current.setZoom(16);
          markerRef.current.position = { lat, lng };
        }

        // Reverse geocode if Maps API is loaded
        if (window.google && window.google.maps) {
          const geocoder = new google.maps.Geocoder();
          geocoder.geocode({ location: { lat, lng } }, (results, status) => {
            let detectedAddress = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
            let placeId: string | undefined;
            if (status === 'OK' && results && results[0]) {
              detectedAddress = results[0].formatted_address;
              placeId = results[0].place_id;
              setAddress(detectedAddress);
            }
            onLocationSelect({
              address: detectedAddress,
              latitude: lat,
              longitude: lng,
              placeId,
            });
            setGeoLoading(false);
          });
        } else {
          const fallbackAddr = address || `Location (${lat.toFixed(5)}, ${lng.toFixed(5)})`;
          onLocationSelect({
            address: fallbackAddr,
            latitude: lat,
            longitude: lng,
          });
          setGeoLoading(false);
        }
      },
      (error) => {
        setGeoLoading(false);
        alert(`Unable to retrieve your location: ${error.message}`);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Search / Autocomplete Bar */}
      <div>
        <label className="block text-xs font-bold uppercase text-gray-500 mb-1">
          {label} (Google Places Autocomplete)
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              ref={autocompleteInputRef}
              type="text"
              value={address}
              onChange={(e) => {
                setAddress(e.target.value);
                if (coords) {
                  onLocationSelect({
                    address: e.target.value,
                    latitude: coords.lat,
                    longitude: coords.lng,
                  });
                }
              }}
              placeholder={
                apiKey
                  ? 'Search location (e.g. Kondapur, Jubilee Hills, Hyderabad)...'
                  : 'Enter delivery or kitchen address...'
              }
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-[#166534]"
            />
          </div>

          <button
            type="button"
            onClick={handleUseCurrentLocation}
            disabled={geoLoading}
            className="flex items-center space-x-1.5 px-4 py-2.5 bg-emerald-50 hover:bg-emerald-100 text-[#166534] border border-emerald-200 rounded-xl text-xs font-bold transition-colors whitespace-nowrap"
            title="Locate via device GPS"
          >
            {geoLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Navigation className="w-3.5 h-3.5" />
            )}
            <span>{geoLoading ? 'Locating...' : 'Use Current Location'}</span>
          </button>
        </div>
      </div>

      {/* API Key Missing Notice */}
      {!apiKey && (
        <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl text-xs flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-bold">Google Maps is not configured</p>
            <p className="text-[11px] text-amber-700 mt-0.5">
              Add <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[10px]">VITE_GOOGLE_MAPS_API_KEY</code> to your <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[10px]">.env</code> to enable live Google Places search and map display. You can still set real coordinates below.
            </p>
          </div>
        </div>
      )}

      {/* Lat/Lng Coordinates Readout */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="font-bold text-[10px] uppercase text-gray-400">Latitude</span>
          <input
            type="number"
            step="0.000001"
            value={coords?.lat !== undefined ? coords.lat : ''}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val)) {
                const newLng = coords?.lng ?? 78.374187;
                setCoords({ lat: val, lng: newLng });
                onLocationSelect({ address, latitude: val, longitude: newLng });
              }
            }}
            placeholder="e.g. 17.448293"
            className="w-full mt-0.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs"
          />
        </div>
        <div>
          <span className="font-bold text-[10px] uppercase text-gray-400">Longitude</span>
          <input
            type="number"
            step="0.000001"
            value={coords?.lng !== undefined ? coords.lng : ''}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val)) {
                const newLat = coords?.lat ?? 17.448293;
                setCoords({ lat: newLat, lng: val });
                onLocationSelect({ address, latitude: newLat, longitude: val });
              }
            }}
            placeholder="e.g. 78.374187"
            className="w-full mt-0.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs"
          />
        </div>
      </div>

      {/* Map Rendering Container */}
      {apiKey && !mapError ? (
        <div
          ref={mapContainerRef}
          style={{ height }}
          className="w-full rounded-2xl overflow-hidden border border-gray-200 shadow-inner bg-gray-100"
        />
      ) : (
        <KitchenMap
          mode="picker"
          latitude={coords?.lat || 17.448293}
          longitude={coords?.lng || 78.374187}
          address={address}
          height={height}
          onLocationSelect={(lat, lng) => updateLocation(lat, lng, address)}
        />
      )}

      {coords && (
        <p className="text-[11px] text-gray-500 flex items-center gap-1">
          <CheckCircle className="w-3 h-3 text-[#166534]" />
          <span>Coordinates registered: {coords.lat.toFixed(6)}, {coords.lng.toFixed(6)}</span>
        </p>
      )}
    </div>
  );
}
