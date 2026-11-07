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
  gross_order_value?: number;
  collected_payments?: number;
  refunded_amount?: number;
  in_flight_revenue?: number;
  platform_commission?: number;
  scenario?: string;
  date_range?: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name?: string;
  role: string;
  status: string;
  is_email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  is_protected?: boolean;
  protection_reason?: string | null;
  can_suspend?: boolean;
  can_delete?: boolean;
  is_self?: boolean;
  is_last_admin?: boolean;
  is_system_account?: boolean;
  has_business_records?: boolean;
  orders_count?: number;
  kitchen_orders?: number;
  reviews_count?: number;
  delete_action_type?: 'delete' | 'archive';
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
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  latitude?: number | null;
  longitude?: number | null;
  is_open?: boolean;
  is_verified?: boolean;
  is_approved?: boolean;
  approval_status?: string;
  rejection_reason?: string | null;
  rating: number | null;
  total_reviews?: number;
  created_at: string;
  is_protected?: boolean;
  protection_reason?: string | null;
  license?: {
    id: number;
    kitchen_id: number;
    license_number: string;
    business_name?: string | null;
    status: string;
    issued_date?: string | null;
    expiry_date?: string | null;
    rejection_reason?: string | null;
    correction_reason?: string | null;
    is_duplicate_flagged: boolean;
    duplicate_notes?: string | null;
    ocr_extracted_number?: string | null;
    ocr_extracted_name?: string | null;
    ocr_extracted_expiry?: string | null;
    ocr_confidence?: number | null;
    verified_at?: string | null;
    documents?: Array<{
      id: number;
      license_id: number;
      original_filename: string;
      file_size_bytes: number;
      mime_type: string;
      version: number;
      is_current: boolean;
      uploaded_at: string;
    }>;
  } | null;
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
  unit_cost: number | null;
  cost_available?: boolean;
  stock_value?: number | null;
  unit?: string;
  status?: string;
  last_updated?: string;
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
  customer?: {
    id: string;
    name: string;
  };
  user?: {
    id: string;
    email?: string;
    first_name: string;
    last_name: string;
  };
  kitchen?: {
    id: string;
    name?: string;
    kitchen_name: string;
  };
  order_id?: string;
  order_number?: string | null;
  order?: {
    id: string;
    order_number: string;
  };
  menu_item_id?: string | null;
  menu_item_name?: string | null;
  menu_item?: {
    id: string;
    name: string;
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
  title?: string;
  description?: string;
  promotion_type: string;
  discount_value: number;
  discount_percent?: number;
  discount_amount?: number;
  min_order_amount?: number;
  max_discount_amount?: number | null;
  usage_limit?: number | null;
  usage_count: number;
  per_user_limit?: number | null;
  is_active: boolean;
  starts_at: string;
  expires_at: string;
  created_at?: string;
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
  unit?: string;
  reason: string | null;
  cost: number;
  estimated_cost?: number;
  recorded_at: string;
  created_at?: string;
  kitchen_id?: string;
  kitchen_name?: string;
  kitchen?: {
    id: string;
    kitchen_name: string;
  };
  ingredient_id?: string | null;
  ingredient_name?: string;
  ingredient?: {
    id: string;
    name: string;
    unit: string;
  };
  menu_item_id?: string | null;
  menu_item_name?: string | null;
  portions_wasted?: number | null;
  recorded_by?: string;
  source_event?: string;
}

export interface WasteSummary {
  total_cost: number;
  total_quantity: number;
  total_records: number;
}

export interface WasteListResponse {
  waste_records: WasteRecord[];
  total: number;
  skip: number;
  limit: number;
  summary?: WasteSummary;
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
  scenario?: string;
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

export interface PlatformSettings {
  platform_name: string;
  support_email: string;
  order_cancellation_window_minutes: number;
  max_delivery_radius_km: number;
  platform_commission_percent: number;
  maintenance_mode: boolean;
  auto_approve_kitchens: boolean;
  min_order_amount: number;
  delivery_base_fee?: number;
  delivery_per_km_fee?: number;
  surge_pricing_enabled?: boolean;
  surge_multiplier?: number;
  platform_fee?: number;
}

export interface AdminNotification {
  id: string;
  user_id?: string;
  title: string;
  message: string;
  event_type: string;
  notification_type: string;
  category: 'KITCHEN' | 'ORDERS' | 'PAYMENTS' | 'INVENTORY' | 'SYSTEM';
  is_read: boolean;
  metadata?: {
    entity_type?: string;
    entity_id?: string;
    order_number?: string;
    kitchen_id?: string;
    kitchen_name?: string;
    link?: string;
    [key: string]: any;
  } | null;
  link: string;
  created_at: string;
}

export interface AdminNotificationListResponse {
  notifications: AdminNotification[];
  unread_count: number;
  read_count: number;
  total_count: number;
  counts_by_tab: {
    all: number;
    unread: number;
    read: number;
    kitchen: number;
    orders: number;
    payments: number;
    inventory: number;
    system: number;
  };
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
  getDashboardStats: async (params?: {
    scenario?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DashboardStats> => {
    const queryParams = new URLSearchParams();
    if (params?.scenario) queryParams.append('scenario', params.scenario);
    if (params?.start_date) queryParams.append('start_date', params.start_date);
    if (params?.end_date) queryParams.append('end_date', params.end_date);
    const qs = queryParams.toString();
    return apiClient.get(`/admin/dashboard${qs ? `?${qs}` : ''}`);
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

  deleteUser: async (userId: string): Promise<{ success: boolean; action: string; message: string }> => {
    return apiClient.delete(`/admin/users/${userId}`);
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

  approveKitchen: async (kitchenId: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/approve`, {});
  },

  rejectKitchen: async (kitchenId: string, reason?: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/reject`, { reason });
  },

  suspendKitchen: async (kitchenId: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/suspend`, {});
  },

  // Kitchen Owners
  getKitchenOwners: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
    status?: string;
  }): Promise<any> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.status) queryParams.append('status', params.status);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/kitchen-owners${query ? `?${query}` : ''}`);
  },

  getPendingKitchenOwners: async (params?: {
    skip?: number;
    limit?: number;
    search?: string;
  }): Promise<any> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.search) queryParams.append('search', params.search);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/kitchen-owners/pending${query ? `?${query}` : ''}`);
  },

  approveKitchenOwner: async (kitchenId: string): Promise<any> => {
    return apiClient.post(`/admin/kitchen-owners/${kitchenId}/approve`, {});
  },

  rejectKitchenOwner: async (kitchenId: string, reason?: string): Promise<any> => {
    return apiClient.post(`/admin/kitchen-owners/${kitchenId}/reject`, { reason });
  },

  removeKitchenOwner: async (kitchenId: string): Promise<{ success: boolean; action: string; message: string }> => {
    return apiClient.delete(`/admin/kitchen-owners/${kitchenId}`);
  },

  batchRemoveKitchenOwners: async (kitchenIds: string[]): Promise<{
    success: boolean;
    deleted_count: number;
    archived_count: number;
    total_processed: number;
    errors?: string[];
    message: string;
  }> => {
    return apiClient.post('/admin/kitchen-owners/batch-remove', { kitchen_ids: kitchenIds });
  },

  // FSSAI License Management
  getKitchenLicense: async (kitchenId: string): Promise<any> => {
    return apiClient.get(`/admin/kitchens/${kitchenId}/license`);
  },

  verifyKitchenLicense: async (kitchenId: string, notes?: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/license/verify`, { notes });
  },

  requestLicenseCorrection: async (kitchenId: string, correctionReason: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/license/request-correction`, {
      correction_reason: correctionReason,
    });
  },

  rejectKitchenLicense: async (kitchenId: string, rejectionReason: string): Promise<any> => {
    return apiClient.post(`/admin/kitchens/${kitchenId}/license/reject`, {
      rejection_reason: rejectionReason,
    });
  },

  getLicenseDocumentUrl: (docId: string | number): string => {
    return `/api/v1/kitchen/license/document/${docId}`;
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

  archivePayment: async (paymentId: string): Promise<{ success: boolean; action: string; message: string }> => {
    return apiClient.delete(`/admin/payments/${paymentId}`);
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
    search?: string;
  }): Promise<PromotionListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params?.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params?.active !== undefined) queryParams.append('active', params.active.toString());
    if (params?.search) queryParams.append('search', params.search);
    
    const query = queryParams.toString();
    return apiClient.get(`/admin/promotions${query ? `?${query}` : ''}`);
  },

  createPromotion: async (data: {
    code: string;
    title?: string;
    description?: string;
    discount_percent?: number;
    discount_amount?: number;
    max_discount_amount?: number;
    min_order_amount?: number;
    usage_limit?: number;
    per_user_limit?: number;
    is_active?: boolean;
    valid_from?: string;
    valid_until?: string;
  }): Promise<Promotion> => {
    return apiClient.post('/admin/promotions', data);
  },

  updatePromotion: async (id: string, data: {
    title?: string;
    description?: string;
    discount_percent?: number;
    discount_amount?: number;
    max_discount_amount?: number;
    min_order_amount?: number;
    usage_limit?: number;
    per_user_limit?: number;
    is_active?: boolean;
    valid_from?: string;
    valid_until?: string;
  }): Promise<Promotion> => {
    return apiClient.put(`/admin/promotions/${id}`, data);
  },

  togglePromotionStatus: async (id: string): Promise<any> => {
    return apiClient.patch(`/admin/promotions/${id}/toggle`);
  },

  deletePromotion: async (id: string): Promise<any> => {
    return apiClient.delete(`/admin/promotions/${id}`);
  },

  sendPromotionCampaign: async (id: string): Promise<{ status: string; promo_code: string; dispatched_count: number; message: string }> => {
    return apiClient.post(`/admin/promotions/${id}/send-campaign`);
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
  getAnalytics: async (scenario: string = 'production'): Promise<AnalyticsResponse> => {
    return apiClient.get(`/admin/analytics?scenario=${encodeURIComponent(scenario)}`);
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

  // Notifications
  getNotifications: async (params?: { category?: string; tab?: string; limit?: number; offset?: number } | number): Promise<AdminNotificationListResponse> => {
    let query = '';
    if (typeof params === 'number') {
      query = `?limit=${params}`;
    } else if (params) {
      const q = new URLSearchParams();
      if (params.category) q.append('category', params.category);
      if (params.tab) q.append('tab', params.tab);
      if (params.limit) q.append('limit', params.limit.toString());
      if (params.offset !== undefined) q.append('offset', params.offset.toString());
      query = `?${q.toString()}`;
    }
    return apiClient.get(`/admin/notifications${query}`);
  },

  getUnreadNotificationCount: async (): Promise<{ unread_count: number }> => {
    return apiClient.get('/admin/notifications/unread-count');
  },

  markNotificationRead: async (notificationId: string): Promise<any> => {
    return apiClient.put(`/admin/notifications/${notificationId}/read`);
  },

  markNotificationUnread: async (notificationId: string): Promise<any> => {
    return apiClient.put(`/admin/notifications/${notificationId}/unread`);
  },

  markAllNotificationsRead: async (): Promise<any> => {
    return apiClient.put('/admin/notifications/read-all');
  },

  clearReadNotifications: async (): Promise<any> => {
    return apiClient.delete('/admin/notifications/clear-read');
  },

  deleteNotification: async (notificationId: string): Promise<any> => {
    return apiClient.delete(`/admin/notifications/${notificationId}`);
  },

  // Platform Settings
  getSettings: async (): Promise<any> => {
    return apiClient.get('/admin/settings');
  },

  updateSettings: async (settings: any): Promise<any> => {
    return apiClient.put('/admin/settings', settings);
  },

  // Cancellation Requests
  getCancellationRequests: async (status?: string): Promise<AdminCancellationRequest[]> => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiClient.get(`/admin/cancellation-requests${q}`);
  },

  getCancellationRequestDetail: async (id: string): Promise<AdminCancellationRequest> => {
    return apiClient.get(`/admin/cancellation-requests/${id}`);
  },

  approveCancellationRequest: async (id: string, adminNote?: string): Promise<any> => {
    return apiClient.post(`/admin/cancellation-requests/${id}/approve`, {
      decision: 'APPROVED',
      admin_note: adminNote,
    });
  },

  rejectCancellationRequest: async (id: string, adminNote: string): Promise<any> => {
    return apiClient.post(`/admin/cancellation-requests/${id}/reject`, {
      decision: 'REJECTED',
      admin_note: adminNote,
    });
  },

  decideCancellationRequest: async (id: string, decision: 'APPROVED' | 'REJECTED', adminNote?: string): Promise<any> => {
    return apiClient.post(`/admin/cancellation-requests/${id}/decide`, {
      decision,
      admin_note: adminNote,
    });
  },
};

export interface AdminCancellationRequest {
  id: string;
  order_id: string;
  order_number?: string | null;
  order_status?: string | null;
  order_total?: number | null;
  customer_id: string;
  customer_name?: string | null;
  customer_email?: string | null;
  kitchen_id: string;
  kitchen_name?: string | null;
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
