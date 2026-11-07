/**
 * Real Interactive Map Component for Cloud Kitchens
 * Built with Leaflet & OpenStreetMap (No external API keys required, production-ready).
 * Supports:
 *  1. Single Kitchen View (Customer KitchenDetail): Marker with popup & directions link
 *  2. Coordinate Picker (Kitchen Owner Settings): Click or drag marker to set exact lat/lng
 *  3. Multi-Kitchen Overview (Admin / Customer Directory): Markers for all kitchens with auto-fit bounds
 */

import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, Navigation, Compass, Check, AlertCircle } from 'lucide-react';

export interface MapKitchen {
  id: string;
  kitchen_name: string;
  address?: string;
  city?: string;
  latitude?: number | null;
  longitude?: number | null;
  is_open?: boolean;
  approval_status?: string;
  rating?: number | null;
}

interface KitchenMapProps {
  // Mode: 'view' for static/browsing display, 'picker' for setting coordinates
  mode?: 'view' | 'picker';
  
  // Single location
  latitude?: number | null;
  longitude?: number | null;
  kitchenName?: string;
  address?: string;

  // Multiple kitchens (for directory/admin overview)
  kitchens?: MapKitchen[];

  // Callback when coordinates are updated in picker mode
  onLocationChange?: (lat: number, lng: number) => void;
  onLocationSelect?: (lat: number, lng: number) => void;

  height?: string;
  zoom?: number;
  className?: string;
}

// Custom modern SVG marker pin icon
const createCustomPinIcon = (color: string = '#166534') => {
  return L.divIcon({
    className: 'custom-map-pin',
    html: `
      <div style="
        background-color: ${color};
        width: 32px;
        height: 32px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        border: 2px solid white;
      ">
        <div style="
          width: 10px;
          height: 10px;
          background-color: white;
          border-radius: 50%;
          transform: rotate(45deg);
        "></div>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  });
};

export default function KitchenMap({
  mode = 'view',
  latitude,
  longitude,
  kitchenName,
  address,
  kitchens,
  onLocationChange,
  onLocationSelect,
  height = '350px',
  zoom = 13,
  className = '',
}: KitchenMapProps) {
  const triggerLocationChange = (lat: number, lng: number) => {
    if (onLocationChange) onLocationChange(lat, lng);
    if (onLocationSelect) onLocationSelect(lat, lng);
  };
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerGroupRef = useRef<L.LayerGroup | null>(null);
  const pickerMarkerRef = useRef<L.Marker | null>(null);

  const [currentCoords, setCurrentCoords] = useState<{ lat: number; lng: number } | null>(() => {
    if (typeof latitude === 'number' && typeof longitude === 'number' && !isNaN(latitude) && !isNaN(longitude)) {
      return { lat: latitude, lng: longitude };
    }
    return null;
  });

  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const firstKitchen = kitchens?.find((k) => k.latitude != null && k.longitude != null);
    const initialLat = currentCoords?.lat ?? (firstKitchen ? Number(firstKitchen.latitude) : 20.5937);
    const initialLng = currentCoords?.lng ?? (firstKitchen ? Number(firstKitchen.longitude) : 78.9629);
    const initialZoom = (currentCoords || firstKitchen) ? zoom : 5;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLng],
        zoom: initialZoom,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const markerGroup = L.layerGroup().addTo(map);
      markerGroupRef.current = markerGroup;
      mapInstanceRef.current = map;

      // Handle map clicks in picker mode
      if (mode === 'picker') {
        map.on('click', (e: L.LeafletMouseEvent) => {
          const { lat, lng } = e.latlng;
          setCurrentCoords({ lat, lng });
          triggerLocationChange(Number(lat.toFixed(6)), Number(lng.toFixed(6)));
        });
      }
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update currentCoords if props change
  useEffect(() => {
    if (typeof latitude === 'number' && typeof longitude === 'number' && !isNaN(latitude) && !isNaN(longitude)) {
      setCurrentCoords({ lat: latitude, lng: longitude });
    }
  }, [latitude, longitude]);

  // Render markers when coords or kitchens change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = markerGroupRef.current;
    if (!map || !group) return;

    group.clearLayers();

    // Multi-kitchens mode
    if (kitchens && kitchens.length > 0) {
      const bounds: L.LatLngTuple[] = [];

      kitchens.forEach((k) => {
        const lat = k.latitude;
        const lng = k.longitude;
        if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng)) {
          bounds.push([lat, lng]);

          // Pick color based on status
          let pinColor = '#166534'; // green approved
          if (k.approval_status === 'PENDING_APPROVAL' || k.approval_status === 'EMAIL_UNVERIFIED') {
            pinColor = '#f59e0b'; // amber
          } else if (k.approval_status === 'REJECTED' || k.approval_status === 'SUSPENDED') {
            pinColor = '#ef4444'; // red
          }

          const marker = L.marker([lat, lng], {
            icon: createCustomPinIcon(pinColor),
          });

          const popupContent = `
            <div style="font-family: system-ui, sans-serif; min-width: 180px; padding: 4px;">
              <h4 style="margin: 0 0 4px; font-weight: bold; font-size: 14px; color: #172033;">${k.kitchen_name}</h4>
              <p style="margin: 0 0 6px; font-size: 11px; color: #64748b;">${k.address || ''}${k.city ? ', ' + k.city : ''}</p>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; border-top: 1px solid #f1f5f9; pt: 4px;">
                <span style="font-size: 10px; font-weight: bold; color: ${k.is_open ? '#166534' : '#94a3b8'};">
                  ${k.is_open ? '● Open Now' : '○ Closed'}
                </span>
                <a href="/kitchens/${k.id}" style="font-size: 11px; font-weight: bold; color: #166534; text-decoration: none;">View Kitchen &rarr;</a>
              </div>
            </div>
          `;

          marker.bindPopup(popupContent);
          group.addLayer(marker);
        }
      });

      if (bounds.length > 1) {
        map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
      } else if (bounds.length === 1) {
        map.setView(bounds[0], 14);
      }
      return;
    }

    // Single coordinate view / picker mode
    if (currentCoords) {
      const pinColor = mode === 'picker' ? '#f97316' : '#166534';
      const marker = L.marker([currentCoords.lat, currentCoords.lng], {
        icon: createCustomPinIcon(pinColor),
        draggable: mode === 'picker',
      });

      if (mode === 'picker') {
        marker.on('dragend', () => {
          const pos = marker.getLatLng();
          const newLat = Number(pos.lat.toFixed(6));
          const newLng = Number(pos.lng.toFixed(6));
          setCurrentCoords({ lat: newLat, lng: newLng });
          triggerLocationChange(newLat, newLng);
        });

        marker.bindPopup(`
          <div style="font-family: system-ui, sans-serif; font-size: 12px;">
            <strong>Drag or click map to reposition kitchen</strong><br/>
            Lat: ${currentCoords.lat.toFixed(5)}, Lng: ${currentCoords.lng.toFixed(5)}
          </div>
        `);
      } else {
        const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${currentCoords.lat},${currentCoords.lng}`;
        marker.bindPopup(`
          <div style="font-family: system-ui, sans-serif; min-width: 180px; padding: 4px;">
            <h4 style="margin: 0 0 4px; font-weight: bold; font-size: 14px; color: #172033;">${kitchenName || 'Kitchen Location'}</h4>
            <p style="margin: 0 0 6px; font-size: 11px; color: #64748b;">${address || ''}</p>
            <a href="${directionsUrl}" target="_blank" rel="noopener noreferrer" style="display: inline-block; font-size: 11px; font-weight: bold; color: #166534; text-decoration: none;">
              Get Driving Directions &rarr;
            </a>
          </div>
        `);
      }

      group.addLayer(marker);
      pickerMarkerRef.current = marker;
      map.setView([currentCoords.lat, currentCoords.lng], zoom);
    }
  }, [currentCoords, kitchens, mode]);

  // GPS Locate Device Feature
  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoError('Geolocation is not supported by your browser.');
      return;
    }
    setLocating(true);
    setGeoError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6));
        const lng = Number(pos.coords.longitude.toFixed(6));
        setCurrentCoords({ lat, lng });
        triggerLocationChange(lat, lng);
        if (mapInstanceRef.current) {
          mapInstanceRef.current.setView([lat, lng], 15);
        }
        setLocating(false);
      },
      (err) => {
        setGeoError(`Unable to retrieve GPS location (${err.message}). Please click on the map directly.`);
        setLocating(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {mode === 'picker' && (
        <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 border border-gray-200 rounded-2xl text-xs">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-orange-600 shrink-0" />
            <span className="font-semibold text-gray-700">
              {currentCoords ? (
                <>
                  Coordinates: <span className="font-mono text-gray-900 font-bold">{currentCoords.lat.toFixed(5)}, {currentCoords.lng.toFixed(5)}</span>
                </>
              ) : (
                'Click map or use GPS button to place your kitchen pin'
              )}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleUseMyLocation}
              disabled={locating}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-300 hover:border-gray-400 text-gray-700 rounded-xl font-bold transition shadow-2xs"
            >
              <Navigation className={`w-3.5 h-3.5 ${locating ? 'animate-spin text-orange-600' : 'text-emerald-700'}`} />
              <span>{locating ? 'Acquiring GPS...' : 'Use My Current Location'}</span>
            </button>
          </div>
        </div>
      )}

      {geoError && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{geoError}</span>
        </div>
      )}

      {/* Leaflet map container */}
      <div
        ref={mapContainerRef}
        style={{ height, width: '100%', minHeight: '260px' }}
        className="rounded-2xl overflow-hidden border border-gray-200 shadow-2xs z-0"
      />

      {mode === 'picker' && (
        <p className="text-[11px] text-gray-500 italic">
          Tip: You can click anywhere on the map or drag the orange pin to refine the exact entrance or delivery pick-up point.
        </p>
      )}
    </div>
  );
}
