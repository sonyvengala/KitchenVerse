/**
 * Admin Audit Logs Page
 */

import { useState, useEffect } from 'react';
import { adminApi, AuditLog } from '../../services/adminApi';
import { DataTable, Pagination, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminAuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getAuditLogs({ skip, limit });
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [skip]);

  const columns = [
    {
      key: 'user',
      header: 'Actor',
      render: (log: AuditLog) => log.user ? (
        <div>
          <div className="font-medium">{log.user.first_name} {log.user.last_name}</div>
          <div className="text-xs text-gray-500">{log.user.email}</div>
        </div>
      ) : 'System',
    },
    {
      key: 'action',
      header: 'Action',
      render: (log: AuditLog) => <span className="font-mono text-xs">{log.action}</span>,
    },
    {
      key: 'resource_type',
      header: 'Resource',
      render: (log: AuditLog) => log.resource_type || 'N/A',
    },
    {
      key: 'ip_address',
      header: 'IP Address',
      render: (log: AuditLog) => log.ip_address || 'N/A',
    },
    {
      key: 'details',
      header: 'Details',
      render: (log: AuditLog) => log.details ? (
        <div className="max-w-xs truncate text-xs font-mono">
          {JSON.stringify(log.details).slice(0, 50)}...
        </div>
      ) : 'N/A',
    },
    {
      key: 'created_at',
      header: 'Timestamp',
      render: (log: AuditLog) => new Date(log.created_at).toLocaleString(),
    },
  ];

  if (loading && logs.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchLogs} />;

  return (
    <div>
      <PageHeader title="Audit Logs" description="System activity and security logs" />
      <Card>
        <DataTable columns={columns} data={logs} keyExtractor={(l) => l.id} emptyMessage="No audit logs found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
