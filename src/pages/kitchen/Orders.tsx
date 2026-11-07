/**
 * Kitchen Order Queue Page
 * Kitchen-specific order operations: Accept, Reject (with reason), and Status Transitions.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import kitchenApi, { KitchenOrder, DeliveryRouteResponse } from '../../services/kitchenApi';
import DeliveryRouteMapModal from '../../components/common/DeliveryRouteMap';
import {
  ShoppingBag,
  Clock,
  Check,
  X,
  ChefHat,
  BellRing,
  Truck,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Search,
  Filter,
  Navigation,
  MapPin,
  ShieldAlert,
  LogIn,
} from 'lucide-react';

import { useRealtime } from '../../context/RealtimeContext';

export default function KitchenOrders() {
  const { subscribe } = useRealtime();
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAuthError, setIsAuthError] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Reject Modal State
  const [rejectingOrderId, setRejectingOrderId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>('');

  // Delivery Route Modal State
  const [routeModalOpen, setRouteModalOpen] = useState(false);
  const [selectedRouteData, setSelectedRouteData] = useState<DeliveryRouteResponse | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeOrderId, setRouteOrderId] = useState<string | null>(null);

  const handleViewRoute = async (orderId: string) => {
    setRouteOrderId(orderId);
    setRouteModalOpen(true);
    setRouteLoading(true);
    setSelectedRouteData(null);
    try {
      const data = await kitchenApi.getDeliveryRoute(orderId);
      setSelectedRouteData(data);
    } catch (err: any) {
      console.error('Failed to fetch delivery route:', err);
    } finally {
      setRouteLoading(false);
    }
  };

  const fetchOrders = async () => {
    try {
      setLoading(true);
      setError(null);
      setIsAuthError(false);
      const data = await kitchenApi.getOrders();
      setOrders(data);
    } catch (err: any) {
      const detail = err?.detail || err?.message || 'Failed to fetch kitchen orders.';
      const isForbiddenOrUnauthorized =
        err?.status === 403 ||
        err?.status === 401 ||
        detail.includes('requires one of roles') ||
        detail.includes('Access forbidden') ||
        detail.includes('Not authenticated');

      setIsAuthError(isForbiddenOrUnauthorized);
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();

    // Instant real-time updates for new orders and status transitions
    const unsubCreated = subscribe('ORDER_CREATED', () => {
      fetchOrders();
    });
    const unsubStatus = subscribe('ORDER_STATUS_CHANGED', () => {
      fetchOrders();
    });

    // Fallback refresh interval - only poll if not currently blocked by an auth/permission error
    const interval = setInterval(() => {
      if (!isAuthError) {
        fetchOrders();
      }
    }, 30000);
    return () => {
      unsubCreated();
      unsubStatus();
      clearInterval(interval);
    };
  }, [subscribe, isAuthError]);

  const handleAccept = async (orderId: string) => {
    try {
      setActionLoading(orderId);
      const updated = await kitchenApi.acceptOrder(orderId);
      setOrders(orders.map((o) => (o.id === orderId ? updated : o)));
    } catch (err: any) {
      alert(err?.detail || 'Failed to accept order.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectConfirm = async () => {
    if (!rejectingOrderId || !rejectionReason.trim()) {
      alert('Please specify a valid rejection reason.');
      return;
    }
    try {
      setActionLoading(rejectingOrderId);
      const updated = await kitchenApi.rejectOrder(rejectingOrderId, rejectionReason);
      setOrders(orders.map((o) => (o.id === rejectingOrderId ? updated : o)));
      setRejectingOrderId(null);
      setRejectionReason('');
    } catch (err: any) {
      alert(err?.detail || 'Failed to reject order.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleTransition = async (orderId: string, nextStatus: string) => {
    try {
      setActionLoading(orderId);
      const updated = await kitchenApi.transitionOrder(orderId, nextStatus);
      setOrders(orders.map((o) => (o.id === orderId ? updated : o)));
    } catch (err: any) {
      alert(err?.detail || `Failed to transition order to ${nextStatus}.`);
    } finally {
      setActionLoading(null);
    }
  };

  const filteredOrders = orders.filter((o) => {
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'PENDING') return o.status === 'PAYMENT_CONFIRMED' || o.status === 'ORDER_PLACED' || o.status === 'PENDING';
    if (statusFilter === 'ACCEPTED') return o.status === 'KITCHEN_ACCEPTED' || o.status === 'CONFIRMED';
    if (statusFilter === 'PREPARING') return o.status === 'PREPARING';
    if (statusFilter === 'READY') return o.status === 'READY';
    if (statusFilter === 'COMPLETED') return o.status === 'DELIVERED';
    if (statusFilter === 'CANCELLED') return o.status === 'CANCELLED' || o.status === 'REJECTED' || o.status === 'PAYMENT_FAILED';
    return o.status === statusFilter;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ORDER_PLACED':
      case 'PAYMENT_CONFIRMED':
        return <span className="px-2.5 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-bold">Awaiting Acceptance</span>;
      case 'KITCHEN_ACCEPTED':
        return <span className="px-2.5 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-bold">Accepted</span>;
      case 'PREPARING':
        return <span className="px-2.5 py-1 bg-purple-100 text-purple-800 rounded-full text-xs font-bold">Cooking</span>;
      case 'READY':
        return <span className="px-2.5 py-1 bg-emerald-100 text-[#166534] rounded-full text-xs font-bold">Ready for Pickup</span>;
      case 'DELIVERED':
        return <span className="px-2.5 py-1 bg-green-100 text-green-800 rounded-full text-xs font-bold">Delivered</span>;
      case 'REJECTED':
      case 'CANCELLED':
        return <span className="px-2.5 py-1 bg-red-100 text-red-800 rounded-full text-xs font-bold">Cancelled / Rejected</span>;
      default:
        return <span className="px-2.5 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-bold">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Bar with Refresh & Filters */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-200/80 shadow-xs">
        <div>
          <h1 className="text-2xl font-black text-[#172033] tracking-tight">Order Queue</h1>
          <p className="text-sm text-gray-500">Live order processing, acceptance, and state transitions.</p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchOrders}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 border-b border-gray-200">
        {[
          { key: 'ALL', label: 'All Orders' },
          { key: 'PENDING', label: 'New / Awaiting' },
          { key: 'ACCEPTED', label: 'Accepted' },
          { key: 'PREPARING', label: 'Preparing' },
          { key: 'READY', label: 'Ready' },
          { key: 'COMPLETED', label: 'Delivered' },
          { key: 'CANCELLED', label: 'Rejected/Cancelled' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setStatusFilter(tab.key)}
            className={`px-4 py-2 text-sm font-bold rounded-xl whitespace-nowrap transition-colors ${
              statusFilter === tab.key
                ? 'bg-[#166534] text-white shadow-xs'
                : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Order List */}
      {loading && orders.length === 0 ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-[#166534] animate-spin" />
        </div>
      ) : error ? (
        isAuthError ? (
          <div className="bg-amber-50/90 border border-amber-200/80 rounded-3xl p-8 text-center max-w-xl mx-auto shadow-xs my-6">
            <div className="w-14 h-14 bg-amber-100 text-amber-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">
              Kitchen Owner Access Required
            </h3>
            <p className="text-sm text-gray-600 mb-6 leading-relaxed">
              Your active session does not possess Kitchen Owner permissions, or your authentication has expired. Please sign in with an authorized Kitchen Owner account to manage kitchen orders.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                to="/login"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#166534] text-white font-bold text-sm hover:bg-[#14532d] shadow-xs transition-colors"
              >
                <LogIn className="w-4 h-4" />
                Sign In as Kitchen Owner
              </Link>
              <button
                onClick={fetchOrders}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-gray-300 bg-white text-gray-700 font-bold text-sm hover:bg-gray-50 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Retry
              </button>
            </div>
            <p className="text-[11px] text-amber-700/70 font-mono mt-5">
              Backend message: {error}
            </p>
          </div>
        ) : (
          <div className="p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-center max-w-xl mx-auto my-6">
            <div className="w-10 h-10 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-2">
              <AlertCircle className="w-5 h-5" />
            </div>
            <p className="font-semibold text-sm mb-3">{error}</p>
            <button
              onClick={fetchOrders}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-600 text-white font-bold text-xs hover:bg-red-700 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Try Again
            </button>
          </div>
        )
      ) : filteredOrders.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200/80 p-12 text-center">
          <ShoppingBag className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-700">No orders found</h3>
          <p className="text-sm text-gray-400 mt-1">There are no orders matching this filter right now.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredOrders.map((order) => (
            <div
              key={order.id}
              className="bg-white rounded-2xl border border-gray-200/80 p-6 shadow-xs hover:border-gray-300 transition-colors"
            >
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between pb-4 border-b border-gray-100 gap-3">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#166534] flex items-center justify-center font-bold">
                    #{order.order_number.slice(-4)}
                  </div>
                  <div>
                    <h3 className="font-bold text-[#172033] text-base">{order.order_number}</h3>
                    <p className="text-xs text-gray-400">
                      {new Date(order.created_at).toLocaleString()} • Customer: {order.customer_name || 'Guest'} ({order.customer_phone || 'N/A'})
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {getStatusBadge(order.status)}
                  <span className="text-base font-black text-[#172033]">₹{order.total_amount.toFixed(2)}</span>
                </div>
              </div>

              {/* Items & Instructions */}
              <div className="py-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="text-xs font-bold uppercase text-gray-400 mb-2">Order Items</h4>
                  <ul className="space-y-1.5">
                    {order.items.map((item) => (
                      <li key={item.id} className="text-sm flex items-center justify-between text-[#172033]">
                        <span>
                          <strong className="text-[#166534]">{item.quantity}x</strong> {item.item_name}
                        </span>
                        <span className="text-gray-500 font-medium">
                          ₹{((item.total_price ?? item.subtotal ?? (item.unit_price * item.quantity)) || 0).toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="text-xs font-bold uppercase text-gray-400 mb-2">Delivery & Notes</h4>
                  <p className="text-xs text-gray-600 mb-1">
                    <strong className="text-gray-700">Address:</strong>{' '}
                    {typeof order.delivery_address === 'string'
                      ? order.delivery_address
                      : order.delivery_address_text ||
                        (order.delivery_address
                          ? `${order.delivery_address.address_line1 || ''}, ${order.delivery_address.city || ''} ${order.delivery_address.postal_code || ''}`.trim()
                          : 'Standard Delivery')}
                  </p>
                  {order.special_instructions && (
                    <div className="p-2.5 bg-amber-50 rounded-xl border border-amber-200/60 text-xs text-amber-800">
                      <strong>Cooking Note:</strong> {order.special_instructions}
                    </div>
                  )}
                  {order.rejection_reason && (
                    <div className="p-2.5 bg-red-50 rounded-xl border border-red-200 text-xs text-red-800 mt-2">
                      <strong>Rejection Reason:</strong> {order.rejection_reason}
                    </div>
                  )}

                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={() => handleViewRoute(order.id)}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-[#166534] hover:text-emerald-800 transition"
                    >
                      <Navigation className="w-3.5 h-3.5" />
                      <span>View Delivery Route Map</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Action Buttons based on Order State */}
              <div className="pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2.5">
                <div>
                  <button
                    onClick={() => handleViewRoute(order.id)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
                      order.status === 'OUT_FOR_DELIVERY'
                        ? 'bg-orange-600 hover:bg-orange-700 text-white shadow-xs ring-2 ring-orange-500/20'
                        : 'bg-white hover:bg-gray-50 border border-gray-200 text-gray-700'
                    }`}
                  >
                    <Navigation className="w-3.5 h-3.5 text-current" />
                    <span>{order.status === 'OUT_FOR_DELIVERY' ? 'Active Delivery Route' : 'View Delivery Route'}</span>
                  </button>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* When order is placed / payment confirmed -> Accept or Reject */}
                  {(order.status === 'PAYMENT_CONFIRMED' || order.status === 'ORDER_PLACED') && (
                    <>
                      <button
                        onClick={() => setRejectingOrderId(order.id)}
                        disabled={actionLoading === order.id}
                        className="px-4 py-2 border border-red-200 text-red-600 rounded-xl text-xs font-bold hover:bg-red-50 transition-colors flex items-center space-x-1.5"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Reject Order</span>
                      </button>
                      <button
                        onClick={() => handleAccept(order.id)}
                        disabled={actionLoading === order.id}
                        className="px-5 py-2 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5 shadow-xs"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>{actionLoading === order.id ? 'Accepting...' : 'Accept Order'}</span>
                      </button>
                    </>
                  )}

                  {/* When order is Accepted -> Transition to Preparing */}
                  {order.status === 'KITCHEN_ACCEPTED' && (
                    <button
                      onClick={() => handleTransition(order.id, 'PREPARING')}
                      disabled={actionLoading === order.id}
                      className="px-5 py-2 bg-[#F97316] hover:bg-orange-600 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5 shadow-xs"
                    >
                      <ChefHat className="w-4 h-4" />
                      <span>{actionLoading === order.id ? 'Updating...' : 'Start Preparing'}</span>
                    </button>
                  )}

                  {/* When order is Preparing -> Transition to Ready */}
                  {order.status === 'PREPARING' && (
                    <button
                      onClick={() => handleTransition(order.id, 'READY')}
                      disabled={actionLoading === order.id}
                      className="px-5 py-2 bg-[#166534] hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5 shadow-xs"
                    >
                      <BellRing className="w-4 h-4" />
                      <span>{actionLoading === order.id ? 'Updating...' : 'Mark Food Ready'}</span>
                    </button>
                  )}

                  {/* When order is Ready -> Ready for delivery dispatch */}
                  {order.status === 'READY' && (
                    <button
                      onClick={() => handleTransition(order.id, 'DELIVERED')}
                      disabled={actionLoading === order.id}
                      className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>{actionLoading === order.id ? 'Updating...' : 'Complete Delivery'}</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Reject Modal */}
      {rejectingOrderId && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Reject Order</h3>
            <p className="text-sm text-gray-500">
              Please enter a reason for rejecting this order (e.g. ingredient out of stock, kitchen overloaded).
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Out of stock for requested ingredients"
              rows={3}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-red-500"
            />
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                onClick={() => {
                  setRejectingOrderId(null);
                  setRejectionReason('');
                }}
                className="px-4 py-2 border border-gray-200 text-gray-600 rounded-xl text-sm font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRejectConfirm}
                disabled={actionLoading === rejectingOrderId}
                className="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-bold hover:bg-red-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delivery Route Map Modal */}
      {routeModalOpen && (
        <DeliveryRouteMapModal
          routeData={selectedRouteData}
          loading={routeLoading}
          onRetry={routeOrderId ? () => handleViewRoute(routeOrderId) : undefined}
          onClose={() => {
            setRouteModalOpen(false);
            setSelectedRouteData(null);
            setRouteOrderId(null);
          }}
        />
      )}
    </div>
  );
}
