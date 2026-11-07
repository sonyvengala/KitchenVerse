/**
 * Admin Payments Page
 */

import { useState, useEffect } from 'react';
import { adminApi, Payment } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminPayments() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [statusFilter, setStatusFilter] = useState('');

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

  const columns = [
    { key: 'id', header: 'Payment ID', render: (p: Payment) => <span className="font-mono text-xs">{p.id.slice(0, 8)}</span> },
    { key: 'amount', header: 'Amount', render: (p: Payment) => `$${p.amount.toFixed(2)}` },
    { key: 'payment_method', header: 'Method', render: (p: Payment) => p.payment_method || 'N/A' },
    {
      key: 'status',
      header: 'Status',
      render: (p: Payment) => (
        <Badge variant={p.status === 'COMPLETED' ? 'success' : p.status === 'FAILED' ? 'danger' : 'warning'}>
          {p.status}
        </Badge>
      ),
    },
    { key: 'paid_at', header: 'Paid At', render: (p: Payment) => p.paid_at ? new Date(p.paid_at).toLocaleString() : 'N/A' },
    { key: 'created_at', header: 'Created', render: (p: Payment) => new Date(p.created_at).toLocaleDateString() },
  ];

  if (loading && payments.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchPayments} />;

  return (
    <div>
      <PageHeader title="Payments" description="View all payment transactions" />
      <Card>
        <div className="p-6 border-b border-gray-200">
          <FilterSelect
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'PENDING', label: 'Pending' },
              { value: 'COMPLETED', label: 'Completed' },
              { value: 'FAILED', label: 'Failed' },
              { value: 'REFUNDED', label: 'Refunded' },
            ]}
            placeholder="All Statuses"
          />
        </div>
        <DataTable columns={columns} data={payments} keyExtractor={(p) => p.id} emptyMessage="No payments found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
