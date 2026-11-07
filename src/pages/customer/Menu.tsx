/**
 * Customer Portal - Full Menu Discovery Page
 * Search across all dishes, filter by cuisine, category, dietary (veg/non-veg),
 * and price range, with instant Add to Cart.
 */

import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { customerApi, MenuItem } from '../../services/customerApi';
import { useCart } from '../../context/CartContext';
import {
  Search,
  Filter,
  Plus,
  Check,
  Leaf,
  Store,
  SlidersHorizontal,
  X,
  Minus,
  UtensilsCrossed,
} from 'lucide-react';

export default function Menu() {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const initialQuery = searchParams.get('query') || '';

  const [dishes, setDishes] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedCuisine, setSelectedCuisine] = useState('');
  const [vegOnly, setVegOnly] = useState(false);
  const [maxPrice, setMaxPrice] = useState(1000);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});

  const { addToCart, getItemQuantity, updateQuantity } = useCart();

  useEffect(() => {
    loadMenu();
  }, [selectedCategory, selectedCuisine, vegOnly]);

  const loadMenu = async () => {
    setLoading(true);
    try {
      const items = await customerApi.getMenuItems({
        query: searchQuery || undefined,
        category: selectedCategory || undefined,
        cuisine: selectedCuisine || undefined,
        is_veg: vegOnly ? true : undefined,
        max_price: maxPrice,
      });
      setDishes(items || []);
    } catch (err) {
      console.error('Failed to load menu dishes:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadMenu();
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

  const categories = Array.from(new Set(dishes.map((d) => d.category).filter(Boolean)));
  const cuisines = Array.from(new Set(dishes.map((d) => d.cuisine).filter(Boolean)));

  return (
    <div className="space-y-8 pb-16">
      {/* Header & Search */}
      <div className="bg-white rounded-3xl border border-gray-200 p-6 md:p-8 shadow-xs">
        <div className="max-w-3xl space-y-2 mb-6">
          <span className="text-xs font-bold text-[#F97316] tracking-wider uppercase bg-orange-50 px-2.5 py-1 rounded-md">
            Full Dish Catalog
          </span>
          <h1 className="text-3xl font-black text-[#172033] tracking-tight">
            Explore All Menu Items
          </h1>
          <p className="text-sm text-gray-600">
            Browse handcrafted recipes prepared by verified KitchenVerse kitchens in your region.
          </p>
        </div>

        {/* Search bar & quick filters */}
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search dishes by name (Biryani, Burger, Paneer, etc.)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#166534] focus:bg-white transition"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  loadMenu();
                }}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <button
            type="submit"
            className="w-full md:w-auto bg-[#166534] hover:bg-[#15803d] text-white px-6 py-2.5 rounded-xl font-bold text-sm transition shadow-xs flex items-center justify-center gap-2"
          >
            Search
          </button>
        </form>

        {/* Detailed Filters row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-6 mt-6 border-t border-gray-100">
          <div>
            <label className="block text-xs font-bold text-gray-600 mb-1.5">Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[#166534]"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-600 mb-1.5">Cuisine</label>
            <select
              value={selectedCuisine}
              onChange={(e) => setSelectedCuisine(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[#166534]"
            >
              <option value="">All Cuisines</option>
              {cuisines.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-600 mb-1.5">
              Max Price: ₹{maxPrice}
            </label>
            <input
              type="range"
              min="50"
              max="1500"
              step="50"
              value={maxPrice}
              onChange={(e) => setMaxPrice(Number(e.target.value))}
              onMouseUp={loadMenu}
              onTouchEnd={loadMenu}
              className="w-full accent-[#166534] cursor-pointer"
            />
          </div>

          <div className="flex items-center sm:justify-center pt-2 sm:pt-4">
            <label className="flex items-center gap-2 text-xs font-bold text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={vegOnly}
                onChange={(e) => setVegOnly(e.target.checked)}
                className="w-4 h-4 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500"
              />
              Pure Vegetarian Only
            </label>
          </div>
        </div>
      </div>

      {/* Dishes Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black text-[#172033] tracking-tight">
            Menu Dishes ({dishes.length})
          </h2>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-pulse">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <div key={i} className="h-56 bg-gray-200 rounded-2xl" />
            ))}
          </div>
        ) : dishes.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center space-y-3">
            <Leaf className="w-12 h-12 text-gray-400 mx-auto" />
            <h3 className="text-lg font-bold text-gray-800">No dishes match your criteria</h3>
            <p className="text-xs text-gray-500">Try loosening your search query or price filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {dishes.map((dish) => {
              const cartQty = getItemQuantity(dish.id);
              const isAvailable = dish.is_available !== false;
              const imageUrl = dish.manual_image_url || dish.image_url;

              return (
                <div
                  key={dish.id}
                  className="bg-white rounded-2xl border border-gray-200 hover:border-emerald-600/40 p-4 shadow-xs hover:shadow-lg transition-all duration-300 flex flex-col justify-between space-y-3 group"
                >
                  <div className="space-y-2.5">
                    {/* Dish Image Thumbnail */}
                    <div className="relative h-36 w-full rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center">
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

                    <h3 className="font-bold text-base text-[#172033] group-hover:text-[#166534] transition-colors leading-tight line-clamp-1">
                      {dish.name}
                    </h3>

                    <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">
                      {dish.description || 'Crafted with authenticated recipes and fresh ingredients upon order.'}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-gray-400 block font-medium">Price</span>
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
                          className="w-6 h-6 flex items-center justify-center rounded-lg bg-emerald-700 text-white font-bold hover:bg-emerald-800 shadow-xs"
                          title="Increase quantity"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleAddToCart(dish)}
                        className="px-3 py-1.5 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-1 bg-[#166534] hover:bg-[#15803d] text-white hover:shadow-md"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add
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
