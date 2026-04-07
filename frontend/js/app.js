/* ═══════════════════════════════════════════════════════════════
   DocFlow – Frontend Application
   ═══════════════════════════════════════════════════════════════ */

const API = '/api';

// ─── State ────────────────────────────────────────────────────
let state = {
  activeTab: 'invoice',        // 'invoice' | 'sales_tax'
  activeFilter: 'all',         // 'all' | 'complete' | 'pending' | 'in_progress'
  documents: [],               // raw documents from API
  currentDocId: null,          // document open in modal
  editMode: false,
  originalValues: {},          // field name → original value (for cancel)
};

// ─── DOM helpers ─────────────────────────────────────────────
const $ = id => document.getElementById(id);
const show = el => el.classList.remove('hidden');
const hide = el => el.classList.add('hidden');

// ─── Toast ────────────────────────────────────────────────────
function toast(msg, duration = 2800) {
  const t = $('toast');
  t.textContent = msg;
  show(t);
  clearTimeout(t._timer);
  t._timer = setTimeout(() => hide(t), duration);
}

// ─── Status badge ─────────────────────────────────────────────
function statusBadge(status) {
  const labels = {
    complete: 'Sent To ERP',
    pending: 'Pending',
    in_progress: 'In Progress',
  };
  return `<span class="badge badge-${status}">${labels[status] || status}</span>`;
}

// ─── Confidence tag ───────────────────────────────────────────
function confTag(conf) {
  const cls = conf >= 0.8 ? 'conf-high' : conf >= 0.5 ? 'conf-medium' : 'conf-low';
  const pct = (conf * 100).toFixed(0);
  return `<span class="conf-score ${cls}" title="Confidence: ${pct}%">${pct}%</span>`;
}

// ─── Field label prettifier ────────────────────────────────────
function prettyField(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ─── Load documents ───────────────────────────────────────────
async function loadDocuments() {
  try {
    const url = state.activeTab === 'invoice'
      ? `${API}/documents?type=invoice`
      : `${API}/documents?type=sales_tax`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.documents = await res.json();
    updateSummaryCards();
    renderTable();
  } catch (err) {
    console.error('Load documents failed:', err);
    $('tableBody').innerHTML = `
      <tr class="empty-row"><td colspan="10">
        <div class="empty-state">
          <div class="empty-icon">⬡</div>
          <p>Failed to load documents. Is the backend running?</p>
        </div>
      </td></tr>`;
  }
}

// ─── Summary cards ────────────────────────────────────────────
function updateSummaryCards() {
  const docs = state.documents;
  const total = docs.length;
  const complete = docs.filter(d => d.status === 'complete').length;
  const pending = docs.filter(d => d.status === 'pending').length;
  const inProgress = docs.filter(d => d.status === 'in_progress').length;

  $('totalCount').textContent = total;
  $('completeCount').textContent = complete;
  $('pendingCount').textContent = pending;
  $('inProgressCount').textContent = inProgress;
}

// ─── Filter documents ─────────────────────────────────────────
function filteredDocs() {
  if (state.activeFilter === 'all') return state.documents;
  return state.documents.filter(d => d.status === state.activeFilter);
}

// ─── Render table ─────────────────────────────────────────────
function renderTable() {
  const docs = filteredDocs();
  const body = $('tableBody');

  if (!docs.length) {
    body.innerHTML = `
      <tr class="empty-row"><td colspan="10">
        <div class="empty-state">
          <div class="empty-icon">⬡</div>
          <p>No documents found.</p>
        </div>
      </td></tr>`;
    return;
  }

  body.innerHTML = docs.map(doc => {
    const ed = doc.extracted_data || {};
    const val = (f) => ed[f]?.value || '—';
    const filename = doc.filename || doc.document_id;
    
    const fieldKeys = Object.keys(ed);
    let avgConf = 0;
    if (fieldKeys.length > 0) {
      const totalConf = fieldKeys.reduce((sum, k) => sum + (ed[k].confidence || 0), 0);
      avgConf = totalConf / fieldKeys.length;
    }
    const colorKey = avgConf >= 0.8 ? 'green' : avgConf >= 0.5 ? 'yellow' : 'red';
    const borderColor = colorKey === 'green' ? 'rgba(34,197,94,.3)' : colorKey === 'yellow' ? 'rgba(245,158,11,.3)' : 'rgba(239,68,68,.3)';
    const pctStr = (avgConf * 100).toFixed(0);
    const confHTML = `
      <div style="display:flex; flex-direction:column; gap:6px; max-width:70px;">
        <span class="badge" style="width:fit-content; background:var(--${colorKey}-bg); color:var(--${colorKey}); border:1px solid ${borderColor};">${pctStr}%</span>
        <div style="height:4px; width:100%; background:var(--border2); border-radius:2px; overflow:hidden;">
          <div style="height:100%; width:${pctStr}%; background:var(--${colorKey}); transition:width 0.3s ease;"></div>
        </div>
      </div>`;

    return `
    <tr>
      <td><a class="file-link" href="#" data-id="${doc.document_id}">${filename}</a></td>
      <td>${val('invoice_id')}</td>
      <td>${val('invoice_date')}</td>
      <td>${val('customer_address')}</td>
      <td>${val('vendor_address')}</td>
      <td>${val('net_amount')}</td>
      <td>${val('grand_total')}</td>
      <td>${confHTML}</td>
      <td>${statusBadge(doc.status)}</td>
      <td>
        <button class="btn-view" data-id="${doc.document_id}">View</button>
      </td>
    </tr>`;
  }).join('');

  // Click handlers
  body.querySelectorAll('[data-id]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      openDetail(el.dataset.id);
    });
  });
}

// ─── Open detail modal ────────────────────────────────────────
async function openDetail(docId) {
  state.currentDocId = docId;
  state.editMode = false;

  const modal = $('detailModal');
  show(modal);

  try {
    const res = await fetch(`${API}/documents/${docId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const doc = await res.json();

    // Set filename
    $('modalFilename').textContent = doc.filename || doc.document_id;

    // Status badge
    const statusEl = $('detailStatus');
    statusEl.className = `status-badge badge badge-${doc.status}`;
    statusEl.textContent = {
      complete: 'Sent To ERP',
      pending: 'Pending',
      in_progress: 'In Progress',
    }[doc.status] || doc.status;

    // Buttons
    const editBtn = $('editBtn');
    const submitBtn = $('submitBtn');
    hide(editBtn);
    hide(submitBtn);

    if (doc.status === 'pending') {
      show(editBtn);
    } else if (doc.status === 'in_progress') {
      show(submitBtn);
    }

    // Load PDF
    try {
      const urlRes = await fetch(`${API}/documents/${docId}/signed-url`);
      if (urlRes.ok) {
        const { signed_url } = await urlRes.json();
        $('pdfViewer').src = signed_url;
        $('openPdfBtn').href = signed_url;
      }
    } catch (_) {
      $('pdfViewer').src = '';
    }

    // Render fields
    renderFields(doc);

  } catch (err) {
    console.error('Load document detail failed:', err);
    toast('Failed to load document details.');
  }
}

// ─── Render fields ────────────────────────────────────────────
const FIELD_ORDER = [
  'invoice_id', 'invoice_date', 'customer_address',
  'vendor_address', 'net_amount', 'grand_total',
];

function renderFields(doc) {
  const ed = doc.extracted_data || {};
  const tbody = $('fieldsBody');

  // Include all known fields + any extras in extracted_data
  const allFields = [...new Set([...FIELD_ORDER, ...Object.keys(ed)])];

  tbody.innerHTML = allFields.map(key => {
    if (key === 'exception_reason') return ''; // handled separately
    const fieldData = ed[key] || { value: '', confidence: 0, manually_edited: false };
    const val = fieldData.value || '';
    const conf = fieldData.confidence || 0;
    const edited = fieldData.manually_edited;

    return `
    <tr data-field="${key}">
      <td class="field-name">${prettyField(key)}</td>
      <td class="field-value">
        <span class="fv-display">
          ${val || '<span style="color:var(--text-muted)">—</span>'}
          ${confTag(conf)}
          ${edited ? '<span class="edited-tag">edited</span>' : ''}
        </span>
        <input class="fv-input hidden" type="text" value="${escHtml(val)}" data-original="${escHtml(val)}" />
      </td>
    </tr>`;
  }).join('');

  // exception_reason row
  const exReason = doc.exception_reason || 'NA';
  tbody.innerHTML += `
    <tr>
      <td class="field-name">Exception Reason</td>
      <td class="field-value">${exReason}</td>
    </tr>`;

  hide($('editActions'));
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

// ─── Edit mode toggle ─────────────────────────────────────────
function enterEditMode() {
  state.editMode = true;
  $('fieldsBody').querySelectorAll('[data-field]').forEach(row => {
    row.querySelector('.fv-display').classList.add('hidden');
    row.querySelector('.fv-input').classList.remove('hidden');
  });
  show($('editActions'));
  hide($('editBtn'));
}

function exitEditMode() {
  state.editMode = false;
  $('fieldsBody').querySelectorAll('[data-field]').forEach(row => {
    const input = row.querySelector('.fv-input');
    input.value = input.dataset.original; // restore
    row.querySelector('.fv-display').classList.remove('hidden');
    input.classList.add('hidden');
  });
  hide($('editActions'));
  show($('editBtn'));
}

// ─── Save edits ───────────────────────────────────────────────
async function saveEdits() {
  const edits = {};
  let hasEmptyField = false;

  $('fieldsBody').querySelectorAll('[data-field]').forEach(row => {
    const field = row.dataset.field;
    const input = row.querySelector('.fv-input');
    if (input) {
      if (!input.value.trim()) {
        hasEmptyField = true;
      }
      if (input.value !== input.dataset.original) {
        edits[field] = input.value;
      }
    }
  });

  if (hasEmptyField) {
    toast('Cannot save. All fields must be filled.');
    return;
  }

  try {
    const res = await fetch(`${API}/documents/${state.currentDocId}/edits`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ edits }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast('Changes saved. Status → In Progress.');
    await openDetail(state.currentDocId); // refresh
    await loadDocuments();
  } catch (err) {
    toast('Failed to save changes.');
    console.error(err);
  }
}

// ─── Submit to ERP ────────────────────────────────────────────
async function submitToERP() {
  if (!confirm('Submit this document to ERP? This will mark it as complete.')) return;
  try {
    const res = await fetch(`${API}/documents/${state.currentDocId}/submit`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast('Document sent to ERP ✓');
    await openDetail(state.currentDocId);
    await loadDocuments();
  } catch (err) {
    toast('Failed to submit document.');
    console.error(err);
  }
}

// ─── Trigger pipeline ─────────────────────────────────────────
async function triggerPipeline() {
  const spinner = $('pipelineSpinner');
  const label = $('triggerLabel');
  show(spinner);
  label.textContent = 'Running…';
  try {
    await fetch(`${API}/pipeline/run`, { method: 'POST' });
    toast('Pipeline cycle triggered in background.');
    setTimeout(loadDocuments, 3000); // reload after a moment
  } catch (err) {
    toast('Failed to trigger pipeline.');
  } finally {
    hide(spinner);
    label.textContent = '↺ Sync';
  }
}

async function syncBucketFromGcs() {
  const spinner = $('bucketSpinner');
  const label = $('bucketLabel');
  show(spinner);
  label.textContent = 'Importing…';
  try {
    const res = await fetch(`${API}/pipeline/sync-bucket`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast('GCS bucket import started.');
    setTimeout(loadDocuments, 5000);
  } catch (err) {
    toast('Failed to import from GCS bucket.');
  } finally {
    hide(spinner);
    label.textContent = '⇣ Import';
  }
}

// ─── Tab switching ────────────────────────────────────────────
function setActiveTab(tab) {
  state.activeTab = tab;
  state.activeFilter = 'all';

  document.querySelectorAll('#mainTabs .tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });

  document.querySelectorAll('.pill').forEach(p => {
    p.classList.toggle('active', p.dataset.filter === 'all');
  });

  $('pageTitle').textContent = tab === 'invoice'
    ? 'Invoice — Dashboard'
    : 'Sales Tax Exempt — Dashboard';

  loadDocuments();
}

// ─── Filter switching ─────────────────────────────────────────
function setFilter(filter) {
  state.activeFilter = filter;
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.toggle('active', p.dataset.filter === filter);
  });
  const titles = {
    all: 'All Documents',
    complete: 'Completed (Sent to ERP)',
    pending: 'Exceptions (Pending)',
    in_progress: 'In Progress',
  };
  $('tableTitle').textContent = titles[filter] || 'All Documents';
  renderTable();
}

// ─── Event wiring ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Main tabs
  document.querySelectorAll('#mainTabs .tab').forEach(btn => {
    btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
  });

  // Summary card buttons
  document.querySelectorAll('.card-btn').forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter));
  });

  // Filter pills
  document.querySelectorAll('.pill').forEach(pill => {
    pill.addEventListener('click', () => setFilter(pill.dataset.filter));
  });

  // Pipeline trigger
  $('triggerPipeline').addEventListener('click', triggerPipeline);
  $('syncBucket').addEventListener('click', syncBucketFromGcs);

  // Modal close
  $('modalClose').addEventListener('click', () => {
    hide($('detailModal'));
    state.editMode = false;
    state.currentDocId = null;
  });

  // Close modal on overlay click
  $('detailModal').addEventListener('click', (e) => {
    if (e.target === $('detailModal')) hide($('detailModal'));
  });

  // Edit button
  $('editBtn').addEventListener('click', enterEditMode);

  // Save button
  $('saveBtn').addEventListener('click', saveEdits);

  // Cancel button
  $('cancelBtn').addEventListener('click', exitEditMode);

  // Submit button
  $('submitBtn').addEventListener('click', submitToERP);

  // Initial load
  loadDocuments();

  // Auto-refresh every 30s
  setInterval(loadDocuments, 30_000);
});
