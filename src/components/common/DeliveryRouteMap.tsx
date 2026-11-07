/**
 * Delivery Route Map Component — Feature 3.
 * Real road-network delivery route visualization using Leaflet & OpenStreetMap.
 * Displays kitchen origin, customer destination snapshot, distance, travel duration,
 * real turn-by-turn road polyline, and "Open in Maps" directions link.
 */

import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  MapPin,
  ExternalLink,
  Navigation,
  Clock,
  Compass,
  AlertCircle,
  X,
  Store,
  Home,
  RefreshCw,
} from 'lucide-react';
import { DeliveryRouteResponse } from '../../services/kitchenApi';

interface DeliveryRouteMapModalProps {
  routeData: DeliveryRouteResponse | null;
  loading: boolean;
  onClose: () => void;
  onRetry?: () => void;
}

// Custom modern SVG pin icons
const createPinIcon = (color: string, label: string) => {
  return L.divIcon({
    className: 'custom-delivery-pin',
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
        <span style="
          color: white;
          font-weight: 900;
          font-size: 11px;
          transform: rotate(45deg);
          font-family: sans-serif;
        ">${label}</span>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  });
};

export default function DeliveryRouteMapModal({
  routeData,
  loading,
  onClose,
  onRetry,
}: DeliveryRouteMapModalProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current || loading || !routeData) {
      if (layerGroupRef.current) {
        layerGroupRef.current.clearLayers();
      }
      return;
    }

    // Initialize Leaflet map if not created yet
    if (!mapInstanceRef.current) {
      const defaultCenter: [number, number] = [12.9716, 77.5946]; // Bangalore default
      const map = L.map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      const layerGroup = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
      layerGroupRef.current = layerGroup;
    }

    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    // Clear previous layers
    layerGroup.clearLayers();

    const origin = routeData.kitchen || (routeData as any).origin;
    const dest = routeData.customer || (routeData as any).destination;
    const coords = routeData.route_coordinates || (routeData as any).route_geometry;
    const bounds: [number, number][] = [];

    // 1. Kitchen Marker (Origin)
    if (origin && origin.latitude != null && origin.longitude != null) {
      const originLat = origin.latitude;
      const originLng = origin.longitude;
      bounds.push([originLat, originLng]);

      const originMarker = L.marker([originLat, originLng], {
        icon: createPinIcon('#166534', 'K'),
      }).bindPopup(`
        <div style="font-family: sans-serif; padding: 4px; min-width: 160px;">
          <strong style="color: #166534; font-size: 13px;">${origin.name}</strong>
          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${origin.address}</div>
          <div style="font-size: 10px; color: #166534; font-weight: bold; margin-top: 4px;">• Dispatch Kitchen</div>
        </div>
      `);
      layerGroup.addLayer(originMarker);
    }

    // 2. Customer Delivery Marker (Destination)
    if (dest && dest.latitude != null && dest.longitude != null) {
      const destLat = dest.latitude;
      const destLng = dest.longitude;
      bounds.push([destLat, destLng]);

      const destMarker = L.marker([destLat, destLng], {
        icon: createPinIcon('#ea580c', 'C'),
      }).bindPopup(`
        <div style="font-family: sans-serif; padding: 4px; min-width: 160px;">
          <strong style="color: #ea580c; font-size: 13px;">${dest.name}</strong>
          <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${dest.address}</div>
          <div style="font-size: 10px; color: #ea580c; font-weight: bold; margin-top: 4px;">• Delivery Destination</div>
        </div>
      `);
      layerGroup.addLayer(destMarker);
    }

    // 3. Real Road Route Polyline
    if (routeData.route_available && coords && coords.length > 0) {
      const latLngs: [number, number][] = Array.isArray(coords[0])
        ? (coords as [number, number][])
        : (coords as any[]).map((pt) => [pt.latitude, pt.longitude]);

      const routePolyline = L.polyline(latLngs, {
        color: '#2563eb',
        weight: 5,
        opacity: 0.85,
        lineCap: 'round',
        lineJoin: 'round',
      });
      layerGroup.addLayer(routePolyline);

      // Fit map to route bounds
      map.fitBounds(routePolyline.getBounds(), { padding: [50, 50], maxZoom: 16 });
    } else if (bounds.length > 0) {
      // Fit to markers if no polyline
      if (bounds.length === 1) {
        map.setView(bounds[0], 14);
      } else {
        map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50], maxZoom: 15 });
      }
    }

    // Invalidate size once modal layout stabilizes
    setTimeout(() => {
      map.invalidateSize();
    }, 200);

    return () => {
      // Cleanup on unmount
    };
  }, [routeData, loading]);

  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        layerGroupRef.current = null;
      }
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5">
      <div className="bg-white rounded-3xl max-w-3xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-gray-100 flex items-center justify-between bg-white shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-50 text-[#166534] rounded-2xl">
              <Navigation className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black text-[#172033]">
                  Delivery Route
                </h3>
                {routeData && (
                  <span className="font-mono text-xs font-bold text-gray-400">
                    #{routeData.order_number}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500">
                Turn-by-turn driving trajectory from registered kitchen to customer address
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="overflow-y-auto p-4 sm:p-5 space-y-4">
          {loading ? (
            <div className="h-96 flex flex-col items-center justify-center space-y-3">
              <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
              <p className="text-xs text-gray-500 font-bold">Calculating driving route...</p>
            </div>
          ) : !routeData ? (
            <div className="p-8 text-center text-xs text-gray-500">No route data available.</div>
          ) : (
            <>
              {/* Route Summary Stats Bar */}
              {routeData.route_available ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-50 p-3.5 rounded-2xl border border-gray-200/70 text-xs">
                  <div>
                    <span className="text-[10px] text-gray-400 font-bold block uppercase tracking-wider">
                      Distance
                    </span>
                    <span className="text-sm font-black text-gray-900 font-mono">
                      {routeData.distance_km != null ? `${routeData.distance_km.toFixed(1)} km` : '—'}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] text-gray-400 font-bold block uppercase tracking-wider">
                      Travel Time
                    </span>
                    <span className="text-sm font-black text-[#166534] font-mono flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {routeData.duration_minutes != null ? `~${Math.round(routeData.duration_minutes)} mins` : '—'}
                    </span>
                  </div>

                  <div className="sm:col-span-2 flex items-center justify-end">
                    {(routeData.maps_url || (routeData as any).google_maps_url) ? (
                      <a
                        href={routeData.maps_url || (routeData as any).google_maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition shadow-xs"
                      >
                        <Compass className="w-3.5 h-3.5" />
                        <span>Open in Maps</span>
                        <ExternalLink className="w-3 h-3 ml-0.5 opacity-80" />
                      </a>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3.5 rounded-2xl text-xs flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>
                      <strong>Route unavailable:</strong>{' '}
                      {(() => {
                        const origin = routeData.kitchen || (routeData as any).origin;
                        const dest = routeData.customer || (routeData as any).destination;
                        if (!origin || origin.latitude == null || origin.longitude == null) {
                          return 'Kitchen location is unavailable.';
                        }
                        if (!dest || dest.latitude == null || dest.longitude == null) {
                          return 'Customer delivery location is not confirmed.';
                        }
                        if (routeData.message) {
                          return routeData.message.replace(/^Route unavailable:\s*/i, '');
                        }
                        return 'Routing could not be determined.';
                      })()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {onRetry && (
                      <button
                        type="button"
                        onClick={onRetry}
                        className="inline-flex items-center gap-1.5 px-3 py-1 bg-white border border-amber-300 text-amber-900 rounded-xl font-bold hover:bg-amber-100 transition shrink-0 shadow-2xs"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> Retry
                      </button>
                    )}
                    {(routeData.maps_url || (routeData as any).google_maps_url) && (
                      <a
                        href={routeData.maps_url || (routeData as any).google_maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-3 py-1 bg-white border border-amber-300 text-amber-900 rounded-xl font-bold hover:bg-amber-100 transition shrink-0"
                      >
                        Open in Maps <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              )}

              {/* FROM & TO Address Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-white border border-gray-200 rounded-2xl space-y-1 shadow-2xs">
                  <div className="flex items-center gap-1.5 font-bold text-[#166534]">
                    <Store className="w-3.5 h-3.5" />
                    <span>FROM: {(routeData.kitchen || (routeData as any).origin)?.name || 'Kitchen'}</span>
                  </div>
                  <p className="text-gray-500 text-[11px] leading-relaxed">
                    {(routeData.kitchen || (routeData as any).origin)?.address || 'Kitchen address not set'}
                  </p>
                  {routeData.kitchen?.latitude != null && (
                    <span className="font-mono text-[10px] text-gray-400 block">
                      Coords: {routeData.kitchen.latitude.toFixed(4)}, {routeData.kitchen.longitude?.toFixed(4)}
                    </span>
                  )}
                </div>

                <div className="p-3 bg-white border border-gray-200 rounded-2xl space-y-1 shadow-2xs">
                  <div className="flex items-center gap-1.5 font-bold text-orange-600">
                    <Home className="w-3.5 h-3.5" />
                    <span>TO: {(routeData.customer || (routeData as any).destination)?.name || 'Customer'}</span>
                  </div>
                  <p className="text-gray-500 text-[11px] leading-relaxed">
                    {(routeData.customer || (routeData as any).destination)?.address || 'Customer address not set'}
                  </p>
                  {routeData.customer?.latitude != null && (
                    <span className="font-mono text-[10px] text-gray-400 block">
                      Coords: {routeData.customer.latitude.toFixed(4)}, {routeData.customer.longitude?.toFixed(4)}
                    </span>
                  )}
                </div>
              </div>

              {/* Interactive Leaflet Map */}
              <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-inner h-80 relative">
                <div ref={mapContainerRef} className="w-full h-full z-10" />
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 bg-gray-50 border-t border-gray-100 flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-100 transition shadow-2xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
