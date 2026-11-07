/**
 * Customer Portal - Home Page
 * Location-Aware Food Discovery:
 * - Real-time device geolocation detection with user explanation banner
 * - Nearby kitchens discoverable by default using road distance and delivery radius
 * - Clear location selector with manual address search / saved address selection fallback
 * - Real-time freshness with focus refresh, explicit refresh, and stale request cancellation
 * - Cuisine, distance, and availability filters with Nearest / Highest-rated sorting
 * - Polished responsive UI with distinct loading, empty, and global browsing states
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { customerApi, Kitchen, MenuItem } from '../../services/customerApi';
import { useCart } from '../../context/CartContext';
import CustomerLocationPicker, { CustomerLocation } from '../../components/common/CustomerLocationPicker';
import {
  Search,
  Store,
  Star,
  Clock,
  Sparkles,
  MapPin,
  Plus,
  Minus,
  Check,
  ArrowRight,
  Flame,
  ShieldCheck,
  Truck,
  Leaf,
  UtensilsCrossed,
  Navigation,
  Compass,
  RefreshCw,
  SlidersHorizontal,
  AlertCircle,
  X,
  ChevronDown,
  Layers,
} from 'lucide-react';

const CUISINES = [
  { name: 'All Cuisines', id: '' },
  { name: 'Biryani', id: 'Biryani' },
  { name: 'North Indian', id: 'North Indian' },
  { name: 'South Indian', id: 'South Indian' },
  { name: 'Fast Food', id: 'Fast Food' },
  { name: 'Desserts', id: 'Desserts' },
  { name: 'Chinese', id: 'Chinese' },
  { name: 'Beverages', id: 'Beverages' },
];

export default function Home() {
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [popularDishes, setPopularDishes] = useState<MenuItem[]>([]);
  const [selectedCuisine, setSelectedCuisine] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});

  // Geolocation & Discovery State
  const [customerLoc, setCustomerLoc] = useState<CustomerLocation | null>(() => {
    try {
      const stored = localStorage.getItem('cloudkitchen_customer_location');
      if (stored) return JSON.parse(stored);
    } catch {
      // ignore
    }
    return null;
  });
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);
  const [geoPermissionStatus, setGeoPermissionStatus] = useState<'prompt' | 'granted' | 'denied' | 'idle'>('idle');
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);
  const [browseAllMode, setBrowseAllMode] = useState(false);

  // Filters & Sorting
  const [radiusKm, setRadiusKm] = useState<number>(10);
  const [sortBy, setSortBy] = useState<'nearest' | 'rating'>('nearest');
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [lastFetchedAt, setLastFetchedAt] = useState<number>(Date.now());

  const requestIdRef = useRef(0);
  const { addToCart, getItemQuantity, updateQuantity } = useCart();
  const navigate = useNavigate();

  // Primary content loader with stale-response protection
  const loadContent = useCallback(
    async (overrideLoc?: CustomerLocation | null, isSilentRefresh = false) => {
      const activeLoc = overrideLoc !== undefined ? overrideLoc : customerLoc;
      const reqId = ++requestIdRef.current;

      if (isSilentRefresh) {
        setIsRefreshing(true);
      } else {
        setLoading(true);
      }

      try {
        const kitchenParams: any = {
          cuisine: selectedCuisine || undefined,
        };

        // When location is available and not in explicit global browsing mode
        if (activeLoc && !browseAllMode) {
          kitchenParams.latitude = activeLoc.latitude;
          kitchenParams.longitude = activeLoc.longitude;
          kitchenParams.radius_km = radiusKm;
        }

        const [kitchenData, menuData] = await Promise.all([
          customerApi.getKitchens(kitchenParams),
          customerApi.getMenuItems(selectedCuisine ? { cuisine: selectedCuisine } : undefined),
        ]);

        if (reqId === requestIdRef.current) {
          let list = kitchenData || [];

          if (onlyOpen) {
            list = list.filter((k) => k.is_open);
          }

          if (sortBy === 'rating') {
            list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
          } else if (sortBy === 'nearest' && activeLoc && !browseAllMode) {
            list.sort((a, b) => (a.distance_km ?? 9999) - (b.distance_km ?? 9999));
          }

          setKitchens(list);
          setPopularDishes(menuData ? menuData.slice(0, 8) : []);
          setLastFetchedAt(Date.now());
        }
      } catch (err) {
        if (reqId === requestIdRef.current) {
          console.error('Failed to load KitchenVerse home content:', err);
        }
      } finally {
        if (reqId === requestIdRef.current) {
          setLoading(false);
          setIsRefreshing(false);
        }
      }
    },
    [customerLoc, browseAllMode, radiusKm, selectedCuisine, onlyOpen, sortBy]
  );

  // Initial load
  useEffect(() => {
    loadContent();
  }, [loadContent]);

  // Real-time freshness on window focus (if data is > 45s old)
  useEffect(() => {
    const handleFocus = () => {
      if (Date.now() - lastFetchedAt > 45000) {
        loadContent(undefined, true);
      }
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [loadContent, lastFetchedAt]);

  // Request browser geolocation with feedback
  const handleRequestGeolocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    setIsDetectingLocation(true);
    setGeoPermissionStatus('prompt');

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        let addr = `Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
        let city = '';

        try {
          const rev = await customerApi.reverseGeocode(lat, lng);
          if (rev.formatted_address) addr = rev.formatted_address;
          if (rev.city) city = rev.city;
        } catch {
          // graceful fallback to coords string
        }

        const newLoc: CustomerLocation = {
          address: addr,
          latitude: lat,
          longitude: lng,
          city: city || undefined,
        };

        localStorage.setItem('cloudkitchen_customer_location', JSON.stringify(newLoc));
        setCustomerLoc(newLoc);
        setBrowseAllMode(false);
        setSortBy('nearest');
        setGeoPermissionStatus('granted');
        setIsDetectingLocation(false);
        loadContent(newLoc);
      },
      (err) => {
        setIsDetectingLocation(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoPermissionStatus('denied');
        } else {
          setGeoPermissionStatus('idle');
          alert(`Unable to acquire location: ${err.message}. Please select your location manually.`);
        }
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  // Location chosen via autocomplete / saved addresses modal
  const handleLocationPicked = (loc: CustomerLocation | null) => {
    if (loc) {
      localStorage.setItem('cloudkitchen_customer_location', JSON.stringify(loc));
      setCustomerLoc(loc);
      setBrowseAllMode(false);
      setSortBy('nearest');
      setGeoPermissionStatus('granted');
      setIsLocationModalOpen(false);
      loadContent(loc);
    } else {
      localStorage.removeItem('cloudkitchen_customer_location');
      setCustomerLoc(null);
      setBrowseAllMode(true);
      setIsLocationModalOpen(false);
      loadContent(null);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/menu?query=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const handleAddToCart = (dish: MenuItem) => {
    const success = addToCart(dish, 1);
    if (success) {
      setAddedIds((prev) => ({ ...prev, [dish.id]: true }));
      setTimeout(() => {
        setAddedIds((prev) => ({ ...prev, [dish.id]: false }));
      }, 1500);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Top Location Bar */}
      <section className="bg-white rounded-2xl border border-gray-200 p-3.5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-[#166534] flex items-center justify-center shrink-0">
            <MapPin className="w-5 h-5 text-[#166534]" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-black uppercase tracking-wider text-gray-400 block">
              {browseAllMode ? 'Browsing Mode' : 'Delivering To Doorstep'}
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-black text-[#172033] truncate max-w-[280px] sm:max-w-md">
                {browseAllMode
                  ? 'All KitchenVerse Hubs (Global View)'
                  : customerLoc?.address || 'Location Not Set — Click to Enable'}
              </span>
              {!browseAllMode && customerLoc && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 shrink-0">
                  GPS Active
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setIsLocationModalOpen(true)}
            className="px-3 py-1.5 rounded-xl border border-gray-200 hover:border-[#166534] hover:bg-emerald-50/50 text-[#172033] text-xs font-bold transition flex items-center gap-1"
          >
            <Compass className="w-3.5 h-3.5 text-[#166534]" />
            <span>Change</span>
          </button>

          <button
            type="button"
            disabled={isRefreshing}
            onClick={() => loadContent(undefined, true)}
            className="p-1.5 rounded-xl border border-gray-200 hover:bg-gray-100 text-gray-600 transition"
            title="Refresh nearby kitchen availability"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-[#166534]' : ''}`} />
          </button>
        </div>
      </section>

      {/* Geolocation Explanation / Permission Prompt Banner */}
      {!customerLoc && !browseAllMode && geoPermissionStatus !== 'denied' && (
        <section className="bg-gradient-to-r from-emerald-900 via-[#166534] to-emerald-800 rounded-3xl p-6 text-white shadow-lg space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-800/80 text-emerald-200 text-[10px] font-bold uppercase tracking-wider">
                <Navigation className="w-3 h-3 text-amber-300" />
                Location-Aware Kitchen Discovery
              </div>
              <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white">
                Find Cloud Kitchens Delivering to You
              </h2>
              <p className="text-xs sm:text-sm text-emerald-100 max-w-2xl leading-relaxed">
                Allow device location access to view verified road distances, exact delivery times, and licensed cloud kitchens capable of doorstep delivery to your address.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5 shrink-0">
              <button
                type="button"
                disabled={isDetectingLocation}
                onClick={handleRequestGeolocation}
                className="px-4 py-2.5 bg-[#F97316] hover:bg-[#ea580c] text-white rounded-xl text-xs font-bold transition shadow-md flex items-center gap-2"
              >
                {isDetectingLocation ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Navigation className="w-4 h-4" />
                )}
                Use Current Location
              </button>

              <button
                type="button"
                onClick={() => setIsLocationModalOpen(true)}
                className="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white border border-white/20 rounded-xl text-xs font-bold transition flex items-center gap-1.5"
              >
                <Search className="w-3.5 h-3.5" /> Select Manually
              </button>

              <button
                type="button"
                onClick={() => {
                  setBrowseAllMode(true);
                  loadContent(null);
                }}
                className="px-3 py-2.5 text-emerald-200 hover:text-white text-xs font-bold transition"
              >
                Browse All Kitchens →
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Geolocation Denied Fallback Banner */}
      {geoPermissionStatus === 'denied' && !customerLoc && !browseAllMode && (
        <section className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-bold">Location access was denied in your browser.</p>
              <p className="text-amber-800 text-[11px] mt-0.5">
                Search your street, area, or colony manually to see nearby kitchens that deliver to your address.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setIsLocationModalOpen(true)}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold transition"
            >
              Choose Location
            </button>
            <button
              onClick={() => {
                setBrowseAllMode(true);
                loadContent(null);
              }}
              className="px-3 py-1.5 border border-amber-300 text-amber-900 hover:bg-amber-100 rounded-xl font-bold transition"
            >
              Browse All
            </button>
          </div>
        </section>
      )}

      {/* Global Browsing Notice (when explicitly active) */}
      {browseAllMode && (
        <section className="bg-blue-50 border border-blue-200 rounded-2xl p-3.5 text-blue-900 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600 shrink-0" />
            <span>
              <strong>Global Kitchen Directory Mode:</strong> Showing all approved kitchens across all regions. Set your delivery address to verify doorstep delivery.
            </span>
          </div>
          <button
            onClick={() => setIsLocationModalOpen(true)}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition shrink-0"
          >
            Set Delivery Location
          </button>
        </section>
      )}

      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#166534] via-[#14532d] to-[#0f3d21] text-white shadow-xl">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:16px_16px]" />

        <div className="relative max-w-5xl mx-auto px-6 py-12 md:py-20 text-center space-y-5">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-400/20 text-amber-200 border border-amber-400/30 text-xs font-semibold uppercase tracking-wider backdrop-blur-md">
            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
            KitchenVerse Network
          </div>

          <h1 className="text-3xl md:text-5xl font-black tracking-tight leading-tight">
            Kitchen<span className="text-[#F97316]">Verse</span> <br className="hidden sm:inline" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-300 via-orange-300 to-amber-200">
              Multiple Kitchens. One Doorstep Destination.
            </span>
          </h1>

          <p className="text-sm md:text-base text-emerald-100 max-w-2xl mx-auto font-normal leading-relaxed">
            Freshly prepared gourmet recipes, transparent recipe ingredients, and verified driving-distance delivery directly from our licensed kitchens.
          </p>

          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="max-w-2xl mx-auto pt-2">
            <div className="flex items-center bg-white rounded-2xl p-2 shadow-2xl text-gray-800 focus-within:ring-4 focus-within:ring-orange-500/30 transition-all">
              <Search className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                type="text"
                placeholder="Search dishes (e.g. Chicken Biryani, Butter Paneer, Noodles)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-4 py-2.5 text-xs sm:text-sm outline-none bg-transparent placeholder-gray-400 font-medium"
              />
              <button
                type="submit"
                className="bg-[#F97316] hover:bg-[#ea580c] text-white px-5 py-2.5 rounded-xl font-bold text-xs tracking-wide transition-all shadow-md hover:shadow-lg shrink-0 flex items-center gap-1.5"
              >
                Search
              </button>
            </div>
          </form>

          {/* Badges */}
          <div className="flex flex-wrap items-center justify-center gap-5 pt-2 text-xs font-medium text-emerald-200">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-amber-400" /> 100% Licensed & Verified Kitchens
            </span>
            <span className="flex items-center gap-1.5">
              <Truck className="w-4 h-4 text-amber-400" /> Real Road-Distance Delivery
            </span>
            <span className="flex items-center gap-1.5">
              <Star className="w-4 h-4 text-amber-400" /> Certified Reviews
            </span>
          </div>
        </div>
      </section>

      {/* Promotion Banner */}
      <section className="bg-gradient-to-r from-amber-500 to-orange-500 rounded-2xl p-5 text-white shadow-md flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white shrink-0">
            <Flame className="w-6 h-6 text-amber-200" />
          </div>
          <div>
            <h3 className="font-black text-base text-white">Save Big with KitchenVerse Promo Codes</h3>
            <p className="text-xs text-amber-100">
              Apply valid promotional coupons at checkout for dynamic discounts on your order!
            </p>
          </div>
        </div>
        <Link
          to="/promotions"
          className="px-4 py-2 bg-white text-orange-600 rounded-xl text-xs font-black hover:bg-orange-50 transition shadow-sm shrink-0"
        >
          View Active Coupons
        </Link>
      </section>

      {/* Cuisine Quick Filter Chips */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-black text-[#172033] tracking-tight">Cuisines</h2>
          <span className="text-xs text-gray-400">Discover your taste</span>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
          {CUISINES.map((c) => {
            const isSelected = selectedCuisine === c.id;
            return (
              <button
                key={c.name}
                onClick={() => setSelectedCuisine(c.id)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-[#166534] text-white shadow-md'
                    : 'bg-white text-gray-700 border border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                {c.name}
              </button>
            );
          })}
        </div>
      </section>

      {/* Nearby Cloud Kitchens Section */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-black tracking-tight text-[#172033] flex items-center gap-2">
              <Store className="w-5 h-5 text-[#166534]" />
              {browseAllMode ? 'All KitchenVerse Kitchens' : 'Nearby Cloud Kitchens'}
            </h2>
            <p className="text-xs text-gray-500 font-medium">
              {browseAllMode
                ? 'Showing all active kitchens across the platform'
                : customerLoc
                ? `Delivering within ${radiusKm} km of ${customerLoc.city || 'your selected location'}`
                : 'Licensed kitchens ready to prepare fresh food'}
            </p>
          </div>

          {/* Controls: Radius, Sorting, Open-Now Toggle */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Radius Selector (when location is set) */}
            {customerLoc && !browseAllMode && (
              <div className="flex items-center bg-gray-100 p-0.5 rounded-xl border border-gray-200">
                {[5, 10, 15].map((r) => (
                  <button
                    key={r}
                    onClick={() => setRadiusKm(r)}
                    className={`px-2.5 py-1 rounded-lg font-bold transition text-[11px] ${
                      radiusKm === r
                        ? 'bg-white text-[#166534] shadow-xs'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    {r} km
                  </button>
                ))}
              </div>
            )}

            {/* Sort Toggle */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-white border border-gray-200 rounded-xl px-2.5 py-1 text-xs font-bold text-gray-700 outline-none hover:border-gray-300 transition"
            >
              {customerLoc && !browseAllMode && <option value="nearest">Nearest First</option>}
              <option value="rating">Highest Rated</option>
            </select>

            {/* Only Open Toggle */}
            <button
              onClick={() => setOnlyOpen(!onlyOpen)}
              className={`px-2.5 py-1 rounded-xl text-xs font-bold border transition ${
                onlyOpen
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              {onlyOpen ? '✓ Open Now' : 'Open Only'}
            </button>

            <Link
              to="/kitchens"
              className="text-xs font-bold text-[#166534] hover:underline flex items-center gap-1 pl-1"
            >
              View Directory <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Kitchen Cards Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-48 bg-gray-200 rounded-3xl" />
            ))}
          </div>
        ) : kitchens.length === 0 ? (
          <div className="bg-white rounded-3xl border border-gray-200 p-10 text-center space-y-4">
            <Store className="w-12 h-12 text-gray-300 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-base font-black text-[#172033]">
                {customerLoc
                  ? `No kitchens deliver within ${radiusKm} km of your location`
                  : 'No kitchens found matching your filter'}
              </h3>
              <p className="text-xs text-gray-500 max-w-md mx-auto">
                {customerLoc
                  ? 'Try expanding your delivery radius or switch to a different delivery address.'
                  : 'Try selecting a different cuisine filter or reset your search query.'}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              {customerLoc && radiusKm < 15 && (
                <button
                  onClick={() => setRadiusKm(15)}
                  className="px-4 py-2 bg-[#166534] text-white rounded-xl text-xs font-bold hover:bg-[#15803d] transition"
                >
                  Expand Radius to 15 km
                </button>
              )}
              <button
                onClick={() => setIsLocationModalOpen(true)}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-xl text-xs font-bold transition"
              >
                Change Delivery Address
              </button>
              <button
                onClick={() => {
                  setBrowseAllMode(true);
                  loadContent(null);
                }}
                className="px-4 py-2 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-xl text-xs font-bold transition"
              >
                Browse All Kitchens
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {kitchens.slice(0, 6).map((kitchen) => {
              const delivers = kitchen.can_deliver !== false;

              return (
                <Link
                  key={kitchen.id}
                  to={`/kitchens/${kitchen.id}`}
                  className="group bg-white rounded-3xl border border-gray-200 hover:border-emerald-600/40 p-5 shadow-xs hover:shadow-xl transition-all duration-300 flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-[#166534] flex items-center justify-center font-bold text-lg group-hover:scale-105 transition-transform shrink-0">
                          <Store className="w-6 h-6 text-[#166534]" />
                        </div>
                        <div className="min-w-0">
                          <h3 className="font-bold text-base text-[#172033] group-hover:text-[#166534] transition-colors leading-tight truncate">
                            {kitchen.kitchen_name}
                          </h3>
                          <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-0.5">
                            <MapPin className="w-3 h-3 text-gray-400 shrink-0" />
                            <span className="truncate">{kitchen.city || 'Local Hub'}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 bg-amber-50 text-amber-800 px-2 py-1 rounded-xl text-xs font-bold shrink-0">
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                        <span>{kitchen.rating ? kitchen.rating.toFixed(1) : 'New'}</span>
                      </div>
                    </div>

                    <p className="text-xs text-gray-600 line-clamp-2 leading-relaxed">
                      {kitchen.description || 'Specializing in fresh, authentic recipes cooked to perfection upon your order.'}
                    </p>

                    {/* Distance & Delivery Time Metadata Pills */}
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      {kitchen.distance_km != null ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                          <Truck className="w-3 h-3 text-emerald-600" />
                          {kitchen.distance_km.toFixed(1)} km (
                          {kitchen.distance_type === 'driving' ? 'driving' : 'estimate'})
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-400 font-medium">
                          📍 Set location for distance
                        </span>
                      )}

                      {kitchen.duration_minutes != null && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
                          <Clock className="w-3 h-3 text-blue-600" />
                          ~{kitchen.duration_minutes} mins
                        </span>
                      )}

                      {kitchen.cuisine && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-600">
                          {kitchen.cuisine}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="pt-4 mt-4 border-t border-gray-100 flex items-center justify-between text-xs font-semibold">
                    <span
                      className={`inline-flex items-center gap-1.5 ${
                        kitchen.is_open ? 'text-emerald-700' : 'text-gray-400'
                      }`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          kitchen.is_open ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'
                        }`}
                      />
                      {kitchen.is_open ? 'Open Now' : 'Closed'}
                    </span>
                    <span className="text-[#166534] group-hover:translate-x-1 transition-transform flex items-center gap-1">
                      Explore Menu <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Trending Dishes */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black tracking-tight text-[#172033]">
              Trending Dishes
            </h2>
            <p className="text-xs text-gray-500 font-medium">Customer favorites ordered today</p>
          </div>
          <Link
            to="/menu"
            className="text-xs font-bold text-[#166534] hover:underline flex items-center gap-1"
          >
            See All Dishes <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 animate-pulse">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-60 bg-gray-200 rounded-3xl" />
            ))}
          </div>
        ) : popularDishes.length === 0 ? (
          <div className="bg-white rounded-3xl border border-gray-200 p-8 text-center space-y-3">
            <Leaf className="w-10 h-10 text-gray-400 mx-auto" />
            <p className="text-gray-600 font-medium">No dishes found matching your selection.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {popularDishes.map((dish) => {
              const cartQty = getItemQuantity(dish.id);
              const isAvailable = dish.is_available !== false;
              const imageUrl = dish.manual_image_url || dish.image_url;

              return (
                <div
                  key={dish.id}
                  className="bg-white rounded-3xl border border-gray-200 hover:border-orange-500/40 p-4 shadow-xs hover:shadow-lg transition-all duration-300 flex flex-col justify-between space-y-3 group"
                >
                  <div className="space-y-2.5">
                    {/* Dish Image */}
                    <div className="relative h-36 w-full rounded-2xl overflow-hidden bg-gray-100 flex items-center justify-center">
                      {imageUrl ? (
                        <img
                          src={imageUrl}
                          alt={dish.name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="flex flex-col items-center justify-center text-gray-300 gap-1">
                          <UtensilsCrossed className="w-8 h-8" />
                          <span className="text-[10px] font-semibold text-gray-400">Authentic Dish</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-gray-100 text-gray-600">
                        {dish.cuisine || dish.category}
                      </span>
                      <span
                        className={`inline-flex items-center justify-center w-4 h-4 rounded border text-[9px] font-black ${
                          dish.is_veg
                            ? 'border-emerald-600 text-emerald-600 bg-emerald-50'
                            : 'border-red-600 text-red-600 bg-red-50'
                        }`}
                        title={dish.is_veg ? 'Vegetarian' : 'Non-Vegetarian'}
                      >
                        ●
                      </span>
                    </div>

                    <h3 className="font-bold text-base text-[#172033] group-hover:text-[#F97316] transition-colors leading-tight line-clamp-1">
                      {dish.name}
                    </h3>

                    <p className="text-xs text-gray-500 line-clamp-2 font-normal leading-relaxed">
                      {dish.description || 'Prepared fresh with premium ingredients and traditional kitchen recipes.'}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                    <div>
                      <span className="text-xs text-gray-400 block font-medium">Price</span>
                      <span className="text-base font-black text-[#172033]">
                        ₹{dish.price.toFixed(2)}
                      </span>
                    </div>

                    {!isAvailable ? (
                      <span className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-gray-100 text-gray-400 border border-gray-200">
                        Unavailable
                      </span>
                    ) : cartQty > 0 ? (
                      <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-300 rounded-xl px-2 py-1">
                        <button
                          type="button"
                          onClick={() => updateQuantity(dish.id, cartQty - 1)}
                          className="w-6 h-6 flex items-center justify-center rounded-lg bg-white text-emerald-800 font-bold hover:bg-emerald-100 shadow-xs border border-emerald-200"
                          title="Decrease quantity"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="text-xs font-bold text-emerald-900 min-w-[18px] text-center">
                          {cartQty}
                        </span>
                        <button
                          type="button"
                          onClick={() => updateQuantity(dish.id, cartQty + 1)}
                          className="w-6 h-6 flex items-center justify-center rounded-lg bg-white text-emerald-800 font-bold hover:bg-emerald-100 shadow-xs border border-emerald-200"
                          title="Increase quantity"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleAddToCart(dish)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1 shadow-xs ${
                          addedIds[dish.id]
                            ? 'bg-emerald-700 text-white'
                            : 'bg-[#166534] hover:bg-[#15803d] text-white'
                        }`}
                      >
                        {addedIds[dish.id] ? (
                          <>
                            <Check className="w-3.5 h-3.5" /> Added
                          </>
                        ) : (
                          <>
                            <Plus className="w-3.5 h-3.5" /> Add
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Location Picker Modal */}
      {isLocationModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <Compass className="w-5 h-5 text-[#166534]" />
                <h3 className="text-base font-black text-[#172033]">
                  Select Delivery Location
                </h3>
              </div>
              <button
                onClick={() => setIsLocationModalOpen(false)}
                className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-gray-500">
              Choose your delivery doorstep via live autocomplete, your saved addresses, or device GPS to find nearby kitchens.
            </p>

            <CustomerLocationPicker
              currentLocation={customerLoc}
              onLocationChange={handleLocationPicked}
            />

            <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
              <button
                type="button"
                onClick={() => {
                  setBrowseAllMode(true);
                  setIsLocationModalOpen(false);
                  loadContent(null);
                }}
                className="text-xs font-bold text-gray-600 hover:text-[#166534] transition"
              >
                Browse All Kitchens (No location filter)
              </button>
              <button
                type="button"
                onClick={() => setIsLocationModalOpen(false)}
                className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
