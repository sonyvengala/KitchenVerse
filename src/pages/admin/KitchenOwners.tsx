/**
 * Admin Kitchen Owners Page
 * Real kitchen owner account approvals, rejection workflow, safe removal/archival, and status monitoring.
 */

import { useState, useEffect, useMemo } from 'react';
import { adminApi } from '../../services/adminApi';
import apiClient from '../../lib/api';
import {
  DataTable,
  Badge,
  Pagination,
  SearchInput,
  FilterSelect,
  PageHeader,
  Card,
  LoadingState,
  ErrorState,
} from '../../components/admin/AdminComponents';
import { CheckCircle2, XCircle, Eye, X, Store, AlertCircle, Trash2, ShieldAlert, ShieldCheck, FileText, AlertTriangle, ExternalLink, Sparkles, Filter, RefreshCw, FileCheck } from 'lucide-react';
import { LicenseStatusBadge } from '../../components/license/LicenseStatusBadge';
import { useDebounce } from '../../hooks/useDebounce';
import { useRealtime } from '../../context/RealtimeContext';

export const PROTECTED_OWNER_EMAILS = new Set<string>();

export const isOwnerProtected = (owner: any): boolean => {
  if (!owner) return false;
  // Account is genuinely protected ONLY when marked by backend with a documented system protection rule
  if (owner.is_protected === true && owner.protection_reason) return true;
  const email = (owner.email || owner.owner?.email || '').trim().toLowerCase();
  if (email === 'admin@cloudkitchen.com') return true;
  return false;
};

export default function AdminKitchenOwners() {
  const [owners, setOwners] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [statusFilter, setStatusFilter] = useState('');
  const [licenseFilter, setLicenseFilter] = useState('');
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Rejection modal
  const [rejectingKitchenId, setRejectingKitchenId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  // Removal modal
  const [removingTarget, setRemovingTarget] = useState<any | null>(null);
  const [removing, setRemoving] = useState(false);

  // Batch Removal modal & selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchRemoving, setBatchRemoving] = useState(false);

  // View detail modal
  const [selectedOwner, setSelectedOwner] = useState<any | null>(null);

  // OCR & License Inspection modal
  const [inspectLicenseKitchen, setInspectLicenseKitchen] = useState<any | null>(null);

  // License Action Modals
  const [licenseActionKitchen, setLicenseActionKitchen] = useState<any | null>(null);
  const [licenseActionMode, setLicenseActionMode] = useState<'verify' | 'correct' | 'reject' | null>(null);
  const [licenseActionReason, setLicenseActionReason] = useState('');
  const [licenseActionNotes, setLicenseActionNotes] = useState('');
  const [licenseActionSubmitting, setLicenseActionSubmitting] = useState(false);

  const fetchOwners = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getKitchenOwners({
        skip,
        limit,
        search: debouncedSearch || undefined,
        status: statusFilter || undefined,
      });
      setOwners(data.kitchens || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.detail || 'Failed to load kitchen owners');
    } finally {
      setLoading(false);
    }
  };

  const filteredOwners = useMemo(() => {
    if (!licenseFilter) return owners;
    return owners.filter((owner) => {
      const lic = owner.license;
      if (licenseFilter === 'DUPLICATE') {
        return Boolean(lic?.duplicate_flag || lic?.is_duplicate_flagged);
      }
      if (licenseFilter === 'PENDING_REVIEW') {
        return !lic || lic.status === 'PENDING_REVIEW' || lic.status === 'PENDING';
      }
      return lic?.status === licenseFilter;
    });
  }, [owners, licenseFilter]);

  const { subscribe } = useRealtime();

  useEffect(() => {
    fetchOwners();

    const unsubApproval = subscribe('KITCHEN_APPROVAL_UPDATED', () => {
      fetchOwners();
    });
    const unsubLicense = subscribe('LICENSE_STATUS_UPDATED', () => {
      fetchOwners();
    });

    return () => {
      unsubApproval();
      unsubLicense();
    };
  }, [skip, debouncedSearch, statusFilter, subscribe]);

  const handleApprove = async (kitchenId: string) => {
    try {
      setActionError(null);
      await adminApi.approveKitchenOwner(kitchenId);
      setActionMessage('Kitchen owner successfully approved!');
      setTimeout(() => setActionMessage(null), 4000);
      fetchOwners();
    } catch (err: any) {
      setActionError(err?.detail || 'Failed to approve kitchen owner');
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectingKitchenId) return;
    try {
      setActionError(null);
      await adminApi.rejectKitchenOwner(rejectingKitchenId, rejectionReason);
      setActionMessage('Kitchen owner application rejected.');
      setTimeout(() => setActionMessage(null), 4000);
      setRejectingKitchenId(null);
      setRejectionReason('');
      fetchOwners();
    } catch (err: any) {
      setActionError(err?.detail || 'Failed to reject kitchen owner');
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleConfirmRemove = async () => {
    if (!removingTarget) return;
    if (isOwnerProtected(removingTarget)) {
      setActionError('Protected legitimate kitchen owner accounts cannot be removed.');
      setRemovingTarget(null);
      return;
    }
    try {
      setRemoving(true);
      setActionError(null);
      const res = await adminApi.removeKitchenOwner(removingTarget.id);
      setActionMessage(res?.message || 'Kitchen owner successfully removed.');
      setTimeout(() => setActionMessage(null), 4000);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(removingTarget.id);
        return next;
      });
      setRemovingTarget(null);
      apiClient.clearCache();
      await fetchOwners();
    } catch (err: any) {
      setActionError(err?.detail || err?.message || 'Failed to remove kitchen owner');
      setTimeout(() => setActionError(null), 5000);
    } finally {
      setRemoving(false);
    }
  };

  const handleConfirmBatchRemove = async () => {
    if (selectedIds.size === 0) return;
    const eligibleIds = Array.from(selectedIds).filter((id) => {
      const owner = owners.find((o) => o.id === id);
      return !isOwnerProtected(owner);
    });
    if (eligibleIds.length === 0) {
      setActionError('No eligible records selected for removal. Protected accounts cannot be removed.');
      setBatchModalOpen(false);
      return;
    }
    try {
      setBatchRemoving(true);
      setActionError(null);
      const res = await adminApi.batchRemoveKitchenOwners(eligibleIds);
      let msg = res?.message || `Processed ${eligibleIds.length} kitchen owners.`;
      if (res.deleted_count > 0 || res.archived_count > 0) {
        msg = `Successfully processed ${res.total_processed} kitchen owners (${res.deleted_count} deleted, ${res.archived_count} archived).`;
      }
      setActionMessage(msg);
      if (res.errors && res.errors.length > 0) {
        setActionError(res.errors.join('; '));
      }
      setTimeout(() => setActionMessage(null), 5000);
      setSelectedIds(new Set());
      setBatchModalOpen(false);
      apiClient.clearCache();
      await fetchOwners();
    } catch (err: any) {
      setActionError(err?.detail || err?.message || 'Failed to batch remove kitchen owners');
      setTimeout(() => setActionError(null), 5000);
    } finally {
      setBatchRemoving(false);
    }
  };

  const handleLicenseAction = async () => {
    if (!licenseActionKitchen || !licenseActionMode) return;
    try {
      setLicenseActionSubmitting(true);
      setActionError(null);

      if (licenseActionMode === 'verify') {
        await adminApi.verifyKitchenLicense(licenseActionKitchen.id, licenseActionNotes || undefined);
        setActionMessage(`FSSAI License for ${licenseActionKitchen.kitchen_name} verified successfully.`);
      } else if (licenseActionMode === 'correct') {
        if (!licenseActionReason.trim()) {
          setActionError('Please specify the correction details required from the owner.');
          setLicenseActionSubmitting(false);
          return;
        }
        await adminApi.requestLicenseCorrection(licenseActionKitchen.id, licenseActionReason);
        setActionMessage(`Correction request sent to ${licenseActionKitchen.kitchen_name}.`);
      } else if (licenseActionMode === 'reject') {
        if (!licenseActionReason.trim()) {
          setActionError('Please specify the rejection reason.');
          setLicenseActionSubmitting(false);
          return;
        }
        await adminApi.rejectKitchenLicense(licenseActionKitchen.id, licenseActionReason);
        setActionMessage(`FSSAI License rejected for ${licenseActionKitchen.kitchen_name}.`);
      }

      setLicenseActionKitchen(null);
      setLicenseActionMode(null);
      setLicenseActionReason('');
      setLicenseActionNotes('');
      setTimeout(() => setActionMessage(null), 4000);
      fetchOwners();
    } catch (err: any) {
      setActionError(err?.detail || 'Failed to execute license action');
      setTimeout(() => setActionError(null), 5000);
    } finally {
      setLicenseActionSubmitting(false);
    }
  };

  const selectableOwners = useMemo(() => {
    return filteredOwners.filter((o) => !isOwnerProtected(o));
  }, [filteredOwners]);

  const isAllSelected = selectableOwners.length > 0 && selectableOwners.every((o) => selectedIds.has(o.id));
  const isSomeSelected = selectableOwners.some((o) => selectedIds.has(o.id)) && !isAllSelected;

  const columns = [
    {
      key: 'select',
      header: (
        <div className="flex items-center justify-center">
          <input
            type="checkbox"
            id="select-all-owners-checkbox"
            aria-label="Select all eligible kitchen owners on this page"
            disabled={selectableOwners.length === 0}
            checked={isAllSelected}
            ref={(el) => {
              if (el) el.indeterminate = isSomeSelected;
            }}
            onChange={(e) => {
              const next = new Set(selectedIds);
              if (e.target.checked) {
                selectableOwners.forEach((o) => next.add(o.id));
              } else {
                selectableOwners.forEach((o) => next.delete(o.id));
              }
              setSelectedIds(next);
            }}
            className="w-4 h-4 rounded border-gray-300 text-emerald-800 focus:ring-emerald-700 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          />
        </div>
      ),
      className: 'w-12 text-center px-2',
      render: (owner: any) => {
        const protectedOwner = isOwnerProtected(owner);
        if (protectedOwner) {
          return (
            <div
              className="flex items-center justify-center cursor-help"
              title={owner.protection_reason || 'Protected system account is guarded against administrative removal'}
            >
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            </div>
          );
        }
        return (
          <div className="flex items-center justify-center">
            <input
              type="checkbox"
              id={`select-owner-${owner.id}`}
              checked={selectedIds.has(owner.id)}
              onChange={(e) => {
                const next = new Set(selectedIds);
                if (e.target.checked) {
                  next.add(owner.id);
                } else {
                  next.delete(owner.id);
                }
                setSelectedIds(next);
              }}
              aria-label={`Select ${owner.kitchen_name}`}
              className="w-4 h-4 rounded border-gray-300 text-emerald-800 focus:ring-emerald-700 cursor-pointer"
            />
          </div>
        );
      },
    },
    {
      key: 'owner',
      header: 'Owner',
      className: 'min-w-[170px]',
      render: (owner: any) => {
        const protectedOwner = isOwnerProtected(owner);
        const fullName =
          owner.owner_name ||
          (owner.first_name || owner.last_name
            ? `${owner.first_name || ''} ${owner.last_name || ''}`.trim()
            : owner.owner?.first_name || owner.owner?.last_name
            ? `${owner.owner.first_name || ''} ${owner.owner.last_name || ''}`.trim()
            : 'Unknown Owner');
        const email = owner.email || owner.owner?.email || 'N/A';
        const isTestRecord = fullName.toLowerCase().includes('master chef') || email.toLowerCase().includes('@cloudkitchen.com');
        const isOrphaned = !owner.user_id && (!owner.owner && fullName === 'Unknown Owner');

        return (
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-gray-900 leading-tight">{fullName}</span>
              {protectedOwner && (
                <span
                  className="px-1.5 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-200 text-[10px] font-bold rounded flex items-center gap-1 cursor-help"
                  title={owner.protection_reason || 'Protected System Account'}
                >
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  Protected Account
                </span>
              )}
              {!protectedOwner && isOrphaned && (
                <span className="px-1.5 py-0.5 bg-rose-50 text-rose-800 border border-rose-200 text-[10px] font-bold rounded">
                  Orphaned Record
                </span>
              )}
              {!protectedOwner && !isOrphaned && isTestRecord && (
                <span className="px-1.5 py-0.5 bg-amber-50 text-amber-800 border border-amber-200 text-[10px] font-bold rounded">
                  Test Record
                </span>
              )}
            </div>
            <div className="text-xs text-gray-500 font-mono truncate max-w-[180px]" title={email}>
              {email}
            </div>
          </div>
        );
      },
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      className: 'min-w-[160px]',
      render: (owner: any) => (
        <div className="flex flex-col">
          <div className="font-semibold text-gray-900 leading-tight">{owner.kitchen_name}</div>
          <div className="text-xs text-gray-500">{owner.city || 'N/A'}</div>
        </div>
      ),
    },
    {
      key: 'fssai_license',
      header: 'FSSAI License',
      className: 'min-w-[170px]',
      render: (owner: any) => {
        const lic = owner.license;
        if (!lic) {
          return (
            <span className="text-xs text-rose-600 font-semibold bg-rose-50 px-2 py-0.5 rounded-md">
              Missing License
            </span>
          );
        }
        return (
          <div className="flex flex-col space-y-1">
            <span className="font-mono text-xs font-bold text-gray-800">
              {lic.license_number}
            </span>
            <LicenseStatusBadge
              status={lic.status}
              isDuplicateFlagged={lic.is_duplicate_flagged}
            />
          </div>
        );
      },
    },
    {
      key: 'approval_status',
      header: 'Approval',
      className: 'w-[110px]',
      render: (owner: any) => {
        const st = (owner.approval_status || (owner.is_approved ? 'APPROVED' : 'PENDING')).toUpperCase();
        if (st === 'APPROVED') {
          return <Badge variant="success">APPROVED</Badge>;
        } else if (st === 'REJECTED') {
          return <Badge variant="danger">REJECTED</Badge>;
        } else if (st === 'ARCHIVED') {
          return (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
              ARCHIVED
            </span>
          );
        }
        return <Badge variant="warning">PENDING</Badge>;
      },
    },
    {
      key: 'status',
      header: 'Account',
      className: 'w-[100px]',
      render: (owner: any) => {
        const active = (owner.status || owner.owner?.status) === 'ACTIVE';
        return (
          <Badge variant={active ? 'info' : 'warning'}>
            {active ? 'ACTIVE' : 'INACTIVE'}
          </Badge>
        );
      },
    },
    {
      key: 'created_at',
      header: 'Joined',
      className: 'w-[100px] hidden sm:table-cell',
      render: (owner: any) => (
        <span className="text-xs text-gray-600">
          {new Date(owner.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      className: 'min-w-[210px] text-right',
      render: (owner: any) => {
        const protectedOwner = isOwnerProtected(owner);
        const st = (owner.approval_status || (owner.is_approved ? 'APPROVED' : 'PENDING')).toUpperCase();
        return (
          <div className="flex items-center space-x-1.5 justify-end">
            {st !== 'APPROVED' && (
              <button
                onClick={() => handleApprove(owner.id)}
                className="inline-flex items-center space-x-1 px-2 py-1 bg-emerald-50 text-[#166534] hover:bg-emerald-100 rounded-lg text-xs font-bold transition-colors"
                title="Approve Kitchen Owner"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
            )}

            {st !== 'REJECTED' && st !== 'ARCHIVED' && (
              <button
                onClick={() => {
                  setRejectingKitchenId(owner.id);
                  setRejectionReason('');
                }}
                className="inline-flex items-center space-x-1 px-2 py-1 bg-amber-50 text-amber-800 hover:bg-amber-100 rounded-lg text-xs font-bold transition-colors"
                title="Reject Kitchen Owner"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            )}

            <button
              onClick={() => setSelectedOwner(owner)}
              className="inline-flex items-center space-x-1 px-2 py-1 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg text-xs font-semibold transition-colors"
              title="View Owner & Kitchen Details"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>View</span>
            </button>

            {owner.license && (
              <button
                onClick={() => setInspectLicenseKitchen(owner)}
                className="inline-flex items-center space-x-1 px-2 py-1 text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded-lg text-xs font-bold transition-colors"
                title="Inspect Food License & OCR Documents"
              >
                <FileCheck className="w-3.5 h-3.5" />
                <span>License</span>
              </button>
            )}

            {protectedOwner ? (
              <span
                className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-xs font-bold cursor-help"
                title={owner.protection_reason || 'Protected system account - protected from deletion'}
              >
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Protected</span>
              </span>
            ) : (
              <button
                id={`remove-owner-${owner.id}`}
                onClick={() => setRemovingTarget(owner)}
                className="inline-flex items-center space-x-1 px-2 py-1 text-red-600 bg-red-50 hover:bg-red-100 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                title="Remove or Archive Kitchen Registration"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Remove</span>
              </button>
            )}
          </div>
        );
      },
    },
  ];

  if (loading && owners.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchOwners} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Kitchen Owners"
        description="Verify, approve, or manage kitchen registrations with business data preservation"
      />

      {actionMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-[#166534] rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Food License Executive Overview & Quick Filters */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-50 text-emerald-800 rounded-xl">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-gray-950">FSSAI Food License Compliance Center</h3>
              <p className="text-xs text-gray-500">Monitor mandatory food safety credentials, OCR extractions, and verifications</p>
            </div>
          </div>
          {licenseFilter && (
            <button
              onClick={() => setLicenseFilter('')}
              className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 flex items-center gap-1 self-start sm:self-auto"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset License Filter</span>
            </button>
          )}
        </div>

        {/* License Status Breakdown Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5 pt-1">
          {[
            { id: '', label: 'All Licenses', count: owners.length, color: 'border-gray-200 bg-gray-50 text-gray-800 hover:border-gray-300' },
            {
              id: 'VERIFIED',
              label: 'Verified',
              count: owners.filter(o => o.license?.status === 'VERIFIED').length,
              color: 'border-emerald-200 bg-emerald-50/70 text-emerald-800 hover:border-emerald-300'
            },
            {
              id: 'PENDING_REVIEW',
              label: 'Pending Review',
              count: owners.filter(o => !o.license || o.license?.status === 'PENDING_REVIEW' || o.license?.status === 'PENDING').length,
              color: 'border-amber-200 bg-amber-50/70 text-amber-800 hover:border-amber-300'
            },
            {
              id: 'CORRECTION_REQUIRED',
              label: 'Needs Correction',
              count: owners.filter(o => o.license?.status === 'CORRECTION_REQUIRED').length,
              color: 'border-orange-200 bg-orange-50/70 text-orange-800 hover:border-orange-300'
            },
            {
              id: 'REJECTED',
              label: 'Rejected',
              count: owners.filter(o => o.license?.status === 'REJECTED').length,
              color: 'border-rose-200 bg-rose-50/70 text-rose-800 hover:border-rose-300'
            },
            {
              id: 'EXPIRED',
              label: 'Expired',
              count: owners.filter(o => o.license?.status === 'EXPIRED').length,
              color: 'border-purple-200 bg-purple-50/70 text-purple-800 hover:border-purple-300'
            },
          ].map(tile => (
            <button
              key={tile.id}
              onClick={() => setLicenseFilter(tile.id)}
              className={`p-3 rounded-xl border text-left transition-all ${tile.color} ${
                licenseFilter === tile.id ? 'ring-2 ring-emerald-600 font-bold shadow-xs' : 'opacity-90'
              }`}
            >
              <div className="text-[11px] font-semibold tracking-tight">{tile.label}</div>
              <div className="text-lg font-black mt-0.5">{tile.count}</div>
            </button>
          ))}
        </div>
      </div>

      <Card>
        <div className="p-6 border-b border-gray-200 flex flex-col sm:flex-row gap-4 justify-between items-center">
          <div className="w-full sm:w-72">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by owner name, email, or kitchen..."
            />
          </div>

          <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto items-center">
            <button
              type="button"
              onClick={() => {
                if (search === 'Master Chef') {
                  setSearch('');
                } else {
                  setSearch('Master Chef');
                }
              }}
              className={`px-3 py-2 text-xs font-bold rounded-xl border transition-colors flex items-center gap-1.5 whitespace-nowrap ${
                search === 'Master Chef'
                  ? 'bg-amber-100 text-amber-900 border-amber-300'
                  : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>{search === 'Master Chef' ? 'Show All Owners' : 'Find Test Records (Master Chef)'}</span>
            </button>

            {filteredOwners.some((o) => {
              const name = (o.owner_name || `${o.first_name || ''} ${o.last_name || ''}`).toLowerCase();
              const mail = (o.email || o.owner?.email || '').toLowerCase();
              return name.includes('master chef') || mail.includes('@cloudkitchen.com');
            }) && (
              <button
                type="button"
                onClick={() => {
                  const testIds = filteredOwners
                    .filter((o) => {
                      const name = (o.owner_name || `${o.first_name || ''} ${o.last_name || ''}`).toLowerCase();
                      const mail = (o.email || o.owner?.email || '').toLowerCase();
                      return name.includes('master chef') || mail.includes('@cloudkitchen.com');
                    })
                    .map((o) => o.id);
                  const next = new Set(selectedIds);
                  testIds.forEach((id) => next.add(id));
                  setSelectedIds(next);
                }}
                className="px-3 py-2 text-xs font-bold rounded-xl border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 transition-colors whitespace-nowrap"
              >
                Select Visible Test Records
              </button>
            )}

            <div className="w-full sm:w-44">
              <FilterSelect
                value={licenseFilter}
                onChange={setLicenseFilter}
                options={[
                  { value: 'VERIFIED', label: 'Verified License' },
                  { value: 'PENDING_REVIEW', label: 'Pending Review' },
                  { value: 'CORRECTION_REQUIRED', label: 'Needs Correction' },
                  { value: 'REJECTED', label: 'Rejected License' },
                  { value: 'EXPIRED', label: 'Expired License' },
                  { value: 'DUPLICATE', label: 'Duplicate Flagged' },
                ]}
                placeholder="All License States"
              />
            </div>

            <div className="w-full sm:w-44">
              <FilterSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  { value: 'PENDING', label: 'Pending Approval' },
                  { value: 'APPROVED', label: 'Approved' },
                  { value: 'REJECTED', label: 'Rejected' },
                  { value: 'ARCHIVED', label: 'Archived / Deactivated' },
                ]}
                placeholder="All Approval Statuses"
              />
            </div>
          </div>
        </div>

        {selectedIds.size > 0 && (
          <div className="p-3.5 bg-red-50/80 border-b border-red-200 flex flex-wrap items-center justify-between gap-3 animate-fade-in px-6">
            <div className="flex items-center space-x-2 text-xs font-semibold text-red-900">
              <span className="bg-red-200 text-red-900 px-2 py-0.5 rounded-full font-bold">
                {selectedIds.size}
              </span>
              <span>kitchen owner record(s) selected</span>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                id="clear-selection-btn"
                onClick={() => setSelectedIds(new Set())}
                className="px-3 py-1.5 border border-gray-300 bg-white text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition cursor-pointer"
              >
                Clear Selection
              </button>
              <button
                type="button"
                id="bulk-remove-btn"
                onClick={() => setBatchModalOpen(true)}
                className="px-3.5 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-xs cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Remove Selected ({selectedIds.size})</span>
              </button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <DataTable
            columns={columns}
            data={filteredOwners}
            keyExtractor={(o) => o.id}
            emptyMessage="No kitchen owners matching the filter criteria"
          />
        </div>

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>

      {/* Reject Modal */}
      {rejectingKitchenId && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-gray-100">
            <div className="flex items-center justify-between pb-2 border-b border-gray-100">
              <h3 className="font-bold text-base text-gray-900">Reject Kitchen Application</h3>
              <button
                onClick={() => setRejectingKitchenId(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Please specify the reason for rejection. This explanation will be logged and communicated to the kitchen owner.
            </p>
            <textarea
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Incomplete business address or unverifiable contact documentation."
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-[#166534] focus:outline-hidden"
            />
            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setRejectingKitchenId(null)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReject}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition-colors"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Remove / Archive Modal */}
      {removingTarget && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-start space-x-3 mb-4">
              <div className="p-2.5 bg-red-100 text-red-600 rounded-xl">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-gray-900">Remove Kitchen Registration</h3>
                <div className="mt-1 p-2.5 bg-gray-50 rounded-xl border border-gray-100 text-xs space-y-0.5">
                  <div className="font-semibold text-gray-900">{removingTarget.kitchen_name}</div>
                  <div className="text-gray-600">
                    Owner: {removingTarget.owner_name || `${removingTarget.first_name || ''} ${removingTarget.last_name || ''}`.trim() || removingTarget.email || 'Unknown Owner'}
                  </div>
                  <div className="text-gray-500 font-mono text-[11px]">
                    Email: {removingTarget.email || removingTarget.owner?.email || 'N/A'}
                  </div>
                  <div className="text-gray-500">
                    Status: <span className="font-medium text-gray-700">{removingTarget.approval_status || 'PENDING'}</span>
                  </div>
                </div>
              </div>
            </div>

            {isOwnerProtected(removingTarget) ? (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-semibold flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-red-600 flex-shrink-0" />
                <span>
                  {removingTarget.protection_reason ||
                    'Protected Account: This system administrator account cannot be removed.'}
                </span>
              </div>
            ) : (
              <div className="space-y-2 mb-6 text-xs text-gray-600 leading-relaxed">
                <p className="font-semibold text-gray-800">Removal & Retention Protections:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>
                    If this kitchen has associated orders, payments, or inventory history, it will be <strong>safely archived and deactivated</strong> rather than permanently deleted, protecting historical business records.
                  </li>
                  <li>
                    If it is a disposable test registration without customer transactions, it will be completely cleaned up from the database.
                  </li>
                </ul>
              </div>
            )}

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                id="cancel-remove-btn"
                onClick={() => setRemovingTarget(null)}
                disabled={removing}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-remove-btn"
                onClick={handleConfirmRemove}
                disabled={removing || isOwnerProtected(removingTarget)}
                className="px-4 py-2 bg-red-600 text-white rounded-xl text-xs font-bold hover:bg-red-700 transition flex items-center space-x-1.5 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                {removing && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                <span>{removing ? 'Processing...' : 'Confirm Remove'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Batch Remove Modal */}
      {batchModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-start space-x-3 mb-4">
              <div className="p-2.5 bg-red-100 text-red-600 rounded-xl">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-gray-900">
                  Batch Remove {selectedIds.size} Kitchen Owners
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Confirm permanent removal or archival of selected registrations.
                </p>
              </div>
            </div>

            <div className="max-h-48 overflow-y-auto p-3 bg-gray-50 rounded-xl border border-gray-200 text-xs space-y-1.5 mb-4">
              {filteredOwners
                .filter((o) => selectedIds.has(o.id))
                .map((o) => {
                  const prot = isOwnerProtected(o);
                  return (
                    <div key={o.id} className="flex justify-between items-center py-1 border-b border-gray-100 last:border-b-0">
                      <span className="font-semibold text-gray-800 flex items-center gap-1.5">
                        {o.kitchen_name}
                        {prot && (
                          <span className="text-[10px] bg-red-100 text-red-700 font-bold px-1.5 py-0.2 rounded">
                            Protected (Will Skip)
                          </span>
                        )}
                      </span>
                      <span className="text-gray-500 font-mono text-[11px]">{o.email || o.owner?.email || 'N/A'}</span>
                    </div>
                  );
                })}
            </div>

            <div className="space-y-2 mb-6 text-xs text-gray-600 leading-relaxed">
              <p className="font-semibold text-gray-800">Business History Protections:</p>
              <ul className="list-disc pl-4 space-y-1">
                <li>
                  Any selected kitchen with historical orders, payments, or inventory will be <strong>safely archived and deactivated</strong> rather than deleted.
                </li>
                <li>
                  Eligible test records without dependent records will be <strong>permanently removed</strong> cleanly from the database.
                </li>
                <li>
                  Audit logs will be preserved for platform compliance.
                </li>
              </ul>
            </div>

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                id="cancel-batch-remove-btn"
                onClick={() => setBatchModalOpen(false)}
                disabled={batchRemoving}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-batch-remove-btn"
                onClick={handleConfirmBatchRemove}
                disabled={batchRemoving}
                className="px-4 py-2 bg-red-600 text-white rounded-xl text-xs font-bold hover:bg-red-700 transition flex items-center space-x-1.5 shadow-sm cursor-pointer"
              >
                {batchRemoving && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                <span>{batchRemoving ? 'Processing...' : `Confirm Remove (${selectedIds.size})`}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Detail Modal */}
      {selectedOwner && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 border border-gray-100">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#166534] flex items-center justify-center">
                  <Store className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-gray-900">
                    {selectedOwner.kitchen_name}
                  </h3>
                  <p className="text-xs text-gray-500">{selectedOwner.city || 'Location N/A'}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedOwner(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 bg-gray-50 rounded-xl">
                <div>
                  <span className="text-gray-400 uppercase font-bold text-[10px]">Owner</span>
                  <p className="font-semibold text-gray-800 text-sm mt-0.5">
                    {selectedOwner.owner_name || `${selectedOwner.first_name || ''} ${selectedOwner.last_name || ''}`.trim() || 'N/A'}
                  </p>
                  <p className="text-gray-500">{selectedOwner.email || 'N/A'}</p>
                  <p className="text-gray-500 mt-0.5">Phone: {selectedOwner.phone || 'N/A'}</p>
                </div>
                <div>
                  <span className="text-gray-400 uppercase font-bold text-[10px]">Approval Status</span>
                  <div className="mt-1">
                    <Badge
                      variant={
                        selectedOwner.approval_status === 'APPROVED'
                          ? 'success'
                          : selectedOwner.approval_status === 'REJECTED'
                          ? 'danger'
                          : 'warning'
                      }
                    >
                      {selectedOwner.approval_status || 'PENDING'}
                    </Badge>
                  </div>
                  <p className="text-gray-400 mt-2">
                    Joined: {new Date(selectedOwner.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <div>
                <span className="text-gray-400 uppercase font-bold text-[10px]">Physical Address</span>
                <p className="font-medium text-gray-700 mt-0.5">
                  {selectedOwner.address || 'No physical address provided.'}
                </p>
              </div>

              {/* FSSAI Food License Section */}
              <div className="p-3.5 bg-emerald-50/60 rounded-xl border border-emerald-200/80 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-700" />
                    <span className="font-bold text-xs text-emerald-950 uppercase tracking-wider">
                      FSSAI Food License Credentials
                    </span>
                  </div>
                  {selectedOwner.license ? (
                    <LicenseStatusBadge
                      status={selectedOwner.license.status}
                      isDuplicateFlagged={selectedOwner.license.is_duplicate_flagged}
                    />
                  ) : (
                    <Badge variant="danger">NO LICENSE</Badge>
                  )}
                </div>

                {selectedOwner.license?.is_duplicate_flagged && (
                  <div className="p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-purple-900 flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                    <div className="space-y-0.5">
                      <p className="font-bold text-xs">Duplicate License Flag Triggered</p>
                      <p className="text-[11px] text-purple-800">
                        {selectedOwner.license.duplicate_notes || 'This license number matches another kitchen submission in the system.'}
                      </p>
                    </div>
                  </div>
                )}

                {selectedOwner.license ? (
                  <div className="space-y-2 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-gray-500 text-[10px] uppercase font-bold">Registration No.</span>
                        <p className="font-mono font-bold text-gray-900">{selectedOwner.license.license_number}</p>
                        {selectedOwner.license.ocr_extracted_number && (
                          <p className="text-[10px] text-gray-500">OCR: {selectedOwner.license.ocr_extracted_number}</p>
                        )}
                      </div>
                      <div>
                        <span className="text-gray-500 text-[10px] uppercase font-bold">Expiry Date</span>
                        <p className="font-semibold text-gray-800">{selectedOwner.license.expiry_date || 'N/A'}</p>
                      </div>
                    </div>

                    <div>
                      <span className="text-gray-500 text-[10px] uppercase font-bold">Business Name</span>
                      <p className="font-medium text-gray-800">{selectedOwner.license.business_name || 'N/A'}</p>
                    </div>

                    {selectedOwner.license.documents && selectedOwner.license.documents.length > 0 && (
                      <div className="pt-2 border-t border-emerald-200/50 flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-gray-700">
                          <FileText className="w-3.5 h-3.5 text-emerald-700" />
                          <span className="font-semibold text-[11px]">
                            {selectedOwner.license.documents[0].original_filename} (v{selectedOwner.license.documents[0].version})
                          </span>
                        </div>
                        <a
                          href={`/api/v1/kitchen/license/document/${selectedOwner.license.documents[0].id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-gray-200 rounded-lg text-[11px] font-bold text-emerald-800 hover:bg-emerald-50 transition"
                        >
                          <span>View Doc</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}

                    {/* Admin License Actions */}
                    <div className="pt-2 border-t border-emerald-200/50 flex items-center justify-end gap-1.5">
                      {selectedOwner.license.status !== 'VERIFIED' && (
                        <button
                          type="button"
                          onClick={() => {
                            setLicenseActionKitchen(selectedOwner);
                            setLicenseActionMode('verify');
                            setLicenseActionNotes('');
                          }}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1"
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Verify License</span>
                        </button>
                      )}

                      {selectedOwner.license.status !== 'CORRECTION_REQUIRED' && (
                        <button
                          type="button"
                          onClick={() => {
                            setLicenseActionKitchen(selectedOwner);
                            setLicenseActionMode('correct');
                            setLicenseActionReason('');
                          }}
                          className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          <span>Request Correction</span>
                        </button>
                      )}

                      {selectedOwner.license.status !== 'REJECTED' && (
                        <button
                          type="button"
                          onClick={() => {
                            setLicenseActionKitchen(selectedOwner);
                            setLicenseActionMode('reject');
                            setLicenseActionReason('');
                          }}
                          className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1"
                        >
                          <XCircle className="w-3 h-3" />
                          <span>Reject License</span>
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-rose-700">No FSSAI license has been submitted for this kitchen.</p>
                )}
              </div>

              {selectedOwner.description && (
                <div>
                  <span className="text-gray-400 uppercase font-bold text-[10px]">Description</span>
                  <p className="text-gray-600 mt-0.5">{selectedOwner.description}</p>
                </div>
              )}

              {selectedOwner.rejection_reason && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800">
                  <span className="text-[10px] font-bold uppercase text-red-600">Kitchen Rejection Reason</span>
                  <p className="mt-0.5">{selectedOwner.rejection_reason}</p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedOwner(null)}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* License Action Modal (Verify / Request Correction / Reject) */}
      {licenseActionKitchen && licenseActionMode && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-gray-100">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <h3 className="font-bold text-base text-gray-900">
                {licenseActionMode === 'verify'
                  ? 'Verify FSSAI Food License'
                  : licenseActionMode === 'correct'
                  ? 'Request License Correction'
                  : 'Reject FSSAI License'}
              </h3>
              <button
                onClick={() => {
                  setLicenseActionKitchen(null);
                  setLicenseActionMode(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-gray-600">
              Kitchen:{' '}
              <strong className="text-gray-900">{licenseActionKitchen.kitchen_name}</strong>{' '}
              ({licenseActionKitchen.license?.license_number || 'N/A'})
            </p>

            {licenseActionMode === 'verify' && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Verification Audit Notes (Optional)
                </label>
                <textarea
                  rows={3}
                  value={licenseActionNotes}
                  onChange={(e) => setLicenseActionNotes(e.target.value)}
                  placeholder="e.g. Verified via official portal / certificate inspection. Authenticity confirmed."
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            )}

            {(licenseActionMode === 'correct' || licenseActionMode === 'reject') && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Reason provided to Kitchen Owner <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  value={licenseActionReason}
                  onChange={(e) => setLicenseActionReason(e.target.value)}
                  placeholder={
                    licenseActionMode === 'correct'
                      ? 'e.g. Blurred document text; please upload a clean high-resolution scan showing the 14-digit number and valid dates.'
                      : 'e.g. Document expired or business name does not correspond with kitchen entity.'
                  }
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-xl focus:ring-2 focus:ring-rose-500"
                />
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setLicenseActionKitchen(null);
                  setLicenseActionMode(null);
                }}
                disabled={licenseActionSubmitting}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleLicenseAction}
                disabled={licenseActionSubmitting}
                className={`px-4 py-2 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-sm ${
                  licenseActionMode === 'verify'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : licenseActionMode === 'correct'
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {licenseActionSubmitting && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                <span>
                  {licenseActionMode === 'verify'
                    ? 'Confirm Verification'
                    : licenseActionMode === 'correct'
                    ? 'Send Correction Request'
                    : 'Confirm Rejection'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Dedicated Food License & OCR Inspection Modal */}
      {inspectLicenseKitchen && inspectLicenseKitchen.license && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 border border-gray-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-800 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-gray-900">
                    FSSAI License & OCR Inspection
                  </h3>
                  <p className="text-xs text-gray-500">
                    {inspectLicenseKitchen.kitchen_name} &bull; Owner: {inspectLicenseKitchen.owner_name || inspectLicenseKitchen.email}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setInspectLicenseKitchen(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Status & Warning Notice */}
            <div className="flex items-center justify-between p-3.5 bg-gray-50 rounded-xl border border-gray-200">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-600">Verification Status:</span>
                <LicenseStatusBadge
                  status={inspectLicenseKitchen.license.status}
                  isDuplicateFlagged={inspectLicenseKitchen.license.duplicate_flag || inspectLicenseKitchen.license.is_duplicate_flagged}
                />
              </div>
              {inspectLicenseKitchen.license.verification_source && (
                <span className="text-[11px] font-mono text-gray-500 bg-white px-2 py-0.5 rounded-md border border-gray-200">
                  Source: {inspectLicenseKitchen.license.verification_source}
                </span>
              )}
            </div>

            {/* Duplicate Flag Alert */}
            {(inspectLicenseKitchen.license.duplicate_flag || inspectLicenseKitchen.license.is_duplicate_flagged) && (
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-purple-900 flex items-start gap-2.5">
                <ShieldAlert className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-xs">Duplicate License Number Flagged</h4>
                  <p className="text-xs text-purple-800 mt-0.5">
                    {inspectLicenseKitchen.license.duplicate_details || 'This license number is registered with another kitchen in the database. Duplicates cannot be verified simultaneously.'}
                  </p>
                </div>
              </div>
            )}

            {/* Submitted Credentials vs OCR Extraction Side-by-Side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Submitted Profile Data */}
              <div className="p-4 bg-gray-50/80 rounded-xl border border-gray-200 space-y-3">
                <div className="flex items-center gap-1.5 text-gray-900 pb-1.5 border-b border-gray-200">
                  <FileText className="w-4 h-4 text-gray-700" />
                  <span className="font-bold text-xs uppercase tracking-wider">Submitted By Owner</span>
                </div>
                <div>
                  <span className="text-gray-500 text-[10px] uppercase font-bold">14-Digit FSSAI Number</span>
                  <p className="font-mono font-bold text-sm text-gray-950 mt-0.5">
                    {inspectLicenseKitchen.license.license_number}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500 text-[10px] uppercase font-bold">Business Name (FBO)</span>
                  <p className="font-semibold text-xs text-gray-800 mt-0.5">
                    {inspectLicenseKitchen.license.business_name || 'N/A'}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500 text-[10px] uppercase font-bold">Expiry Date</span>
                  <p className="font-semibold text-xs text-gray-800 mt-0.5">
                    {inspectLicenseKitchen.license.expiry_date
                      ? new Date(inspectLicenseKitchen.license.expiry_date).toLocaleDateString()
                      : 'N/A'}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500 text-[10px] uppercase font-bold">Submission Date</span>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {inspectLicenseKitchen.license.submission_date || inspectLicenseKitchen.license.created_at
                      ? new Date(inspectLicenseKitchen.license.submission_date || inspectLicenseKitchen.license.created_at).toLocaleDateString()
                      : 'N/A'}
                  </p>
                </div>
              </div>

              {/* Extracted OCR Information */}
              <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200 space-y-3">
                <div className="flex items-center justify-between pb-1.5 border-b border-emerald-200">
                  <div className="flex items-center gap-1.5 text-emerald-950">
                    <Sparkles className="w-4 h-4 text-emerald-700" />
                    <span className="font-bold text-xs uppercase tracking-wider">Automated OCR Extraction</span>
                  </div>
                  <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">
                    Advisory Only
                  </span>
                </div>

                <div>
                  <span className="text-emerald-900 text-[10px] uppercase font-bold">Detected Number</span>
                  <p className="font-mono font-bold text-sm text-gray-950 mt-0.5">
                    {inspectLicenseKitchen.license.ocr_extracted_number ||
                     inspectLicenseKitchen.license.ocr_extracted_data?.extracted_license_number ||
                     'Not detected by OCR'}
                  </p>
                </div>
                <div>
                  <span className="text-emerald-900 text-[10px] uppercase font-bold">Detected Business Name</span>
                  <p className="font-semibold text-xs text-gray-800 mt-0.5">
                    {inspectLicenseKitchen.license.ocr_extracted_name ||
                     inspectLicenseKitchen.license.ocr_extracted_data?.extracted_business_name ||
                     'Not detected by OCR'}
                  </p>
                </div>
                <div>
                  <span className="text-emerald-900 text-[10px] uppercase font-bold">Detected Validity / Expiry</span>
                  <p className="font-semibold text-xs text-gray-800 mt-0.5">
                    {inspectLicenseKitchen.license.ocr_extracted_expiry ||
                     inspectLicenseKitchen.license.ocr_extracted_data?.extracted_expiry_date ||
                     'Not detected by OCR'}
                  </p>
                </div>
                <div className="p-2 bg-white/70 rounded-lg border border-emerald-200/60 text-[11px] text-emerald-900 leading-snug">
                  <strong>Notice:</strong> Automated OCR extraction assists document review and does not constitute official regulatory verification.
                </div>
              </div>
            </div>

            {/* Document Versions & Secure Viewer Actions */}
            <div className="space-y-2">
              <span className="text-gray-500 uppercase font-bold text-[10px] tracking-wider">
                Uploaded Verification Documents
              </span>
              {inspectLicenseKitchen.license.documents && inspectLicenseKitchen.license.documents.length > 0 ? (
                <div className="space-y-2">
                  {inspectLicenseKitchen.license.documents.map((doc: any, index: number) => (
                    <div
                      key={doc.id || index}
                      className="p-3 bg-white rounded-xl border border-gray-200 flex items-center justify-between shadow-2xs hover:border-gray-300 transition"
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 bg-gray-100 text-gray-700 rounded-lg">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="font-semibold text-xs text-gray-900 flex items-center gap-1.5">
                            <span>{doc.original_filename}</span>
                            {doc.is_active && (
                              <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-bold">
                                Current
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-gray-500">
                            {doc.document_type || 'Initial'} &bull; {(doc.file_size / 1024).toFixed(1)} KB &bull; Uploaded: {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <a
                          href={`/api/v1/kitchen/license/document/${doc.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 rounded-lg text-xs font-bold transition border border-emerald-200"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>View Document</span>
                          <ExternalLink className="w-3 h-3 ml-0.5" />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              ) : inspectLicenseKitchen.license.active_document ? (
                <div className="p-3 bg-white rounded-xl border border-gray-200 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <FileText className="w-4 h-4 text-emerald-700" />
                    <div>
                      <div className="font-semibold text-xs text-gray-900">
                        {inspectLicenseKitchen.license.active_document.original_filename}
                      </div>
                      <div className="text-[11px] text-gray-500">
                        {inspectLicenseKitchen.license.active_document.mime_type} &bull; {(inspectLicenseKitchen.license.active_document.file_size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <a
                    href={`/api/v1/kitchen/license/document/${inspectLicenseKitchen.license.active_document.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 rounded-lg text-xs font-bold transition border border-emerald-200"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Document</span>
                    <ExternalLink className="w-3 h-3 ml-0.5" />
                  </a>
                </div>
              ) : (
                <p className="text-xs text-gray-500 italic p-3 bg-gray-50 rounded-xl">
                  No document files found for this license record.
                </p>
              )}
            </div>

            {/* Modal Review Actions */}
            <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setInspectLicenseKitchen(null)}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50"
              >
                Close
              </button>

              <div className="flex items-center gap-2">
                {inspectLicenseKitchen.license.status !== 'VERIFIED' && (
                  <button
                    type="button"
                    onClick={() => {
                      const target = inspectLicenseKitchen;
                      setInspectLicenseKitchen(null);
                      setLicenseActionKitchen(target);
                      setLicenseActionMode('verify');
                      setLicenseActionNotes('');
                    }}
                    className="px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Verify License</span>
                  </button>
                )}

                {inspectLicenseKitchen.license.status !== 'CORRECTION_REQUIRED' && (
                  <button
                    type="button"
                    onClick={() => {
                      const target = inspectLicenseKitchen;
                      setInspectLicenseKitchen(null);
                      setLicenseActionKitchen(target);
                      setLicenseActionMode('correct');
                      setLicenseActionReason('');
                    }}
                    className="px-3 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Request Correction</span>
                  </button>
                )}

                {inspectLicenseKitchen.license.status !== 'REJECTED' && (
                  <button
                    type="button"
                    onClick={() => {
                      const target = inspectLicenseKitchen;
                      setInspectLicenseKitchen(null);
                      setLicenseActionKitchen(target);
                      setLicenseActionMode('reject');
                      setLicenseActionReason('');
                    }}
                    className="px-3 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Reject License</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
