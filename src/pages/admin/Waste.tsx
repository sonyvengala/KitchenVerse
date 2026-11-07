/**
 * Admin Waste Management Page
 * Displays platform-wide waste audit records and summary analytics.
 */

import { useState, useEffect } from 'react';
import { adminApi, WasteRecord, Kitchen, WasteSummary } from '../../services/adminApi';
import {
  DataTable,
  Badge,
  Pagination,
  PageHeader,
  Card,
  StatCard,
  LoadingState,
  ErrorState,
} from '../../components/admin/AdminComponents';

export default function AdminWaste() {
  const [wasteRecords, setWasteRecords] = useState<WasteRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<WasteSummary | null>(null);
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [selectedKitchenId, setSelectedKitchenId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  // Load kitchens once for filtering
  useEffect(() => {
    adminApi.getKitchens()
      .then((res) => setKitchens(res.kitchens || []))
      .catch((err) => console.error('Failed to load kitchens for waste filter:', err));
  }, []);

  const fetchWaste = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getWasteRecords({
        skip,
        limit,
        kitchen_id: selectedKitchenId || undefined,
      });
      setWasteRecords(data.waste_records || []);
      setTotal(data.total || 0);
      if (data.summary) {
        setSummary(data.summary);
      }
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to load waste records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWaste();
  }, [skip, selectedKitchenId]);

  const columns = [
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (w: WasteRecord) => (
        <div>
          <div className="font-semibold text-gray-900">
            {w.kitchen?.kitchen_name || w.kitchen_name || 'Unknown Kitchen'}
          </div>
          {w.recorded_by && (
            <div className="text-[11px] text-gray-400">By: {w.recorded_by}</div>
          )}
        </div>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      render: (w: WasteRecord) => {
        const isAuto = w.source_event === 'ORDER_CANCELLATION';
        return (
          <Badge variant={isAuto ? 'warning' : 'default'}>
            {isAuto ? 'Auto Cancellation' : 'Manual Loss'}
          </Badge>
        );
      },
    },
    {
      key: 'item',
      header: 'Ingredient / Dish',
      render: (w: WasteRecord) => {
        if (w.ingredient?.name || (w.ingredient_name && w.ingredient_name !== 'N/A')) {
          return (
            <div>
              <div className="font-medium text-gray-900">
                {w.ingredient?.name || w.ingredient_name}
              </div>
              <div className="text-xs text-gray-500">
                Unit: {w.ingredient?.unit || w.unit || 'units'}
              </div>
            </div>
          );
        }
        if (w.menu_item_name) {
          return (
            <div>
              <div className="font-medium text-gray-900">{w.menu_item_name}</div>
              <div className="text-xs text-amber-700 font-medium">Prepared Item Loss</div>
            </div>
          );
        }
        return <span className="text-gray-400">N/A</span>;
      },
    },
    {
      key: 'quantity',
      header: 'Quantity',
      render: (w: WasteRecord) => (
        <span className="font-mono font-bold text-red-600">
          -{(w.quantity ?? 0).toFixed(2)} {w.unit || ''}
        </span>
      ),
    },
    {
      key: 'cost',
      header: 'Est. Cost',
      render: (w: WasteRecord) => {
        const costVal = w.cost ?? w.estimated_cost;
        const hasCost = costVal !== null && costVal !== undefined && Number(costVal) > 0;
        return hasCost ? (
          <span className="font-mono font-bold text-gray-900">
            ₹{Number(costVal).toFixed(2)}
          </span>
        ) : (
          <span className="text-gray-400 text-[11px] font-normal italic">
            Cost not set
          </span>
        );
      },
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (w: WasteRecord) => (
        <span className="text-gray-700 max-w-xs truncate block" title={w.reason || ''}>
          {w.reason || 'Not specified'}
        </span>
      ),
    },
    {
      key: 'recorded_at',
      header: 'Date & Time',
      render: (w: WasteRecord) => {
        const dt = w.recorded_at || w.created_at;
        return (
          <span className="text-xs text-gray-500 whitespace-nowrap">
            {dt ? new Date(dt).toLocaleString() : 'N/A'}
          </span>
        );
      },
    },
  ];

  if (loading && wasteRecords.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchWaste} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Waste Management"
          description="Platform-wide wastage ledger, recipe-driven cancellation losses, and spoilage analytics"
        />

        {/* Kitchen Filter */}
        <div className="flex items-center space-x-2">
          <label htmlFor="kitchen-filter" className="text-xs font-semibold text-gray-600">
            Filter Kitchen:
          </label>
          <select
            id="kitchen-filter"
            value={selectedKitchenId}
            onChange={(e) => {
              setSelectedKitchenId(e.target.value);
              setSkip(0);
            }}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium focus:ring-orange-500 focus:border-orange-500"
          >
            <option value="">All Kitchens</option>
            {kitchens.map((k) => (
              <option key={k.id} value={k.id}>
                {k.kitchen_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* KPI Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Total Waste Records"
          value={summary?.total_records ?? total}
          icon="🗑️"
          color="bg-red-500"
          subtitle="Audit ledger entries across platform"
        />
        <StatCard
          title="Total Quantity Lost"
          value={`${(summary?.total_quantity ?? 0).toFixed(2)} units`}
          icon="⚖️"
          color="bg-amber-500"
          subtitle="Ingredients & portions wasted"
        />
        <StatCard
          title="Total Wastage Cost"
          value={`₹${(summary?.total_cost ?? 0).toFixed(2)}`}
          icon="💰"
          color="bg-purple-600"
          subtitle="Calculated from real inventory purchases"
        />
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={wasteRecords}
          keyExtractor={(w) => w.id}
          emptyMessage="No waste records found"
        />
        <Pagination
          total={total}
          skip={skip}
          limit={limit}
          onPageChange={setSkip}
        />
      </Card>
    </div>
  );
}
