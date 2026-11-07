/**
 * Customer Portal - Kitchen Detail Page
 * View kitchen profile, address, rating, and browse its specific menu items with Add to Cart.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { customerApi, Kitchen, MenuItem } from '../../services/customerApi';
import { useCart } from '../../context/CartContext';
import KitchenMap from '../../components/common/KitchenMap';
import {
  Store,
  Star,
  MapPin,
  Phone,
  ArrowLeft,
  Plus,
  Minus,
  Check,
  Leaf,
  Clock,
  ShoppingBag,
  Navigation,
  UtensilsCrossed,
} from 'lucide-react';

export default function KitchenDetail() {
  const { id } = useParams<{ id: string }>();
  const [kitchen, setKitchen] = useState<Kitchen | null>(null);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [vegOnly, setVegOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});

  const { addToCart, getItemQuantity, updateQuantity } = useCart();

  useEffect(() => {
    if (id) {
      loadKitchenData(id);
    }
  }, [id]);

  const loadKitchenData = async (kitchenId: string) => {
    setLoading(true);
    try {
      const [kData, allMenu] = await Promise.all([
        customerApi.getKitchenDetail(kitchenId),
        customerApi.getMenuItems(),
      ]);
      setKitchen(kData);
      // Items belonging to this kitchen
      const kitchenItems = allMenu.filter((m) => m.kitchen_id === kitchenId);
      setMenuItems(kitchenItems);
    } catch (err) {
      console.error('Failed to load kitchen details:', err);
    } finally {
      setLoading(false);
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

  const categories = ['All', ...Array.from(new Set(menuItems.map((m) => m.category).filter(Boolean)))];

  const filteredItems = menuItems.filter((m) => {
    if (selectedCategory !== 'All' && m.category !== selectedCategory) return false;
    if (vegOnly && !m.is_veg) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse pb-16">
        <div className="h-64 bg-gray-200 rounded-3xl" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 bg-gray-200 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!kitchen) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center space-y-4">
        <Store className="w-12 h-12 text-gray-400 mx-auto" />
        <h2 className="text-xl font-bold text-gray-800">Kitchen Not Found</h2>
        <p className="text-sm text-gray-500">The cloud kitchen you are looking for does not exist or has been deactivated.</p>
        <Link to="/kitchens" className="inline-flex items-center gap-2 text-sm font-bold text-[#166534]">
          <ArrowLeft className="w-4 h-4" /> Back to Kitchens
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Back button */}
      <div>
        <Link
          to="/kitchens"
          className="inline-flex items-center gap-2 text-xs font-bold text-gray-500 hover:text-[#166534] transition"
        >
          <ArrowLeft className="w-4 h-4" /> All KitchenVerse Kitchens
        </Link>
      </div>

      {/* Kitchen Hero Banner */}
      <div className="relative overflow-hidden bg-white rounded-3xl border border-gray-200 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-gradient-to-br from-[#166534] to-[#15803d] flex items-center justify-center text-white shrink-0 shadow-md">
              <Store className="w-8 h-8 md:w-10 md:h-10 text-amber-300" />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl md:text-3xl font-black text-[#172033] tracking-tight">
                  {kitchen.kitchen_name}
                </h1>
                <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full ${
                  kitchen.is_open ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${kitchen.is_open ? 'bg-emerald-500' : 'bg-gray-400'}`} />
                  {kitchen.is_open ? 'Open Now' : 'Closed'}
                </span>
              </div>

              <p className="text-xs md:text-sm text-gray-600 max-w-2xl leading-relaxed">
                {kitchen.description || 'KitchenVerse kitchen crafting authentic, chef-curated meals from fresh local stock.'}
              </p>

              <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 pt-1">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  {kitchen.address}, {kitchen.city}
                </span>
                {kitchen.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="w-3.5 h-3.5 text-gray-400" />
                    {kitchen.phone}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex md:flex-col items-center md:items-end justify-between border-t md:border-t-0 pt-4 md:pt-0 border-gray-100">
            <div className="flex items-center gap-1.5 bg-amber-50 text-amber-900 px-3.5 py-2 rounded-2xl border border-amber-200">
              <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
              <span className="text-base font-black">{kitchen.rating ? kitchen.rating.toFixed(1) : '4.8'}</span>
              <span className="text-xs text-amber-700">({kitchen.rating_count || 32} reviews)</span>
            </div>
            <span className="text-xs text-gray-400 mt-2 font-medium">Licensed Cloud Hub</span>
          </div>
        </div>

        {/* Location & Map Overview */}
        <div className="mt-6 pt-6 border-t border-gray-100 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-[#166534]" />
              Kitchen Location & Pickup Point
            </h3>
            <p className="text-sm font-semibold text-gray-800 leading-snug">
              {kitchen.address}
            </p>
            <p className="text-xs text-gray-500">
              {kitchen.city}{kitchen.state ? `, ${kitchen.state}` : ''}{kitchen.postal_code ? ` - ${kitchen.postal_code}` : ''}
            </p>
            {kitchen.operating_hours && (
              <p className="text-xs text-gray-600 flex items-center gap-1.5 pt-1">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span>Hours: {kitchen.operating_hours}</span>
              </p>
            )}
            {kitchen.latitude && kitchen.longitude && (
              <a
                href={`https://www.google.com/maps/dir/?api=1&destination=${kitchen.latitude},${kitchen.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[#166534] hover:underline pt-1"
              >
                <Navigation className="w-3.5 h-3.5" />
                Get Driving Directions
              </a>
            )}
          </div>

          <div className="md:col-span-2 rounded-2xl overflow-hidden border border-gray-200 shadow-xs">
            <KitchenMap
              mode="view"
              latitude={kitchen.latitude}
              longitude={kitchen.longitude}
              kitchenName={kitchen.kitchen_name}
              address={`${kitchen.address}, ${kitchen.city}`}
              height="200px"
            />
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-gray-200 shadow-xs">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                selectedCategory === cat
                  ? 'bg-[#166534] text-white shadow-xs'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs font-bold text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={vegOnly}
            onChange={(e) => setVegOnly(e.target.checked)}
            className="w-4 h-4 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500"
          />
          Pure Vegetarian
        </label>
      </div>

      {/* Menu Dishes Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black text-[#172033] tracking-tight">
            Available Dishes ({filteredItems.length})
          </h2>
        </div>

        {filteredItems.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center space-y-3">
            <Leaf className="w-10 h-10 text-gray-400 mx-auto" />
            <p className="text-gray-600 font-medium">No dishes match the selected category or filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredItems.map((dish) => {
              const cartQty = getItemQuantity(dish.id);
              const isAvailable = dish.is_available !== false;
              const imageUrl = dish.manual_image_url || dish.image_url;

              return (
                <div
                  key={dish.id}
                  className="bg-white rounded-2xl border border-gray-200 hover:border-emerald-600/40 p-5 shadow-xs hover:shadow-lg transition-all duration-300 flex flex-col justify-between space-y-4 group"
                >
                  <div className="space-y-2.5">
                    {/* Dish Image Thumbnail */}
                    <div className="relative h-40 w-full rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center">
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
                        {dish.category}
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

                    <h3 className="font-bold text-base text-[#172033] group-hover:text-[#166534] transition-colors leading-tight">
                      {dish.name}
                    </h3>

                    <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">
                      {dish.description || 'Handcrafted fresh to order with precision inventory deduction on preparation.'}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-gray-400 block font-medium">Price</span>
                      <span className="text-lg font-black text-[#172033]">
                        ₹{dish.price.toFixed(2)}
                      </span>
                    </div>

                    {!isAvailable ? (
                      <span className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-gray-100 text-gray-400 border border-gray-200">
                        Unavailable
                      </span>
                    ) : cartQty > 0 ? (
                      <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-300 rounded-xl px-2 py-1">
                        <button
                          type="button"
                          onClick={() => updateQuantity(dish.id, cartQty - 1)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg bg-white text-emerald-800 font-bold hover:bg-emerald-100 shadow-xs border border-emerald-200"
                          title="Decrease quantity"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="text-xs font-bold text-emerald-900 min-w-[20px] text-center">
                          {cartQty}
                        </span>
                        <button
                          type="button"
                          onClick={() => updateQuantity(dish.id, cartQty + 1)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg bg-emerald-700 text-white font-bold hover:bg-emerald-800 shadow-xs"
                          title="Increase quantity"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleAddToCart(dish)}
                        className="px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 bg-[#166534] hover:bg-[#15803d] text-white hover:shadow-md"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add to Cart
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
