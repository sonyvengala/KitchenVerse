/**
 * Admin Orders Page
 * Orders management and Admin-Assisted Cancellation workflow
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { adminApi, Order, AdminCancellationRequest } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import { AlertCircle, CheckCircle2, Clock, Ban, X } from 'lucide-react';
import { formatINR } from '../../utils/currency';

import { useRealtime } from '../../context/RealtimeContext';

export default function AdminOrders() {
  const { subscribe } = useRealtime();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') === 'cancellations' ? 'cancellations' : 'orders';
  const [activeTab, setActiveTab] = useState<'orders' | 'cancellations'>(initialTab);

  // Orders State
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [statusFilter, setStatusFilter] = useState('');

  // Cancellation Requests State
  const [cancellationRequests, setCancellationRequests] = useState<AdminCancellationRequest[]>([]);
  const [crLoading, setCrLoading] = useState(false);
  const [crError, setCrError] = useState<string | null>(null);
  const [crFilter, setCrFilter] = useState<string>('ALL');

  // Modals State
  const [approveTarget, setApproveTarget] = useState<AdminCancellationRequest | null>(null);
  const [approveNote, setApproveNote] = useState('');
  const [approving, setApproving] = useState(false);

  const [rejectTarget, setRejectTarget] = useState<AdminCancellationRequest | null>(null);
  const [rejectNote, setRejectNote] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getOrders({ skip, limit, status: statusFilter || undefined });
      setOrders(data.orders);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  };

  const fetchCancellationRequests = async () => {
    try {
      setCrLoading(true);
      setCrError(null);
      const data = await adminApi.getCancellationRequests(crFilter === 'ALL' ? undefined : crFilter);
      setCancellationRequests(data);
    } catch (err: any) {
      setCrError(err.detail || 'Failed to load cancellation requests');
    } finally {
      setCrLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'orders') {
      fetchOrders();
    }
  }, [skip, statusFilter, activeTab]);

  useEffect(() => {
    if (activeTab === 'cancellations') {
      fetchCancellationRequests();
    }
  }, [crFilter, activeTab]);

  // Real-time updates for admin order events
  useEffect(() => {
    const unsubCreated = subscribe('ORDER_CREATED', () => {
      if (activeTab === 'orders') fetchOrders();
    });
    const unsubStatus = subscribe('ORDER_STATUS_CHANGED', () => {
      if (activeTab === 'orders') fetchOrders();
      if (activeTab === 'cancellations') fetchCancellationRequests();
    });
    return () => {
      unsubCreated();
      unsubStatus();
    };
  }, [subscribe, activeTab]);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'cancellations') {
      setActiveTab('cancellations');
    } else {
      setActiveTab('orders');
    }
  }, [searchParams]);

  const handleTabChange = (tab: 'orders' | 'cancellations') => {
    setActiveTab(tab);
    setSearchParams(tab === 'cancellations' ? { tab: 'cancellations' } : {});
  };

  const handleApprove = async () => {
    if (!approveTarget) return;
    setApproving(true);
    try {
      await adminApi.approveCancellationRequest(approveTarget.id, approveNote.trim() || undefined);
      setActionSuccessMsg(`Cancellation approved for Order #${approveTarget.order_number || approveTarget.order_id.slice(0, 8)}. Food wastage recorded.`);
      setApproveTarget(null);
      setApproveNote('');
      setTimeout(() => setActionSuccessMsg(null), 4000);
      await fetchCancellationRequests();
      await fetchOrders();
    } catch (err: any) {
      alert(err.detail || 'Failed to approve cancellation.');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectTarget || !rejectNote.trim()) return;
    setRejecting(true);
    try {
      await adminApi.rejectCancellationRequest(rejectTarget.id, rejectNote.trim());
      setActionSuccessMsg(`Cancellation rejected for Order #${rejectTarget.order_number || rejectTarget.order_id.slice(0, 8)}. Order remains READY.`);
      setRejectTarget(null);
      setRejectNote('');
      setTimeout(() => setActionSuccessMsg(null), 4000);
      await fetchCancellationRequests();
      await fetchOrders();
    } catch (err: any) {
      alert(err.detail || 'Failed to reject cancellation.');
    } finally {
      setRejecting(false);
    }
  };

  const pendingCount = cancellationRequests.filter((r) => r.status === 'PENDING').length;

  const orderColumns = [
    {
      key: 'id',
      header: 'Order ID',
      render: (order: Order) => <span className="font-mono text-xs">{order.id.slice(0, 8)}</span>,
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (order: Order) => order.customer ? `${order.customer.first_name} ${order.customer.last_name}` : 'N/A',
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (order: Order) => order.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'total_amount',
      header: 'Amount',
      render: (order: Order) => <span className="font-semibold text-gray-900">{formatINR(order.total_amount)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (order: Order) => (
        <Badge variant={
          order.status === 'DELIVERED' ? 'success' :
          order.status === 'CANCELLED' ? 'danger' :
          order.status === 'PENDING' ? 'warning' : 'info'
        }>
          {order.status}
        </Badge>
      ),
    },
    {
      key: 'payment',
      header: 'Payment',
      render: (order: Order) => order.payment ? (
        <Badge variant={order.payment.status === 'COMPLETED' || order.payment.status === 'SUCCESS' ? 'success' : 'warning'}>
          {order.payment.status}
        </Badge>
      ) : 'N/A',
    },
    {
      key: 'ordered_at',
      header: 'Date',
      render: (order: Order) => new Date(order.ordered_at).toLocaleDateString(),
    },
  ];

  const cancellationColumns = [
    {
      key: 'order_id',
      header: 'Order ID',
      render: (cr: AdminCancellationRequest) => (
        <div>
          <span className="font-mono text-xs font-bold text-gray-900">
            #{cr.order_number || cr.order_id.slice(0, 8).toUpperCase()}
          </span>
          {cr.order_total && (
            <span className="block text-[10px] text-gray-500">₹{cr.order_total.toFixed(2)}</span>
          )}
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (cr: AdminCancellationRequest) => (
        <div>
          <span className="font-semibold text-xs text-gray-900">{cr.customer_name || 'Customer'}</span>
          {cr.customer_email && <span className="block text-[10px] text-gray-400">{cr.customer_email}</span>}
        </div>
      ),
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (cr: AdminCancellationRequest) => (
        <span className="text-xs text-gray-700 font-medium">{cr.kitchen_name || 'Kitchen'}</span>
      ),
    },
    {
      key: 'requested_at',
      header: 'Requested At',
      render: (cr: AdminCancellationRequest) => (
        <span className="text-xs text-gray-500 whitespace-nowrap">
          {new Date(cr.requested_at || cr.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (cr: AdminCancellationRequest) => (
        <span className="inline-block px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 text-xs font-medium">
          {cr.reason || 'Not specified'}
        </span>
      ),
    },
    {
      key: 'customer_note',
      header: 'Customer Note',
      render: (cr: AdminCancellationRequest) => (
        <span className="text-xs text-gray-600 italic max-w-xs block truncate" title={cr.customer_note || undefined}>
          {cr.customer_note || '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (cr: AdminCancellationRequest) => (
        <Badge variant={
          cr.status === 'APPROVED' ? 'success' :
          cr.status === 'REJECTED' ? 'danger' : 'warning'
        }>
          {cr.status}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (cr: AdminCancellationRequest) => {
        if (cr.status === 'PENDING') {
          return (
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setApproveTarget(cr);
                  setApproveNote('');
                }}
                className="px-2.5 py-1 text-[11px] font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-md transition shadow-2xs whitespace-nowrap"
              >
                Approve Cancellation
              </button>
              <button
                onClick={() => {
                  setRejectTarget(cr);
                  setRejectNote('');
                }}
                className="px-2.5 py-1 text-[11px] font-bold bg-red-600 hover:bg-red-700 text-white rounded-md transition shadow-2xs whitespace-nowrap"
              >
                Reject Cancellation
              </button>
            </div>
          );
        }
        return (
          <div className="text-[11px] text-gray-500 max-w-xs">
            <span className="font-semibold text-gray-700">Reviewed</span>
            {cr.admin_note && <p className="italic text-gray-600 truncate" title={cr.admin_note}>Note: {cr.admin_note}</p>}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Orders & Cancellations" description="View orders and review admin-assisted cancellation requests" />

      {/* Action Notification Banner */}
      {actionSuccessMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span className="font-bold">{actionSuccessMsg}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-gray-200">
        <button
          onClick={() => handleTabChange('orders')}
          className={`px-4 py-2.5 text-xs font-bold border-b-2 transition flex items-center gap-1.5 ${
            activeTab === 'orders'
              ? 'border-orange-500 text-orange-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          All Orders ({total})
        </button>
        <button
          onClick={() => handleTabChange('cancellations')}
          className={`px-4 py-2.5 text-xs font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'cancellations'
              ? 'border-orange-500 text-orange-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <span>Cancellation Requests</span>
          {pendingCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-white">
              {pendingCount} Pending
            </span>
          )}
        </button>
      </div>

      {/* Tab: All Orders */}
      {activeTab === 'orders' && (
        <Card>
          <div className="p-6 border-b border-gray-200">
            <FilterSelect
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'PENDING', label: 'Pending' },
                { value: 'CONFIRMED', label: 'Confirmed' },
                { value: 'PREPARING', label: 'Preparing' },
                { value: 'READY', label: 'Ready' },
                { value: 'OUT_FOR_DELIVERY', label: 'Out for Delivery' },
                { value: 'DELIVERED', label: 'Delivered' },
                { value: 'CANCELLED', label: 'Cancelled' },
              ]}
              placeholder="All Statuses"
            />
          </div>

          {loading && orders.length === 0 ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={fetchOrders} />
          ) : (
            <>
              <DataTable columns={orderColumns} data={orders} keyExtractor={(o) => o.id} emptyMessage="No orders found." />
              <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
            </>
          )}
        </Card>
      )}

      {/* Tab: Cancellation Requests */}
      {activeTab === 'cancellations' && (
        <Card>
          <div className="p-6 border-b border-gray-200 flex flex-wrap items-center justify-between gap-4">
            <div className="w-64">
              <FilterSelect
                value={crFilter}
                onChange={setCrFilter}
                options={[
                  { value: 'ALL', label: 'All Requests' },
                  { value: 'PENDING', label: 'Pending Only' },
                  { value: 'APPROVED', label: 'Approved Only' },
                  { value: 'REJECTED', label: 'Rejected Only' },
                ]}
                placeholder="Filter by Status"
              />
            </div>
            <button
              onClick={fetchCancellationRequests}
              className="text-xs font-bold text-gray-600 hover:text-gray-900 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              Refresh Requests
            </button>
          </div>

          {crLoading && cancellationRequests.length === 0 ? (
            <LoadingState />
          ) : crError ? (
            <ErrorState message={crError} onRetry={fetchCancellationRequests} />
          ) : (
            <DataTable
              columns={cancellationColumns}
              data={cancellationRequests}
              keyExtractor={(cr) => cr.id}
              emptyMessage="No cancellation requests found."
            />
          )}
        </Card>
      )}

      {/* Approve Modal */}
      {approveTarget && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-black text-gray-900">Approve cancellation?</h3>
              </div>
              <button
                onClick={() => setApproveTarget(null)}
                className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-amber-50 border border-amber-200 text-amber-800 p-3.5 rounded-xl text-xs space-y-1">
              <p className="font-bold">This order is already prepared.</p>
              <p className="text-amber-700">Approving will cancel the order and record the prepared food as wastage.</p>
            </div>

            <div className="text-xs text-gray-600 space-y-1">
              <p><span className="font-semibold text-gray-800">Order:</span> #{approveTarget.order_number || approveTarget.order_id.slice(0, 8)}</p>
              <p><span className="font-semibold text-gray-800">Customer:</span> {approveTarget.customer_name || 'Customer'}</p>
              <p><span className="font-semibold text-gray-800">Reason:</span> {approveTarget.reason || 'None'}</p>
              {approveTarget.customer_note && <p><span className="font-semibold text-gray-800">Note:</span> {approveTarget.customer_note}</p>}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-700">Admin Note (optional)</label>
              <input
                type="text"
                value={approveNote}
                onChange={(e) => setApproveNote(e.target.value)}
                placeholder="Optional approval note..."
                className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex gap-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setApproveTarget(null)}
                className="flex-1 py-2 text-xs font-bold text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={approving}
                className="flex-1 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl disabled:opacity-50"
              >
                {approving ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {rejectTarget && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <Ban className="w-5 h-5 text-red-600" />
                <h3 className="text-base font-black text-gray-900">Reject Cancellation Request</h3>
              </div>
              <button
                onClick={() => setRejectTarget(null)}
                className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-gray-500">
              Order remains READY. Please provide a reason for the rejection (required). The customer will be notified with this reason.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-700">Rejection Reason *</label>
              <textarea
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                placeholder="Explain why the cancellation request cannot be granted..."
                rows={3}
                className="w-full text-xs p-2.5 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
              />
            </div>

            <div className="flex gap-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setRejectTarget(null)}
                className="flex-1 py-2 text-xs font-bold text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={rejecting || !rejectNote.trim()}
                className="flex-1 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl disabled:opacity-50"
              >
                {rejecting ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
