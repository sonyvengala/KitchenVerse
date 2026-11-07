/**
 * Customer Portal - Kitchens Directory
 * Browse, search, and filter all approved cloud kitchens.
 * Integrated with Google Maps Platform location discovery, radius filtering,
 * distance calculation, and optional external Google Places restaurant lookup.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { customerApi, Kitchen } from '../../services/customerApi';
import KitchenMap from '../../components/common/KitchenMap';
import CustomerLocationPicker, { CustomerLocation } from '../../components/common/CustomerLocationPicker';
import {
  Store,
  Star,
  MapPin,
  Phone,
  Search,
  ArrowRight,
  UtensilsCrossed,
  LayoutGrid,
  Map as MapIcon,
  Compass,
  Navigation2,
  ExternalLink,
  Info,
} from 'lucide-react';

interface ExternalRestaurant {
  id: string;
  name: string;
  address?: string;
  rating?: number;
  openNow?: boolean;
}

export default function Kitchens() {
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [filteredKitchens, setFilteredKitchens] = useState<Kitchen[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [cityFilter, setCityFilter] = useState('');
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'map'>('grid');
  const [loading, setLoading] = useState(true);

  // Geographic discovery state
  const [customerLoc, setCustomerLoc] = useState<CustomerLocation | null>(() => {
    try {
      const stored = localStorage.getItem('cloudkitchen_customer_location');
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // ignore
    }
    return null;
  });
  const [radiusKm, setRadiusKm] = useState<number>(5);
  const [showExternalRestaurants, setShowExternalRestaurants] = useState(false);
  const [externalRestaurants, setExternalRestaurants] = useState<ExternalRestaurant[]>([]);
  const [externalLoading, setExternalLoading] = useState(false);

  const loadKitchens = useCallback(async () => {
    setLoading(true);
    try {
      const data = await customerApi.getKitchens({
        latitude: customerLoc?.latitude,
        longitude: customerLoc?.longitude,
        radius_km: customerLoc ? radiusKm : undefined,
        city: cityFilter || undefined,
        query: searchQuery || undefined,
      });
      setKitchens(data || []);
      setFilteredKitchens(data || []);
    } catch (err) {
      console.error('Failed to load kitchens:', err);
      setKitchens([]);
      setFilteredKitchens([]);
    } finally {
      setLoading(false);
    }
  }, [customerLoc, radiusKm, cityFilter, searchQuery]);

  useEffect(() => {
    loadKitchens();
  }, [loadKitchens]);

  // Client-side quick filter for open status & search refinement
  useEffect(() => {
    let result = kitchens;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (k) =>
          k.kitchen_name.toLowerCase().includes(q) ||
          k.city.toLowerCase().includes(q) ||
          (k.description && k.description.toLowerCase().includes(q))
      );
    }

    if (cityFilter) {
      result = result.filter((k) => k.city.toLowerCase() === cityFilter.toLowerCase());
    }

    if (onlyOpen) {
      result = result.filter((k) => k.is_open);
    }

    setFilteredKitchens(result);
  }, [searchQuery, cityFilter, onlyOpen, kitchens]);

  // Optional: Search external nearby restaurants via Google Places API if user explicitly selects it
  const handleLoadExternalPlaces = () => {
    if (!customerLoc) {
      alert('Please set your delivery location first to find nearby places.');
      return;
    }

    setShowExternalRestaurants(true);
    setExternalLoading(true);

    if (window.google?.maps?.places?.PlacesService) {
      try {
        const dummyNode = document.createElement('div');
        const service = new google.maps.places.PlacesService(dummyNode);
        const loc = new google.maps.LatLng(customerLoc.latitude, customerLoc.longitude);

        service.nearbySearch(
          {
            location: loc,
            radius: radiusKm * 1000,
            type: 'restaurant',
          },
          (results, status) => {
            setExternalLoading(false);
            if (status === google.maps.places.PlacesServiceStatus.OK && results) {
              const mapped: ExternalRestaurant[] = results.slice(0, 8).map((r) => ({
                id: r.place_id || Math.random().toString(),
                name: r.name || 'Restaurant',
                address: r.vicinity,
                rating: r.rating,
                openNow: r.opening_hours?.isOpen?.() ?? undefined,
              }));
              setExternalRestaurants(mapped);
            } else {
              setExternalRestaurants([]);
            }
          }
        );
      } catch (err) {
        console.warn('Google Places nearbySearch error:', err);
        setExternalLoading(false);
        setExternalRestaurants([]);
      }
    } else {
      setExternalLoading(false);
      setExternalRestaurants([]);
    }
  };

  const cities = Array.from(new Set(kitchens.map((k) => k.city).filter(Boolean)));

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 md:p-8 shadow-xs space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="max-w-2xl space-y-2">
            <span className="text-xs font-bold text-[#166534] tracking-wider uppercase bg-emerald-50 px-2.5 py-1 rounded-md">
              KitchenVerse • Multiple Kitchens. One Destination.
            </span>
            <h1 className="text-3xl font-black text-[#172033] tracking-tight">
              Browse Our Kitchen Network
            </h1>
            <p className="text-sm text-gray-600">
              Find licensed KitchenVerse kitchens nearby preparing fresh, authentic cuisines with real-time stock and recipe tracking.
            </p>
          </div>

          <div className="flex items-center gap-1 bg-gray-100 p-1.5 rounded-xl border border-gray-200 self-start md:self-auto">
            <button
              onClick={() => setViewMode('grid')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                viewMode === 'grid'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Grid View</span>
            </button>
            <button
              onClick={() => setViewMode('map')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                viewMode === 'map'
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
            >
              <MapIcon className="w-3.5 h-3.5" />
              <span>Map View</span>
            </button>
          </div>
        </div>

        {/* Geographic Delivery Location & Radius Filter */}
        <div className="bg-emerald-50/50 p-4 rounded-xl border border-emerald-100 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <label className="text-xs font-bold uppercase tracking-wider text-[#166534] flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-[#166534]" />
              Delivery Location & Search Radius
            </label>
            {customerLoc ? (
              <span className="text-xs text-emerald-800 font-medium">
                Filtering kitchens within <span className="font-bold">{radiusKm} km</span> of your delivery spot
              </span>
            ) : (
              <span className="text-xs text-gray-500 font-medium">
                Showing all approved kitchens &bull; Select a location for radius filtering
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
            <div className="md:col-span-2">
              <CustomerLocationPicker
                currentLocation={customerLoc}
                onLocationChange={(loc) => setCustomerLoc(loc)}
              />
            </div>

            <div className="flex items-center gap-2">
              <div className="w-full">
                <select
                  value={radiusKm}
                  onChange={(e) => setRadiusKm(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm font-semibold text-gray-700 focus:outline-none focus:ring-2 focus:ring-[#166534] shadow-xs"
                >
                  <option value={2}>Radius: 2 km</option>
                  <option value={5}>Radius: 5 km (Default)</option>
                  <option value={10}>Radius: 10 km</option>
                  <option value={15}>Radius: 15 km</option>
                  <option value={25}>Radius: 25 km</option>
                </select>
              </div>

              {customerLoc && (
                <button
                  type="button"
                  onClick={handleLoadExternalPlaces}
                  className="px-3 py-2 bg-white hover:bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 transition whitespace-nowrap shadow-xs"
                  title="Search external restaurants on Google Places"
                >
                  Google Places
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Text & Status Filters */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-gray-100">
          <div className="relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search by kitchen name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#166534] focus:bg-white transition"
            />
          </div>

          <div>
            <select
              value={cityFilter}
              onChange={(e) => setCityFilter(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#166534] focus:bg-white transition"
            >
              <option value="">All Cities</option>
              {cities.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-gray-700">
              <input
                type="checkbox"
                checked={onlyOpen}
                onChange={(e) => setOnlyOpen(e.target.checked)}
                className="w-4 h-4 text-[#166534] rounded border-gray-300 focus:ring-[#166534]"
              />
              Show Only Open Kitchens
            </label>
          </div>
        </div>
      </div>

      {/* External Places Drawer / Alert if requested */}
      {showExternalRestaurants && (
        <div className="bg-amber-50/80 border border-amber-200 p-5 rounded-2xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-amber-700" />
              <h3 className="text-sm font-black text-amber-900 uppercase tracking-wider">
                Google Places &bull; External Restaurants
              </h3>
            </div>
            <button
              onClick={() => setShowExternalRestaurants(false)}
              className="text-xs font-bold text-amber-700 hover:underline"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed">
            These results are fetched live from Google Places. They are external establishments and{' '}
            <span className="font-bold">are NOT KitchenVerse kitchens</span>. They cannot accept KitchenVerse orders or stock allocations.
          </p>

          {externalLoading ? (
            <div className="text-xs text-amber-700 font-medium animate-pulse py-2">
              Querying Google Places Nearby Search...
            </div>
          ) : externalRestaurants.length === 0 ? (
            <p className="text-xs text-gray-500 italic py-1">
              No external restaurants returned for this radius or Google Maps API key is not configured.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              {externalRestaurants.map((ext) => (
                <div key={ext.id} className="bg-white p-3 rounded-xl border border-amber-200 shadow-xs space-y-1">
                  <div className="font-bold text-xs text-gray-900 truncate">{ext.name}</div>
                  <div className="text-[11px] text-gray-500 truncate">{ext.address || 'Nearby address'}</div>
                  <div className="flex items-center justify-between text-[10px] text-amber-700 pt-1">
                    <span>{ext.rating ? `★ ${ext.rating}` : 'External place'}</span>
                    <span className="font-semibold text-gray-400">Google Places</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* View Content */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-56 bg-gray-200 rounded-2xl" />
          ))}
        </div>
      ) : filteredKitchens.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center space-y-4">
          <UtensilsCrossed className="w-12 h-12 text-gray-400 mx-auto" />
          <h3 className="text-lg font-bold text-gray-800">
            {customerLoc
              ? `No approved kitchens found within ${radiusKm} km of your location.`
              : 'No kitchens found matching your filters.'}
          </h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            {customerLoc
              ? 'Try expanding your search radius or exploring another delivery area.'
              : 'Try clearing your search query or city filter to view available kitchens.'}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            {customerLoc && radiusKm < 25 && (
              <button
                type="button"
                onClick={() => setRadiusKm(25)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#166534] hover:bg-[#15803d] text-white text-xs font-bold rounded-xl transition shadow-xs"
              >
                <Compass className="w-4 h-4" />
                Expand Search Radius to 25 km
              </button>
            )}

            {customerLoc && (
              <button
                type="button"
                onClick={() => {
                  try {
                    localStorage.removeItem('cloudkitchen_customer_location');
                  } catch {}
                  setCustomerLoc(null);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold rounded-xl transition shadow-xs"
              >
                Show All Approved Kitchens
              </button>
            )}
          </div>
        </div>
      ) : viewMode === 'map' ? (
        <div className="space-y-6">
          <div className="bg-white p-4 rounded-3xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="mb-3 px-2 flex items-center justify-between">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                Geographic Map View &bull; {filteredKitchens.length} Kitchens
              </span>
              <span className="text-xs text-gray-400">
                Click any marker to view address and start ordering
              </span>
            </div>
            <KitchenMap
              kitchens={filteredKitchens}
              height="580px"
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredKitchens.map((kitchen) => (
            <div
              key={kitchen.id}
              className="bg-white rounded-2xl border border-gray-200 hover:border-emerald-600/40 p-6 shadow-xs hover:shadow-xl transition-all duration-300 flex flex-col justify-between group"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-50 text-[#166534] flex items-center justify-center font-bold text-lg group-hover:scale-105 transition-transform">
                      <Store className="w-6 h-6 text-[#166534]" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-[#172033] group-hover:text-[#166534] transition-colors leading-tight">
                        {kitchen.kitchen_name}
                      </h3>
                      <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-gray-400" />
                          {kitchen.city || 'Central City'}
                        </span>
                        {kitchen.distance_km !== undefined && kitchen.distance_km !== null && (
                          <span className="bg-emerald-100 text-emerald-800 font-bold px-1.5 py-0.5 rounded text-[11px]">
                            {kitchen.distance_km.toFixed(1)} km away
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 bg-amber-50 text-amber-800 px-2 py-1 rounded-lg text-xs font-bold shrink-0">
                    <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    <span>{kitchen.rating ? kitchen.rating.toFixed(1) : 'New'}</span>
                  </div>
                </div>

                <p className="text-xs text-gray-600 leading-relaxed line-clamp-2">
                  {kitchen.description || 'Specializing in fresh, authentic recipes cooked to perfection upon your order.'}
                </p>

                <div className="space-y-1.5 text-xs text-gray-500 bg-gray-50 p-3 rounded-xl border border-gray-100">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                    <span className="truncate">{kitchen.address}</span>
                  </div>
                  {kitchen.phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <span>{kitchen.phone}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-4 mt-4 border-t border-gray-100 flex items-center justify-between">
                <span className={`inline-flex items-center gap-1.5 text-xs font-bold ${kitchen.is_open ? 'text-emerald-700' : 'text-gray-400'}`}>
                  <span className={`w-2 h-2 rounded-full ${kitchen.is_open ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'}`} />
                  {kitchen.is_open ? 'Kitchen Open' : 'Closed'}
                </span>

                <Link
                  to={`/kitchens/${kitchen.id}`}
                  className="bg-[#166534] hover:bg-[#15803d] text-white px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 group-hover:shadow-md"
                >
                  View Dishes <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
