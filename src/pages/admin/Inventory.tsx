/**
 * Admin Inventory Page
 */

import { useState, useEffect } from 'react';
import { adminApi, InventoryItem } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import { formatINR } from '../../utils/currency';

export default function AdminInventory() {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [stockFilter, setStockFilter] = useState('');

  const fetchInventory = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getInventory({
        skip,
        limit,
        low_stock: stockFilter === 'low' ? true : stockFilter === 'normal' ? false : undefined,
      });
      setInventory(data.inventory);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, [skip, stockFilter]);

  const columns = [
    {
      key: 'ingredient',
      header: 'Ingredient',
      render: (item: any) => {
        const name = item.ingredient?.name || item.ingredient_name || 'Unknown Ingredient';
        const unit = item.ingredient?.unit || item.unit || '';
        return (
          <div>
            <div className="font-medium text-gray-900">{name}</div>
            {unit && <div className="text-xs text-gray-500">{unit}</div>}
          </div>
        );
      },
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (item: any) => item.kitchen?.kitchen_name || item.kitchen_name || 'N/A',
    },
    {
      key: 'quantity_on_hand',
      header: 'Quantity',
      render: (item: any) => {
        const qty = item.quantity_on_hand ?? item.quantity ?? 0;
        const unit = item.ingredient?.unit || item.unit || '';
        return `${Number(qty).toFixed(2)} ${unit}`.trim();
      },
    },
    {
      key: 'min_quantity',
      header: 'Min Stock',
      render: (item: any) => {
        const minQ = item.min_quantity ?? 0;
        return Number(minQ).toFixed(2);
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => {
        const qty = item.quantity_on_hand ?? item.quantity ?? 0;
        const minQ = item.min_quantity ?? 0;
        const isLow = item.status === 'LOW_STOCK' || (minQ > 0 && qty <= minQ);
        return (
          <Badge variant={isLow ? 'danger' : 'success'}>
            {isLow ? 'Low Stock' : 'Available'}
          </Badge>
        );
      },
    },
    {
      key: 'unit_cost',
      header: 'Unit Cost',
      render: (item: any) => {
        const hasCost = item.cost_available && item.unit_cost !== null && item.unit_cost !== undefined;
        const unit = item.ingredient?.unit || item.unit || '';
        return hasCost ? (
          <span className="font-semibold text-gray-900">
            {formatINR(item.unit_cost)}
            {unit && <span className="text-xs text-gray-500 font-normal"> / {unit}</span>}
          </span>
        ) : (
          <span className="text-gray-400 text-xs italic font-normal">Cost not set</span>
        );
      },
    },
    {
      key: 'stock_value',
      header: 'Stock Value',
      render: (item: any) => {
        const hasValue = item.cost_available && item.stock_value !== null && item.stock_value !== undefined;
        return hasValue ? (
          <span className="font-bold text-emerald-800">
            {formatINR(item.stock_value)}
          </span>
        ) : (
          <span className="text-gray-400 text-xs italic font-normal">Cost not set</span>
        );
      },
    },
  ];

  if (loading && inventory.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchInventory} />;

  return (
    <div>
      <PageHeader title="Inventory" description="Monitor stock levels across kitchens" />
      <Card>
        <div className="p-6 border-b border-gray-200">
          <FilterSelect
            value={stockFilter}
            onChange={setStockFilter}
            options={[
              { value: 'low', label: 'Low Stock' },
              { value: 'normal', label: 'Normal Stock' },
            ]}
            placeholder="All Stock Levels"
          />
        </div>
        <DataTable columns={columns} data={inventory} keyExtractor={(i) => i.id} emptyMessage="No inventory records yet." />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
