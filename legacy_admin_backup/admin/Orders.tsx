/**
 * Admin Orders Page
 */

import { useState, useEffect } from 'react';
import { adminApi, Order } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [statusFilter, setStatusFilter] = useState('');

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

  useEffect(() => {
    fetchOrders();
  }, [skip, statusFilter]);

  const columns = [
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
      render: (order: Order) => `$${order.total_amount.toFixed(2)}`,
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
        <Badge variant={order.payment.status === 'COMPLETED' ? 'success' : 'warning'}>
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

  if (loading && orders.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchOrders} />;
  }

  return (
    <div>
      <PageHeader title="Orders" description="View and manage all orders" />

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
              { value: 'DELIVERED', label: 'Delivered' },
              { value: 'CANCELLED', label: 'Cancelled' },
            ]}
            placeholder="All Statuses"
          />
        </div>

        <DataTable columns={columns} data={orders} keyExtractor={(o) => o.id} emptyMessage="No orders found" />

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
