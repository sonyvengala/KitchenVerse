/**
 * Customer API Service
 * Handles all customer operations: browsing kitchens, menu discovery, cart preview,
 * order placement, tracking, reviews, favorites, addresses, and notifications.
 */

import apiClient from '../lib/api';

export interface MenuItem {
  id: string;
  kitchen_id: string;
  meal_id?: number | null;
  name: string;
  description?: string | null;
  category: string;
  cuisine: string;
  price: number;
  is_available: boolean;
  is_veg: boolean;
  image_url?: string | null;
  image_source?: 'MANUAL' | string;
  manual_image_url?: string | null;
}

export interface Kitchen {
  id: string;
  kitchen_name: string;
  center_id?: number | null;
  description?: string | null;
  address: string;
  city: string;
  state?: string | null;
  postal_code?: string | null;
  operating_hours?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  cuisine?: string | null;
  phone?: string | null;
  is_open: boolean;
  rating: number;
  rating_count: number;
  distance_km?: number | null;
  distance_type?: 'driving' | 'estimated_straight_line' | null;
  is_estimate?: boolean;
  duration_minutes?: number | null;
  can_deliver?: boolean;
  menu_items?: MenuItem[];
}

export interface CartItemInput {
  menu_item_id: string;
  quantity: number;
  special_requests?: string;
}

export interface CheckoutPreviewRequest {
  kitchen_id: string;
  items: CartItemInput[];
  delivery_address_id?: string;
  promo_code?: string;
  promotion_code?: string;
}

export interface CheckoutPreviewResponse {
  kitchen_id: string;
  items_count: number;
  subtotal: number;
  discount_amount: number;
  applied_promo?: string | null;
  applied_promotion_code?: string | null;
  tax: number;
  delivery_fee: number;
  total_amount: number;
  currency: string;
  available: boolean;
  unavailable_items: string[];
  distance_km?: number | null;
  distance_type?: 'driving' | 'estimated_straight_line' | null;
  is_estimate?: boolean;
  distance_label?: string | null;
  base_delivery_fee?: number;
  distance_fee?: number;
  surge_fee?: number;
  platform_fee?: number;
  formula_display?: string | null;
  requires_location?: boolean;
  out_of_range?: boolean;
  max_delivery_radius_km?: number;
  pricing_breakdown?: any;
}

export interface OrderCreateRequest {
  kitchen_id: string;
  items: CartItemInput[];
  delivery_address_id?: string;
  payment_method?: string;
  special_instructions?: string;
  promo_code?: string;
  promotion_code?: string;
}

export interface OrderItem {
  id: string;
  menu_item_id?: string | null;
  item_name: string;
  unit_price: number;
  quantity: number;
  subtotal: number;
  special_requests?: string | null;
}

export interface OrderDetail {
  id: string;
  order_number: string;
  kitchen_id: string;
  kitchen_name?: string | null;
  status: string;
  subtotal: number;
  discount_amount?: number;
  promotion_code?: string | null;
  tax: number;
  delivery_fee: number;
  total_amount: number;
  payment_status: string;
  special_instructions?: string | null;
  rejection_reason?: string | null;
  cancellation_reason?: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  delivery_address?: Address | null;
  delivery_address_text?: string;
  delivery_address_snapshot?: any;
  delivery_latitude?: number | null;
  delivery_longitude?: number | null;
  delivery_distance_km?: number | null;
  pricing_breakdown_json?: string | null;
  pricing_breakdown?: any;
  can_cancel?: boolean;
  cancellation_warning?: string | null;
  cancellation_request?: CancellationRequest | null;
}

export interface Address {
  id: string;
  address_line1: string;
  address_line2?: string | null;
  city: string;
  state: string;
  postal_code: string;
  landmark?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  label?: string | null;
  delivery_instructions?: string | null;
  is_default: boolean;
}

export interface AddressCreateInput {
  address_line1: string;
  address_line2?: string;
  city: string;
  state: string;
  postal_code: string;
  landmark?: string;
  latitude?: number | null;
  longitude?: number | null;
  label?: string | null;
  delivery_instructions?: string | null;
  is_default?: boolean;
}

export interface CustomerNotification {
  id: string;
  title: string;
  message: string;
  event_type: string;
  is_read: boolean;
  created_at: string;
}

export interface CancellationRequest {
  id: string;
  order_id: string;
  customer_id: string;
  kitchen_id: string;
  reason?: string | null;
  customer_note?: string | null;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  admin_id?: string | null;
  reviewed_by?: string | null;
  admin_note?: string | null;
  created_at: string;
  requested_at?: string | null;
  resolved_at?: string | null;
  reviewed_at?: string | null;
}

export const customerApi = {
  // Kitchens
  getKitchens: async (params?: {
    query?: string;
    city?: string;
    cuisine?: string;
    latitude?: number | null;
    longitude?: number | null;
    radius_km?: number;
  }): Promise<Kitchen[]> => {
    const q = new URLSearchParams();
    if (params?.query) q.append('query', params.query);
    if (params?.city) q.append('city', params.city);
    if (params?.cuisine) q.append('cuisine', params.cuisine);
    if (params?.latitude !== undefined && params?.latitude !== null) q.append('latitude', params.latitude.toString());
    if (params?.longitude !== undefined && params?.longitude !== null) q.append('longitude', params.longitude.toString());
    if (params?.radius_km !== undefined) q.append('radius_km', params.radius_km.toString());
    const qs = q.toString();
    return apiClient.get(`/api/v1/customer/kitchens${qs ? `?${qs}` : ''}`);
  },

  getKitchenDetail: async (kitchenId: string): Promise<Kitchen> => {
    return apiClient.get(`/api/v1/customer/kitchens/${kitchenId}`);
  },

  // Menu
  getMenuItems: async (params?: {
    query?: string;
    category?: string;
    cuisine?: string;
    is_veg?: boolean;
    max_price?: number;
  }): Promise<MenuItem[]> => {
    const q = new URLSearchParams();
    if (params?.query) q.append('query', params.query);
    if (params?.category) q.append('category', params.category);
    if (params?.cuisine) q.append('cuisine', params.cuisine);
    if (params?.is_veg !== undefined) q.append('is_veg', params.is_veg.toString());
    if (params?.max_price !== undefined) q.append('max_price', params.max_price.toString());
    const qs = q.toString();
    return apiClient.get(`/api/v1/customer/menu${qs ? `?${qs}` : ''}`);
  },

  // Checkout Preview
  checkoutPreview: async (data: CheckoutPreviewRequest): Promise<CheckoutPreviewResponse> => {
    return apiClient.post('/api/v1/customer/checkout/preview', data);
  },

  // Orders
  placeOrder: async (data: OrderCreateRequest): Promise<OrderDetail> => {
    return apiClient.post('/api/v1/customer/orders', data);
  },

  getOrders: async (): Promise<OrderDetail[]> => {
    return apiClient.get('/api/v1/customer/orders');
  },

  getOrderDetail: async (orderId: string): Promise<OrderDetail> => {
    return apiClient.get(`/api/v1/customer/orders/${orderId}`);
  },

  cancelOrder: async (orderId: string, reason?: string): Promise<OrderDetail> => {
    const query = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return apiClient.post(`/api/v1/customer/orders/${orderId}/cancel${query}`);
  },

  requestCancellation: async (
    orderId: string,
    data: { reason: string; customer_note?: string }
  ): Promise<CancellationRequest> => {
    return apiClient.post(`/api/v1/customer/orders/${orderId}/cancellation-request`, data);
  },

  getCancellationRequest: async (orderId: string): Promise<CancellationRequest | null> => {
    return apiClient.get(`/api/v1/customer/orders/${orderId}/cancellation-request`);
  },

  updateOrderDeliveryLocation: async (
    orderId: string,
    data: { latitude: number; longitude: number; address_text?: string }
  ): Promise<OrderDetail> => {
    return apiClient.put(`/api/v1/customer/orders/${orderId}/delivery-location`, data);
  },

  submitReview: async (data: { order_id: string; rating: number; comment?: string; menu_item_id?: string }): Promise<any> => {
    return apiClient.post(`/api/v1/customer/orders/${data.order_id}/review`, {
      order_id: data.order_id,
      rating: data.rating,
      comment: data.comment,
      menu_item_id: data.menu_item_id,
    });
  },

  // Favorites
  toggleFavorite: async (data: { kitchen_id?: string; menu_item_id?: string }): Promise<any> => {
    return apiClient.post('/api/v1/customer/favorites/toggle', data);
  },

  getFavorites: async (): Promise<any[]> => {
    return apiClient.get('/api/v1/customer/favorites');
  },

  // Notifications
  getNotifications: async (): Promise<CustomerNotification[]> => {
    return apiClient.get('/api/v1/customer/notifications');
  },

  markNotificationRead: async (id: string): Promise<any> => {
    return apiClient.patch(`/api/v1/customer/notifications/${id}/read`);
  },

  // Addresses
  getAddresses: async (): Promise<Address[]> => {
    return apiClient.get('/api/v1/customer/addresses');
  },

  createAddress: async (data: AddressCreateInput): Promise<Address> => {
    return apiClient.post('/api/v1/customer/addresses', data);
  },

  updateAddress: async (addressId: string, data: Partial<AddressCreateInput>): Promise<Address> => {
    return apiClient.put(`/api/v1/customer/addresses/${addressId}`, data);
  },

  deleteAddress: async (addressId: string): Promise<any> => {
    return apiClient.delete(`/api/v1/customer/addresses/${addressId}`);
  },

  setDefaultAddress: async (addressId: string): Promise<Address> => {
    return apiClient.put(`/api/v1/customer/addresses/${addressId}/default`, {});
  },

  // Locations Autocomplete & Geocoding
  autocompleteLocations: async (
    q: string,
    latitude?: number | null,
    longitude?: number | null
  ): Promise<LocationSuggestion[]> => {
    const params = new URLSearchParams();
    params.append('q', q);
    if (latitude !== undefined && latitude !== null) params.append('latitude', latitude.toString());
    if (longitude !== undefined && longitude !== null) params.append('longitude', longitude.toString());
    return apiClient.get(`/api/v1/customer/locations/autocomplete?${params.toString()}`);
  },

  reverseGeocode: async (lat: number, lng: number): Promise<ReverseGeocodeResult> => {
    return apiClient.get(`/api/v1/customer/locations/reverse-geocode?lat=${lat}&lng=${lng}`);
  },

  // Profile
  getProfile: async (): Promise<any> => {
    return apiClient.get('/api/v1/customer/profile');
  },

  updateProfile: async (data: any): Promise<any> => {
    return apiClient.put('/api/v1/customer/profile', data);
  },
};

export interface LocationSuggestion {
  place_id: string;
  main_text: string;
  secondary_text: string;
  formatted_address: string;
  latitude: number;
  longitude: number;
  city?: string;
}

export interface ReverseGeocodeResult {
  formatted_address: string;
  latitude: number;
  longitude: number;
  city?: string;
}
