import React, { useState } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  RefreshCw,
  FileText,
  AlertCircle,
  ExternalLink,
  History,
  Info
} from 'lucide-react';
import { KitchenLicense } from '../../types';
import kitchenApi from '../../services/kitchenApi';
import { LicenseStatusBadge } from './LicenseStatusBadge';
import { LicenseUploadSection } from './LicenseUploadSection';

interface FssaiManagementTabProps {
  license: KitchenLicense | null;
  onLicenseUpdated: () => void;
}

export const FssaiManagementTab: React.FC<FssaiManagementTabProps> = ({
  license,
  onLicenseUpdated,
}) => {
  const [activeMode, setActiveMode] = useState<'view' | 'renew' | 'correct'>('view');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [formLicenseData, setFormLicenseData] = useState({
    license_number: license?.license_number || '',
    business_name: license?.business_name || '',
    expiry_date: license?.expiry_date || '',
    document_base64: '',
    filename: '',
  });

  const handleRenewalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formLicenseData.license_number || !formLicenseData.document_base64) {
      setError('Both license number and certificate document are required.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      await kitchenApi.renewLicense({
        license_number: formLicenseData.license_number,
        business_name: formLicenseData.business_name || undefined,
        expiry_date: formLicenseData.expiry_date || undefined,
        document_base64: formLicenseData.document_base64,
        filename: formLicenseData.filename,
      });

      setSuccessMessage('Updated license and document uploaded successfully. Awaiting administrative review.');
      setActiveMode('view');
      onLicenseUpdated();
    } catch (err: any) {
      setError(err?.detail || 'Failed to submit updated license.');
    } finally {
      setSubmitting(false);
    }
  };

  const currentDoc = license?.current_document || (license?.documents && license.documents.find((d) => d.is_current));

  return (
    <div className="space-y-6">
      {/* Current License Status Banner */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-gray-900">Food Safety & FSSAI License</h2>
              <LicenseStatusBadge
                status={license?.status}
                isDuplicateFlagged={license?.is_duplicate_flagged}
              />
            </div>
            <p className="text-xs text-gray-500">
              Government-mandated food licensing credentials. Active verification is required to accept customer orders.
            </p>
          </div>

          {activeMode === 'view' && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setFormLicenseData({
                    license_number: license?.license_number || '',
                    business_name: license?.business_name || '',
                    expiry_date: license?.expiry_date || '',
                    document_base64: '',
                    filename: '',
                  });
                  setActiveMode('renew');
                }}
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Upload Renewal / Replacement</span>
              </button>
            </div>
          )}
        </div>

        {successMessage && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold">
            {successMessage}
          </div>
        )}

        {/* Status Callouts */}
        {license?.status === 'CORRECTION_REQUIRED' && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>Administrative Correction Requested</span>
            </div>
            <p className="text-xs text-amber-800/90 pl-6">
              <strong>Admin Note:</strong> {license.correction_reason || 'Please re-upload a clear copy of your license or rectify mismatched details.'}
            </p>
          </div>
        )}

        {license?.status === 'REJECTED' && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-sm text-rose-800">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>License Submission Rejected</span>
            </div>
            <p className="text-xs text-rose-800/90 pl-6">
              <strong>Reason:</strong> {license.rejection_reason || 'Document or identifier did not meet compliance requirements.'}
            </p>
          </div>
        )}

        {license?.status === 'EXPIRED' && (
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-xl text-orange-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-sm text-orange-800">
              <AlertCircle className="w-4 h-4 text-orange-600 shrink-0" />
              <span>License Expired — Kitchen Operations Suspended</span>
            </div>
            <p className="text-xs text-orange-800/90 pl-6">
              Your license validity period has ended. Kitchen operations and order acceptance are paused until a renewed certificate is uploaded and verified.
            </p>
          </div>
        )}

        {license?.status === 'PENDING_REVIEW' && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 space-y-1">
            <div className="flex items-center gap-2 font-bold text-sm text-blue-800">
              <Clock className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Verification Under Review</span>
            </div>
            <p className="text-xs text-blue-800/90 pl-6">
              Our safety verification team is reviewing your uploaded FSSAI certificate. You will be notified once verified.
            </p>
          </div>
        )}

        {/* License Details Cards */}
        {license ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                14-Digit Registration No.
              </span>
              <p className="text-base font-mono font-bold text-gray-900 mt-1">
                {license.license_number}
              </p>
              {license.ocr_extracted_number && license.ocr_extracted_number !== license.license_number && (
                <p className="text-[10px] text-gray-500 mt-0.5">
                  (OCR raw: {license.ocr_extracted_number})
                </p>
              )}
            </div>

            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Registered Business Name
              </span>
              <p className="text-sm font-semibold text-gray-800 mt-1">
                {license.business_name || 'Not provided'}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Expiry Date
              </span>
              <p className="text-sm font-semibold text-gray-800 mt-1">
                {license.expiry_date || 'N/A'}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-200">
            <p className="text-sm font-semibold text-gray-700">No FSSAI License Record Found</p>
            <p className="text-xs text-gray-500 mt-1">
              Please upload your mandatory food safety certificate below to initiate kitchen verification.
            </p>
          </div>
        )}

        {/* Current Document Preview link */}
        {currentDoc && (
          <div className="p-3 bg-emerald-50/60 border border-emerald-200/80 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-emerald-700 shrink-0" />
              <div>
                <p className="text-xs font-bold text-gray-900">
                  {currentDoc.original_filename} (Version {currentDoc.version})
                </p>
                <p className="text-[10px] text-gray-500">
                  Uploaded on {new Date(currentDoc.uploaded_at).toLocaleString()} •{' '}
                  {(currentDoc.file_size_bytes / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <a
              href={`/api/v1/kitchen/license/document/${currentDoc.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 hover:border-gray-300 text-gray-800 rounded-lg text-xs font-semibold transition"
            >
              <span>View Document</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}
      </div>

      {/* Renewal / Correction Form Mode */}
      {activeMode !== 'view' && (
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div>
              <h3 className="text-base font-bold text-gray-900">
                Submit Updated License / Document
              </h3>
              <p className="text-xs text-gray-500">
                Upload a newly renewed certificate or replace an existing file. Previous versions will be archived in document history.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setActiveMode('view')}
              className="text-xs text-gray-500 hover:text-gray-800 font-semibold"
            >
              Cancel
            </button>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold">
              {error}
            </div>
          )}

          <form onSubmit={handleRenewalSubmit} className="space-y-4">
            <LicenseUploadSection
              initialLicenseNumber={formLicenseData.license_number}
              initialBusinessName={formLicenseData.business_name}
              initialExpiryDate={formLicenseData.expiry_date}
              required={true}
              onChange={(data) => setFormLicenseData(data)}
            />

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActiveMode('view')}
                disabled={submitting}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
              >
                {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>{submitting ? 'Submitting...' : 'Upload & Submit for Review'}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Document History Log */}
      {license?.documents && license.documents.length > 0 && (
        <div className="bg-white p-6 rounded-2xl border border-gray-200/80 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-gray-100">
            <History className="w-4 h-4 text-gray-500" />
            <h3 className="text-sm font-bold text-gray-900">Document Audit & Renewal History</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {license.documents.map((doc) => (
              <div key={doc.id} className="py-2.5 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      doc.is_current ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    v{doc.version} {doc.is_current ? '(Current)' : '(Archived)'}
                  </span>
                  <span className="font-semibold text-gray-800">{doc.original_filename}</span>
                  <span className="text-gray-400">
                    • {(doc.file_size_bytes / 1024).toFixed(1)} KB • {new Date(doc.uploaded_at).toLocaleDateString()}
                  </span>
                </div>
                <a
                  href={`/api/v1/kitchen/license/document/${doc.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-700 hover:text-emerald-900 font-semibold inline-flex items-center gap-1"
                >
                  <span>Download</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
