/**
 * Admin Payments Page
 * Displays payments with verified Indian Rupee (INR) formatting and audit preservation.
 */

import { useState, useEffect } from 'react';
import { adminApi, Payment } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import { formatINR } from '../../utils/currency';
import { ShieldCheck, AlertCircle, CheckCircle2, Archive } from 'lucide-react';

export default function AdminPayments() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [statusFilter, setStatusFilter] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Archive confirmation modal state
  const [archiveTarget, setArchiveTarget] = useState<Payment | null>(null);
  const [archiving, setArchiving] = useState(false);

  const fetchPayments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getPayments({ skip, limit, status: statusFilter || undefined });
      setPayments(data.payments);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load payments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, [skip, statusFilter]);

  const handleConfirmArchive = async () => {
    if (!archiveTarget) return;
    try {
      setArchiving(true);
      setActionError(null);
      const res = await adminApi.archivePayment(archiveTarget.id);
      setActionSuccess(res.message || `Payment #${archiveTarget.id.slice(0, 8)} archived with audit preservation.`);
      setTimeout(() => setActionSuccess(null), 5000);
      setArchiveTarget(null);
      fetchPayments();
    } catch (err: any) {
      setActionError(err.detail || 'Failed to archive payment transaction');
      setTimeout(() => setActionError(null), 6000);
    } finally {
      setArchiving(false);
    }
  };

  const columns = [
    {
      key: 'id',
      header: 'Payment ID',
      render: (p: Payment) => (
        <span className="font-mono text-xs font-semibold text-gray-700" title={p.id}>
          #{p.id.slice(0, 8)}
        </span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount (INR)',
      render: (p: Payment) => (
        <span className="font-bold text-gray-900 text-sm">
          {formatINR(p.amount)}
        </span>
      ),
    },
    {
      key: 'payment_method',
      header: 'Method',
      render: (p: Payment) => (
        <span className="text-xs font-medium text-gray-600">
          {p.payment_method || 'COD'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (p: Payment) => {
        const isSuccess = p.status === 'COMPLETED' || p.status === 'SUCCESS';
        return (
          <Badge variant={isSuccess ? 'success' : p.status === 'FAILED' ? 'danger' : 'warning'}>
            {p.status}
          </Badge>
        );
      },
    },
    {
      key: 'paid_at',
      header: 'Paid At',
      render: (p: Payment) => (
        <span className="text-xs text-gray-500">
          {p.paid_at ? new Date(p.paid_at).toLocaleString('en-IN') : 'N/A'}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (p: Payment) => (
        <span className="text-xs text-gray-500">
          {new Date(p.created_at).toLocaleDateString('en-IN')}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Audit & Actions',
      render: (p: Payment) => {
        const isCompleted = p.status === 'COMPLETED' || p.status === 'SUCCESS';
        if (isCompleted) {
          return (
            <span
              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 select-none"
              title="Completed transaction is immutable and preserved in ledger for financial auditing"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Auditable Ledger</span>
            </span>
          );
        }

        return (
          <button
            onClick={() => setArchiveTarget(p)}
            className="inline-flex items-center space-x-1 text-xs text-amber-700 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 border border-amber-200 px-2.5 py-1 rounded-md transition font-medium"
            title="Archive non-completed payment from active view with full audit log"
          >
            <Archive className="w-3.5 h-3.5" />
            <span>Archive</span>
          </button>
        );
      },
    },
  ];

  if (loading && payments.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchPayments} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payments"
        description="Monitor platform payment transactions — all amounts verified in Indian Rupees (₹) with permanent financial auditing."
      />

      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-[#166534] rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      <Card>
        <div className="p-6 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <FilterSelect
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'PENDING', label: 'Pending' },
              { value: 'COMPLETED', label: 'Completed' },
              { value: 'SUCCESS', label: 'Success' },
              { value: 'FAILED', label: 'Failed' },
              { value: 'REFUNDED', label: 'Refunded' },
            ]}
            placeholder="All Payment Statuses"
          />

          <div className="text-xs text-gray-500 flex items-center space-x-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Financial Integrity: Completed payments cannot be permanently deleted</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <DataTable
            columns={columns}
            data={payments}
            keyExtractor={(p) => p.id}
            emptyMessage="No payment transactions found."
          />
        </div>

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>

      {/* Archive Confirmation Modal */}
      {archiveTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-start space-x-3 mb-4">
              <div className="p-2 bg-amber-100 text-amber-700 rounded-xl">
                <Archive className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900">Archive Payment Transaction</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  ID: <span className="font-mono text-gray-700">#{archiveTarget.id.slice(0, 8)}</span> • Amount: <span className="font-bold text-gray-900">{formatINR(archiveTarget.amount)}</span>
                </p>
              </div>
            </div>

            <p className="text-xs text-gray-600 leading-relaxed mb-6">
              This action will archive the transaction from active view. A permanent audit log entry will be created, and all financial ledger data will remain intact for reporting.
            </p>

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={() => setArchiveTarget(null)}
                disabled={archiving}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmArchive}
                disabled={archiving}
                className="px-4 py-2 bg-amber-600 text-white rounded-xl text-xs font-bold hover:bg-amber-700 transition flex items-center space-x-1.5"
              >
                {archiving && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                <span>{archiving ? 'Archiving...' : 'Confirm Archive'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
