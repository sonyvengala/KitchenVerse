/**
 * Admin API Service
 * Handles all API calls to admin endpoints
 */

import apiClient from '../lib/api';

// Types
export interface DashboardStats {
  total_users: number;
  customers: number;
  kitchen_owners: number;
  kitchens: number;
  total_orders: number;
  pending_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  revenue: number;
  low_stock_items: number;
  reviews: number;
  waste_records: number;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  is_email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserListResponse {
  users: User[];
  total: number;
  skip: number;
  limit: number;
}

export interface Kitchen {
  id: string;
  kitchen_name: string;
  description: string | null;
  is_verified: boolean;
  rating: number | null;
  total_reviews: number;
  created_at: string;
  owner?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    status: string;
  };
}

export interface KitchenListResponse {
  kitchens: Kitchen[];
  total: number;
  skip: number;
  limit: number;
}

export interface Order {
  id: string;
  status: string;
  total_amount: number;
  ordered_at: string;
  customer?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
  };
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
  payment?: {
    id: string;
    amount: number;
    status: string;
    payment_method: string | null;
  };
}

export interface OrderListResponse {
  orders: Order[];
  total: number;
  skip: number;
  limit: number;
}

export interface Payment {
  id: string;
  amount: number;
  status: string;
  payment_method: string | null;
  transaction_id: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface PaymentListResponse {
  payments: Payment[];
  total: number;
  skip: number;
  limit: number;
}

export interface InventoryItem {
  id: string;
  quantity_on_hand: number;
  min_quantity: number;
  max_quantity: number | null;
  unit_cost: number;
  last_restocked_at: string | null;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
  ingredient?: {
    id: string;
    name: string;
    unit: string;
  };
}

export interface InventoryListResponse {
  inventory: InventoryItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface Review {
  id: string;
  rating: number;
  comment: string | null;
  is_visible: boolean;
  created_at: string;
  user?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
  };
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
}

export interface ReviewListResponse {
  reviews: Review[];
  total: number;
  skip: number;
  limit: number;
}

export interface Promotion {
  id: string;
  code: string;
  promotion_type: string;
  discount_value: number;
  is_active: boolean;
  starts_at: string;
  expires_at: string;
  usage_count: number;
  usage_limit: number | null;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
}

export interface PromotionListResponse {
  promotions: Promotion[];
  total: number;
  skip: number;
  limit: number;
}

export interface WasteRecord {
  id: string;
  quantity: number;
  reason: string | null;
  cost: number;
  recorded_at: string;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
  ingredient?: {
    id: string;
    name: string;
    unit: string;
  };
}

export interface WasteListResponse {
  waste_records: WasteRecord[];
  total: number;
  skip: number;
  limit: number;
}

export interface DemandPrediction {
  id: string;
  prediction_date: string;
  predicted_demand: number;
  confidence_score: number | null;
  model_version: string | null;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
  menu_item?: {
    id: string;
    name: string;
    price: number;
  };
}

export interface DemandPredictionListResponse {
  predictions: DemandPrediction[];
  total: number;
  skip: number;
  limit: number;
}

export interface AnalyticsResponse {
  orders_over_time: Array<{ date: string; count: number }>;
  revenue_over_time: Array<{ date: string; revenue: number }>;
  order_status: Array<{ status: string; count: number }>;
  kitchen_activity: Array<{ kitchen: string; orders: number }>;
  popular_items: Array<{ item: string; ordered: number }>;
  customer_growth: Array<{ date: string; count: number }>;
  inventory_status: { total: number; low_stock: number };
  waste_trends: Array<{ date: string; cost: number }>;
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, any> | null;
  ip_address: string | null;
  created_at: string;
  user?: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
  };
}

export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
  skip: number;
  limit: number;
}

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number;
  is_available: boolean;
  created_at: string;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
}

export interface MenuItemListResponse {
  items: MenuItem[];
  total: number;
  skip: number;
  limit: number;
}

// API Functions
export const adminApi = {
  // Dashboard
  getDashboardStats: async (): Promise<DashboardStats> => {
    return apiClient.get('/admin/dashboard');
  },

  // Users
  getUsers: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    role?: string;
    status?: string;
    verified?: boolean;
  }): Promise<UserListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.role) queryParams.append('role', params.role);
    if (params?.status) queryParams.append('status', params.status);
    if (params?.verified !== undefined) queryParams.append('verified', params.verified.toString());
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/users${query ? `?${query}` : ''}`);
  },

  getUser: async (userId: string): Promise<any> => {
    return apiClient.get(`/admin/users/${userId}`);
  },

  updateUserStatus: async (userId: string, status: string): Promise<any> => {
    return apiClient.patch(`/admin/users/${userId}/status`, { status });
  },

  // Kitchens
  getKitchens: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }): Promise<KitchenListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/kitchens${query ? `?${query}` : ''}`);
  },

  // Kitchen Owners
  getKitchenOwners: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }): Promise<any> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/kitchen-owners${query ? `?${query}` : ''}`);
  },

  // Menu Items
  getMenuItems: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    kitchen_id?: string;
    available?: boolean;
  }): Promise<MenuItemListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    if (params?.available !== undefined) queryParams.append('available', params.available.toString());
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/menu${query ? `?${query}` : ''}`);
  },

  // Orders
  getOrders: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
    customer_id?: string;
    kitchen_id?: string;
  }): Promise<OrderListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.status) queryParams.append('status', params.status);
    if (params?.customer_id) queryParams.append('customer_id', params.customer_id);
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/orders${query ? `?${query}` : ''}`);
  },

  // Payments
  getPayments: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
  }): Promise<PaymentListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.status) queryParams.append('status', params.status);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/payments${query ? `?${query}` : ''}`);
  },

  // Inventory
  getInventory: async (params?: {
    skip?: number;
    limit?: number;
    kitchen_id?: string;
    low_stock?: boolean;
  }): Promise<InventoryListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    if (params?.low_stock !== undefined) queryParams.append('low_stock', params.low_stock.toString());
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/inventory${query ? `?${query}` : ''}`);
  },

  // Reviews
  getReviews: async (params?: {
    skip?: number;
    limit?: number;
    kitchen_id?: string;
    min_rating?: number;
  }): Promise<ReviewListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    if (params?.min_rating !== undefined) queryParams.append('min_rating', params.min_rating.toString());
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/reviews${query ? `?${query}` : ''}`);
  },

  // Promotions
  getPromotions: async (params?: {
    skip?: number;
    limit?: number;
    active?: boolean;
  }): Promise<PromotionListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.active !== undefined) queryParams.append('active', params.active.toString());
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/promotions${query ? `?${query}` : ''}`);
  },

  // Waste
  getWasteRecords: async (params?: {
    skip?: number;
    limit?: number;
    kitchen_id?: string;
  }): Promise<WasteListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/waste${query ? `?${query}` : ''}`);
  },

  // Demand Predictions
  getDemandPredictions: async (params?: {
    skip?: number;
    limit?: number;
    kitchen_id?: string;
  }): Promise<DemandPredictionListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.kitchen_id) queryParams.append('kitchen_id', params.kitchen_id);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/demand-predictions${query ? `?${query}` : ''}`);
  },

  // Analytics
  getAnalytics: async (): Promise<AnalyticsResponse> => {
    return apiClient.get('/admin/analytics');
  },

  // Audit Logs
  getAuditLogs: async (params?: {
    skip?: number;
    limit?: number;
    user_id?: string;
    action?: string;
  }): Promise<AuditLogListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.user_id) queryParams.append('user_id', params.user_id);
    if (params?.action) queryParams.append('action', params.action);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/audit-logs${query ? `?${query}` : ''}`);
  },
};
