// Add click listener to "View" buttons
document.addEventListener('click', function (e) {
    if (e.target.closest('.status-badge.allocated.view-btn')) {
        const viewBtn = e.target.closest('.status-badge.allocated.view-btn');
        const allocationId = viewBtn.dataset.allocationId;

        if (allocationId) {
            fetch(`/api/v1/allocations/${allocationId}/`)
                .then(response => response.json())
                .then(orderData => {
                    if (orderData.success) {
                        showOrderDetailsFromApi(orderData);
                    } else {
                        throw new Error(orderData.error || 'Failed to fetch task details');
                    }
                })
                .catch(error => {
                    console.error('Error fetching order allocation data:', error);
                });
        }
    }

    // Add handler for start-action button
    if (e.target.closest('.action-btn.start-action')) {
        const clickedBtn = e.target.closest('.action-btn.start-action');
        const originalBtnHTML = clickedBtn.innerHTML;
        clickedBtn.disabled = true;
        clickedBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        const row = clickedBtn.closest('tr');
        const cells = row.getElementsByTagName('td');

        // Get data from the row
        const projectName = cells[1].textContent;
        const clientCode = cells[2].textContent;
        const workType = cells[3].textContent;
        const batch = cells[4].textContent !== 'N/A' ? cells[4].textContent : '';

        // First find the project ID for the project name
        const projectOption = Array.from(projectSelect.options).find(opt => opt.textContent === projectName);
        if (!projectOption) {
            console.error('Project not found in dropdown:', projectName);
            clickedBtn.disabled = false;
            clickedBtn.innerHTML = originalBtnHTML;
            return;
        }

        // Use an async function to handle the sequential population
        (async () => {
            try {
                // 1. Set project value and wait for client codes to load
                projectSelect.value = projectOption.value;
                await new Promise((resolve, reject) => {
                    const observer = new MutationObserver((mutationsList, obs) => {
                        if (clientCodeSelect.querySelector(`option[value="${clientCode}"]`)) {
                            obs.disconnect();
                            resolve();
                        }
                    });
                    observer.observe(clientCodeSelect, { childList: true, subtree: true });
                    projectSelect.dispatchEvent(new Event('change'));
                    setTimeout(() => { observer.disconnect(); reject(new Error('Timeout loading client codes')); }, 15000);
                });

                // 2. Set client code and wait for work types to load
                clientCodeSelect.value = clientCode;
                await new Promise((resolve, reject) => {
                    const observer = new MutationObserver(() => {
                        if (workTypeSelect.querySelector(`option[value="${workType}"]`)) {
                            observer.disconnect();
                            resolve();
                        }
                    });
                    observer.observe(workTypeSelect, { childList: true, subtree: true });
                    clientCodeSelect.dispatchEvent(new Event('change'));
                    setTimeout(() => { observer.disconnect(); reject(new Error('Timeout loading work types')); }, 15000);
                });

                // 3. Set work type and other fields
                workTypeSelect.value = workType;
                workTypeSelect.dispatchEvent(new Event('change'));
                batchInput.value = batch;

                // 4. Click the start button
                startBtn.disabled = false;
                startBtn.click();

            } catch (error) {
                console.error("Error setting up allocated task:", error);
                alert("Could not start allocated task automatically. Please try again.");
                // Restore button on error
                clickedBtn.disabled = false;
                clickedBtn.innerHTML = originalBtnHTML;
            }
        })();
    }
});

// Function to display order details in popup
function displayOrderDetails(order) {
    // First fetch order types
    fetch('/api/v1/allocations/rates/order_types/')
        .then(response => response.json())
        .then(orderTypes => {
            // Parse dates
            const receivedDate = order.received_date ? new Date(order.received_date).toLocaleString() : '-';
            const eta = order.eta ? new Date(order.eta).toLocaleString() : '-';
            const dispatchDate = order.dispatch_date ? new Date(order.dispatch_date).toLocaleString() : '-';

            // Remove any existing popups
            const existingPopup = document.querySelector('.oa-details-popup');
            if (existingPopup) {
                existingPopup.remove();
            }

            // Create the popup content
            const popup = document.createElement('div');
            popup.className = 'oa-details-popup';
            popup.innerHTML = `
                <div class="oa-details-container">
                    <div class="oa-details-header">
                        <h3><i class="fas fa-file-alt"></i> Order Details</h3>
                        <div class="oa-details-actions">
                            <button class="oa-details-save" title="Save changes">
                                <i class="fas fa-save"></i> Save
                            </button>
                            <button class="oa-details-close">&times;</button>
                        </div>
                    </div>
                    <div class="oa-details-body">
                        <div class="oa-details-grid">
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Task ID</div>  
                                <div class="oa-detail-value">${order.task_id || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Project</div>
                                <div class="oa-detail-value">${order.projectName || order.project || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Client Code</div>
                                <div class="oa-detail-value">${order.client_code || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Work Type</div>
                                <div class="oa-detail-value">${order.work_type || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Batch ID</div>
                                <div class="oa-detail-value">${order.batch_id || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">AR Number</div>
                                <div class="oa-detail-value">${order.ar_number || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Order Type</div>
                                <div class="oa-detail-value editable">
                                    <select class="editable-input" data-original="${order.order_details || ''}">
                                        <option value="">Select Order Type</option>
                                        ${orderTypes.map(type => `
                                            <option value="${type}" ${type === order.order_details ? 'selected' : ''}>
                                                ${type}
                                            </option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Owner Name</div>
                                <div class="oa-detail-value">${order.owner_name || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Property Address</div>
                                <div class="oa-detail-value">${order.property_address || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">State</div>
                                <div class="oa-detail-value">${order.state || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">County</div>
                                <div class="oa-detail-value">${order.county || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Assigned To</div>
                                <div class="oa-detail-value">${order.employeeName || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Received Date</div>
                                <div class="oa-detail-value">${receivedDate}</div>
                            </div>
                            <div class="oa-detail-item eta-field" ${order.search_type !== 'Ground' ? 'style="display: block;"' : ''}>
                                <div class="oa-detail-label">ETA</div>
                                <div class="oa-detail-value">${eta}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Dispatch Date</div>
                                <div class="oa-detail-value">${dispatchDate}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Fee Type</div>
                                <div class="oa-detail-value">${order.search_type || '-'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Fees</div>
                                <div class="oa-detail-value">$${order.fees || '0'}</div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Instructions</div>
                                <div class="oa-detail-value">
                                    <span class="oa-display-value" style="white-space: pre-wrap;">${order.remarks || '-'}</span>
                                </div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Employee Comments</div>
                                <div class="oa-detail-value editable">
                                    <textarea class="editable-input" data-original="${order.employee_comments || ''}">${order.employee_comments || ''}</textarea>
                                </div>
                            </div>
                            <div class="oa-detail-item">
                                <div class="oa-detail-label">Status</div>
                                <div class="oa-detail-value">
                                    <span class="oa-status-badge ${(order.status || 'pending').toLowerCase()}">
                                        ${order.status || 'Pending'}
                                    </span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Add Documents Section -->
                        <div class="oa-documents-section">
                            <div class="oa-documents-header">
                                <h4><i class="fas fa-file-upload"></i> Attachments </h4>
                                <button class="oa-add-document" title="Add Document">
                                    <i class="fas fa-plus"></i> Add Document
                                </button>
                                <input type="file" class="document-file-input" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,image/*" multiple style="display: none;">
                            </div>
                            <div class="oa-documents-grid"></div>
                        </div>
                    </div>
                </div>
            `;

            // Add helper function to determine document icon
            function getDocumentIcon(filename) {
                const ext = filename.split('.').pop().toLowerCase();
                switch (ext) {
                    case 'pdf':
                        return 'fa-file-pdf';
                    case 'doc':
                    case 'docx':
                        return 'fa-file-word';
                    case 'xls':
                    case 'xlsx':
                        return 'fa-file-excel';
                    case 'txt':
                        return 'fa-file-alt';
                    case 'jpg':
                    case 'jpeg':
                    case 'png':
                    case 'gif':
                        return 'fa-file-image';
                    default:
                        return 'fa-file';
                }
            }

            // First append the popup to the document
            document.body.appendChild(popup);

            // Force a reflow to ensure the transition works
            popup.offsetHeight;

            // Add the show class to trigger the animation
            requestAnimationFrame(() => {
                popup.classList.add('show');
            });

            // Handle save button click
            const saveBtn = popup.querySelector('.oa-details-save');
            if (saveBtn) {
                saveBtn.addEventListener('click', async function () {
                    const orderTypeSelect = popup.querySelector('select.editable-input');
                    const remarksInput = popup.querySelector('textarea.editable-input');

                    const newOrderType = orderTypeSelect.value;
                    const newRemarks = remarksInput.value.trim();

                    // Check if there are any changes
                    if (newOrderType === orderTypeSelect.dataset.original &&
                        newRemarks === remarksInput.dataset.original &&
                        newDocuments.length === 0) {
                        showNotification('No changes to save', 'error');
                        return;
                    }

                    // Validate order type selection
                    if (!newOrderType) {
                        showNotification('Please select an order type', 'error');
                        return;
                    }

                    // Show loading state
                    saveBtn.disabled = true;
                    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

                    try {
                        // Prepare form data for multipart upload
                        const formData = new FormData();

                        // Add basic update data
                        const updateData = {
                            task_id: order.task_id,
                            employee_id: order.employee_id || order.emp_id,
                            work_type: order.work_type,
                            search_type: order.search_type,
                            fees: order.fees,
                            order_details: newOrderType,
                            employee_comments: newRemarks
                        };

                        formData.append('data', JSON.stringify(updateData));

                        // Add new documents if any
                        newDocuments.forEach((doc, index) => {
                            // Convert base64 to Blob
                            const byteString = atob(doc.data.split(',')[1]);
                            const mimeString = doc.data.split(',')[0].split(':')[1].split(';')[0];
                            const ab = new ArrayBuffer(byteString.length);
                            const ia = new Uint8Array(ab);
                            for (let i = 0; i < byteString.length; i++) {
                                ia[i] = byteString.charCodeAt(i);
                            }
                            const blob = new Blob([ab], { type: mimeString });

                            // Create a File object from the Blob
                            const file = new File([blob], doc.name, { type: mimeString });
                            formData.append(`file_${index}`, file);
                        });
                        // Add removed files if any
                        if (removedFiles.length > 0) {
                            formData.append('removed_files', JSON.stringify(removedFiles));
                        }

                        // Send update request
                        const response = await fetch(`/api/order-allocation/${order.task_id}/update`, {
                            method: 'POST',
                            body: formData
                        });

                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }

                        const data = await response.json();

                        if (data.success) {
                            // Update the original values
                            orderTypeSelect.dataset.original = newOrderType;
                            remarksInput.dataset.original = newRemarks;
                            newDocuments = []; // Clear new documents array
                            showNotification('Changes saved successfully');
                            // Refresh the work data table
                            const today = new Date().toISOString().split('T')[0];
                            fetchWorkData(today);
                            // Instead of closing, fetch latest order data and show updated popup
                            fetch(`/api/v1/allocations/${order.task_id}/`)
                                .then(res => res.json())
                                .then(orderData => {
                                    if (orderData.success) {
                                        closePopup(popup);
                                        showOrderDetailsFromApi(orderData);
                                    } else {
                                        closePopup(popup);
                                    }
                                });
                        } else {
                            throw new Error(data.error || 'Failed to save changes');
                        }
                    } catch (error) {
                        console.error('Error:', error);
                        showNotification(error.message || 'Failed to save changes', 'error');
                    } finally {
                        // Reset save button
                        saveBtn.disabled = false;
                        saveBtn.innerHTML = '<i class="fas fa-save"></i> Save';
                    }
                });
            }

            // Handle close button click
            const closeBtn = popup.querySelector('.oa-details-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', function () {
                    // Check for unsaved changes using more reliable selectors
                    const orderTypeSelect = popup.querySelector('select.editable-input');
                    const remarksInput = popup.querySelector('textarea.editable-input');

                    if (orderTypeSelect.value !== orderTypeSelect.dataset.original ||
                        remarksInput.value.trim() !== remarksInput.dataset.original) {
                        if (!confirm('You have unsaved changes. Are you sure you want to close?')) {
                            return;
                        }
                    }
                    closePopup(popup);
                });
            }

            // Handle click outside
            function handleOutsideClick(e) {
                if (popup.contains(e.target) && !popup.querySelector('.oa-details-container').contains(e.target)) {
                    closePopup(popup);
                }
            }

            // Add click outside event listener
            document.addEventListener('click', handleOutsideClick);

            // Handle escape key
            function handleEscKey(e) {
                if (e.key === 'Escape') {
                    closePopup(popup);
                }
            }

            // Add escape key event listener
            document.addEventListener('keydown', handleEscKey);

            // Function to handle closing the popup
            function closePopup(popup) {
                popup.classList.remove('show');

                // Remove event listeners
                document.removeEventListener('click', handleOutsideClick);
                document.removeEventListener('keydown', handleEscKey);

                // Remove the popup after the animation
                setTimeout(() => {
                    popup.remove();
                }, 300); // Match this with your CSS transition duration
            }

            // Add document upload handling
            const addDocumentBtn = popup.querySelector('.oa-add-document');
            const fileInput = popup.querySelector('.document-file-input');
            const documentsGrid = popup.querySelector('.oa-documents-grid');
            let newDocuments = [];
            let removedFiles = [];
            // Helper to render all documents (existing + new)
            function renderDocumentsGrid() {
                documentsGrid.innerHTML = '';
                // Existing documents
                (order.batch_documents || []).forEach((doc, idx) => {
                    if (removedFiles.includes(doc.name)) return; // skip removed
                    const item = document.createElement('div');
                    item.className = 'oa-document-item';
                    item.innerHTML = `
                        <div class="oa-document-icon">
                            <i class="fas ${getDocumentIcon(doc.name)}"></i>
                        </div>
                        <div class="oa-document-info">
                            <span class="oa-document-name" title="${doc.name}">${doc.name}</span>
                            <div class="oa-document-actions">
                                <a href="/api/v1/allocations/${order.allocation_id || order.id}/download/?doc=${doc.type}" 
                                   class="oa-document-download" 
                                   target="_blank">
                                    <i class="fas fa-download"></i> Download
                                </a>
                                <button class="oa-document-remove" title="Remove">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                    `;
                    // Attach remove handler for existing document
                    const removeBtn = item.querySelector('.oa-document-remove');
                    removeBtn.addEventListener('click', () => {
                        removedFiles.push(doc.name);
                        renderDocumentsGrid();
                    });
                    documentsGrid.appendChild(item);
                });
                // New documents
                newDocuments.forEach((doc, idx) => {
                    const item = document.createElement('div');
                    item.className = 'oa-document-item new';
                    item.innerHTML = `
                        <div class="oa-document-icon">
                            <i class="fas ${getDocumentIcon(doc.name)}"></i>
                        </div>
                        <div class="oa-document-info">
                            <span class="oa-document-name" title="${doc.name}">${doc.name}</span>
                            <div class="oa-document-actions">
                                <button class="oa-document-remove" title="Remove">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                    `;
                    // Attach remove handler for new document
                    const removeBtn = item.querySelector('.oa-document-remove');
                    removeBtn.addEventListener('click', () => {
                        newDocuments.splice(idx, 1);
                        renderDocumentsGrid();
                    });
                    documentsGrid.appendChild(item);
                });
                if (!(order.batch_documents?.length - removedFiles.length) && !newDocuments.length) {
                    documentsGrid.innerHTML = '<div class="oa-no-documents">No documents attached</div>';
                }
            }
            // Initial render
            renderDocumentsGrid();

            if (addDocumentBtn && fileInput) {
                addDocumentBtn.addEventListener('click', () => fileInput.click());
                fileInput.addEventListener('change', function (e) {
                    const files = Array.from(e.target.files);
                    const allowedTypes = [
                        'image/jpeg', 'image/png', 'image/jpg', 'image/gif',
                        'application/pdf',
                        'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'text/plain'
                    ];
                    const validFiles = files.filter(file => {
                        const fileType = file.type.toLowerCase();
                        const fileExtension = file.name.split('.').pop().toLowerCase();
                        return allowedTypes.includes(fileType) ||
                            ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt'].includes(fileExtension);
                    });
                    if (validFiles.length !== files.length) {
                        showNotification('Only images, PDF, Word, Excel, and text files are allowed', 'error');
                        return;
                    }
                    validFiles.forEach(file => {
                        if (file.size > 35 * 1024 * 1024) {
                            showNotification(`File ${file.name} exceeds 35MB limit`, 'error');
                            return;
                        }
                        const reader = new FileReader();
                        reader.onload = function (e) {
                            newDocuments.push({
                                data: e.target.result,
                                name: file.name,
                                type: file.type,
                                file: file
                            });
                            renderDocumentsGrid();
                        };
                        reader.readAsDataURL(file);
                    });
                });
            }
        })
        .catch(error => {
            console.error('Error fetching order types:', error);
            alert('Failed to load order types. Please try again.');
        });
}

// Add this function at the top level
function showNotification(message, type = 'success') {
    // Remove existing notification if any
    const existingNotification = document.querySelector('.oa-notification');
    if (existingNotification) {
        existingNotification.remove();
    }

    const notification = document.createElement('div');
    notification.className = `oa-notification ${type}`;
    notification.innerHTML = `
        <div class="oa-notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span>${message}</span>
        </div>
    `;

    document.body.appendChild(notification);

    // Show notification with animation
    setTimeout(() => notification.classList.add('show'), 100);

    // Auto hide after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add these variables at the top of the file
let isPendingView = false;
let pendingTasksInterval;

// Add these new functions for pending tasks
function checkPendingTasks() {
    const userId = sessionStorage.getItem('emp_id');
    if (!userId) return;

    fetch(`/api/v1/tracking/sessions/?emp_id=${userId}&open=true`)
        .then(response => response.json())
        .then(res => {
            const data = res.data || res;
            const pendingCount = data.length;
            const pendingCountBadge = document.getElementById('pendingCount');
            const pendingTasksBtn = document.getElementById('pendingTasksBtn');

            // if (pendingCount > 0) {
            //     pendingCountBadge.textContent = pendingCount;
            //     pendingCountBadge.style.display = 'inline';

            //     if (!isPendingView) {
            //         pendingTasksBtn.classList.add('blinking');
            //     }
            // } else {
            //     pendingCountBadge.style.display = 'none';
            //     pendingTasksBtn.classList.remove('blinking');
            // }
        })
        .catch(error => console.error('Error checking pending tasks:', error));
}

// Add this to your existing DOMContentLoaded event listener, right after it starts
document.addEventListener('DOMContentLoaded', function () {

    // Initialize pending tasks functionality
    const pendingTasksBtn = document.getElementById('pendingTasksBtn');
    if (pendingTasksBtn) {
        pendingTasksBtn.addEventListener('click', function () {
            isPendingView = !isPendingView;
            const dateFilter = document.getElementById('date-filter');
            fetchWorkData(dateFilter.value);

            // Update button appearance
            if (isPendingView) {
                this.classList.remove('blinking');
                this.innerHTML = '<i class="fas fa-calendar-day"></i> Today\'s Tasks';
            } else {
                this.innerHTML = '<i class="fas fa-tasks"></i> OverDue Tasks <span id="pendingCount" class="badge badge-light" style="display: none;">0</span>';
                checkPendingTasks();
            }
        });

        // Initial check for pending tasks
        // Run once on load
        checkPendingTasks();

        // Listen for new assignment events via WebSocket
        if (typeof window.socket !== 'undefined' && window.socket) {
            window.socket.on('new_assignment', (data) => {
                console.log('Received new_assignment event:', data);
                checkPendingTasks();
            });
        }
    }

    // Add click handlers for view buttons
    document.addEventListener('click', function (e) {
        if (e.target.closest('.view-btn')) {
            const viewBtn = e.target.closest('.view-btn');
            const allocationId = viewBtn.dataset.allocationId;
            if (allocationId) {
                fetch(`/api/v1/allocations/${allocationId}/`)
                    .then(response => response.json())
                    .then(orderData => {
                        showOrderDetailsFromApi(orderData);
                    })
                    .catch(error => {
                        console.error('Error fetching order allocation data:', error);
                    });
            }
        }
    });
});

// Add this after your existing feedback-related code
document.addEventListener('DOMContentLoaded', function () {
    // Initialize feedback form functionality
    initializeFeedbackForm();
});

let feedbackFormInitialized = false;

function initializeFeedbackForm() {
    if (feedbackFormInitialized) {
        return;
    }

    const newFeedbackBtn = document.getElementById('newFeedbackBtn');
    const newFeedbackSection = document.getElementById('newFeedbackSection');
    const closeFeedbackForm = document.querySelector('.close-feedback-form');
    const feedbackReports = document.querySelector('.feedback-reports');
    const feedbackDetailPreview = document.querySelector('.feedback-detail-preview');

    let isInitialized = false;
    let projectsLoaded = false;

    // Set default values for dates and feedback provider
    const today = new Date();
    // Convert to IST by adding 5 hours and 30 minutes
    today.setHours(today.getHours() + 5);
    today.setMinutes(today.getMinutes() + 30);
    const istDate = today.toISOString().split('T')[0];

    // Set the dates
    $('#new_processedDate').val(istDate);
    $('#new_feedbackReceivedDate').val(istDate);
    $('#new_openDate').val(istDate);

    // Set the feedback provider as the logged-in user
    const loggedInUser = $('#user-name').text().trim().replace(/^\s*[\r\n]/gm, '').split('\n')[0];
    $('#new_feedbackProvidedBy').val(loggedInUser);

    function loadInitialData() {
        if (projectsLoaded) {
            return;
        }

        fetch('/api/v1/masters/emp_get_projects/')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {

                const projectDropdown = $('#new_project');
                projectDropdown.empty().append('<option value="">Select a project</option>');

                if (Array.isArray(data) && data.length > 0) {
                    data.forEach(project => {
                        projectDropdown.append(new Option(project.project_name, project.project_name, false, false));
                    });
                    projectsLoaded = true;

                } else {
                    console.warn('No projects data received');
                }
            })
            .catch(error => {
                console.error('Error loading projects:', error);
                $('#new_project').html('<option value="">Error loading projects</option>');
            });
    }

    // Remove all existing event handlers before adding new ones
    $('#new_project').off('change');
    $('#new_empIdName').off('change');
    $('#new_clientCode').off('change');
    $('#new_workType').off('change');

    // Project change handler
    $('#new_project').on('change', function (e) {
        // Prevent the handler from running on programmatic changes
        if (e.originalEvent === undefined) return;

        const selectedProject = $(this).val();

        // Reset and disable dependent dropdowns
        $('#new_empIdName').prop('disabled', true).empty().append('<option value="">Select employee(s)</option>');
        $('#new_clientCode').prop('disabled', true).empty().append('<option value="">Select client code</option>');
        $('#new_workType').prop('disabled', true).empty().append('<option value="">Select work type</option>');

        if (!selectedProject) return;

        // Fetch employees for the selected project
        fetch(`/get_project_employees/${encodeURIComponent(selectedProject)}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                const empDropdown = $('#new_empIdName');

                if (Array.isArray(data) && data.length > 0) {
                    data.forEach(emp => {
                        empDropdown.append(new Option(
                            `${emp.employee_id} - ${emp.name}`,
                            emp.employee_id,
                            false,
                            false
                        ));
                    });
                    empDropdown.prop('disabled', false);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                $('#new_empIdName')
                    .html('<option value="">Error loading employees</option>')
                    .prop('disabled', true);
            });
    });

    // Employee change handler
    $('#new_empIdName').on('change', function (e) {
        // Prevent the handler from running on programmatic changes
        if (e.originalEvent === undefined) return;

        const selectedValues = $(this).val();
        const selectedProject = $('#new_project').val();

        // Reset dependent dropdowns
        $('#new_clientCode').prop('disabled', true).empty().append('<option value="">Select client code</option>');
        $('#new_workType').prop('disabled', true).empty().append('<option value="">Select work type</option>');

        if (!selectedValues || selectedValues.length === 0 || !selectedProject) {
            $('#new_empId, #new_empName').val('');
            return;
        }

        const firstEmpId = selectedValues[0];
        $('#new_empId').val(firstEmpId);

        // Only make the API call if we have both employee ID and project
        if (firstEmpId && selectedProject) {
            fetch(`/get_employee_project_details/${encodeURIComponent(firstEmpId)}/${encodeURIComponent(selectedProject)}`)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    if (data.error) throw new Error(data.error);

                    const clientCodeDropdown = $('#new_clientCode');

                    if (data.client_codes && data.client_codes.length > 0) {
                        data.client_codes.forEach(code => {
                            clientCodeDropdown.append(new Option(code, code, false, false));
                        });
                        clientCodeDropdown.prop('disabled', false);
                    }

                    $('#new_empName').val(data.emp_name);
                })
                .catch(error => {
                    console.error('Error:', error);
                    $('#new_clientCode')
                        .html('<option value="">Error loading client codes</option>')
                        .prop('disabled', true);
                });
        }
    });

    // Client code change handler
    $('#new_clientCode').on('change', function () {
        const selectedClientCode = $(this).val();
        const selectedProject = $('#new_project').val();
        const selectedEmployees = $('#new_empIdName').val();

        $('#new_workType').prop('disabled', true).val(null).trigger('change');

        if (!selectedClientCode || !selectedProject || !selectedEmployees || selectedEmployees.length === 0) return;

        const firstEmpId = selectedEmployees[0];

        $('#new_workType')
            .html('<option value="">Loading work types...</option>')
            .prop('disabled', true);

        fetch(`/get_work_types/${encodeURIComponent(firstEmpId)}/${encodeURIComponent(selectedProject)}/${encodeURIComponent(selectedClientCode)}`)
            .then(response => response.json())
            .then(data => {
                const workTypeDropdown = $('#new_workType');
                workTypeDropdown.empty().append('<option value="">Select a work type</option>');

                if (data.work_types && data.work_types.length > 0) {
                    data.work_types.forEach(type => {
                        workTypeDropdown.append(new Option(type, type, false, false));
                    });
                    workTypeDropdown.prop('disabled', false);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                $('#new_workType')
                    .html('<option value="">Error loading work types</option>')
                    .prop('disabled', true);
            });
    });

    // Initialize Select2 only once
    if (!isInitialized && typeof jQuery !== 'undefined' && typeof jQuery.fn.select2 !== 'undefined') {
        // Project dropdown
        $('#new_project').select2({
            placeholder: 'Select a project',
            allowClear: true,
            width: '100%'
        }).on('select2:select', function (e) {
            const selectedProject = e.params.data.id;

            // Reset and disable dependent dropdowns
            $('#new_empIdName').prop('disabled', true).empty().append('<option value="">Select employee(s)</option>');
            $('#new_clientCode').prop('disabled', true).empty().append('<option value="">Select client code</option>');
            $('#new_workType').prop('disabled', true).empty().append('<option value="">Select work type</option>');

            if (!selectedProject) return;

            // Fetch employees for the selected project
            fetch(`/get_project_employees/${encodeURIComponent(selectedProject)}`)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    const empDropdown = $('#new_empIdName');

                    if (Array.isArray(data) && data.length > 0) {
                        data.forEach(emp => {
                            empDropdown.append(new Option(
                                `${emp.employee_id} - ${emp.name}`,
                                emp.employee_id,
                                false,
                                false
                            ));
                        });
                        empDropdown.prop('disabled', false).trigger('change.select2');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    $('#new_empIdName')
                        .html('<option value="">Error loading employees</option>')
                        .prop('disabled', true);
                });
        });

        // Employee dropdown
        $('#new_empIdName').select2({
            placeholder: 'Select employee(s)',
            allowClear: true,
            multiple: true,
            width: '100%',
            closeOnSelect: false
        }).on('select2:select select2:unselect', function (e) {
            const selectedValues = $(this).val();
            const selectedProject = $('#new_project').val();

            // Reset dependent dropdowns
            $('#new_clientCode').prop('disabled', true).empty().append('<option value="">Select client code</option>');
            $('#new_workType').prop('disabled', true).empty().append('<option value="">Select work type</option>');

            if (!selectedValues || selectedValues.length === 0 || !selectedProject) {
                $('#new_empId, #new_empName').val('');
                return;
            }

            const firstEmpId = selectedValues[0];
            $('#new_empId').val(firstEmpId);

            // Only make the API call if we have both employee ID and project
            if (firstEmpId && selectedProject) {
                fetch(`/get_employee_project_details/${encodeURIComponent(firstEmpId)}/${encodeURIComponent(selectedProject)}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok');
                        return response.json();
                    })
                    .then(data => {
                        if (data.error) throw new Error(data.error);

                        const clientCodeDropdown = $('#new_clientCode');

                        if (data.client_codes && data.client_codes.length > 0) {
                            data.client_codes.forEach(code => {
                                clientCodeDropdown.append(new Option(code, code, false, false));
                            });
                            clientCodeDropdown.prop('disabled', false).trigger('change.select2');
                        }

                        $('#new_empName').val(data.emp_name);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        $('#new_clientCode')
                            .html('<option value="">Error loading client codes</option>')
                            .prop('disabled', true);
                    });
            }
        });

        // Client code dropdown
        $('#new_clientCode').select2({
            placeholder: 'Select client code',
            allowClear: true,
            width: '100%'
        }).on('select2:select', function (e) {
            const selectedClientCode = e.params.data.id;
            const selectedProject = $('#new_project').val();
            const selectedEmployees = $('#new_empIdName').val();

            $('#new_workType').prop('disabled', true).empty().append('<option value="">Select work type</option>');

            if (!selectedClientCode || !selectedProject || !selectedEmployees || selectedEmployees.length === 0) return;

            const firstEmpId = selectedEmployees[0];

            fetch(`/get_work_types/${encodeURIComponent(firstEmpId)}/${encodeURIComponent(selectedProject)}/${encodeURIComponent(selectedClientCode)}`)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.json();
                })
                .then(data => {
                    const workTypeDropdown = $('#new_workType');

                    if (data.work_types && data.work_types.length > 0) {
                        data.work_types.forEach(type => {
                            workTypeDropdown.append(new Option(type, type, false, false));
                        });
                        workTypeDropdown.prop('disabled', false).trigger('change.select2');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    $('#new_workType')
                        .html('<option value="">Error loading work types</option>')
                        .prop('disabled', true);
                });
        });

        // Work type dropdown
        $('#new_workType').select2({
            placeholder: 'Select work type',
            allowClear: true,
            width: '100%'
        });

        isInitialized = true;
    }

    // Initialize file upload
    initializeFileUpload();

    feedbackFormInitialized = true;
}

// Add this at the beginning of the file, before any other code
let initializeSelect2, loadInitialData;

document.addEventListener('DOMContentLoaded', function () {

    const newFeedbackBtn = document.getElementById('newFeedbackBtn');
    const newFeedbackSection = document.getElementById('newFeedbackSection');
    const closeFeedbackForm = document.querySelector('.close-feedback-form');
    const feedbackReports = document.querySelector('.feedback-reports');
    const feedbackDetailPreview = document.querySelector('.feedback-detail-preview');

    // Initialize feedback form functionality
    initializeFeedbackForm();

    // Handle form submission - single source of truth
    const feedbackForm = document.getElementById('newFeedbackForm');
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', function (event) {
            event.preventDefault();

            const formData = new FormData(this);

            // Add basic form fields
            formData.append('orderBatchId', document.getElementById('new_orderBatchId').value);
            formData.append('feedbackRecorded', 'internalAudit');
            formData.append('project', document.getElementById('new_project').value);

            // Handle employee selection - convert to array format
            const selectedEmployees = $('#new_empIdName').val() || [];
            formData.append('selectedEmployees', JSON.stringify(selectedEmployees));

            // Add employee details
            formData.append('empId', document.getElementById('new_empId').value);
            formData.append('empName', document.getElementById('new_empName').value);

            // Add other form fields
            formData.append('clientCode', document.getElementById('new_clientCode').value);
            formData.append('workType', document.getElementById('new_workType').value);
            formData.append('processedDate', document.getElementById('new_processedDate').value);
            formData.append('feedbackReceivedDate', document.getElementById('new_feedbackReceivedDate').value);
            formData.append('feedbackReceivedMode', document.getElementById('new_feedbackReceivedMode').value);
            formData.append('feedbackProvidedBy', document.getElementById('new_feedbackProvidedBy').value);
            formData.append('feedback', document.getElementById('new_feedbackText').value);
            formData.append('fields', document.getElementById('new_fields').value);
            formData.append('severity', document.getElementById('new_severity').value);
            formData.append('type', document.getElementById('new_type').value);
            formData.append('comments', document.getElementById('new_comments').value);
            formData.append('actionTaken', document.getElementById('new_actionTaken').value);
            formData.append('status', document.getElementById('new_status').value);
            formData.append('openDate', document.getElementById('new_openDate').value);
            formData.append('closureDate', document.getElementById('new_closureDate').value);

            // Handle file uploads
            const fileInput = document.getElementById('new_closureScreenshot');
            if (fileInput && fileInput.files.length > 0) {
                Array.from(fileInput.files).forEach((file, index) => {
                    formData.append('closureScreenshots', file);
                });
            }

            // Validate required fields
            if (!selectedEmployees.length) {
                alert('Please select at least one employee');
                return;
            }

            if (!formData.get('feedback')) {
                alert('Please enter feedback text');
                return;
            }

            // Log form data for debugging
            for (let [key, value] of formData.entries()) {
            }

            fetch('/add_feedback', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Feedback submitted successfully!');
                        // Don't clear any form fields or file inputs
                        // Just show success message and keep form data
                    } else {
                        alert('Failed to submit feedback: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while submitting feedback');
                });
        });
    }

    // Define initializeSelect2 function
    initializeSelect2 = function () {

        if (typeof jQuery !== 'undefined' && typeof jQuery.fn.select2 !== 'undefined') {
            try {

                $('#new_project').select2({
                    placeholder: 'Select a project',
                    allowClear: true,
                    width: '100%'
                });

                $('#new_empIdName').select2({
                    placeholder: 'Select employee(s)',
                    allowClear: true,
                    multiple: true,
                    width: '100%',
                    selectionCssClass: 'select2-selection--multiple',
                    dropdownCssClass: 'select2-dropdown',
                    minimumResultsForSearch: 0,
                    closeOnSelect: false,
                    templateResult: formatEmployee,
                    templateSelection: formatEmployeeSelection
                });

                $('#new_clientCode').select2({
                    placeholder: 'Select client code',
                    allowClear: true,
                    width: '100%'
                });

                $('#new_workType').select2({
                    placeholder: 'Select work type',
                    allowClear: true,
                    width: '100%'
                });

            } catch (error) {
                console.error('Error initializing Select2:', error);
            }
        } else {
            console.error('Required libraries not loaded. jQuery:', typeof jQuery, 'Select2:', typeof jQuery?.fn?.select2);
        }
    };

    // Define loadInitialData function
    loadInitialData = function () {

        fetch('/api/v1/masters/selections/')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error:', data.error);
                    return;
                }

                const projectDropdown = document.getElementById('new_project');
                if (projectDropdown && data.projects) {
                    projectDropdown.innerHTML = '<option value="">Select a project</option>';

                    // Add projects to dropdown
                    data.projects.forEach(project => {
                        const option = document.createElement('option');
                        option.value = project.project_name;
                        option.textContent = project.project_name;
                        projectDropdown.appendChild(option);
                    });

                    // If there's only one project, auto-select it
                    if (data.projects.length === 1) {
                        projectDropdown.value = data.projects[0].project_name;

                        // Fetch employees for the selected project
                        fetch(`/get_project_employees/${encodeURIComponent(data.projects[0].project_name)}`)
                            .then(response => {
                                if (!response.ok) throw new Error('Network response was not ok');
                                return response.json();
                            })
                            .then(empData => {
                                const empDropdown = $('#new_empIdName');
                                empDropdown.empty().append('<option value="">Select employee(s)</option>');

                                if (Array.isArray(empData) && empData.length > 0) {
                                    empData.forEach(emp => {
                                        empDropdown.append(new Option(
                                            `${emp.employee_id} - ${emp.name}`,
                                            emp.employee_id,
                                            false,
                                            false
                                        ));
                                    });
                                    empDropdown.prop('disabled', false);
                                }
                            })
                            .catch(error => {
                                console.error('Error loading employees:', error);
                                $('#new_empIdName')
                                    .html('<option value="">Error loading employees</option>')
                                    .prop('disabled', true);
                            });
                    }
                } else {
                    console.error('Project dropdown element not found or no projects available');
                }
            })
            .catch(error => {
                console.error('Error loading projects:', error);
            });
    };

    // Show/hide feedback form
    if (newFeedbackBtn) {
        newFeedbackBtn.addEventListener('click', function (event) {
            event.preventDefault();

            try {
                feedbackReports.style.display = 'none';
                feedbackDetailPreview.style.display = 'none';
                newFeedbackSection.style.display = 'block';

                initializeSelect2();
                loadInitialData();

                // Set Internal Audit value
                const feedbackRecordedSelect = document.getElementById('new_feedbackRecorded');
                if (feedbackRecordedSelect) {
                    feedbackRecordedSelect.value = 'internalAudit';
                    feedbackRecordedSelect.dispatchEvent(new Event('change'));
                }
            } catch (error) {
                console.error('Error in new feedback button handler:', error);
            }
        });
    }

    // Add close button functionality
    if (closeFeedbackForm) {
        closeFeedbackForm.addEventListener('click', function () {
            // Reset form
            const feedbackForm = document.getElementById('newFeedbackForm');
            if (feedbackForm) {
                feedbackForm.reset();

                // Reset Select2 dropdowns
                $('#new_project').val('').trigger('change');
                $('#new_empIdName').val('').trigger('change');
                $('#new_clientCode').val('').trigger('change');
                $('#new_workType').val('').trigger('change');

                // Clear file preview
                const previewContainer = document.getElementById('new_previewContainer');
                if (previewContainer) {
                    previewContainer.innerHTML = '';
                }
            }

            // Hide form and show reports
            newFeedbackSection.style.display = 'none';
            feedbackReports.style.display = 'block';

            // Refresh feedback reports
            fetchFeedbackReports();
        });
    }
});

// Add these helper functions at the top of the file
function formatEmployee(employee) {
    if (!employee.id || employee.id === 'all') return employee.text;
    return $('<div>').text(employee.text).addClass('employee-option');
}

function formatEmployeeSelection(employee) {
    if (!employee.id || employee.id === 'all') return employee.text;
    return $('<div>').text(employee.text).addClass('employee-selection');
}

function initializeFileUpload() {
    const dropZone = document.getElementById('new_dropZone');
    const fileInput = document.getElementById('new_closureScreenshot');
    const previewContainer = document.getElementById('new_previewContainer');
    let uploadedFiles = new Set();

    if (dropZone && fileInput) {
        dropZone.addEventListener('click', (e) => {
            if (e.target === dropZone || e.target.tagName === 'P') {
                fileInput.click();
            }
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#1abc9c';
            dropZone.classList.add('loading');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.style.borderColor = '#ccc';
            dropZone.classList.remove('loading');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#ccc';
            dropZone.classList.remove('loading');
            handleFiles(e.dataTransfer.files);
        });

        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });

        // Add paste event listener
        document.addEventListener('paste', (e) => {
            const activeElement = document.activeElement;
            const isTextInput = activeElement.tagName === 'INPUT' && activeElement.type === 'text';
            const isTextArea = activeElement.tagName === 'TEXTAREA';

            if (isTextInput || isTextArea) return;

            if (e.clipboardData.files.length > 0) {
                e.preventDefault();
                handleFiles(e.clipboardData.files);
            }
        });
    }

    function handleFiles(files) {
        Array.from(files).forEach(file => {
            if (!file.type.startsWith("image/")) {
                alert("Only image files are allowed!");
                return;
            }

            // Check if file is already uploaded
            if (uploadedFiles.has(file.name)) {
                alert(`File "${file.name}" has already been added!`);
                return;
            }

            uploadedFiles.add(file.name);

            const reader = new FileReader();
            reader.onload = (e) => {
                const wrapper = document.createElement("div");
                wrapper.className = "preview-image-wrapper new-feedback-preview";

                const img = document.createElement("img");
                img.src = e.target.result;
                img.className = 'preview-image';
                img.setAttribute('data-filename', file.name);

                // Add click event for full-screen preview
                img.onclick = () => showFullScreenImage(e.target.result, Array.from(previewContainer.querySelectorAll('img')).indexOf(img));

                const removeBtn = document.createElement("button");
                removeBtn.className = "remove-image";
                removeBtn.innerHTML = '<i class="fas fa-times"></i>';
                removeBtn.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    removeFile(file.name, wrapper);
                };

                wrapper.appendChild(img);
                wrapper.appendChild(removeBtn);
                previewContainer.appendChild(wrapper);
            };
            reader.readAsDataURL(file);
        });

        updateFileInputFiles(Array.from(files));
    }

    function removeFile(fileName, wrapper) {
        uploadedFiles.delete(fileName);
        wrapper.remove();

        const newFileList = Array.from(fileInput.files).filter(file => file.name !== fileName);
        updateFileInputFiles(newFileList);
    }

    function updateFileInputFiles(files) {
        const dataTransfer = new DataTransfer();
        files.forEach(file => dataTransfer.items.add(file));
        fileInput.files = dataTransfer.files;
    }
}

// Full-screen image preview functionality
function showFullScreenImage(src, currentIndex) {
    const modal = document.createElement('div');
    modal.className = 'image-preview-modal';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    const img = document.createElement('img');
    img.src = src;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-modal';
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.onclick = () => modal.remove();

    const images = Array.from(document.querySelectorAll('.preview-image'));

    if (images.length > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.className = 'nav-btn prev';
        prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i>';
        prevBtn.onclick = () => navigateImages((currentIndex - 1 + images.length) % images.length);

        const nextBtn = document.createElement('button');
        nextBtn.className = 'nav-btn next';
        nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
        nextBtn.onclick = () => navigateImages((currentIndex + 1) % images.length);

        modalContent.appendChild(prevBtn);
        modalContent.appendChild(nextBtn);
    }

    modalContent.appendChild(closeBtn);
    modalContent.appendChild(img);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    function navigateImages(newIndex) {
        const newSrc = images[newIndex].src;
        img.src = newSrc;
        currentIndex = newIndex;
    }

    // Handle keyboard navigation
    function handleKeyPress(e) {
        if (e.key === 'Escape') {
            modal.remove();
        } else if (e.key === 'ArrowLeft' && images.length > 1) {
            navigateImages((currentIndex - 1 + images.length) % images.length);
        } else if (e.key === 'ArrowRight' && images.length > 1) {
            navigateImages((currentIndex + 1) % images.length);
        }
    }

    document.addEventListener('keydown', handleKeyPress);
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    };
}

// Add TitleIndexing configuration
const TITLE_INDEXING_CONFIG = {
    types: [
        'Others',
        'Book Type Wrong',
        'Inst Type Wrong',
        'Remark Typo Error',
        'Clerk Number Wrong',
        'Volume Wrong',
        'Page Wrong',
        'Inst Date Wrong',
        'Inst Date is greater than File date',
        'File Date Wrong',
        'File Date is smaller than Inst date',
        'Amount Missing',
        'Amount Wrong capture',
        'Grontor Name wrong capture',
        'Grantor Name Missing',
        'Grantor Format wrong',
        'Typo Error',
        'Grantee Name wrong capture',
        'Grantee Name Missing',
        'Grantee Format wrong',
        'Suffix Missing',
        'Comment Missing',
        'Additional Entry Missing',
        'Both Side Wrong Entry Capture',
        'Died Comment Missing',
        'Sub Name Wrong',
        'Abstract Name Wrong',
        'Parcel ID Missing',
        'Address Missing',
        'Vol page Missing',
        'Micro Title entry Missing',
        'Acres Dividation skip',
        'Acress Wrong capture',
        'Comment Wrong capture',
        'Part of skip'
    ],
    fields: [
        'Book Type',
        'Instrument Type',
        'Remarks',
        'Cleark Number',
        'Volume',
        'Page',
        'Instrument Date',
        'Filing Date',
        'Lien Amount',
        'User Comment',
        'Grantor',
        'Grantee',
        'User Comment',
        'Subdivision',
        'Lot',
        'Block',
        'Section',
        'Abstract Name',
        'Acreage',
        'Legal Notes',
        'Prior Reference'
    ]
};

// Function to check if project is TitleIndexing
function isTitleIndexingProject(projectName) {
    if (!projectName) return false;
    const lower = projectName.toLowerCase();
    return lower.includes('titleindexing') || lower.includes('title indexing');
}

// Function to update type dropdown based on project
function updateTypeDropdown(projectName) {
    const typeSelect = document.getElementById('new_type');
    typeSelect.innerHTML = ''; // Clear existing options

    if (isTitleIndexingProject(projectName)) {
        // Add TitleIndexing specific options
        TITLE_INDEXING_CONFIG.types.forEach(type => {
            const option = document.createElement('option');
            option.value = type.toLowerCase().replace(/\s+/g, '_');
            option.textContent = type;
            typeSelect.appendChild(option);
        });
    } else {
        // Add default options
        const defaultOptions = [
            'typoErrors',
            'missedToKey',
            'instructionsNotFollowed',
            'misinterpretation',
            'softwareIssue',
            'wrongFeedback',
            'newFeedback',
            'duplicateFeedback',
            'repeatMistake',
            'errorpriortosopupdate'
        ];

        defaultOptions.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option.replace(/([A-Z])/g, ' $1').trim();
            typeSelect.appendChild(optionElement);
        });
    }
}

// Function to update fields based on project
function updateFields(projectName) {
    const fieldsContainer = document.getElementById('new_fieldsContainer');
    if (!fieldsContainer) return;

    if (isTitleIndexingProject(projectName)) {
        // Create multi-select dropdown for TitleIndexing
        fieldsContainer.innerHTML = `
            <label for="new_fields">
                <i class="fas fa-hashtag"></i> Fields:
            </label>
            <select id="new_fields" name="fields" multiple class="fields-dropdown">
                ${TITLE_INDEXING_CONFIG.fields.map(field => `
                    <option value="${field}">${field}</option>
                `).join('')}
            </select>
        `;

        // Initialize Select2 for the fields dropdown
        $('#new_fields').select2({
            placeholder: 'Select fields',
            allowClear: true,
            multiple: true,
            width: '100%'
        });
    } else {
        // Reset to default text input
        fieldsContainer.innerHTML = `
            <label for="new_fields">
                <i class="fas fa-hashtag"></i> Fields:
            </label>
            <input type="text" id="new_fields" name="fields">
        `;
    }
}

// Update project change handler in initializeFeedbackForm
$('#new_project').on('change', function () {
    const selectedProject = $(this).find('option:selected').text();
    updateFields(selectedProject);
    updateTypeDropdown(selectedProject);

    // ... rest of the existing project change handler code ...
});

// Add type change handler to update feedback text
$('#new_type').on('change', function () {
    const selectedType = $(this).find('option:selected').text();
    $('#new_feedbackText').val(selectedType);
});

// --- Fix: Update Type and Fields on Project Change (use value, not text) ---
function handleNewProjectChange() {
    const selectedProject = document.getElementById('new_project').value;
    updateFields(selectedProject);
    updateTypeDropdown(selectedProject);
}

// Attach the handler to the project dropdown
$(document).ready(function () {
    // On change
    $('#new_project').off('change').on('change', handleNewProjectChange);
    // On initial load (in case a project is pre-selected)
    handleNewProjectChange();
});

// Patch: Map employeeName and projectName before calling displayOrderDetails
function showOrderDetailsFromApi(orderData) {
    if (orderData && orderData.success && orderData.order) {
        const order = orderData.order;
        // Helper to finish and show details
        function finish() {
            displayOrderDetails(order);
        }
        // Fetch employee name if missing
        if (!order.employeeName && order.employee_id) {
            fetch(`/api/v1/allocations/employees/`)
                .then(res => res.json())
                .then(emps => {
                    const emp = emps.find(e => e.employee_id == order.employee_id);
                    order.employeeName = emp ? emp.name : order.employee_id;
                    // Fetch project name if missing
                    if (!order.projectName && order.project) {
                        fetch(`/api/v1/allocations/projects/`)
                            .then(res => res.json())
                            .then(projData => {
                                if (projData.project && projData.project.id == order.project) {
                                    order.projectName = projData.project.name;
                                } else {
                                    order.projectName = order.project;
                                }
                                finish();
                            });
                    } else {
                        finish();
                    }
                });
        } else if (!order.projectName && order.project) {
            fetch(`/api/v1/allocations/projects/`)
                .then(res => res.json())
                .then(projData => {
                    if (projData.project && projData.project.id == order.project) {
                        order.projectName = projData.project.name;
                    } else {
                        order.projectName = order.project;
                    }
                    finish();
                });
        } else {
            finish();
        }
    } else if (orderData && orderData.task_id) {
        displayOrderDetails(orderData);
    }
}

// --- Pending Acknowledgment Modal Logic ---
(function () {
    // Inject modal HTML and CSS if not present
    function injectPendingAckModal() {
        if (document.getElementById('pendingAckModal')) return;
        const modal = document.createElement('div');
        modal.id = 'pendingAckModal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="pending-ack-modal-overlay">
                <div class="pending-ack-modal-content">
                    <h2><i class="fas fa-exclamation-triangle" style="color:#e67e22;"></i> Pending Feedback Acknowledgments</h2>
                    <div class="pending-ack-list"></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Show the modal with a list of pending items
    function showPendingAckModal(pendingList) {
        injectPendingAckModal();
        const modal = document.getElementById('pendingAckModal');
        const listDiv = modal.querySelector('.pending-ack-list');
        listDiv.innerHTML = '';
        pendingList.forEach(item => {
            const div = document.createElement('div');
            div.className = 'pending-ack-item';
            div.innerHTML = `
                <div class="pending-ack-info">
                    <b>Project:</b> ${item.project || '-'}<br>
                    <b>Client Code:</b> ${item.client_code || '-'}<br>
                    <b>Date:</b> ${item.feedback_received_date ? new Date(item.feedback_received_date).toLocaleDateString() : '-'}
                </div>
                <button class="pending-ack-btn" data-id="${item.id}">View & Acknowledge</button>
            `;
            listDiv.appendChild(div);
        });
        modal.style.display = 'block';
        // Block scroll
        document.body.style.overflow = 'hidden';
        // Add button listeners
        modal.querySelectorAll('.pending-ack-btn').forEach(btn => {
            btn.onclick = function () {
                // Switch to feedback tab and highlight the feedback
                showContent('feedback');
                setTimeout(() => {
                    // Optionally scroll to the feedback row
                    const row = Array.from(document.querySelectorAll('#feedback-table tbody tr')).find(r => r.textContent.includes(`Report-${btn.dataset.id}`));
                    if (row) {
                        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        row.classList.add('pending-ack-highlight');
                        setTimeout(() => row.classList.remove('pending-ack-highlight'), 2000);
                    }
                }, 400);
                hidePendingAckModal();
            };
        });
    }

    function hidePendingAckModal() {
        const modal = document.getElementById('pendingAckModal');
        if (modal) modal.style.display = 'none';
        document.body.style.overflow = '';
    }

    // Check for pending acknowledgments
    async function checkPendingAcknowledgments(force) {
        // Only run if not on feedback tab
        const feedbackSection = document.getElementById('feedback-section');
        if (feedbackSection && feedbackSection.style.display !== 'block') {
            const res = await fetch('/api/v1/feedback/');
            if (!res.ok) return;
            const payload = await res.json();
            const data = payload.data || payload; // handle envelope
            // Only consider pending feedbacks where 24h have passed since created_at
            const now = Date.now();
            const pending = data.filter(fb => {
                if (fb.acknowledgment === null || fb.acknowledgment === undefined) {
                    if (fb.created_at) {
                        const created = new Date(fb.created_at).getTime();
                        return (now - created) >= 24 * 60 * 60 * 1000;
                    }
                }
                return false;
            });
            if (pending.length > 0) {
                showPendingAckModal(pending);
                return true;
            } else {
                hidePendingAckModal();
                return false;
            }
        } else {
            hidePendingAckModal();
            return false;
        }
    }
    // Hook into tab switching
    const origShowContent = window.showContent;
    window.showContent = function (contentId) {
        origShowContent.apply(this, arguments);
        if (contentId !== 'feedback') {
            setTimeout(() => checkPendingAcknowledgments(), 200);
        } else {
            hidePendingAckModal();
        }
    };
    // On page load
    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(() => checkPendingAcknowledgments(), 400);
    });
    // Prevent tab switch if modal is open
    document.addEventListener('click', function (e) {
        const modal = document.getElementById('pendingAckModal');
        if (modal && modal.style.display === 'block') {
            // Only allow clicks inside the modal
            if (!modal.contains(e.target)) {
                e.stopPropagation();
                e.preventDefault();
            }
        }
    }, true);
})();

// --- ProvenAir Tasks Button Logic ---
document.addEventListener('DOMContentLoaded', function () {
    const paTasksBtn = document.getElementById('paTasksBtn');
    let isPATodayView = false; // Track toggle state
    let allPaTasksData = [];
    const dateFilter = document.getElementById('date-filter');
    if (paTasksBtn) {
        paTasksBtn.addEventListener('click', function () {
            document.getElementById('pendingTasksBtn')?.classList.remove('active');
            isPATodayView = !isPATodayView;
            window.isPATodayView = isPATodayView;
            if (isPATodayView) {
                paTasksBtn.classList.add('active');
                paTasksBtn.innerHTML = '<i class="fas fa-calendar-day"></i> My Tasks';
                // Show ProvenAir tasks for the selected date only
                fetch('/get_pa_tasks')
                    .then(response => response.json())
                    .then(data => {
                        allPaTasksData = data;
                        renderPaTasksForDate();
                    })
                    .catch(error => {
                        const tableBody = document.getElementById('work-data-table').querySelector('tbody');
                        tableBody.innerHTML = '<tr><td colspan="12">Error loading ProvenAir tasks.</td></tr>';
                        console.error('Error fetching ProvenAir tasks:', error);
                    });
                // Listen for date filter changes while in PA view
                if (dateFilter) {
                    dateFilter.addEventListener('change', renderPaTasksForDate);
                }
            } else {
                // On second click, revert label and call fetchWorkData(today)
                paTasksBtn.innerHTML = '<i class="fas fa-tasks"></i> ProvenAir Tasks';
                paTasksBtn.classList.remove('active');
                if (dateFilter) {
                    dateFilter.removeEventListener('change', renderPaTasksForDate);
                }
                const today = new Date().toISOString().split('T')[0];
                fetchWorkData(today);
            }
        });
    }

    // Helper to render PA tasks for the selected date
    function renderPaTasksForDate() {
        const tableBody = document.getElementById('work-data-table').querySelector('tbody');
        tableBody.innerHTML = '';
        let selectedDate = dateFilter ? dateFilter.value : '';
        if (!selectedDate) {
            selectedDate = new Date().toISOString().split('T')[0];
        }
        const filtered = allPaTasksData
            .filter(task => (task.date === selectedDate))
            .filter(task => task.status !== 'Completed');
        if (filtered.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="12">No ProvenAir tasks found for this date.</td></tr>';
            return;
        }
        filtered.forEach(task => {
            let actionsContent = '';
            if (task.status === 'Completed') {
                actionsContent = `<span class="status-badge completed"><i class="fas fa-check-circle"></i> Completed</span>`;
            } else if (task.status === 'In Progress') {
                actionsContent = `<span class="status-badge in-progress"><i class="fas fa-spinner"></i> In Progress</span>`;
            } else {
                actionsContent = `<button class="pa-task-start-btn action-btn" data-pa-task-id="${task.pa_task_id}" style="background:#2c3e50;color:#fff;padding:6px 12px;border-radius:6px;display:inline-flex;align-items:center;gap:4px;"><i class="fas fa-play"></i></button>`;
            }
            const row = document.createElement('tr');
            if (task.project === 'ProvenAir-AAR') {
                row.classList.add('provenair-row');
            }
            row.innerHTML = `
                <td>${task.date || '-'}</td>
                <td>${task.project || '-'}</td>
                <td>${task.client_code || '-'}</td>
                <td>${task.work_type || '-'}</td>
                <td>${task.batch || '-'}</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>${task.pages || '-'}</td>
                <td>${actionsContent}</td>
            `;
            tableBody.appendChild(row);
        });

        // Add event listeners for Start buttons
        document.querySelectorAll('.pa-task-start-btn').forEach(btn => {
            btn.addEventListener('click', async function () {
                const clickedBtn = this;
                const paTaskId = clickedBtn.getAttribute('data-pa-task-id');
                // Validate latest status to avoid duplicates/conflicts
                try {
                    const latest = await fetch('/get_pa_tasks').then(r => r.json());
                    if (Array.isArray(latest)) {
                        allPaTasksData = latest;
                    }
                    const latestTask = (latest || []).find(t => String(t.pa_task_id) === String(paTaskId));
                    if (!latestTask) {
                        alert('Task not found. Please refresh and try again.');
                        return;
                    }
                    if (latestTask.status === 'In Progress') {
                        alert('This task has already been started. Please pick another task.');
                        return;
                    }
                    if (latestTask.status === 'Completed') {
                        alert('This task is already completed.');
                        return;
                    }
                } catch (e) {
                    console.error('Failed to validate task status:', e);
                    alert('Unable to validate task status. Please try again.');
                    return;
                }
                const task = allPaTasksData.find(t => t.pa_task_id == paTaskId);

                const originalBtnHTML = clickedBtn.innerHTML;
                clickedBtn.disabled = true;
                clickedBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

                try {
                    // Pre-fill the work form
                    const projectSelect = document.getElementById('project-select');
                    const clientCodeSelect = document.getElementById('client-code-select');
                    const workTypeSelect = document.getElementById('work-type-select');
                    const batchInput = document.getElementById('batch');
                    const pagesInput = document.getElementById('pages');

                    // 1. Set project and wait for client codes
                    let projectOption = Array.from(projectSelect.options).find(opt => opt.textContent === task.project || opt.value === task.project);
                    if (projectOption) {
                        projectSelect.value = projectOption.value;
                        await new Promise((resolve, reject) => {
                            const observer = new MutationObserver(() => {
                                if (Array.from(clientCodeSelect.options).some(opt => opt.value === task.client_code)) {
                                    observer.disconnect();
                                    resolve();
                                }
                            });
                            observer.observe(clientCodeSelect, { childList: true, subtree: true });
                            projectSelect.dispatchEvent(new Event('change'));
                            setTimeout(() => { observer.disconnect(); reject(new Error('Timeout loading client codes for ProvenAir task.')); }, 15000);
                        });
                    }

                    // 2. Set client code and wait for work types
                    let clientOption = Array.from(clientCodeSelect.options).find(opt => opt.textContent === task.client_code || opt.value === task.client_code);
                    if (clientOption) {
                        clientCodeSelect.value = clientOption.value;
                        await new Promise((resolve, reject) => {
                            const observer = new MutationObserver(() => {
                                if (Array.from(workTypeSelect.options).some(opt => opt.value === task.work_type)) {
                                    observer.disconnect();
                                    resolve();
                                }
                            });
                            observer.observe(workTypeSelect, { childList: true, subtree: true });
                            clientCodeSelect.dispatchEvent(new Event('change'));
                            setTimeout(() => { observer.disconnect(); reject(new Error('Timeout loading work types for ProvenAir task.')); }, 15000);
                        });
                    }

                    // 3. Set work type and other fields
                    let workTypeOption = Array.from(workTypeSelect.options).find(opt => opt.textContent === task.work_type || opt.value === task.work_type);
                    if (workTypeOption) {
                        workTypeSelect.value = workTypeOption.value;
                        workTypeSelect.dispatchEvent(new Event('change'));
                    }

                    batchInput.value = task.batch || '';
                    pagesInput.value = task.pages || '';

                    if (task.project === 'ProvenAir-AAR' && task.pages) {
                        localStorage.setItem('lastProvenAirPages', task.pages);
                    }

                    // 4. Click the Start button
                    document.getElementById('start-btn').click();
                    // Keep PA view active and refresh PA list with latest statuses
                    isPATodayView = true;
                    setTimeout(async () => {
                        try {
                            const refreshed = await fetch('/get_pa_tasks').then(r => r.json());
                            if (Array.isArray(refreshed)) {
                                allPaTasksData = refreshed;
                            }
                            renderPaTasksForDate();
                        } catch (err) {
                            console.error('Failed to refresh PA tasks:', err);
                        }
                    }, 800);

                } catch (error) {
                    console.error("Failed to start ProvenAir task:", error);
                    alert("Could not start the task automatically. Please check the form and try again.\n" + error.message);
                    clickedBtn.disabled = false;
                    clickedBtn.innerHTML = originalBtnHTML;
                }
            });
        });
    }

    // Expose a global refresh for PA view so other flows (submit/end) can update immediately
    window.refreshProvenAirTasksView = async function () {
        try {
            const data = await fetch('/get_pa_tasks').then(r => r.json());
            if (Array.isArray(data)) {
                allPaTasksData = data;
            }
            renderPaTasksForDate();
        } catch (err) {
            console.error('Failed to refresh ProvenAir tasks:', err);
        }
    };
});

// Assignment popup for newly assigned orders (persistent until acknowledged)
(function () {
    let assignmentQueue = [];
    let isShowingAssignment = false;

    function createAssignmentModal(item) {
        const modal = document.createElement('div');
        modal.className = 'assignment-popup';
        modal.innerHTML = `
            <div class="assignment-popup-card" role="dialog" aria-modal="true" aria-label="New Assignment">
                <div class="assignment-popup-header">
                    <h3><i class="fas fa-user-check"></i> New Task Assigned</h3>
                    <button class="oa-details-close" aria-label="Close">&times;</button>
                </div>
                <div class="assignment-popup-body">
                    <div class="assignment-detail">
                        <div class="label">Task ID</div>
                        <div class="value">${item.task_id || '-'}</div>
                    </div>
                    <div class="assignment-detail">
                        <div class="label">Work Type</div>
                        <div class="value">${item.work_type || '-'}</div>
                    </div>
                    <div class="assignment-detail">
                        <div class="label">Assigned By</div>
                        <div class="value">${item.assigned_by_name || item.assigned_by || '-'}</div>
                    </div>
                    <div class="assignment-detail">
                        <div class="label">Assigned On</div>
                        <div class="value">${item.assigned_on ? new Date(item.assigned_on.replace(' ', 'T')).toLocaleString() : '-'}</div>
                    </div>
                </div>
                <div class="assignment-popup-actions">
                    <button class="assignment-ack-btn"><i class="fas fa-check-circle"></i> Got it</button>
                </div>
            </div>
        `;
        // Prevent closing without ack
        modal.querySelector('.oa-details-close').addEventListener('click', (e) => {
            e.stopPropagation();
        });
        // Acknowledge button
        modal.querySelector('.assignment-ack-btn').addEventListener('click', async () => {
            try {
                await fetch(`/api/v1/allocations/${item.allocation_id}/status/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
                    },
                    body: JSON.stringify({ status: 'in_progress' })
                });
            } catch (e) {
                console.error('Failed to acknowledge assignment', e);
            }
            document.body.style.overflow = '';
            modal.classList.remove('show');
            setTimeout(() => { modal.remove(); showNextAssignment(); }, 200);
        });
        document.body.appendChild(modal);
        requestAnimationFrame(() => {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        });
        return modal;
    }

    function showNextAssignment() {
        if (assignmentQueue.length === 0) {
            isShowingAssignment = false;
            return;
        }
        isShowingAssignment = true;
        const item = assignmentQueue.shift();
        createAssignmentModal(item);
    }

    async function fetchPendingAssignments() {
        try {
            const res = await fetch('/api/v1/allocations/?open=true&status=pending');
            if (!res.ok) return;
            const data = await res.json();
            if (data && Array.isArray(data.data || data) && (data.data || data).length > 0) {
                data.assignments = data.data || data;
                // If currently showing, queue up newly fetched unseen items behind existing ones
                const idsInQueue = new Set(assignmentQueue.map(a => a.history_id));
                const newly = data.assignments.filter(a => !idsInQueue.has(a.allocation_id));
                assignmentQueue = assignmentQueue.concat(newly);
                if (!isShowingAssignment) showNextAssignment();
            }
        } catch (e) {
            console.error('Error fetching pending assignments', e);
        }
    }

    // Assignment popup disabled — new orders appear in the bell notification
    // centre instead of a blocking modal popup.
    document.addEventListener('DOMContentLoaded', function () {
        // fetchPendingAssignments(); // disabled: use bell notifications instead
    });
})();

function patchEndPopupPagesField() {
    const endPopup = document.getElementById('end-popup');
    const endForm = document.getElementById('end-form');
    const pagesLabel = document.getElementById('pages-label');
    const pagesInput = document.getElementById('pages');
    const projectSelect = document.getElementById('project-select');
    if (!endPopup || !endForm || !pagesLabel || !pagesInput || !projectSelect) return;
    // When end popup is shown, check if project is ProvenAir-AAR and show pages
    const observer = new MutationObserver(() => {
        const selectedOption = projectSelect.options[projectSelect.selectedIndex];
        const isProvenAirAAR = selectedOption && selectedOption.textContent === 'ProvenAir-AAR';
        pagesLabel.style.display = isProvenAirAAR ? 'block' : 'none';
        pagesInput.style.display = isProvenAirAAR ? 'block' : 'none';
        if (isProvenAirAAR) {
            pagesInput.required = true;
            // If pages is not set, try to restore from localStorage
            if (!pagesInput.value) {
                const lastPages = localStorage.getItem('lastProvenAirPages');
                if (lastPages) {
                    pagesInput.value = lastPages;
                }
            }
        } else {
            pagesInput.required = false;
            pagesInput.value = '';
        }
    });
    observer.observe(endPopup, { attributes: true, attributeFilter: ['class'] });
}
document.addEventListener('DOMContentLoaded', patchEndPopupPagesField);

// Custom table filtering removed in favor of DataTables pagination and search
function styleProvenAirProjectCells() {
    const workDataTable = document.getElementById('work-data-table');
    if (!workDataTable) return;
    workDataTable.querySelectorAll('tbody tr').forEach(row => {
        const projectCell = row.children[1];
        if (projectCell && projectCell.textContent.trim() === 'ProvenAir-AAR') {
            row.style.background = '#e3f0fd'; // Light blue background for ProvenAir rows
            // row.style.color = '#1a237e'; // Dark blue text for readability
            // Optionally, reset fontWeight if previously set
            projectCell.style.fontWeight = '';
            projectCell.style.color = '';
        } else {
            // Reset background and color for non-ProvenAir rows
            row.style.background = '';
            row.style.color = '';
        }
    });
}
// Call after table updates
const workDataTable = document.getElementById('work-data-table');
if (workDataTable) {
    const observer = new MutationObserver(styleProvenAirProjectCells);
    observer.observe(workDataTable.querySelector('tbody'), { childList: true, subtree: false });
    styleProvenAirProjectCells();
}

document.addEventListener('DOMContentLoaded', function () {
    // Enhance ProvenAir Tasks button style
    const paTasksBtn = document.getElementById('paTasksBtn');
    if (paTasksBtn) {
        paTasksBtn.style.background = 'linear-gradient(90deg, #1976d2 0%, #2196f3 100%)';
        paTasksBtn.style.color = '#fff';
        paTasksBtn.style.fontWeight = 'bold';
        paTasksBtn.style.border = 'none';
        paTasksBtn.style.borderRadius = '8px';
        paTasksBtn.style.boxShadow = '0 2px 8px rgba(25, 118, 210, 0.10)';
        paTasksBtn.style.padding = '10px 22px';
        paTasksBtn.style.fontSize = '16px';
        paTasksBtn.style.display = 'inline-flex';
        paTasksBtn.style.alignItems = 'center';
        paTasksBtn.style.gap = '8px';
        paTasksBtn.style.transition = 'background 0.2s, box-shadow 0.2s';
        paTasksBtn.onmouseover = function () {
            paTasksBtn.style.background = 'linear-gradient(90deg, #1565c0 0%, #1976d2 100%)';
            paTasksBtn.style.boxShadow = '0 4px 16px rgba(25, 118, 210, 0.18)';
        };
        paTasksBtn.onmouseout = function () {
            paTasksBtn.style.background = 'linear-gradient(90deg, #1976d2 0%, #2196f3 100%)';
            paTasksBtn.style.boxShadow = '0 2px 8px rgba(25, 118, 210, 0.10)';
        };
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const uploadTaskTab = document.getElementById('upload-task-tab');
    if (uploadTaskTab) {
        uploadTaskTab.addEventListener('click', function (e) {
            e.preventDefault();
            window.open('http://192.168.1.250:8002', '_blank');
        });
    }

    const chatTab = document.getElementById('chat-tab');
    if (chatTab) {
        chatTab.addEventListener('click', function (e) {
            e.preventDefault();
            fetch('/chat_url')
                .then(r => r.json())
                .then(data => {
                    if (data && data.url) {
                        window.open(data.url, '_blank');
                    } else if (data && data.error) {
                        alert(data.error);
                    } else {
                        alert('Unable to get chat URL');
                    }
                })
                .catch(() => alert('Unable to get chat URL'));
        });
    }
});


