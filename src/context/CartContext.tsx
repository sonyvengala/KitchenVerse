/**
 * Cart Context & Hook
 * Manages shopping cart state, persistence in localStorage, kitchen isolation,
 * item quantities, and order subtotals.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { MenuItem } from '../services/customerApi';
import { Store, AlertTriangle } from 'lucide-react';

export interface CartItem {
  menuItem: MenuItem;
  quantity: number;
}

interface PendingConflict {
  item: MenuItem;
  quantity: number;
}

interface CartContextType {
  items: CartItem[];
  kitchenId: string | null;
  appliedPromoCode: string | null;
  setAppliedPromoCode: (code: string | null) => void;
  addToCart: (item: MenuItem, quantity?: number) => boolean;
  removeFromCart: (menuItemId: string) => void;
  updateQuantity: (menuItemId: string, quantity: number) => void;
  clearCart: () => void;
  getItemQuantity: (menuItemId: string) => number;
  itemCount: number;
  subtotal: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

const CART_STORAGE_KEY = 'cloudkitchen_cart_v1';
const PROMO_STORAGE_KEY = 'cloudkitchen_applied_promo_v1';

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const saved = localStorage.getItem(CART_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [kitchenId, setKitchenId] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(`${CART_STORAGE_KEY}_kitchen`);
      return saved || null;
    } catch {
      return null;
    }
  });

  const [appliedPromoCode, setAppliedPromoCodeState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(PROMO_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });

  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);

  const setAppliedPromoCode = (code: string | null) => {
    const clean = code ? code.trim().toUpperCase() : null;
    setAppliedPromoCodeState(clean);
    try {
      if (clean) {
        localStorage.setItem(PROMO_STORAGE_KEY, clean);
      } else {
        localStorage.removeItem(PROMO_STORAGE_KEY);
      }
    } catch {
      // storage ignored
    }
  };

  useEffect(() => {
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
      if (kitchenId) {
        localStorage.setItem(`${CART_STORAGE_KEY}_kitchen`, kitchenId);
      } else {
        localStorage.removeItem(`${CART_STORAGE_KEY}_kitchen`);
        setAppliedPromoCode(null);
      }
    } catch {
      // Storage error ignored
    }
  }, [items, kitchenId]);

  const addToCart = (item: MenuItem, quantity = 1): boolean => {
    if (items.length > 0 && kitchenId && kitchenId !== item.kitchen_id) {
      setPendingConflict({ item, quantity });
      return false;
    }

    setKitchenId(item.kitchen_id);
    setItems((prev) => {
      const existing = prev.find((i) => i.menuItem.id === item.id);
      if (existing) {
        return prev.map((i) =>
          i.menuItem.id === item.id ? { ...i, quantity: i.quantity + quantity } : i
        );
      }
      return [...prev, { menuItem: item, quantity }];
    });
    return true;
  };

  const removeFromCart = (menuItemId: string) => {
    setItems((prev) => {
      const updated = prev.filter((i) => i.menuItem.id !== menuItemId);
      if (updated.length === 0) {
        setKitchenId(null);
        setAppliedPromoCode(null);
      }
      return updated;
    });
  };

  const updateQuantity = (menuItemId: string, quantity: number) => {
    if (quantity <= 0) {
      removeFromCart(menuItemId);
      return;
    }
    setItems((prev) =>
      prev.map((i) => (i.menuItem.id === menuItemId ? { ...i, quantity } : i))
    );
  };

  const clearCart = () => {
    setItems([]);
    setKitchenId(null);
    setAppliedPromoCode(null);
  };

  const getItemQuantity = (menuItemId: string) => {
    const found = items.find((i) => i.menuItem.id === menuItemId);
    return found ? found.quantity : 0;
  };

  const itemCount = items.reduce((sum, i) => sum + i.quantity, 0);
  const subtotal = items.reduce((sum, i) => sum + i.menuItem.price * i.quantity, 0);

  return (
    <CartContext.Provider
      value={{
        items,
        kitchenId,
        appliedPromoCode,
        setAppliedPromoCode,
        addToCart,
        removeFromCart,
        updateQuantity,
        clearCart,
        getItemQuantity,
        itemCount,
        subtotal,
      }}
    >
      {children}

      {/* Kitchen Conflict Application Modal */}
      {pendingConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
                <Store className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900">
                  Your cart contains items from another kitchen.
                </h3>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                  Orders must be from a single kitchen to guarantee timely preparation and delivery dispatch. Would you like to clear your existing cart to order from this kitchen?
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setPendingConflict(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                Keep Current Cart
              </button>
              <button
                type="button"
                onClick={() => {
                  const { item, quantity } = pendingConflict;
                  setItems([{ menuItem: item, quantity }]);
                  setKitchenId(item.kitchen_id);
                  setAppliedPromoCode(null);
                  setPendingConflict(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-red-600 hover:bg-red-700 transition-colors shadow-sm"
              >
                Clear Cart & Add
              </button>
            </div>
          </div>
        </div>
      )}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
};
