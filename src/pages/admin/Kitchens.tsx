/**
 * Admin Kitchens & Approvals Page
 * Allows administrators to review onboarding kitchens, approve, reject, or suspend.
 */

import { useState, useEffect } from 'react';
import { adminApi, Kitchen } from '../../services/adminApi';
import { DataTable, Badge, Pagination, SearchInput, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import KitchenMap from '../../components/common/KitchenMap';
import { CheckCircle2, XCircle, Ban, AlertTriangle, LayoutList, Map as MapIcon } from 'lucide-react';

import { useDebounce } from '../../hooks/useDebounce';

export default function AdminKitchens() {
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [viewMode, setViewMode] = useState<'table' | 'map'>('table');

  // Rejection modal
  const [rejectingKitchenId, setRejectingKitchenId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  const fetchKitchens = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getKitchens({ skip, limit, search: debouncedSearch || undefined });
      setKitchens(data.kitchens);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load kitchens');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKitchens();
  }, [skip, debouncedSearch]);

  const handleApprove = async (kitchenId: string) => {
    try {
      await adminApi.approveKitchen(kitchenId);
      setActionMessage('Kitchen successfully approved and activated!');
      setTimeout(() => setActionMessage(null), 4000);
      fetchKitchens();
    } catch (err: any) {
      alert(err.detail || 'Failed to approve kitchen');
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectingKitchenId) return;
    try {
      await adminApi.rejectKitchen(rejectingKitchenId, rejectionReason);
      setActionMessage('Kitchen application rejected.');
      setTimeout(() => setActionMessage(null), 4000);
      setRejectingKitchenId(null);
      setRejectionReason('');
      fetchKitchens();
    } catch (err: any) {
      alert(err.detail || 'Failed to reject kitchen');
    }
  };

  const handleSuspend = async (kitchenId: string) => {
    if (!window.confirm('Are you sure you want to suspend this kitchen?')) return;
    try {
      await adminApi.suspendKitchen(kitchenId);
      setActionMessage('Kitchen has been suspended.');
      setTimeout(() => setActionMessage(null), 4000);
      fetchKitchens();
    } catch (err: any) {
      alert(err.detail || 'Failed to suspend kitchen');
    }
  };

  const columns = [
    {
      key: 'kitchen_name',
      header: 'Kitchen Name',
      render: (kitchen: Kitchen & any) => (
        <div>
          <div className="font-semibold text-gray-900">{kitchen.kitchen_name}</div>
          <div className="text-xs text-gray-500">{kitchen.city} • {kitchen.address}</div>
          {kitchen.rejection_reason && (
            <div className="text-xs text-red-600 mt-0.5">Reason: {kitchen.rejection_reason}</div>
          )}
        </div>
      ),
    },
    {
      key: 'owner',
      header: 'Kitchen Owner',
      render: (kitchen: Kitchen) => kitchen.owner ? (
        <div>
          <div className="font-medium text-gray-800">{kitchen.owner.first_name} {kitchen.owner.last_name}</div>
          <div className="text-xs text-gray-500">{kitchen.owner.email}</div>
        </div>
      ) : 'N/A',
    },
    {
      key: 'approval_status',
      header: 'Approval Status',
      render: (kitchen: any) => {
        const st = kitchen.approval_status || (kitchen.is_approved ? 'APPROVED' : 'PENDING_APPROVAL');
        if (st === 'APPROVED') {
          return <Badge variant="success">Approved</Badge>;
        } else if (st === 'PENDING_APPROVAL') {
          return <Badge variant="warning">Pending Approval</Badge>;
        } else if (st === 'EMAIL_UNVERIFIED') {
          return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">Email Unverified</span>;
        } else if (st === 'REJECTED') {
          return <Badge variant="danger">Rejected</Badge>;
        } else if (st === 'SUSPENDED') {
          return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-700">Suspended</span>;
        }
        return <Badge variant="info">{st}</Badge>;
      },
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (kitchen: Kitchen) => kitchen.rating ? `${kitchen.rating.toFixed(1)} ⭐` : 'N/A',
    },
    {
      key: 'created_at',
      header: 'Registered',
      render: (kitchen: Kitchen) => new Date(kitchen.created_at).toLocaleDateString(),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (kitchen: any) => {
        const isApproved = kitchen.approval_status === 'APPROVED' || kitchen.is_approved;
        return (
          <div className="flex items-center gap-2">
            {!isApproved ? (
              <button
                onClick={() => handleApprove(kitchen.id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-2xs"
                title="Approve Kitchen"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
            ) : (
              <button
                onClick={() => handleSuspend(kitchen.id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-2xs"
                title="Suspend Kitchen"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>Suspend</span>
              </button>
            )}
            {kitchen.approval_status !== 'REJECTED' && (
              <button
                onClick={() => {
                  setRejectingKitchenId(kitchen.id);
                  setRejectionReason('');
                }}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-2xs"
                title="Reject Kitchen"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            )}
          </div>
        );
      },
    },
  ];

  if (loading && kitchens.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchKitchens} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          title="Kitchen Approvals & Directory"
          description="Review kitchen owner onboarding applications, approve accounts, or manage operations."
        />
        <div className="flex items-center gap-1 bg-gray-100 p-1.5 rounded-xl border border-gray-200 self-start sm:self-auto shrink-0">
          <button
            onClick={() => setViewMode('table')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              viewMode === 'table'
                ? 'bg-white text-gray-900 shadow-xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <LayoutList className="w-3.5 h-3.5" />
            <span>Table View</span>
          </button>
          <button
            onClick={() => setViewMode('map')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              viewMode === 'map'
                ? 'bg-emerald-700 text-white shadow-xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <MapIcon className="w-3.5 h-3.5" />
            <span>Map View ({kitchens.length})</span>
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm font-medium animate-fade-in">
          {actionMessage}
        </div>
      )}

      {viewMode === 'map' ? (
        <Card>
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <span className="text-xs font-bold text-gray-600 uppercase tracking-wider">
              Geographic Kitchen Network Map
            </span>
            <span className="text-xs text-gray-400">
              Markers are color-coded by approval status (Green: Approved, Amber: Pending, Red: Suspended)
            </span>
          </div>
          <div className="p-4">
            <KitchenMap
              kitchens={kitchens}
              height="580px"
            />
          </div>
        </Card>
      ) : (
        <Card>
          <div className="p-6 border-b border-gray-200">
            <SearchInput value={search} onChange={setSearch} placeholder="Search kitchens by name or city..." />
          </div>

          <DataTable columns={columns} data={kitchens} keyExtractor={(k) => k.id} emptyMessage="No kitchens found" />

          <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
        </Card>
      )}

      {/* Reject Modal */}
      {rejectingKitchenId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-3 text-rose-600">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-lg font-bold text-gray-900">Reject Kitchen Application</h3>
            </div>
            <p className="text-sm text-gray-600">
              Provide a reason for rejecting this kitchen application. The kitchen owner will receive a notification with this message.
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Incomplete address verification or kitchen safety documents required."
              className="w-full h-24 p-3 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-rose-500 focus:outline-hidden"
            />
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setRejectingKitchenId(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="px-4 py-2 text-sm font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
