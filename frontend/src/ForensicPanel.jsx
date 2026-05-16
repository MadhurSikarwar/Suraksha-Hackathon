import React, { useState } from 'react';

const VAL = ({ v, className = '' }) => {
  if (v === null || v === undefined || v === 'N/A' || v === '') {
    return <span className="text-slate-600 italic text-xs">N/A</span>;
  }
  if (typeof v === 'boolean') {
    return (
      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
        v ? 'bg-red-500/20 text-red-400 border border-red-500/30'
          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
      } ${className}`}>
        {v ? 'YES' : 'NO'}
      </span>
    );
  }
  return <span className={`text-slate-200 font-mono text-xs break-all ${className}`}>{String(v)}</span>;
};

const Row = ({ label, value, alert = false }) => (
  <div className={`flex justify-between items-start py-2 border-b border-slate-800/60 gap-4 ${alert ? 'bg-red-500/5' : ''}`}>
    <span className={`text-xs shrink-0 w-48 ${alert ? 'text-red-400 font-semibold' : 'text-slate-500'}`}>{label}</span>
    <div className="text-right"><VAL v={value} /></div>
  </div>
);

const HashRow = ({ label, value }) => (
  <div className="py-2.5 border-b border-slate-800/60">
    <div className="text-xs text-slate-500 mb-1">{label}</div>
    <div className="font-mono text-xs text-emerald-400 break-all bg-slate-900/60 px-3 py-1.5 rounded border border-slate-700/50">
      {value || <span className="text-slate-600 italic">N/A</span>}
    </div>
  </div>
);

const Section = ({ title, icon, children, defaultOpen = false, accentColor = 'blue' }) => {
  const [open, setOpen] = useState(defaultOpen);
  const accents = {
    blue: 'border-blue-500/40 text-blue-400',
    red: 'border-red-500/40 text-red-400',
    purple: 'border-purple-500/40 text-purple-400',
    emerald: 'border-emerald-500/40 text-emerald-400',
    amber: 'border-amber-500/40 text-amber-400',
    cyan: 'border-cyan-500/40 text-cyan-400',
  };
  return (
    <div className={`border rounded-lg overflow-hidden mb-3 ${accents[accentColor]}`}
         style={{ borderWidth: '1px', background: 'rgba(15,23,42,0.6)' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{icon}</span>
          <span className={`font-bold text-sm tracking-wide ${accents[accentColor].split(' ')[1]}`}>{title}</span>
        </div>
        <span className="text-slate-500 text-xs">{open ? '▲ Collapse' : '▼ Expand'}</span>
      </button>
      {open && <div className="px-5 py-3 border-t border-slate-800/60">{children}</div>}
    </div>
  );
};

const AnomalyBadge = ({ label }) => (
  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded px-3 py-2 text-xs text-red-300 mb-2">
    <span className="text-red-500 mt-0.5 shrink-0">⚠</span>
    <span>{label}</span>
  </div>
);

const StatCard = ({ label, value, sub, color = 'blue' }) => {
  const colors = {
    blue: 'text-blue-400',
    red: 'text-red-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    purple: 'text-purple-400',
  };
  return (
    <div className="bg-slate-900/70 border border-slate-700/50 rounded-lg p-4 text-center">
      <div className="text-slate-500 text-xs uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-black ${colors[color]}`}>{value}</div>
      {sub && <div className="text-slate-600 text-xs mt-1">{sub}</div>}
    </div>
  );
};

export default function ForensicPanel({ forensicData, vitData }) {
  if (!forensicData) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500 text-sm">
        <span>No forensic data available for this document.</span>
      </div>
    );
  }

  const { cryptographic, file_identity, image_forensics, visual_signals, pdf_forensics, fraud_intelligence } = forensicData;
  const fi = fraud_intelligence || {};
  const vs = visual_signals || {};
  const img = image_forensics || {};
  const pdf = pdf_forensics || {};
  const fid = file_identity || {};
  const crypt = cryptographic || {};

  const riskColors = { CRITICAL: 'red', HIGH: 'red', MEDIUM: 'amber', LOW: 'emerald' };
  const riskColor = riskColors[fi.risk_category] || 'blue';

  return (
    <div className="space-y-4 animate-fade-up">

      {/* ── Summary KPI Strip ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <StatCard
          label="Fraud Confidence"
          value={`${fi.fraud_confidence_pct?.toFixed(1) ?? '–'}%`}
          sub={fi.risk_category}
          color={riskColor}
        />
        <StatCard
          label="Anomalies Found"
          value={fi.anomaly_count ?? 0}
          sub="detected signals"
          color={fi.anomaly_count > 0 ? 'red' : 'emerald'}
        />
        <StatCard
          label="ELA Tamper Score"
          value={vs.ela_mean_score?.toFixed(2) ?? '–'}
          sub={vs.ela_is_suspicious ? '⚠ Suspicious' : '✓ Clean'}
          color={vs.ela_is_suspicious ? 'red' : 'emerald'}
        />
        <StatCard
          label="Tampering Prob."
          value={`${vs.tampering_probability_pct ?? '–'}%`}
          sub="visual analysis"
          color={vs.tampering_probability_pct > 50 ? 'red' : 'emerald'}
        />
      </div>

      {/* ── Fraud Intelligence ── */}
      <Section title="Fraud Intelligence Summary" icon="🔴" defaultOpen={true} accentColor="red">
        <div className="mb-4">
          <div className="flex items-center gap-3 mb-3">
            <span className={`px-3 py-1 rounded-full text-xs font-black border ${
              fi.risk_category === 'CRITICAL' || fi.risk_category === 'HIGH'
                ? 'bg-red-500/20 text-red-400 border-red-500/30'
                : fi.risk_category === 'MEDIUM'
                ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
            }`}>{fi.risk_category || 'N/A'}</span>
            <span className="text-slate-400 text-sm">{fi.potential_forgery_type || '–'}</span>
          </div>

          {fi.detected_anomalies?.length > 0 ? (
            <div className="mb-4">
              {fi.detected_anomalies.map((a, i) => <AnomalyBadge key={i} label={a} />)}
            </div>
          ) : (
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded px-3 py-2 text-xs text-emerald-400 mb-4">
              ✓ No forensic anomalies detected
            </div>
          )}
        </div>
        <Row label="Recommended Action" value={fi.recommended_action} />
        <Row label="Legal Defensibility" value={fi.legal_defensibility} />
        <Row label="Integrity Verified" value={fi.integrity_verified} />
        <Row label="Duplicate Doc. Probability" value={fi.duplicate_document_probability !== undefined ? `${fi.duplicate_document_probability}%` : 'N/A'} />
      </Section>

      {/* ── Cryptographic Fingerprints ── */}
      <Section title="Cryptographic Fingerprints" icon="🔑" accentColor="emerald">
        <HashRow label="MD5 Hash" value={crypt.md5} />
        <HashRow label="SHA-1 Hash" value={crypt.sha1} />
        <HashRow label="SHA-256 Hash (Primary Fingerprint)" value={crypt.sha256} />
        <div className="mt-3 text-xs text-slate-600 italic">
          These hashes uniquely identify this exact document. Any single byte change produces a completely different hash.
          Suitable as evidence under IT Act 2000, Sec 65B.
        </div>
      </Section>

      {/* ── File Identity ── */}
      <Section title="File Identity & Structure" icon="📄" accentColor="blue">
        <Row label="File Size" value={fid.file_size_human} />
        <Row label="Raw Size (bytes)" value={fid.file_size_bytes?.toLocaleString()} />
        <Row label="Extension" value={fid.file_extension} />
        <Row label="MIME (Magic Bytes)" value={fid.mime_type_detected} />
        <Row label="MIME (From Extension)" value={fid.mime_type_from_extension} />
        <Row label="MIME Mismatch" value={fid.mime_mismatch} alert={fid.mime_mismatch} />
        <Row label="FS Created" value={fid.fs_created} />
        <Row label="FS Modified" value={fid.fs_modified} />
        <Row label="FS Accessed" value={fid.fs_accessed} />
      </Section>

      {/* ── Visual Forensic Signals ── */}
      {Object.keys(vs).length > 0 && !vs.error && (
        <Section title="Visual Forensic Signals (ELA)" icon="👁" accentColor="purple">
          <Row label="ELA Mean Score" value={vs.ela_mean_score} alert={vs.ela_is_suspicious} />
          <Row label="ELA Max Score" value={vs.ela_max_score} />
          <Row label="ELA Std Deviation" value={vs.ela_std_deviation} />
          <Row label="Suspicious (ELA)" value={vs.ela_is_suspicious} alert={vs.ela_is_suspicious} />
          <Row label="High Anomaly Regions" value={`${vs.ela_anomaly_regions} / 16 blocks`} alert={vs.ela_anomaly_regions > 4} />
          <Row label="Region Variance" value={vs.ela_region_variance} />
          <Row label="Noise (Left Half)" value={vs.noise_left_half} />
          <Row label="Noise (Right Half)" value={vs.noise_right_half} />
          <Row label="Noise L/R Ratio" value={vs.noise_ratio_lr} alert={vs.noise_inconsistency_flag} />
          <Row label="Noise Inconsistency" value={vs.noise_inconsistency_flag} alert={vs.noise_inconsistency_flag} />
          <Row label="Laplacian Sharpness" value={vs.laplacian_sharpness} />
          <Row label="Double-JPEG Indicator" value={vs.double_jpeg_indicator} alert={vs.double_jpeg_indicator} />
          <Row label="Tampering Probability" value={`${vs.tampering_probability_pct}%`} alert={vs.tampering_probability_pct > 50} />
        </Section>
      )}

      {/* ── Vision Transformer Analysis ── */}
      {vitData && vitData.score !== undefined && vitData.score !== null && (
        <Section title="Vision Transformer Analysis" icon="🧠" defaultOpen={true} accentColor="purple">
          <Row label="ViT Anomaly Score" value={vitData.score} alert={vitData.score > 60} />
          <Row label="ViT Confidence" value={vitData.confidence} />
          {vitData.indicators && vitData.indicators.length > 0 && (
            <div className="mt-3 mb-2 px-1">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">ViT Visual Indicators</div>
              {vitData.indicators.map((ind, i) => (
                <div key={i} className="text-sm text-slate-300 py-1 flex items-start gap-2">
                  <span className="text-purple-400 mt-0.5">•</span>
                  <span>{ind}</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* ── Image Metadata / EXIF ── */}
      {Object.keys(img).length > 0 && !img.error && (
        <Section title="Image Metadata & EXIF" icon="📸" accentColor="cyan">
          <Row label="Dimensions" value={img.dimensions} />
          <Row label="Color Mode" value={img.color_mode} />
          <Row label="Color Channels" value={img.color_channels} />
          <Row label="DPI" value={img.dpi} />
          <Row label="Format" value={img.format} />
          <Row label="Has Transparency" value={img.has_transparency} />
          <Row label="EXIF Fields Found" value={img.exif_field_count} />
          <Row label="GPS Embedded" value={img.has_gps} alert={img.has_gps} />
          <Row label="GPS Data" value={img.gps_raw} />
          {img.editing_software_detected?.length > 0 && (
            <Row
              label="Editing Software"
              value={img.editing_software_detected.join(', ')}
              alert={true}
            />
          )}
          {img.exif && Object.keys(img.exif).length > 0 && (
            <div className="mt-3">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Full EXIF Data</div>
              <div className="max-h-48 overflow-y-auto rounded border border-slate-700/50 bg-slate-900/50">
                {Object.entries(img.exif).slice(0, 40).map(([k, v]) => (
                  <div key={k} className="flex justify-between items-start px-3 py-1.5 border-b border-slate-800/50 gap-3">
                    <span className="text-xs text-slate-500 shrink-0 w-40">{k}</span>
                    <span className="text-xs text-slate-300 font-mono text-right break-all">{String(v).slice(0, 80)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>
      )}

      {/* ── PDF Structure Forensics ── */}
      {Object.keys(pdf).length > 0 && !pdf.error && (
        <Section title="PDF Structure Forensics" icon="📋" accentColor="amber">
          <Row label="Page Count" value={pdf.page_count} />
          <Row label="Page Sizes" value={pdf.page_sizes?.join(', ')} />
          <Row label="Embedded Images" value={pdf.embedded_images} />
          <Row label="Embedded Fonts" value={pdf.embedded_fonts} />
          <Row label="Font Names" value={pdf.font_names?.join(', ')} />
          <Row label="Producer Tool" value={pdf.producer} alert={pdf.suspicious_producer} />
          <Row label="Creator Tool" value={pdf.creator_tool} alert={pdf.suspicious_producer} />
          <Row label="Author" value={pdf.author} />
          <Row label="Title" value={pdf.title} />
          <Row label="Keywords" value={pdf.keywords} />
          <Row label="Creation Date" value={pdf.creation_date} />
          <Row label="Modification Date" value={pdf.modification_date} />
          <Row label="Date Mismatch" value={pdf.date_mismatch} alert={pdf.date_mismatch} />
          <Row label="Suspicious Producer" value={pdf.suspicious_producer} alert={pdf.suspicious_producer} />
          <Row label="Incremental Saves" value={pdf.incremental_saves} alert={pdf.incremental_saves} />
          <Row label="EOF Markers Found" value={pdf.eof_markers_found} alert={pdf.eof_markers_found > 1} />
          <Row label="Embedded JavaScript" value={pdf.has_javascript} alert={pdf.has_javascript} />
          <Row label="Embedded Attachments" value={pdf.has_attachments} />
          <Row label="Encrypted" value={pdf.pdf_encrypted} />
        </Section>
      )}

      <div className="text-center text-slate-700 text-xs pt-2 pb-1">
        Forensic report generated by Suraksha Intelligence · {new Date().toLocaleString()}
      </div>
    </div>
  );
}
