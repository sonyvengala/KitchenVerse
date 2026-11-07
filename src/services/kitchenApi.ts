/**
 * Kitchen Owner API Service
 * Handles all API calls for the Kitchen Owner Portal (Phase 4).
 * Communicates with /api/v1/kitchen endpoints.
 */

import apiClient from '../lib/api';

export interface KitchenDashboardStats {
  kitchen_id: string;
  kitchen_name: string;
  is_open: boolean;
  rating: number;
  rating_count: number;
  pending_orders_count: number;
  active_orders_count: number;
  completed_orders_today: number;
  revenue_today: number;
  total_menu_items: number;
  low_stock_count: number;
  unread_notifications_count: number;
}

export interface OrderItem {
  id: string;
  menu_item_id: string;
  item_name: string;
  quantity: number;
  unit_price: number;
  subtotal?: number;
  total_price?: number;
}

export interface KitchenOrder {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name: string | null;
  customer_phone: string | null;
  status: string;
  subtotal: number;
  tax: number;
  delivery_fee: number;
  total_amount: number;
  payment_status: string;
  special_instructions: string | null;
  rejection_reason: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  delivery_address?: any;
  delivery_address_text?: string;
  delivery_latitude?: number | null;
  delivery_longitude?: number | null;
  kitchen_latitude?: number | null;
  kitchen_longitude?: number | null;
  kitchen_address?: string | null;
}

export interface RecipeIngredient {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity_required: number;
}

export interface MenuItemWithRecipe {
  id: string;
  kitchen_id: string;
  meal_id: number | null;
  name: string;
  description: string | null;
  category: string;
  cuisine: string;
  price: number;
  is_available: boolean;
  is_veg: boolean;
  image_url: string | null;
  image_source?: 'MANUAL' | string;
  manual_image_url?: string | null;
  created_at: string;
  recipe_ingredients: RecipeIngredient[];
}

export interface MenuItemCreateInput {
  name: string;
  description?: string;
  category: string;
  cuisine: string;
  price: number;
  is_available?: boolean;
  is_veg?: boolean;
  meal_id?: number;
  image_url?: string;
}

export interface MenuItemUpdateInput {
  name?: string;
  description?: string;
  category?: string;
  cuisine?: string;
  price?: number;
  is_available?: boolean;
  is_veg?: boolean;
  image_url?: string;
}

export interface Ingredient {
  id: string;
  kitchen_id: string;
  name: string;
  unit: string;
  current_stock: number;
  minimum_stock_threshold: number;
  reorder_quantity: number;
  is_low_stock: boolean;
  unit_cost?: number | null;
  stock_value?: number | null;
  cost_available?: boolean;
  created_at?: string;
}

export interface IngredientCreateInput {
  name: string;
  unit: string;
  initial_stock?: number;
  minimum_stock_threshold?: number;
  reorder_quantity?: number;
  unit_cost?: number | null;
  initial_cost?: number;
  supplier_name?: string;
}

export interface IngredientUpdateInput {
  name?: string;
  unit?: string;
  minimum_stock_threshold?: number;
  reorder_quantity?: number;
  unit_cost?: number | null;
}

export interface RestockInput {
  ingredient_id: string;
  quantity: number;
  purchase_unit?: string;
  total_price?: number;
  total_cost?: number;
  movement_type?: string;
  supplier_name?: string;
  unit_cost?: number;
  purchase_date?: string;
  batch_number?: string;
  expiry_date?: string;
  reason?: string;
  notes?: string;
}

export interface InventoryTransaction {
  id: string;
  kitchen_id: string;
  ingredient_id: string;
  ingredient_name: string | null;
  transaction_type: string;
  quantity: number;
  balance_after: number;
  reference_order_id: string | null;
  reason: string | null;
  created_at: string;
}

export interface RestockingRecommendation {
  ingredient_id: string;
  ingredient_name: string;
  current_stock: number;
  expected_usage?: number;
  projected_stock?: number;
  minimum_threshold: number;
  minimum_stock_threshold?: number;
  short_by?: number;
  restock_needed?: number;
  recommended_reorder_qty: number;
  recommended_reorder_quantity?: number;
  unit: string;
  urgency_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'NORMAL';
  urgency?: string;
  forecast_status?: 'RESTOCK REQUIRED' | 'SUFFICIENT' | 'SHORTAGE' | string;
  status?: string;
  unit_cost?: number | null;
  estimated_cost?: number | null;
  cost_available?: boolean;
}

export interface WasteRecordInput {
  ingredient_id: string;
  quantity: number;
  reason: string;
  notes?: string;
}

export interface WasteRecord {
  id: string;
  kitchen_id: string;
  ingredient_id: string;
  ingredient_name: string | null;
  order_id?: string | null;
  menu_item_id?: string | null;
  menu_item_name?: string | null;
  portions_wasted?: number | null;
  quantity: number;
  unit: string;
  reason: string;
  recorded_by: string;
  estimated_cost: number | null;
  cost_available?: boolean;
  source_event?: string | null;
  created_at: string;
}

export interface WasteByReasonItem {
  reason: string;
  count: number;
  total_cost: number | null;
  cost_available?: boolean;
  total_quantity: number;
}

export interface WasteByMenuItem {
  menu_item_name: string;
  portions_wasted: number;
  estimated_cost: number | null;
  cost_available?: boolean;
}

export interface WasteByIngredientItem {
  ingredient_name: string;
  total_quantity: number;
  quantity?: number;
  unit: string;
  unit_cost?: number | null;
  estimated_cost: number | null;
  cost_available?: boolean;
}

export interface MonthlyWasteTrendItem {
  month: string;
  month_label: string;
  total_cost: number;
  portions_wasted: number;
  count: number;
}

export interface WasteAnalytics {
  period_label: string;
  total_cost: number;
  wasted_orders_count: number;
  total_wasted_portions: number;
  prepared_food_portions: number;
  wastage_rate: number;
  by_reason: WasteByReasonItem[];
  by_menu_item: WasteByMenuItem[];
  by_ingredient: WasteByIngredientItem[];
  monthly_trend: MonthlyWasteTrendItem[];
}

export interface DeliveryLocationInfo {
  name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  phone?: string | null;
}

export interface DeliveryRouteResponse {
  order_id: string;
  order_number: string;
  order_status: string;
  is_active_delivery?: boolean;
  kitchen: DeliveryLocationInfo;
  customer: DeliveryLocationInfo;
  distance_km?: number | null;
  duration_minutes?: number | null;
  route_coordinates?: [number, number][];
  route_available: boolean;
  message?: string | null;
  maps_url?: string | null;
}

export interface KitchenNotification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

export interface KitchenSettingsInput {
  kitchen_name?: string;
  description?: string;
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  latitude?: number | null;
  longitude?: number | null;
  operating_hours?: string;
  cuisine?: string;
  phone?: string;
  is_open?: boolean;
}

export const kitchenApi = {
  // Dashboard
  getDashboard: async (): Promise<KitchenDashboardStats> => {
    return apiClient.get('/api/v1/kitchen/dashboard');
  },

  // Order Queue
  getOrders: async (orderStatus?: string): Promise<KitchenOrder[]> => {
    const query = orderStatus ? `?order_status=${encodeURIComponent(orderStatus)}` : '';
    return apiClient.get(`/api/v1/kitchen/orders${query}`);
  },

  getOrder: async (orderId: string): Promise<KitchenOrder> => {
    return apiClient.get(`/api/v1/kitchen/orders/${orderId}`);
  },

  acceptOrder: async (orderId: string): Promise<KitchenOrder> => {
    return apiClient.post(`/api/v1/kitchen/orders/${orderId}/accept`);
  },

  rejectOrder: async (orderId: string, reason: string): Promise<KitchenOrder> => {
    return apiClient.post(`/api/v1/kitchen/orders/${orderId}/reject`, {
      rejection_reason: reason,
    });
  },

  transitionOrder: async (orderId: string, targetStatus: string, reason?: string): Promise<KitchenOrder> => {
    return apiClient.post(`/api/v1/kitchen/orders/${orderId}/transition`, {
      target_status: targetStatus,
      reason,
    });
  },

  getDeliveryRoute: async (orderId: string): Promise<DeliveryRouteResponse> => {
    return apiClient.get(`/api/v1/kitchen/orders/${orderId}/delivery-route`);
  },

  // Menu Management
  getMenuItems: async (): Promise<MenuItemWithRecipe[]> => {
    return apiClient.get('/api/v1/kitchen/menu');
  },

  createMenuItem: async (data: MenuItemCreateInput): Promise<MenuItemWithRecipe> => {
    return apiClient.post('/api/v1/kitchen/menu', data);
  },

  updateMenuItem: async (itemId: string, data: MenuItemUpdateInput): Promise<MenuItemWithRecipe> => {
    return apiClient.put(`/api/v1/kitchen/menu/${itemId}`, data);
  },

  deleteMenuItem: async (itemId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/kitchen/menu/${itemId}`);
  },

  uploadMenuItemImageFile: async (itemId: string, file: File): Promise<MenuItemWithRecipe> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/api/v1/kitchen/menu/${itemId}/upload-image`, formData);
  },

  uploadMenuItemImageUrl: async (itemId: string, imageUrl: string): Promise<MenuItemWithRecipe> => {
    return apiClient.post(`/api/v1/kitchen/menu/${itemId}/upload-image`, { image_url: imageUrl });
  },

  uploadMenuItemImage: async (itemId: string, imageUrl: string): Promise<MenuItemWithRecipe> => {
    return apiClient.post(`/api/v1/kitchen/menu/${itemId}/upload-image`, { image_url: imageUrl });
  },

  removeMenuItemImage: async (itemId: string): Promise<MenuItemWithRecipe> => {
    return apiClient.delete(`/api/v1/kitchen/menu/${itemId}/image`);
  },

  linkRecipeIngredient: async (
    itemId: string,
    data: { ingredient_id: string; quantity_required: number }
  ): Promise<any> => {
    return apiClient.post(`/api/v1/kitchen/menu/${itemId}/recipe`, data);
  },

  unlinkRecipeIngredient: async (itemId: string, ingredientId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/kitchen/menu/${itemId}/recipe/${ingredientId}`);
  },

  // Ingredients & Inventory
  getIngredients: async (): Promise<Ingredient[]> => {
    return apiClient.get('/api/v1/kitchen/ingredients');
  },

  createIngredient: async (data: IngredientCreateInput): Promise<Ingredient> => {
    return apiClient.post('/api/v1/kitchen/ingredients', data);
  },

  updateIngredient: async (ingredientId: string, data: IngredientUpdateInput): Promise<Ingredient> => {
    return apiClient.put(`/api/v1/kitchen/ingredients/${ingredientId}`, data);
  },

  deleteIngredient: async (ingredientId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/kitchen/ingredients/${ingredientId}`);
  },

  restockIngredient: async (data: RestockInput): Promise<Ingredient> => {
    return apiClient.post('/api/v1/kitchen/inventory/restock', data);
  },

  getTransactions: async (ingredientId?: string, limit: number = 100): Promise<InventoryTransaction[]> => {
    const params = new URLSearchParams();
    if (ingredientId) params.append('ingredient_id', ingredientId);
    params.append('limit', limit.toString());
    return apiClient.get(`/api/v1/kitchen/inventory/transactions?${params.toString()}`);
  },

  getRecommendations: async (includeAll: boolean = true): Promise<RestockingRecommendation[]> => {
    return apiClient.get(`/api/v1/kitchen/inventory/recommendations?include_all=${includeAll}`);
  },

  // Waste Records
  recordWaste: async (data: WasteRecordInput): Promise<WasteRecord> => {
    return apiClient.post('/api/v1/kitchen/waste', data);
  },

  getWasteRecords: async (limit: number = 50): Promise<WasteRecord[]> => {
    return apiClient.get(`/api/v1/kitchen/waste?limit=${limit}`);
  },

  getWasteAnalytics: async (year?: number, month?: number): Promise<WasteAnalytics> => {
    const params = new URLSearchParams();
    if (year) params.append('year', year.toString());
    if (month) params.append('month', month.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    return apiClient.get(`/api/v1/kitchen/waste/analytics${query}`);
  },

  // Notifications
  getNotifications: async (limit: number = 50): Promise<KitchenNotification[]> => {
    return apiClient.get(`/api/v1/kitchen/notifications?limit=${limit}`);
  },

  markNotificationRead: async (notificationId: string): Promise<void> => {
    return apiClient.put(`/api/v1/kitchen/notifications/${notificationId}/read`);
  },

  markAllNotificationsRead: async (): Promise<void> => {
    return apiClient.put('/api/v1/kitchen/notifications/read-all');
  },

  // Settings
  getSettings: async (): Promise<any> => {
    return apiClient.get('/api/v1/kitchen/settings');
  },

  updateSettings: async (data: KitchenSettingsInput): Promise<any> => {
    return apiClient.put('/api/v1/kitchen/settings', data);
  },

  // FSSAI Food License
  ocrScanLicense: async (formData: FormData): Promise<any> => {
    return apiClient.post('/api/v1/kitchen/license/ocr-scan', formData);
  },

  getLicense: async (): Promise<any> => {
    return apiClient.get('/api/v1/kitchen/license');
  },

  submitLicense: async (data: FormData | {
    license_number: string;
    business_name?: string;
    expiry_date?: string;
    document_base64?: string;
    filename?: string;
    file_token?: string;
  }): Promise<any> => {
    return apiClient.post('/api/v1/kitchen/license/submit', data);
  },

  renewLicense: async (data: FormData | {
    license_number: string;
    business_name?: string;
    expiry_date?: string;
    document_base64?: string;
    filename?: string;
    file_token?: string;
  }): Promise<any> => {
    return apiClient.post('/api/v1/kitchen/license/renew', data);
  },

  getLicenseDocumentUrl: (docId: string | number): string => {
    return `/api/v1/kitchen/license/document/${docId}`;
  },
};

export default kitchenApi;
