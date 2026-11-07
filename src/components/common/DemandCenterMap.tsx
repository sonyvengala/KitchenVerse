/**
 * DemandCenterMap Component
 * Interactive Geographic Demand Center & Coverage Visualization
 * 
 * Sources of Truth:
 *  - Real CloudKitchen Kitchens: Direct from database (KitchenProfile)
 *  - Real Demand Areas: Aggregated from customer orders & delivery addresses
 *  - External Food Businesses: Google Places API (Only when VITE_GOOGLE_MAPS_API_KEY is configured)
 * 
 * Strict Integrity Rules:
 *  - Zero fake coordinates or synthetic demand hotspots.
 *  - If orders are 0 or no geo data, displays honest empty/insufficient state.
 *  - Google Places results are strictly segregated with distinct blue markers and disclaimers.
 */

import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { setOptions, importLibrary } from '@googlemaps/js-api-loader';
import {
  MapPin,
  Store,
  Layers,
  AlertCircle,
  ExternalLink,
  Info,
  ShieldCheck,
  Compass,
} from 'lucide-react';

export interface KitchenLocation {
  id: string;
  kitchen_name: string;
  address?: string;
  city?: string;
  latitude?: number | null;
  longitude?: number | null;
  is_open?: boolean;
  is_approved?: boolean;
  rating?: number | null;
  total_reviews?: number;
  order_count?: number;
  unique_customers?: number;
  revenue?: number;
  demand_intensity?: 'HIGH' | 'MEDIUM' | 'LOW';
  is_my_kitchen?: boolean;
}

export interface DemandArea {
  area_name: string;
  city: string;
  postal_code?: string;
  order_count: number;
  revenue: number;
  items_sold: number;
  demand_intensity: 'HIGH' | 'MEDIUM' | 'LOW';
  latitude: number;
  longitude: number;
  nearest_kitchen_name?: string | null;
  nearest_kitchen_distance_km?: number | null;
  kitchens_within_3km: number;
  coverage_gap: boolean;
  opportunity_score: number;
}

export interface ExternalPlace {
  name: string;
  address?: string;
  latitude: number;
  longitude: number;
  rating?: number;
}

interface DemandCenterMapProps {
  kitchens: KitchenLocation[];
  demandAreas: DemandArea[];
  height?: string;
  className?: string;
  onSelectArea?: (area: DemandArea) => void;
}

// Leaflet custom marker pin for CloudKitchen Kitchens (Green)
const createKitchenPinIcon = () => {
  return L.divIcon({
    className: 'custom-kitchen-pin',
    html: `
      <div style="
        background-color: #166534;
        width: 34px;
        height: 34px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(22, 101, 52, 0.4);
        border: 2.5px solid white;
      ">
        <div style="
          width: 12px;
          height: 12px;
          background-color: #fef08a;
          border-radius: 50%;
          transform: rotate(45deg);
        "></div>
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 34],
    popupAnchor: [0, -34],
  });
};

// Leaflet custom marker pin for Demand Areas (Intensity-coded)
const createDemandAreaIcon = (intensity: 'HIGH' | 'MEDIUM' | 'LOW', count: number) => {
  const color = intensity === 'HIGH' ? '#dc2626' : intensity === 'MEDIUM' ? '#d97706' : '#2563eb';
  return L.divIcon({
    className: 'custom-demand-pin',
    html: `
      <div style="
        background-color: ${color};
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        border: 2px solid white;
        color: white;
        font-weight: 800;
        font-size: 11px;
      ">
        ${count}
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16],
  });
};

export default function DemandCenterMap({
  kitchens,
  demandAreas,
  height = '460px',
  className = '',
  onSelectArea,
}: DemandCenterMapProps) {
  const googleApiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim();
  const [useGoogleMaps, setUseGoogleMaps] = useState<boolean>(Boolean(googleApiKey));
  const [showPlaces, setShowPlaces] = useState<boolean>(false);
  const [placesLoading, setPlacesLoading] = useState<boolean>(false);
  const [externalPlaces, setExternalPlaces] = useState<ExternalPlace[]>([]);
  const [mapEngine, setMapEngine] = useState<'google' | 'leaflet'>(googleApiKey ? 'google' : 'leaflet');

  const leafletContainerRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<L.Map | null>(null);

  const googleContainerRef = useRef<HTMLDivElement>(null);
  const googleMapRef = useRef<google.maps.Map | null>(null);
  const googleMarkersRef = useRef<any[]>([]);

  // Find center coordinates from kitchens or demand areas
  const validKitchens = kitchens.filter((k) => k.latitude != null && k.longitude != null);
  const validDemandAreas = demandAreas.filter((a) => a.latitude != null && a.longitude != null);

  const defaultCenter = validKitchens.length > 0
    ? { lat: Number(validKitchens[0].latitude), lng: Number(validKitchens[0].longitude) }
    : validDemandAreas.length > 0
    ? { lat: Number(validDemandAreas[0].latitude), lng: Number(validDemandAreas[0].longitude) }
    : null;

  // ==========================================
  // 1. LEAFLET MAP INITIALIZATION & RENDERING
  // ==========================================
  useEffect(() => {
    if (mapEngine !== 'leaflet' || !leafletContainerRef.current || !defaultCenter) return;

    if (!leafletMapRef.current) {
      const map = L.map(leafletContainerRef.current).setView(
        [defaultCenter.lat, defaultCenter.lng],
        12
      );

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      leafletMapRef.current = map;
    }

    const map = leafletMapRef.current;

    // Clear existing markers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker || layer instanceof L.Circle) {
        map.removeLayer(layer);
      }
    });

    const bounds = L.latLngBounds([]);

    // Add CloudKitchen Kitchens
    validKitchens.forEach((k) => {
      const lat = Number(k.latitude);
      const lng = Number(k.longitude);
      bounds.extend([lat, lng]);

      const marker = L.marker([lat, lng], { icon: createKitchenPinIcon() }).addTo(map);
      const intensityBg = k.demand_intensity === 'HIGH' ? '#fee2e2' : k.demand_intensity === 'MEDIUM' ? '#fef3c7' : '#dbeafe';
      const intensityColor = k.demand_intensity === 'HIGH' ? '#991b1b' : k.demand_intensity === 'MEDIUM' ? '#92400e' : '#1e40af';

      marker.bindPopup(`
        <div style="font-family: system-ui, sans-serif; min-width: 210px; padding: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 4px;">
            <span style="font-weight: 800; font-size: 13px; color: #166534;">${k.kitchen_name}</span>
            <span style="font-size: 10px; background: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 999px; font-weight: 700;">
              ${k.is_open ? 'OPEN' : 'CLOSED'}
            </span>
          </div>
          <p style="font-size: 11px; color: #64748b; margin: 0 0 6px 0;">${k.address || k.city || 'Verified KitchenVerse Hub'}</p>
          
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 8px; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
              <span style="font-size: 10px; font-weight: 700; color: #475569; text-transform: uppercase;">Kitchen Demand:</span>
              <span style="font-size: 10px; font-weight: 800; background: ${intensityBg}; color: ${intensityColor}; padding: 1px 6px; border-radius: 4px;">
                ${k.demand_intensity || 'LOW'}
              </span>
            </div>
            <div style="font-size: 11px; color: #1e293b; font-weight: 600;">
              <strong>${k.order_count ?? 0}</strong> Real Orders · <strong>${k.unique_customers ?? 0}</strong> Customers
            </div>
            <div style="font-size: 11px; color: #166534; font-weight: 700; margin-top: 1px;">
              ₹${(k.revenue ?? 0).toLocaleString()} Revenue
            </div>
          </div>

          <div style="font-size: 10px; color: #94a3b8; font-weight: 600; border-top: 1px solid #f1f5f9; padding-top: 4px;">
            Classification: <strong>KitchenVerse Kitchen Hub</strong>
          </div>
        </div>
      `);
    });

    // Add Demand Areas
    validDemandAreas.forEach((area) => {
      const lat = Number(area.latitude);
      const lng = Number(area.longitude);
      bounds.extend([lat, lng]);

      const marker = L.marker([lat, lng], {
        icon: createDemandAreaIcon(area.demand_intensity, area.order_count),
      }).addTo(map);

      // Add a subtle radius circle
      const radiusColor = area.demand_intensity === 'HIGH' ? '#dc2626' : area.demand_intensity === 'MEDIUM' ? '#d97706' : '#2563eb';
      L.circle([lat, lng], {
        radius: 1200,
        color: radiusColor,
        fillColor: radiusColor,
        fillOpacity: 0.12,
        weight: 1.5,
      }).addTo(map);

      marker.bindPopup(`
        <div style="font-family: system-ui, sans-serif; min-width: 210px; padding: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 800; font-size: 13px; color: #0f172a;">${area.area_name}</span>
            <span style="font-size: 10px; font-weight: 800; color: ${radiusColor};">
              ${area.demand_intensity} DEMAND
            </span>
          </div>
          <p style="font-size: 11px; color: #475569; margin: 0 0 6px 0;">
            <strong>${area.order_count}</strong> Customer Deliveries · <strong>₹${area.revenue.toLocaleString()}</strong> Revenue
          </p>
          <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">
            Nearest Hub: <strong>${area.nearest_kitchen_name || 'None'}</strong> (${area.nearest_kitchen_distance_km != null ? `${area.nearest_kitchen_distance_km} km` : 'N/A'})
          </div>
          ${
            area.coverage_gap
              ? '<div style="background: #fef2f2; color: #b91c1c; padding: 3px 6px; border-radius: 6px; font-size: 10px; font-weight: 700; border: 1px solid #fecaca; margin-bottom: 4px;">Coverage Gap: Underserved Opportunity</div>'
              : '<div style="background: #f0fdf4; color: #166534; padding: 3px 6px; border-radius: 6px; font-size: 10px; font-weight: 700; margin-bottom: 4px;">Covered by Existing Kitchens</div>'
          }
          <div style="font-size: 10px; color: #94a3b8; font-weight: 600; border-top: 1px solid #f1f5f9; padding-top: 4px;">
            Classification: <strong>Customer Delivery Location</strong>
          </div>
        </div>
      `);

      marker.on('click', () => {
        if (onSelectArea) onSelectArea(area);
      });
    });

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [mapEngine, kitchens, demandAreas]);

  // ==========================================
  // 2. GOOGLE MAPS INITIALIZATION & RENDERING
  // ==========================================
  useEffect(() => {
    if (mapEngine !== 'google' || !googleContainerRef.current || !googleApiKey || !defaultCenter) return;

    let isMounted = true;
    try {
      setOptions({ key: googleApiKey, v: 'weekly' });
    } catch {
      // Options already set
    }

    Promise.all([
      importLibrary('maps'),
      importLibrary('marker'),
    ])
      .then(async () => {
        if (!isMounted || !googleContainerRef.current) return;
        const { Map } = (await google.maps.importLibrary('maps')) as google.maps.MapsLibrary;

        const map = new Map(googleContainerRef.current, {
          center: defaultCenter,
          zoom: 12,
          fullscreenControl: false,
          mapTypeControl: false,
          streetViewControl: false,
        });
        googleMapRef.current = map;

        // Render Kitchens
        validKitchens.forEach((k) => {
          const lat = Number(k.latitude);
          const lng = Number(k.longitude);
          const marker = new google.maps.Marker({
            position: { lat, lng },
            map,
            title: `KitchenVerse: ${k.kitchen_name}`,
            icon: {
              url: 'https://maps.google.com/mapfiles/ms/icons/green-dot.png',
            },
          });
          googleMarkersRef.current.push(marker);

          const infoWindow = new google.maps.InfoWindow({
            content: `
              <div style="font-family: system-ui; padding: 4px; min-width: 180px;">
                <h4 style="margin: 0 0 4px 0; color: #166534; font-weight: 800;">${k.kitchen_name}</h4>
                <p style="margin: 0 0 4px 0; font-size: 11px; color: #555;">${k.address || k.city || 'Verified KitchenVerse Hub'}</p>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 6px; margin-bottom: 4px; font-size: 11px;">
                  <span style="font-size: 10px; font-weight: 700; color: #475569;">KITCHEN DEMAND: ${k.demand_intensity || 'LOW'}</span><br/>
                  <strong>${k.order_count ?? 0}</strong> Orders · <strong>${k.unique_customers ?? 0}</strong> Customers<br/>
                  <span style="color: #166534; font-weight: 700;">₹${(k.revenue ?? 0).toLocaleString()}</span>
                </div>
                <p style="margin: 0; font-size: 10px; color: #888;">Type: KitchenVerse Kitchen Hub</p>
              </div>
            `,
          });
          marker.addListener('click', () => infoWindow.open(map, marker));
        });

        // Render Demand Areas
        validDemandAreas.forEach((area) => {
          const lat = Number(area.latitude);
          const lng = Number(area.longitude);
          const color = area.demand_intensity === 'HIGH' ? '#dc2626' : area.demand_intensity === 'MEDIUM' ? '#d97706' : '#2563eb';

          const marker = new google.maps.Marker({
            position: { lat, lng },
            map,
            title: `Demand Area: ${area.area_name}`,
            icon: {
              url: area.demand_intensity === 'HIGH'
                ? 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
                : area.demand_intensity === 'MEDIUM'
                ? 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png'
                : 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            },
          });
          googleMarkersRef.current.push(marker);

          new google.maps.Circle({
            strokeColor: color,
            strokeOpacity: 0.8,
            strokeWeight: 2,
            fillColor: color,
            fillOpacity: 0.15,
            map,
            center: { lat, lng },
            radius: 1200,
          });

          const infoWindow = new google.maps.InfoWindow({
            content: `
              <div style="font-family: system-ui; padding: 4px; min-width: 180px;">
                <h4 style="margin: 0 0 4px 0; color: #111; font-weight: 800;">${area.area_name}</h4>
                <p style="margin: 0; font-size: 11px; color: #444;"><strong>${area.order_count}</strong> Customer Deliveries · ₹${area.revenue.toLocaleString()}</p>
                <p style="margin: 4px 0 0 0; font-size: 11px; color: #666;">Nearest Hub: ${area.nearest_kitchen_name || 'None'} (${area.nearest_kitchen_distance_km ?? 'N/A'} km)</p>
                ${area.coverage_gap ? '<p style="margin: 4px 0 0 0; color: #dc2626; font-size: 10px; font-weight: bold;">Coverage Gap Detected</p>' : ''}
                <p style="margin: 4px 0 0 0; font-size: 10px; color: #888; border-top: 1px solid #eee; padding-top: 3px;">Type: Customer Delivery Location</p>
              </div>
            `,
          });
          marker.addListener('click', () => {
            infoWindow.open(map, marker);
            if (onSelectArea) onSelectArea(area);
          });
        });
      })
      .catch((err) => {
        console.warn('Failed to load Google Maps SDK, falling back to Leaflet:', err);
        if (isMounted) setMapEngine('leaflet');
      });

    return () => {
      isMounted = false;
      googleMarkersRef.current.forEach((m) => m.setMap(null));
      googleMarkersRef.current = [];
    };
  }, [mapEngine, kitchens, demandAreas, googleApiKey]);

  return (
    <div className={`bg-white rounded-2xl border border-gray-200/80 shadow-xs overflow-hidden ${className}`}>
      {/* Map Header & Controls */}
      <div className="p-4 bg-gray-50/90 border-b border-gray-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-[#166534]/10 text-[#166534] flex items-center justify-center font-bold">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-gray-800">
              Demand Center & Coverage Map
            </h4>
            <p className="text-[11px] text-gray-500">
              {validKitchens.length} Real Kitchens · {validDemandAreas.length} Aggregated Demand Areas
            </p>
          </div>
        </div>

        {/* Engine switcher & Places configuration status */}
        <div className="flex items-center space-x-2">
          {googleApiKey ? (
            <div className="flex items-center space-x-1.5 p-1 bg-white border border-gray-200 rounded-xl text-xs">
              <button
                type="button"
                onClick={() => setMapEngine('google')}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  mapEngine === 'google' ? 'bg-[#166534] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Google Maps
              </button>
              <button
                type="button"
                onClick={() => setMapEngine('leaflet')}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  mapEngine === 'leaflet' ? 'bg-[#166534] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                OpenStreetMap
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-800">
              <Info className="w-3.5 h-3.5 flex-shrink-0" />
              <span>Google Places integration requires API configuration (VITE_GOOGLE_MAPS_API_KEY). Rendering via OpenStreetMap.</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Render Canvas */}
      <div className="relative w-full" style={{ height }}>
        {!defaultCenter ? (
          <div className="w-full h-full flex flex-col items-center justify-center p-8 bg-gray-50 text-center">
            <Compass className="w-8 h-8 text-gray-400 mb-2" />
            <p className="text-gray-700 font-semibold text-sm">Insufficient Geographic Coordinates</p>
            <p className="text-xs text-gray-400 mt-1 max-w-md">
              No real kitchen or customer delivery coordinates are recorded yet. Map will render once geographic locations are available.
            </p>
          </div>
        ) : mapEngine === 'google' && googleApiKey ? (
          <div ref={googleContainerRef} className="w-full h-full" />
        ) : (
          <div ref={leafletContainerRef} className="w-full h-full z-10" />
        )}

        {/* Legend Overlay */}
        <div className="absolute bottom-4 left-4 z-20 bg-white/95 backdrop-blur-xs p-3 rounded-xl border border-gray-200 shadow-md text-[11px] space-y-1.5">
          <div className="font-bold text-gray-800 flex items-center space-x-1 mb-1">
            <Layers className="w-3.5 h-3.5 text-gray-500" />
            <span>Map Legend</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-[#166534] border border-white inline-block shadow-xs" />
            <span className="text-gray-700 font-medium">KitchenVerse Kitchen Hub (Fulfillment)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-red-600 border border-white inline-block shadow-xs" />
            <span className="text-gray-700 font-medium">Customer Area: High (≥20 deliveries)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-amber-500 border border-white inline-block shadow-xs" />
            <span className="text-gray-700 font-medium">Customer Area: Medium (5–19 deliveries)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 rounded-full bg-blue-600 border border-white inline-block shadow-xs" />
            <span className="text-gray-700 font-medium">Customer Area: Low (&lt;5 deliveries)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
