/**
 * Allocated Orders panel for the User Dashboard.
 *
 * Fetches the current employee's open allocations, renders them in the
 * #allocated-orders-table, and keeps the table live by subscribing to
 * realtime events on the shared bus.
 *
 * This is an ES6 module so it can import from the core bus/toast stack.
 */

import { bus } from "../core/bus.js";
import { toast } from "../core/toast.js";

const CSRF = () =>
  (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
  document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
  "";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" });
}

function statusBadge(status) {
  const map = {
    pending: "badge-pending",
    search_in_progress: "badge-inprogress",
    qc_in_progress: "badge-inprogress",
    completed: "badge-completed",
    on_hold: "badge-onhold",
    cancelled: "badge-cancelled",
    dispatch: "badge-dispatch",
    ready_for_qc: "badge-sendforqc"
  };
  const cls = map[status.toLowerCase()] || map[status] || "badge-pending";
  let label = status || "pending";
  if (label.toLowerCase() === 'ready_for_qc') label = 'Ready for QC';
  else if (label.toLowerCase() === 'search_in_progress') label = 'Search In Progress';
  else if (label.toLowerCase() === 'qc_in_progress') label = 'QC In Progress';
  else if (label.toLowerCase() === 'completed') label = 'Search Complete';
  else label = label.replace(/_+/g, " ");
  return `<span class="alloc-status-badge ${cls}">${label}</span>`;
}

// ── render ────────────────────────────────────────────────────────────────────

function renderRow(alloc, hasActiveTask = false) {
  const currentEmpId = document.getElementById("user-name")?.dataset?.employeeId;
  const isAssignedEmployee = alloc.employee_id === currentEmpId;
  const isAssignedQC = alloc.qc_id === currentEmpId;

  let currentRole = "Search";
  if (isAssignedQC && !isAssignedEmployee) {
    currentRole = "QC";
  } else if (isAssignedEmployee && !isAssignedQC) {
    currentRole = "Search";
  } else if (isAssignedEmployee && isAssignedQC) {
    // If assigned both roles, role switches to QC after search completes
    if (["ready_for_qc", "qc_in_progress", "dispatch", "completed"].includes((alloc.status || "").toLowerCase())) {
      currentRole = "QC";
    } else {
      currentRole = "Search";
    }
  }
  const isQC = currentRole === "QC";

  const tr = document.createElement("tr");
  if (alloc.is_overdue) tr.classList.add("alloc-row-overdue");

  tr.innerHTML = `
    <td style="display:none;">${alloc.client_code || "-"}</td>
    <td>${alloc.work_type || "-"}</td>
    <td>${alloc.order_id || "-"}</td>
    <td>${alloc.ar_number || "-"}</td>
    <td>${alloc.owner_name || "-"}</td>
    <td>${alloc.property_address || "-"}</td>
    <td>${alloc.state || "-"}</td>
    <td>${alloc.county || "-"}</td>
    <td>${fmtDate(alloc.allocated_at)}</td>
    <td>${alloc.due_at ? fmtDate(alloc.due_at) : "-"}</td>
    <td>${statusBadge(alloc.status)}</td>
    <td><span style="font-weight: 500; color: ${isQC ? '#8e24aa' : '#1e8449'}; background: ${isQC ? '#f3e5f5' : '#e8f5e9'}; padding: 4px 8px; border-radius: 4px; font-size: 11px;">${currentRole}</span></td>
    <td>
      ${(alloc.status === "pending" && !isQC) || (["ready_for_qc", "completed"].includes(alloc.status) && isQC) ? `
      <button
        class="alloc-start-btn action-btn"
        data-allocation-id="${alloc.allocation_id}"
        data-project="${alloc.project || ''}"
        data-client-code="${alloc.client_code || ''}"
        data-work-type="${alloc.work_type || ''}"
        data-batch="${alloc.batch || alloc.order_id || ''}"
        data-target-status="${isQC ? 'qc_in_progress' : 'search_in_progress'}"
        data-is-qc="${isQC}"
        data-has-qc="${!!alloc.qc_id}"
        title="${hasActiveTask ? 'Complete your active task first' : 'Start this order'}"
        ${hasActiveTask ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}
      >
        <i class="fas fa-play"></i>
      </button>
      ` : alloc.status === "search_in_progress" && !isQC ? `
      <button
        class="alloc-complete-btn action-btn"
        data-allocation-id="${alloc.allocation_id}"
        data-has-qc="${!!alloc.qc_id}"
        title="Complete this order"
      >
        <i class="fas fa-check-circle"></i>
      </button>
      ` : alloc.status === "qc_in_progress" && isQC ? `
      <button
        class="alloc-review-btn action-btn"
        data-allocation-id="${alloc.allocation_id}"
        data-is-qc="true"
        title="Review this order"
        style="background: #10b981; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 500;"
      >
        <i class="fas fa-search"></i> Review
      </button>
      ` : `
      <button class="action-btn" disabled><i class="fas fa-check"></i></button>
      `}
    </td>
  `;
  tr.style.cursor = "pointer";
  tr.addEventListener("click", (e) => {
    if (e.target.closest("button") || e.target.tagName.toLowerCase() === "button") return;
    showOrderDetailsModal(alloc);
  });

  return tr;
}

function showOrderDetailsModal(alloc) {
  const modal = document.getElementById("orderDetailsModal");
  const content = document.getElementById("orderDetailsContent");

  let html = `
    <div class="oa-details-container">
        <div class="oa-details-header">
            <h3 style="color: white;"><i class="fas fa-file-alt"></i> Order Details: ${alloc.ar_number || "-"}</h3>
            <div class="oa-details-actions">
                <button class="oa-details-close" style="color: white;">&times;</button>
            </div>
        </div>
        <div class="oa-details-body">
            
            <div style="margin-bottom: 15px;">
              <strong>General Instructions:</strong>
              <p style="background: #f8f9fa; padding: 10px; border-radius: 4px; border-left: 4px solid #007bff; margin-top: 5px;">
                ${alloc.general_instructions ? alloc.general_instructions.replace(/\n/g, '<br>') : "<i>No general instructions provided.</i>"}
              </p>
            </div>
            
            <div style="margin-bottom: 20px;">
              <strong>Special Instructions:</strong>
              <p style="background: #e9ecef; padding: 10px; border-radius: 4px; margin-top: 5px;">
                ${alloc.remarks ? alloc.remarks.replace(/\n/g, '<br>') : "<i>No specific remarks provided.</i>"}
              </p>
            </div>
            ${alloc.employee_comments ? `
            <div style="margin-bottom: 20px;">
              <strong>Employee Comments:</strong>
              <p style="background: #e2e3e5; padding: 10px; border-radius: 4px; border-left: 4px solid #6c757d; margin-top: 5px;">
                ${alloc.employee_comments.replace(/\n/g, '<br>')}
              </p>
            </div>
            ` : ''}
            
            ${alloc.qc_comments ? `
            <div style="margin-bottom: 20px;">
              <strong>QC Comments:</strong>
              <p style="background: #fff3cd; padding: 10px; border-radius: 4px; border-left: 4px solid #ffc107; margin-top: 5px;">
                ${alloc.qc_comments.replace(/\n/g, '<br>')}
              </p>
            </div>
            ` : ''}
            
            <div class="oa-details-grid">
                <div class="oa-detail-item" style="display:none;">
                    <div class="oa-detail-label">Client Code</div>
                    <div class="oa-detail-value">${alloc.client_code || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Work Type</div>
                    <div class="oa-detail-value">${alloc.work_type || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Order Type</div>
                    <div class="oa-detail-value">${alloc.order_id || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">AR Number</div>
                    <div class="oa-detail-value">${alloc.ar_number || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Owner Name</div>
                    <div class="oa-detail-value">${alloc.owner_name || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Property Address</div>
                    <div class="oa-detail-value">${alloc.property_address || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">State</div>
                    <div class="oa-detail-value">${alloc.state || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">County</div>
                    <div class="oa-detail-value">${alloc.county || '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Received Date</div>
                    <div class="oa-detail-value">${fmtDate(alloc.allocated_at)}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">ETA</div>
                    <div class="oa-detail-value">${alloc.due_at ? fmtDate(alloc.due_at) : '-'}</div>
                </div>
                <div class="oa-detail-item">
                    <div class="oa-detail-label">Status</div>
                    <div class="oa-detail-value">${statusBadge(alloc.status)}</div>
                </div>
            </div>
            
            <div class="oa-documents-section" style="margin-top: 20px;">
                <div class="oa-documents-header">
                    <h4><i class="fas fa-file-upload"></i> Attachments </h4>
                </div>
                <div class="oa-documents-grid">
                    ${(() => {
      let docsHtml = '';
      if (alloc.document_name) {
        docsHtml += `
                                <div class="oa-document-item" style="display: flex; align-items: center; background: #f8f9fa; padding: 10px; border-radius: 4px; border: 1px solid #dee2e6; margin-bottom: 10px;">
                                    <div class="oa-document-icon" style="font-size: 24px; color: #dc3545; margin-right: 15px;">
                                        <i class="fas fa-file-pdf"></i>
                                    </div>
                                    <div class="oa-document-info">
                                        <span class="oa-document-name" style="display: block; font-weight: 500; margin-bottom: 5px;">${alloc.document_name}</span>
                                        <!-- Downloads Disabled
                                        <a href="/api/v1/allocations/${alloc.allocation_id}/download/" download class="oa-document-download" style="color: #007bff; text-decoration: none; font-size: 14px;">
                                            <i class="fas fa-download"></i> Download Original
                                        </a>
                                        -->
                                    </div>
                                </div>
                            `;
      }
      if (alloc.chain_sheet_name) {
        docsHtml += `
                                <div class="oa-document-item" style="display: flex; align-items: center; background: #f8f9fa; padding: 10px; border-radius: 4px; border: 1px solid #dee2e6; margin-bottom: 10px;">
                                    <div class="oa-document-icon" style="font-size: 24px; color: #28a745; margin-right: 15px;">
                                        <i class="fas fa-file-excel"></i>
                                    </div>
                                    <div class="oa-document-info">
                                        <span class="oa-document-name" style="display: block; font-weight: 500; margin-bottom: 5px;">${alloc.chain_sheet_name}</span>
                                        <!-- Downloads Disabled
                                        <a href="/api/v1/allocations/${alloc.allocation_id}/download/?doc=chain_sheet" download class="oa-document-download" style="color: #007bff; text-decoration: none; font-size: 14px;">
                                            <i class="fas fa-download"></i> Download Chain Sheet
                                        </a>
                                        -->
                                    </div>
                                </div>
                            `;
      }
      if (alloc.search_package_name) {
        docsHtml += `
                                <div class="oa-document-item" style="display: flex; align-items: center; background: #f8f9fa; padding: 10px; border-radius: 4px; border: 1px solid #dee2e6; margin-bottom: 10px;">
                                    <div class="oa-document-icon" style="font-size: 24px; color: #dc3545; margin-right: 15px;">
                                        <i class="fas fa-file-pdf"></i>
                                    </div>
                                    <div class="oa-document-info">
                                        <span class="oa-document-name" style="display: block; font-weight: 500; margin-bottom: 5px;">${alloc.search_package_name}</span>
                                        <!-- Downloads Disabled
                                        <a href="/api/v1/allocations/${alloc.allocation_id}/download/?doc=search_package" download class="oa-document-download" style="color: #007bff; text-decoration: none; font-size: 14px;">
                                            <i class="fas fa-download"></i> Download Search Package
                                        </a>
                                        -->
                                    </div>
                                </div>
                            `;
      }
      if (alloc.report_name) {
        docsHtml += `
                                <div class="oa-document-item" style="display: flex; align-items: center; background: #f8f9fa; padding: 10px; border-radius: 4px; border: 1px solid #dee2e6; margin-bottom: 10px;">
                                    <div class="oa-document-icon" style="font-size: 24px; color: #007bff; margin-right: 15px;">
                                        <i class="fas fa-file-word"></i>
                                    </div>
                                    <div class="oa-document-info">
                                        <span class="oa-document-name" style="display: block; font-weight: 500; margin-bottom: 5px;">${alloc.report_name}</span>
                                        <!-- Downloads Disabled
                                        <a href="/api/v1/allocations/${alloc.allocation_id}/download/?doc=report" download class="oa-document-download" style="color: #007bff; text-decoration: none; font-size: 14px;">
                                            <i class="fas fa-download"></i> Download Report
                                        </a>
                                        -->
                                    </div>
                                </div>
                            `;
      }

      return docsHtml ? docsHtml : '<div class="oa-no-documents">No documents attached</div>';
    })()}
                </div>
            </div>
            
        </div>
    </div>
  `;

  content.innerHTML = html;
  modal.style.display = "flex";
  // Add animation class after a tiny delay
  setTimeout(() => modal.classList.add("show"), 10);

  // Bind close button
  const closeBtn = content.querySelector(".oa-details-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.remove("show");
      setTimeout(() => (modal.style.display = "none"), 300);
    });
  }
}

// Setup modal close handlers
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("orderDetailsModal");

  window.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("show");
      setTimeout(() => (modal.style.display = "none"), 300);
    }
  });
});

// ── data loading ─────────────────────────────────────────────────────────────

async function loadAllocatedOrders() {
  const table = document.getElementById("allocated-orders-table");
  if (!table) return;

  const tbody = table.querySelector("tbody");
  const empty = document.getElementById("allocated-orders-empty");
  const badge = document.getElementById("allocated-orders-badge");
  const spinner = document.getElementById("allocated-orders-spinner");

  if (spinner) spinner.style.display = "inline-block";

  try {
    const res = await fetch("/api/v1/allocations/mine/", {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const payload = await res.json();
    // API wraps results: { success: true, data: [...] } or just [...]
    const items = Array.isArray(payload)
      ? payload
      : Array.isArray(payload.data)
        ? payload.data
        : [];

    tbody.innerHTML = "";
    const hasActiveTask = items.some(a => a.status === "search_in_progress" || a.status === "qc_in_progress");
    items.forEach((alloc) => tbody.appendChild(renderRow(alloc, hasActiveTask)));

    if (empty) empty.hidden = items.length > 0;
    if (badge) {
      const openCount = items.filter((a) => a.status === "pending").length;
      badge.textContent = openCount > 99 ? "99+" : String(openCount);
      badge.hidden = openCount === 0;
    }
  } catch (err) {
    console.error("Failed to load allocated orders:", err);
  } finally {
    if (spinner) spinner.style.display = "none";
  }
}

// ── actions ───────────────────────────────────────────────────────────────────

async function markInProgress(btn) {
  const startBtn = document.getElementById('start-btn');
  if (startBtn && startBtn.innerText === "End") {
    if (typeof toast !== 'undefined') {
      toast.show("Please end your current work session before starting a new one.", { type: "warning" });
    } else {
      alert("Please end your current work session before starting a new one.");
    }
    return;
  }

  const allocationId = btn.dataset.allocationId;
  const project = btn.dataset.project;
  const clientCode = btn.dataset.clientCode;
  const workType = btn.dataset.workType;
  const batch = btn.dataset.batch;

  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

  try {
    const res = await fetch(`/api/v1/allocations/${allocationId}/status/`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": CSRF(),
      },
      body: JSON.stringify({ status: btn.dataset.targetStatus || "search_in_progress" }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Auto-start tracking session
    if (window.startAllocatedWorkSession) {
      const isQC = btn.dataset.isQc === "true";
      const hasQC = btn.dataset.hasQc === "true";
      await window.startAllocatedWorkSession({
        allocation_id: allocationId,
        project: project,
        client_code: clientCode,
        work_type: workType,
        batch: batch,
        is_qc: isQC,
        has_qc: hasQC
      });
    }

    toast.show("Order started", { type: "success" });
    await loadAllocatedOrders();
  } catch (err) {
    console.error("Failed to update allocation status:", err);
    toast.show("Failed to update order status", { type: "error" });
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-play"></i>';
  }
}

function markCompleted(btn) {
  const allocationId = btn.dataset.allocationId;
  const isQC = btn.dataset.isQc === "true";
  const hasQC = btn.dataset.hasQc === "true";

  let targetStatus = "completed"; // Default: Mark completed if no QC is assigned
  if (isQC) targetStatus = "dispatch";
  else if (hasQC) targetStatus = "ready_for_qc";

  if (window.completeAllocatedOrder) {
    window.completeAllocatedOrder(allocationId, targetStatus);
  } else {
    toast.show("Work session tracking not available.", { type: "error" });
  }
}

// ── panel toggle ──────────────────────────────────────────────────────────────

function initPanel() {
  const toggleBtn = document.getElementById("allocated-orders-toggle-btn");
  const panel = document.getElementById("allocated-orders-panel");
  if (!toggleBtn || !panel) return;

  toggleBtn.addEventListener("click", () => {
    const isOpen = panel.style.display !== "none";
    panel.style.display = isOpen ? "none" : "block";
    const nowOpen = !isOpen;
    toggleBtn.setAttribute("aria-expanded", String(nowOpen));
    toggleBtn.innerHTML = nowOpen
      ? '<i class="fas fa-chevron-up"></i> Collapse'
      : '<i class="fas fa-chevron-down"></i> Expand';
    if (nowOpen) loadAllocatedOrders(); // refresh on open
  });

  // Delegated click for action buttons
  const table = document.getElementById("allocated-orders-table");
  if (table) {
    table.addEventListener("click", (e) => {
      const startBtn = e.target.closest(".alloc-start-btn");
      const completeBtn = e.target.closest(".alloc-complete-btn");
      const reviewBtn = e.target.closest(".alloc-review-btn");

      if (startBtn && startBtn.dataset.allocationId) {
        markInProgress(startBtn);
      } else if (completeBtn && completeBtn.dataset.allocationId) {
        markCompleted(completeBtn);
      } else if (reviewBtn && reviewBtn.dataset.allocationId) {
        markCompleted(reviewBtn);
      }
    });
  }
}

// ── realtime wiring ───────────────────────────────────────────────────────────

function initRealtimeListeners() {
  // A new order was assigned to this employee.
  bus.on("notification.created", (notification) => {
    if (notification.notif_type === "allocation.assigned") {
      loadAllocatedOrders();
      // toast is already shown by notifications.js — no double-toast here.
    }
  });

  // An allocation this employee owns changed status.
  bus.on("allocation.updated", () => {
    loadAllocatedOrders();
  });

  // Also react to the broader allocation.assigned event (sent directly
  // by AllocationService._announce) in case it arrives without a notif wrap.
  bus.on("allocation.assigned", () => {
    loadAllocatedOrders();
  });
}

// ── boot ──────────────────────────────────────────────────────────────────────

export function initAllocations() {
  if (!document.getElementById("allocated-orders-panel")) return;

  initPanel();
  initRealtimeListeners();
  loadAllocatedOrders(); // initial load
}

// Expose so userdashboard-work.js can refresh the table
window.loadAllocatedOrders = loadAllocatedOrders;

// Auto-boot when the DOM is ready.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAllocations);
} else {
  initAllocations();
}
