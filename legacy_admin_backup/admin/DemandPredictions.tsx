/**
 * Admin Demand Predictions Page
 */

import { useState, useEffect } from 'react';
import { adminApi, DemandPrediction } from '../../services/adminApi';
import { DataTable, Pagination, PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../../components/admin/AdminComponents';

export default function AdminDemandPredictions() {
  const [predictions, setPredictions] = useState<DemandPrediction[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  const fetchPredictions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getDemandPredictions({ skip, limit });
      setPredictions(data.predictions);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load demand predictions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPredictions();
  }, [skip]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchPredictions} />;

  // If no predictions exist, show message about forecasting engine
  if (total === 0) {
    return (
      <div>
        <PageHeader title="Demand Predictions" description="ML-powered demand forecasting" />
        <Card>
          <EmptyState
            icon="🔮"
            title="Forecasting engine not yet configured"
            description="The demand forecasting engine has not been set up yet. Once configured, predictions will appear here."
          />
        </Card>
      </div>
    );
  }

  const columns = [
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (p: DemandPrediction) => p.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'menu_item',
      header: 'Menu Item',
      render: (p: DemandPrediction) => p.menu_item?.name || 'N/A',
    },
    {
      key: 'prediction_date',
      header: 'Prediction Date',
      render: (p: DemandPrediction) => new Date(p.prediction_date).toLocaleDateString(),
    },
    {
      key: 'predicted_demand',
      header: 'Predicted Demand',
      render: (p: DemandPrediction) => p.predicted_demand.toFixed(2),
    },
    {
      key: 'confidence_score',
      header: 'Confidence',
      render: (p: DemandPrediction) => p.confidence_score ? `${(p.confidence_score * 100).toFixed(1)}%` : 'N/A',
    },
    {
      key: 'model_version',
      header: 'Model',
      render: (p: DemandPrediction) => p.model_version || 'N/A',
    },
  ];

  return (
    <div>
      <PageHeader title="Demand Predictions" description="ML-powered demand forecasting" />
      <Card>
        <DataTable columns={columns} data={predictions} keyExtractor={(p) => p.id} emptyMessage="No predictions found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
