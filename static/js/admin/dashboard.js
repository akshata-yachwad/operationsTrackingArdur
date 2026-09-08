// Initialize header user menu + reset popup on load
document.addEventListener('DOMContentLoaded', function () {
    if (window.__resetInit) return;
    window.__resetInit = true;
    const userNameBtn = document.getElementById('user-name');
    const userMenu = document.getElementById('user-menu');
    const openResetLink = document.getElementById('open-reset-link');
    const resetPopup = document.getElementById('reset-popup');
    const closeReset = document.querySelector('.close-reset');
    const resetForm = document.getElementById('reset-form');
    const resetCancel = document.getElementById('reset-cancel');
    let isSubmitting = false;

    if (userNameBtn && userMenu) {
        userNameBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userMenu.classList.toggle('hidden');
        });
    }
    if (openResetLink && resetPopup && userMenu) {
        openResetLink.addEventListener('click', (e) => {
            e.preventDefault();
            userMenu.classList.add('hidden');
            resetPopup.classList.remove('hidden');
        });
    }
    document.addEventListener('click', (e) => {
        if (userMenu && !userMenu.classList.contains('hidden')) {
            if (!userMenu.contains(e.target) && e.target !== userNameBtn) {
                userMenu.classList.add('hidden');
            }
        }
    });
    if (closeReset) {
        closeReset.addEventListener('click', () => {
            resetPopup.classList.add('hidden');
            if (resetForm) resetForm.reset();
        });
    }
    if (resetCancel) {
        resetCancel.addEventListener('click', () => {
            resetPopup.classList.add('hidden');
            if (resetForm) resetForm.reset();
        });
    }
    if (resetForm) {
        // Setup password visibility toggles (accessible, no layout shift)
        const container = resetForm;
        const setupToggles = () => {
            container.querySelectorAll('.password-field').forEach(wrapper => {
                const input = wrapper.querySelector('input');
                const btn = wrapper.querySelector('.password-toggle');
                if (!input || !btn) return;
                btn.addEventListener('click', () => {
                    const isPassword = input.type === 'password';
                    input.type = isPassword ? 'text' : 'password';
                    btn.setAttribute('aria-pressed', String(isPassword));
                    const icon = btn.querySelector('i');
                    if (icon) {
                        icon.classList.toggle('fa-eye', !isPassword);
                        icon.classList.toggle('fa-eye-slash', isPassword);
                    }
                }, { once: false });
            });
        };
        setupToggles();
        resetForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (isSubmitting) return;
            const oldPassword = document.getElementById('old-password').value.trim();
            const newPassword = document.getElementById('new-password').value.trim();
            const confirmPassword = document.getElementById('confirm-password').value.trim();
            if (!oldPassword || !newPassword || !confirmPassword) { alert('Please fill all fields'); return; }
            if (newPassword.length < 6) { alert('New password must be at least 6 characters'); return; }
            if (newPassword !== confirmPassword) { alert('New password and confirm password do not match'); return; }
            const submitBtn = document.getElementById('reset-submit');
            const originalHTML = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            isSubmitting = true;
            fetch('/reset_password', {
                method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '' },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) { alert('Password updated successfully'); resetForm.reset(); resetPopup.classList.add('hidden'); }
                    else { alert(data.error || 'Failed to update password'); }
                })
                .catch(() => { alert('Error updating password'); })
                .finally(() => { isSubmitting = false; submitBtn.disabled = false; submitBtn.innerHTML = originalHTML; });
        });
    }
});

const VALID_TABS = [
    'employees', 'projects', 'clientcodes', 'worktypes',
    'reports', 'breakreports', 'auditreports', 'summaryreports',
    'feedback', 'orderallocation'
];

function getTabFromHash() {
    const hash = (window.location.hash || '').replace(/^#/, '').trim();
    if (!hash) return null;
    if (hash === 'master') return 'employees';
    if (hash === 'mainreports') return 'reports';
    if (VALID_TABS.includes(hash)) return hash;
    return null;
}

function showContent(tabName, updateHash = true) {
    const userNameBtn = document.getElementById('user-name');
    const employeeId = userNameBtn ? userNameBtn.getAttribute('data-employee-id') : null;

    // Special handling for OA0001
    if (employeeId === 'OA0001') {
        document.querySelectorAll('.side-nav ul li').forEach(li => {
            if (!li.querySelector('a[href="#orderallocation"]')) {
                li.style.display = 'none';
            }
        });

        var tabs = document.getElementsByClassName("tab-content");
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].style.display = "none";
        }
        const oaTab = document.getElementById('orderallocation');
        if (oaTab) oaTab.style.display = "block";
        if (updateHash && window.location.hash !== '#orderallocation') {
            history.replaceState(null, '', '#orderallocation');
        }
        return;
    }

    if (!tabName || !VALID_TABS.includes(tabName)) {
        if (document.getElementById('reports')) {
            tabName = 'reports';
        } else if (document.getElementById('orderallocation')) {
            tabName = 'orderallocation';
        } else {
            tabName = 'reports'; // ultimate fallback
        }
    }

    // Hide all tab content
    var tabs = document.getElementsByClassName("tab-content");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].style.display = "none";
    }

    // Show the selected tab content
    var selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.style.display = "block";

        // If order allocation tab is opened, trigger data fetch
        if (tabName === 'orderallocation') {
            if (typeof window.fetchExistingOrders === 'function') {
                window.fetchExistingOrders();
            }
        }
        if (tabName === 'employees') {
            if (typeof window.fetchEmployees === 'function') {
                window.fetchEmployees();
            }
        }
    }

    // Remove all active classes
    var allLinks = document.querySelectorAll('.side-nav-btn');
    allLinks.forEach(link => {
        link.classList.remove('main-tab-active');
        link.classList.remove('sub-tab-active');
    });

    // Add appropriate active class based on tab type
    var activeLink = document.querySelector(`a[href="#${tabName}"]`);
    if (activeLink) {
        // Check if this is a sub-tab
        const isSubTab = activeLink.closest('.sub-master') || activeLink.closest('.sub-reports');

        if (isSubTab) {
            activeLink.classList.add('sub-tab-active');
            // Highlight parent tab
            const parentTab = isSubTab.closest('li').querySelector('a[href^="#master"], a[href^="#mainreports"]');
            if (parentTab) {
                parentTab.classList.add('main-tab-active');
            }
        } else {
            activeLink.classList.add('main-tab-active');
        }
    }

    // Handle sub-menu visibility
    const subMaster = document.getElementById('subMaster');
    const subReports = document.getElementById('subReports');

    if (subMaster) {
        subMaster.style.display = ['employees', 'projects', 'clientcodes', 'worktypes'].includes(tabName) ? 'block' : 'none';
    }
    if (subReports) {
        subReports.style.display = ['reports', 'breakreports', 'auditreports', 'summaryreports'].includes(tabName) ? 'block' : 'none';
    }

    // Keep URL hash in sync without scrolling the page
    if (updateHash && window.location.hash !== '#' + tabName) {
        history.replaceState(null, '', '#' + tabName);
    }
}

// Update the toggle functions to maintain active states
function toggleSubMaster(event) {
    event.preventDefault();
    const subMaster = document.getElementById('subMaster');
    const masterLink = event.currentTarget;

    if (subMaster.style.display === 'none' || subMaster.style.display === '') {
        subMaster.style.display = 'block';
        masterLink.classList.add('main-tab-active');
        showContent('employees');
    } else {
        subMaster.style.display = 'none';
        masterLink.classList.remove('main-tab-active');
    }
}

function toggleSubReports(event) {
    event.preventDefault();
    const subReports = document.getElementById('subReports');
    const reportsLink = event.currentTarget;

    if (subReports.style.display === 'none' || subReports.style.display === '') {
        subReports.style.display = 'block';
        reportsLink.classList.add('main-tab-active');
        showContent('reports');
    } else {
        subReports.style.display = 'none';
        reportsLink.classList.remove('main-tab-active');
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Get employee ID
    const userNameBtn = document.getElementById('user-name');
    const employeeId = userNameBtn ? userNameBtn.getAttribute('data-employee-id') : null;

    // Special handling for OA0001
    if (employeeId === 'OA0001') {
        // Hide all navigation items except Order Allocation
        document.querySelectorAll('.side-nav ul li').forEach(li => {
            if (!li.querySelector('a[href="#orderallocation"]')) {
                li.style.display = 'none';
            }
        });
        showContent('orderallocation', false);
    } else {
        // Restore tab from URL hash if available, otherwise pass null to let showContent handle fallback
        const initialTab = getTabFromHash();
        showContent(initialTab, false);
    }

    // Respond when user clicks back/forward or modifies the URL hash
    window.addEventListener('hashchange', function () {
        const activeTab = getTabFromHash();
        if (activeTab) {
            showContent(activeTab, false);
        }
    });

    // Get elements
    const logoutBtn = document.getElementById('logout-btn');
    const logoutPopup = document.getElementById('logout-popup');
    const confirmLogout = document.getElementById('confirm-logout');
    const cancelLogout = document.getElementById('cancel-logout');

    // Get side navigation elements
    const sideNav = document.getElementById('side-nav');
    const content = document.getElementById('content');
    const wtcontent = document.getElementById('wtcontent');
    const procontent = document.getElementById('procontent');
    const cccontent = document.getElementById('cccontent');
    const repcontent = document.getElementById('repcontent');
    const feedbackcontent = document.getElementById('feedbackcontent');
    const breakscontent = document.getElementById('breakscontent');
    const summarycontent = document.getElementById('summarycontent');
    const auditcontent = document.getElementById('auditcontent');
    const orderallocationcontent = document.getElementById('orderallocationcontent');

    // Remove the toggle button since we're using hover
    const toggleNavButton = document.getElementById('toggle-nav');
    if (toggleNavButton) {
        toggleNavButton.style.display = 'none';
    }

    // Ensure content starts unshifted for collapsed side nav
    if (content) content.classList.remove('shifted');

    // Function to expand side nav
    function expandSideNav() {
        if (content) content.classList.add('shifted');

        // Show active sub-menu
        if (document.querySelector('.main-tab-active')) {
            const activeMainTab = document.querySelector('.main-tab-active').getAttribute('href');
            if (activeMainTab === '#master' && subMaster) {
                subMaster.style.display = 'block';
            } else if (activeMainTab === '#mainreports' && subReports) {
                subReports.style.display = 'block';
            }
        }
    }

    // Function to collapse side nav
    function collapseSideNav() {
        if (content) content.classList.remove('shifted');
    }

    // Add hover event listeners to side nav
    if (sideNav) {
        sideNav.addEventListener('mouseenter', expandSideNav);
        sideNav.addEventListener('mouseleave', collapseSideNav);
    }

    // Modified toggleSubMaster function
    window.toggleSubMaster = function (event) {
        event.preventDefault();
        const subMaster = document.getElementById('subMaster');
        const masterLink = event.currentTarget;

        if (subMaster.style.display === 'none' || subMaster.style.display === '') {
            subMaster.style.display = 'block';
            masterLink.classList.add('main-tab-active');
            showContent('employees');
        } else if (!sideNav.classList.contains('collapsed') || sideNav.matches(':hover')) {
            subMaster.style.display = 'none';
            masterLink.classList.remove('main-tab-active');
        }
    }

    // Modified toggleSubReports function
    window.toggleSubReports = function (event) {
        event.preventDefault();
        const subReports = document.getElementById('subReports');
        const reportsLink = event.currentTarget;

        if (subReports.style.display === 'none' || subReports.style.display === '') {
            subReports.style.display = 'block';
            reportsLink.classList.add('main-tab-active');
            showContent('reports');
        } else if (!sideNav.classList.contains('collapsed') || sideNav.matches(':hover')) {
            subReports.style.display = 'none';
            reportsLink.classList.remove('main-tab-active');
        }
    }

    // showContent('employees'); // You can set the initial tab content here
    const manualButton = document.getElementById("manualButton");
    const manualModal = document.getElementById("manualModal");
    const manualClose = manualModal ? manualModal.querySelector(".manual-close") : null;

    if (manualButton && manualModal) {
        const toggleManual = (show) => {
            manualModal.classList.toggle('hidden', !show);
            document.body.style.overflow = show ? 'hidden' : '';
        };

        manualButton.addEventListener('click', () => toggleManual(true));
        if (manualClose) {
            manualClose.addEventListener('click', () => toggleManual(false));
        }
        manualModal.addEventListener('click', (e) => {
            if (e.target === manualModal) {
                toggleManual(false);
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !manualModal.classList.contains('hidden')) {
                toggleManual(false);
            }
        });
    }

    // --- Employee Table State & Initialization ---
    window.allEmployees = [];
    window.filteredEmployees = [];
    window.currentEmployeePage = 1;
    window.employeeRowsPerPage = 15;
    window.employeeIdToDelete = null;

    window.fetchEmployees = function() {
        const tbody = document.querySelector("#employees-table tbody");
        if (tbody) tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;padding:20px;"><i class="fas fa-spinner fa-spin"></i> Loading employees...</td></tr>';
        
        fetch("/api/v1/auth/employees/", { credentials: 'same-origin' })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || (Array.isArray(resp) ? resp : []);
                window.allEmployees = Array.isArray(data) ? data : [];
                if (typeof window.filterEmployees === 'function') {
                    window.filterEmployees();
                }
            })
            .catch(error => {
                console.error("Error fetching employees:", error);
                if (tbody) tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;color:#ef4444;padding:20px;">Error loading employees: ${error.message}</td></tr>`;
            });
    };

    window.renderEmployeesTable = function() {
        const tbody = document.querySelector("#employees-table tbody");
        const pageNumberSpan = document.getElementById("PageNumber");
        const prevPageButton = document.getElementById("empprevPage");
        const nextPageButton = document.getElementById("empnextPage");

        if (!tbody) return;
        tbody.innerHTML = "";

        const totalPages = Math.max(1, Math.ceil(window.filteredEmployees.length / window.employeeRowsPerPage));
        if (pageNumberSpan) {
            pageNumberSpan.textContent = `${window.filteredEmployees.length === 0 ? 0 : window.currentEmployeePage} of ${totalPages}`;
        }
        if (prevPageButton) prevPageButton.disabled = window.currentEmployeePage <= 1;
        if (nextPageButton) nextPageButton.disabled = window.currentEmployeePage >= totalPages;

        if (window.filteredEmployees.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13" class="no-data-text" style="text-align:center;padding:24px;color:#888;">No employees found</td></tr>';
            return;
        }

        const startIndex = (window.currentEmployeePage - 1) * window.employeeRowsPerPage;
        const endIndex = Math.min(startIndex + window.employeeRowsPerPage, window.filteredEmployees.length);
        const pageItems = window.filteredEmployees.slice(startIndex, endIndex);

        pageItems.forEach((emp, index) => {
            const tr = document.createElement("tr");
            const statusClass = (emp.status || '').toLowerCase() === 'active' ? 'status-active' : 'status-inactive';
            tr.innerHTML = `
                <td>${startIndex + index + 1}</td>
                <td><strong>${emp.name || '-'}</strong></td>
                <td>${emp.employee_id || '-'}</td>
                <td>${emp.role || '-'}</td>
                <td>${emp.joining_date || emp.date_of_joining || '-'}</td>
                <td>${emp.work_location || emp.department || '-'}</td>
                <td>${emp.shift_time || emp.shift || '-'}</td>
                <td><a href="#" class="project-link" style="color: #12b76a; font-weight: 600;" data-employee-id="${emp.employee_id}"><i class="fas fa-project-diagram"></i> ${(emp.project_names && emp.project_names.length) || 0}</a></td>
                <td><a href="#" class="empclient-code-link" style="color: #12b76a; font-weight: 600;" data-employee-id="${emp.employee_id}"><i class="fas fa-code"></i> ${(emp.client_code_names && emp.client_code_names.length) || 0}</a></td>
                <td><a href="#" class="work-type-link" style="color: #12b76a; font-weight: 600;" data-employee-id="${emp.employee_id}"><i class="fas fa-list-ul"></i> ${(emp.work_type_names && emp.work_type_names.length) || 0}</a></td>
                <td><span class="${statusClass}">${emp.status || '-'}</span></td>
                <td>${emp.active_inactive_date || '-'}</td>
                <td class="action-buttons">
                    <button class="edit-btn" data-id="${emp.employee_id}" title="Edit"><i class="fas fa-edit"></i></button>
                    <button class="delete-btn" data-id="${emp.employee_id}" title="Delete"><i class="fas fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    };

    // Pagination handlers
    const prevPageButton = document.getElementById("empprevPage");
    const nextPageButton = document.getElementById("empnextPage");
    if (prevPageButton) {
        prevPageButton.addEventListener("click", function () {
            if (window.currentEmployeePage > 1) {
                window.currentEmployeePage--;
                window.renderEmployeesTable();
            }
        });
    }
    if (nextPageButton) {
        nextPageButton.addEventListener("click", function () {
            const totalPages = Math.ceil(window.filteredEmployees.length / window.employeeRowsPerPage);
            if (window.currentEmployeePage < totalPages) {
                window.currentEmployeePage++;
                window.renderEmployeesTable();
            }
        });
    }

    // Initialize fetching when script loads
    window.fetchEmployees();

    // Event Delegation for Employee Table Actions
    const employeesTable = document.getElementById("employees-table");
    if (employeesTable) {
        employeesTable.addEventListener("click", function (e) {
            const projectLink = e.target.closest(".project-link");
            const clientCodeLink = e.target.closest(".empclient-code-link");
            const workTypeLink = e.target.closest(".work-type-link");
            const editBtn = e.target.closest(".edit-btn");
            const deleteBtn = e.target.closest(".delete-btn");

            if (projectLink) {
                e.preventDefault();
                const employeeId = projectLink.getAttribute("data-employee-id");
                fetch(`/api/v1/auth/employees/${employeeId}/`, { credentials: 'same-origin' })
                    .then(response => response.json())
                    .then(resp => {
                        const data = resp.data || resp;
                        if (data.project_names && data.project_names.length > 0) {
                            const projectList = document.getElementById("projectList");
                            projectList.innerHTML = "";
                            data.project_names.forEach((project, index) => {
                                const row = document.createElement("tr");
                                row.innerHTML = `<td>${index + 1}</td><td>${project}</td>`;
                                projectList.appendChild(row);
                            });
                            document.getElementById("projectModalHeader").textContent = `Projects for Employee ID: ${employeeId}`;
                            document.getElementById("projectModal").style.display = "block";
                            const closeModal = document.getElementById("projectModal").querySelector(".close");
                            closeModal.addEventListener("click", () => {
                                document.getElementById("projectModal").style.display = "none";
                            }, { once: true });
                        } else {
                            alert("No projects found for this employee.");
                        }
                    })
                    .catch(error => alert("An error occurred while fetching projects."));
            } else if (clientCodeLink) {
                e.preventDefault();
                const employeeId = clientCodeLink.getAttribute("data-employee-id");
                fetch(`/api/v1/auth/employees/${employeeId}/`, { credentials: 'same-origin' })
                    .then(response => response.json())
                    .then(resp => {
                        const data = resp.data || resp;
                        if (data.client_code_names && data.client_code_names.length > 0) {
                            const clientCodeList = document.getElementById("clientCodeList");
                            clientCodeList.innerHTML = "";
                            data.client_code_names.forEach((code, index) => {
                                const row = document.createElement("tr");
                                row.innerHTML = `<td>${index + 1}</td><td>${code}</td>`;
                                clientCodeList.appendChild(row);
                            });
                            document.getElementById("clientCodeModalHeader").textContent = `Client Codes for Employee ID: ${employeeId}`;
                            document.getElementById("clientCodeModal").style.display = "block";
                            const closeModal = document.getElementById("clientCodeModal").querySelector(".close");
                            closeModal.addEventListener("click", () => {
                                document.getElementById("clientCodeModal").style.display = "none";
                            }, { once: true });
                        } else {
                            alert("No client codes found for this employee.");
                        }
                    })
                    .catch(error => alert("An error occurred while fetching client codes."));
            } else if (workTypeLink) {
                e.preventDefault();
                const employeeId = workTypeLink.getAttribute("data-employee-id");
                fetch(`/api/v1/auth/employees/${employeeId}/`, { credentials: 'same-origin' })
                    .then(response => response.json())
                    .then(resp => {
                        const data = resp.data || resp;
                        if (data.work_type_names && data.work_type_names.length > 0) {
                            const workTypeList = document.getElementById("workTypeList");
                            workTypeList.innerHTML = "";
                            data.work_type_names.forEach((workType, index) => {
                                const row = document.createElement("tr");
                                row.innerHTML = `<td>${index + 1}</td><td>${workType}</td>`;
                                workTypeList.appendChild(row);
                            });
                            document.getElementById("workTypeModalHeader").textContent = `Work Types for Employee ID: ${employeeId}`;
                            document.getElementById("workTypeModal").style.display = "block";
                            const closeModal = document.getElementById("workTypeModal").querySelector(".wtclose");
                            closeModal.addEventListener("click", () => {
                                document.getElementById("workTypeModal").style.display = "none";
                            }, { once: true });
                        } else {
                            alert("No work types found for this employee.");
                        }
                    })
                    .catch(error => alert("An error occurred while fetching work types."));
            } else if (editBtn) {
                const employeeId = editBtn.getAttribute("data-id");
                fetch(`/api/v1/auth/employees/${employeeId}/`, { credentials: 'same-origin' })
                    .then(response => response.json())
                    .then(resp => {
                        const data = resp.data || resp;
                        if (data.error) {
                            alert(data.error.message || data.error);
                        } else {
                            document.getElementById("employee-id").value = data.id;
                            document.getElementById("employee-name").value = data.name;
                            document.getElementById("employee-email").value = data.email || "";
                            document.getElementById("employee-phone").value = data.phone || "";
                            document.getElementById("employee-alternate_phone").value = data.alternate_phone || "";
                            document.getElementById("employee-employee_id").value = data.employee_id;
                            document.getElementById("employee-employee_id").setAttribute("data-original", data.employee_id);
                            
                            const roleSelect = document.getElementById("employee-role");
                            roleSelect.value = data.role.toLowerCase(); // Map nicely
                            roleSelect.dispatchEvent(new Event('change'));
                            
                            document.getElementById("employee-employee_type").value = data.employee_type ? data.employee_type.toLowerCase() : "employee";
                            document.getElementById("employee-joining_date").value = data.joining_date;
                            document.getElementById("employee-work_location").value = data.work_location;
                            document.getElementById("employee-active_inactive_date").value = data.active_inactive_date;
                            
                            // Make status dropdown tolerant
                            const statusSel = document.getElementById("employee-status");
                            if (statusSel) {
                                Array.from(statusSel.options).forEach(opt => {
                                    if(opt.value.toLowerCase() === (data.status || '').toLowerCase()) {
                                        statusSel.value = opt.value;
                                    }
                                });
                            }

                            if (typeof window.fetchShifts === 'function') window.fetchShifts(data.shift_time);

                            initialSelectedProjects = data.projects ? data.projects.split('|') : [];
                            initialSelectedClientCodes = data.client_code ? data.client_code.split('|') : [];
                            initialSelectedWorkTypes = data.work_type ? data.work_type.split('|') : [];

                            if (typeof fetchProjectsForEdit === 'function') fetchProjectsForEdit(initialSelectedProjects);
                            if (typeof fetchClientCodesForEdit === 'function') fetchClientCodesForEdit(initialSelectedProjects, initialSelectedClientCodes);
                            if (typeof fetchWorkTypesForEdit === 'function') fetchWorkTypesForEdit(initialSelectedClientCodes, initialSelectedWorkTypes);

                            document.getElementById("employeeModal").style.display = "flex";
                        }
                    })
                    .catch(error => console.error("Error fetching employee data:", error));
            } else if (deleteBtn) {
                window.employeeIdToDelete = deleteBtn.getAttribute("data-id");
                document.getElementById("confirmDeleteModal").style.display = "flex";
            }
        });
    }

    // Modal Close logic for edit modal
    const employeeModal = document.getElementById("employeeModal");
    const closeEmployeeModal = document.querySelector(".close-btn"); // the first one is actually add modal but there's multiple
    // Let's bind directly to the specific close buttons
    const empModalCloseBtn = employeeModal ? employeeModal.querySelector(".close-btn") : null;
    if (empModalCloseBtn) {
        empModalCloseBtn.addEventListener("click", () => {
            employeeModal.style.display = "none";
        });
    }
    
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
    const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
    const confirmDeleteModal = document.getElementById("confirmDeleteModal");
    
    if (cancelDeleteBtn) {
        cancelDeleteBtn.addEventListener("click", () => {
            confirmDeleteModal.style.display = "none";
        });
    }
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", function () {
            if (!window.employeeIdToDelete) return;
            fetch(`/api/v1/auth/employees/${window.employeeIdToDelete}/`, {
                method: "DELETE",
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '' }
            })
                .then(response => {
                    if (response.ok) {
                        window.fetchEmployees();
                    } else {
                        alert("Failed to delete employee.");
                    }
                    confirmDeleteModal.style.display = "none";
                });
        });
    }


    const addButton = document.getElementById("addEmployeeButton");
    const addModal = document.getElementById("addEmployeeModal");
    const editButtons = document.querySelectorAll(".edit-btn");
    const modal = document.getElementById("employeeModal");
    const closeModal = document.querySelector(".close-btn");
    const addForm = document.getElementById("addEmployeeForm");
    const form = document.getElementById("editEmployeeForm");

    const projectLinks = document.querySelectorAll(".project-link");
    const clientCodeLinks = document.querySelectorAll(".empclient-code-link");





    // Fetch shifts when page loads
    fetchShifts();

    // Open the Add Employee modal
    addButton.addEventListener("click", function () {
        addForm.reset();
        fetchProjects();
        fetchShifts(); // Refresh shifts when opening add modal
        
        const newRoleSelect = document.getElementById("new-employee-role");
        if (newRoleSelect) {
            newRoleSelect.dispatchEvent(new Event('change'));
        }
        
        addModal.style.display = "flex";
    });

    // Close the modal when the "X" button is clicked
    closeModal.addEventListener("click", function () {
        addModal.style.display = "none";
    });


    // Fetch all projects
    function fetchProjects() {
        fetch('/api/v1/masters/emp_get_projects/')
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const addProjectSelect = document.getElementById("new-employee-projects");
                addProjectSelect.innerHTML = '';

                data.projects.forEach(project => {
                    const option = document.createElement("option");
                    option.value = project.project_id;
                    option.textContent = project.project_name;
                    addProjectSelect.appendChild(option);
                });

                // Setup checkboxes for add form
                setupCheckboxList(
                    'new-employee-projects',
                    'add-projects-list',
                    'add-projects-search'
                )();
            })
            .catch(error => console.error('Error fetching projects:', error));
    }

    // Fetch client codes
    function fetchClientCodes(projectIds) {
        return fetch('/api/v1/masters/emp_get_client_codes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '' },
            body: JSON.stringify({ project_ids: projectIds })
        })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const clientCodeSelect = document.getElementById("new-employee-client_code");
                clientCodeSelect.innerHTML = '';

                data.client_codes.forEach(clientCode => {
                    const option = document.createElement("option");
                    option.value = clientCode;
                    option.textContent = clientCode;
                    clientCodeSelect.appendChild(option);
                });

                // Setup checkboxes for add form
                setupCheckboxList(
                    'new-employee-client_code',
                    'add-client-codes-list',
                    'add-client-codes-search'
                )();
            })
            .catch(error => console.error('Error fetching client codes:', error));
    }

    // Fetch work types
    function fetchWorkTypes(clientCodes) {
        return fetch('/api/v1/masters/emp_get_worktypes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '' },
            body: JSON.stringify({ client_codes: clientCodes })
        })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const workTypeSelect = document.getElementById("new-employee-work_type");
                workTypeSelect.innerHTML = '';

                data.work_types.forEach(workType => {
                    const option = document.createElement("option");
                    option.value = workType;
                    option.textContent = workType;
                    workTypeSelect.appendChild(option);
                });

                // Setup checkboxes for add form
                setupCheckboxList(
                    'new-employee-work_type',
                    'add-work-types-list',
                    'add-work-types-search'
                )();
            })
            .catch(error => console.error('Error fetching work types:', error));
    }

    // Temporary object to store selected values
    const tempSelectedValues = {
        projects: [],
        clientCodes: [],
        workTypes: []
    };

    // Store the initially selected values from employee data
    let initialSelectedProjects = [];
    let initialSelectedClientCodes = [];
    let initialSelectedWorkTypes = [];

    // Function to fetch and populate projects dropdown for edit form
    function fetchProjectsForEdit(selectedProjects = []) {
        fetch('/api/v1/masters/emp_get_projects/')
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const projectSelect = document.getElementById("employee-projects");
                projectSelect.innerHTML = '';

                data.projects.forEach(project => {
                    const option = document.createElement("option");
                    option.value = project.project_id;
                    option.textContent = project.project_name;
                    if (initialSelectedProjects.includes(project.project_id) ||
                        selectedProjects.includes(project.project_id)) {
                        option.selected = true;
                    }
                    projectSelect.appendChild(option);
                });

                // Setup checkboxes for edit form
                setupCheckboxList(
                    'employee-projects',
                    'edit-projects-list',
                    'edit-projects-search'
                )();

                tempSelectedValues.projects = Array.from(projectSelect.selectedOptions).map(option => option.value);
            })
            .catch(error => console.error('Error fetching projects:', error));
    }

    // Function to fetch and populate client codes dropdown for edit form
    function fetchClientCodesForEdit(selectedProjects, selectedClientCodes = []) {
        fetch('/api/v1/masters/emp_get_client_codes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '' },
            body: JSON.stringify({ project_ids: selectedProjects })
        })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const clientCodeSelect = document.getElementById("employee-client_code");
                clientCodeSelect.innerHTML = '';

                data.client_codes.forEach(clientCode => {
                    const option = document.createElement("option");
                    option.value = clientCode;
                    option.textContent = clientCode;
                    if (initialSelectedClientCodes.includes(clientCode) ||
                        selectedClientCodes.includes(clientCode)) {
                        option.selected = true;
                    }
                    clientCodeSelect.appendChild(option);
                });

                // Setup checkboxes for edit form - removed readonly
                setupCheckboxList(
                    'employee-client_code',
                    'edit-client-codes-list',
                    'edit-client-codes-search',
                    false  // Changed from true to false to make it editable
                )();

                tempSelectedValues.clientCodes = Array.from(clientCodeSelect.selectedOptions).map(option => option.value);
            })
            .catch(error => console.error('Error fetching client codes:', error));
    }

    // Function to fetch and populate work types dropdown for edit form
    function fetchWorkTypesForEdit(selectedClientCodes, selectedWorkTypes = []) {
        fetch('/api/v1/masters/emp_get_worktypes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '' },
            body: JSON.stringify({ client_codes: selectedClientCodes })
        })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                const workTypeSelect = document.getElementById("employee-work_type");
                workTypeSelect.innerHTML = '';

                data.work_types.forEach(workType => {
                    const option = document.createElement("option");
                    option.value = workType;
                    option.textContent = workType;
                    if (initialSelectedWorkTypes.includes(workType) ||
                        selectedWorkTypes.includes(workType)) {
                        option.selected = true;
                    }
                    workTypeSelect.appendChild(option);
                });

                // Setup checkboxes for edit form - removed readonly
                setupCheckboxList(
                    'employee-work_type',
                    'edit-work-types-list',
                    'edit-work-types-search',
                    false  // Changed from true to false to make it editable
                )();

                tempSelectedValues.workTypes = Array.from(workTypeSelect.selectedOptions).map(option => option.value);
            })
            .catch(error => console.error('Error fetching work types:', error));
    }

    // Event listener for project selection in edit form
    document.getElementById("employee-projects").addEventListener("change", function () {
        const selectedProjects = Array.from(this.selectedOptions).map(option => option.value);
        tempSelectedValues.projects = selectedProjects; // Store temporarily
        fetchClientCodesForEdit(selectedProjects); // Fetch client codes
    });

    // Handle Employee Type visibility based on Role for Edit form
    document.getElementById("employee-role").addEventListener("change", function () {
        const typeGroup = document.getElementById("employee-type-group");
        if (this.value.toLowerCase() === "employee") {
            typeGroup.style.display = "block";
            document.getElementById("employee-employee_type").required = true;
        } else {
            typeGroup.style.display = "none";
            document.getElementById("employee-employee_type").required = false;
        }
    });

    // Handle Employee Type visibility based on Role for Add form
    const newRoleSelect = document.getElementById("new-employee-role");
    if (newRoleSelect) {
        newRoleSelect.addEventListener("change", function () {
            const typeGroup = document.getElementById("new-employee-type-group");
            if (this.value.toLowerCase() === "employee") {
                typeGroup.style.display = "block";
                document.getElementById("new-employee-employee_type").required = true;
            } else {
                typeGroup.style.display = "none";
                document.getElementById("new-employee-employee_type").required = false;
            }
        });
    }

    // Event listener for client code selection in edit form
    document.getElementById("employee-client_code").addEventListener("change", function () {
        const selectedClientCodes = Array.from(this.selectedOptions).map(option => option.value);
        tempSelectedValues.clientCodes = selectedClientCodes; // Store temporarily
        fetchWorkTypesForEdit(selectedClientCodes); // Fetch work types
    });

    // Event listener for project selection in add form
    document.getElementById("new-employee-projects").addEventListener("change", function () {
        const selectedProjects = Array.from(this.selectedOptions).map(option => option.value);
        fetchClientCodes(selectedProjects); // Fetch client codes
    });

    // Event listener for client code selection in add form
    document.getElementById("new-employee-client_code").addEventListener("change", function () {
        const selectedClientCodes = Array.from(this.selectedOptions).map(option => option.value);
        fetchWorkTypes(selectedClientCodes); // Fetch work types
    });

    // Event listener for joining date change in add form
    document.getElementById("new-employee-joining_date").addEventListener("change", function () {
        document.getElementById("new-employee-active_inactive_date").value = this.value;
    });

    // Handle Add Employee form submission
    addForm.addEventListener("submit", function (e) {
        e.preventDefault();

        const selectedWorkTypes = Array.from(document.getElementById("new-employee-work_type").selectedOptions)
            .map(option => option.value).join('|');
        const newEmployeeData = {
            name: document.getElementById("new-employee-name").value,
            email: document.getElementById("new-employee-email").value,
            phone: document.getElementById("new-employee-phone").value,
            alternate_phone: document.getElementById("new-employee-alternate_phone").value,
            employee_id: document.getElementById("new-employee-employee_id").value,
            role: document.getElementById("new-employee-role").value,
            employee_type: document.getElementById("new-employee-employee_type").value,
            joining_date: document.getElementById("new-employee-joining_date").value,
            work_location: document.getElementById("new-employee-work_location").value,
            shift_time: document.getElementById("new-employee-shift_time").value,
            client_code: Array.from(document.getElementById("new-employee-client_code").selectedOptions)
                .map(option => option.value).join('|'),
            projects: Array.from(document.getElementById("new-employee-projects").selectedOptions)
                .map(option => option.value).join('|'),
            work_type: selectedWorkTypes,
            status: document.getElementById("new-employee-status").value,
            active_inactive_date: document.getElementById("new-employee-active_inactive_date").value
        };

        fetch('/api/v1/auth/employees/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            body: JSON.stringify(newEmployeeData)
        })
            .then(response => response.json())
            .then(resp => {
                if (!resp.error) {
                    alert('Employee added successfully');
                    addModal.style.display = "none";
                } else {
                    alert(resp.error.message || 'Error adding employee');
                }
                if(typeof window.fetchEmployees === "function") window.fetchEmployees();
            })
            .catch(error => console.error("Error adding employee:", error));
    });


    form.addEventListener("submit", function (e) {
        e.preventDefault();

        // Get form data
        const name = document.getElementById("employee-name").value;
        const email = document.getElementById("employee-email").value;
        const phone = document.getElementById("employee-phone").value;
        const alternatePhone = document.getElementById("employee-alternate_phone").value;
        const employeeId = document.getElementById("employee-employee_id").value;
        const role = document.getElementById("employee-role").value;
        const employeeType = document.getElementById("employee-employee_type").value;
        const joiningDate = document.getElementById("employee-joining_date").value;
        const workLocation = document.getElementById("employee-work_location").value;
        const shiftTime = document.getElementById("employee-shift_time").value;
        const status = document.getElementById("employee-status").value;
        const activeInactiveDate = document.getElementById("employee-active_inactive_date").value;

        // Get original employee ID for the URL (in case it was changed)
        const employeeIdInput = document.getElementById("employee-employee_id");
        const originalEmployeeId = employeeIdInput.getAttribute("data-original") || employeeId;

        // Collect selected client codes and join them with '|'
        const clientCodeSelect = document.getElementById("employee-client_code");
        const selectedClientCodes = Array.from(clientCodeSelect.selectedOptions).map(option => option.value).join('|');

        // Collect selected projects and join them with '|'
        const projectSelect = document.getElementById("employee-projects");
        const selectedProjects = Array.from(projectSelect.selectedOptions).map(option => option.value).join('|');

        // Collect selected work types and join them with '|'
        const workTypeSelect = document.getElementById("employee-work_type");
        const selectedWorkTypes = Array.from(workTypeSelect.selectedOptions).map(option => option.value).join('|');

        // Send the data in the POST request
        fetch(`/api/v1/auth/employees/${originalEmployeeId}/`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            body: JSON.stringify({
                name: name,
                email: email,
                phone: phone,
                alternate_phone: alternatePhone,
                employee_id: employeeId,
                role: role,
                employee_type: employeeType,
                joining_date: joiningDate,
                work_location: workLocation,
                shift_time: shiftTime,
                client_code: selectedClientCodes, // Send the joined client codes
                projects: selectedProjects, // Send the joined projects
                work_type: selectedWorkTypes, // Send the joined work types
                status: status,
                active_inactive_date: activeInactiveDate,
            }),
        })
            .then(response => response.json())
            .then(resp => {
                if (resp.error) {
                    alert("Error updating employee data: " + resp.error.message);
                    return;
                }
                alert("Employee updated successfully!");
                modal.style.display = "none";
                if(typeof window.fetchEmployees === "function") window.fetchEmployees();
            })
            .catch(error => {
                alert("Error updating employee data.");
                console.error("Error:", error);
            });
    });


    // Show popup when logout button is clicked
    logoutBtn.addEventListener('click', (e) => {
        e.preventDefault(); // Stop the form from submitting immediately
        // Check for active work session before allowing logout
        fetch('/api/v1/tracking/sessions/current/')
            .then(response => response.json())
            .then(res => {
                // The API omits 'data' entirely if there is no active session (returns {ok: true})
                if (res.data) {
                    alert('You have an active work session. Do you want to end it first?');
                    // Do not show logout popup, restrict logout
                    return;
                } else {
                    logoutPopup.classList.remove('hidden');
                }
            })
            .catch(error => {
                // On error, fallback to showing the popup (or optionally block logout)
                console.error('Error checking active work session:', error);
                logoutPopup.classList.remove('hidden');
            });
    });

    // Handle confirm logout
    confirmLogout.addEventListener('click', () => {
        fetch('/api/v1/auth/logout/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        })
            .then(response => {
                if (response.ok) {
                    window.location.href = '/login/'; // Redirect to login page
                } else {
                    alert('Error logging out. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });

    // Close popup when cancel is clicked
    cancelLogout.addEventListener('click', () => {
        logoutPopup.classList.add('hidden');
    });

});

function filterEmployees() {
    const searchInput = document.getElementById("search");
    const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
    
    if (!query) {
        window.filteredEmployees = [...window.allEmployees];
    } else {
        window.filteredEmployees = window.allEmployees.filter(emp => {
            const name = (emp.name || "").toLowerCase();
            const empId = (emp.employee_id || "").toLowerCase();
            const role = (emp.role || "").toLowerCase();
            const loc = (emp.work_location || emp.department || "").toLowerCase();
            const status = (emp.status || "").toLowerCase();
            const shift = (emp.shift_time || emp.shift || "").toLowerCase();
            return name.includes(query) || empId.includes(query) || role.includes(query) || loc.includes(query) || status.includes(query) || shift.includes(query);
        });
    }
    window.currentEmployeePage = 1;
    if (typeof window.renderEmployeesTable === 'function') {
        window.renderEmployeesTable();
    }
    
    // Show/hide clear button based on input value
    const clearBtn = searchInput ? searchInput.nextElementSibling : null;
    if (clearBtn && clearBtn.classList.contains('clear-search')) {
        clearBtn.style.display = searchInput.value ? "block" : "none";
    }
}
window.filterEmployees = filterEmployees;

function filterProjects() {
    var input = document.getElementById("searchProject");
    var filter = input.value.toLowerCase();
    var table = document.getElementById("projects-table");
    var rows = table.getElementsByTagName("tr");

    for (var i = 1; i < rows.length; i++) {
        var row = rows[i];
        var cells = row.getElementsByTagName("td");
        var matchFound = false;

        for (var j = 0; j < cells.length; j++) {
            var cell = cells[j];
            if (cell.innerText.toLowerCase().includes(filter)) {
                matchFound = true;
                break;
            }
        }

        row.style.display = matchFound ? "" : "none";
    }

    // Show/hide clear button based on input value
    const clearBtn = input.nextElementSibling;
    if (clearBtn && clearBtn.classList.contains('clear-search')) {
        clearBtn.style.display = input.value ? "block" : "none";
    }
}

function dashboardFilterClientCodes() {
    // Legacy DOM-only filter kept for compatibility if needed, prefer window.filterClientCodes
    if (typeof window.filterClientCodes === 'function') {
        window.filterClientCodes();
        return;
    }
    var input = document.getElementById("searchClientCode");
    var filter = input.value.toLowerCase();
    var table = document.getElementById("client-codes-table");
    if (!table) return;
    var rows = table.getElementsByTagName("tr");
    for (var i = 1; i < rows.length; i++) {
        var row = rows[i];
        var cells = row.getElementsByTagName("td");
        var matchFound = false;
        for (var j = 0; j < cells.length; j++) {
            var cell = cells[j];
            if (cell.innerText.toLowerCase().includes(filter)) { matchFound = true; break; }
        }
        row.style.display = matchFound ? "" : "none";
    }
    const clearBtn = input.nextElementSibling;
    if (clearBtn && clearBtn.classList.contains('clear-search')) {
        clearBtn.style.display = input.value ? "block" : "none";
    }
}

function dashboardFilterWorktypes() {
    if (typeof window.filterWorktypes === 'function') {
        window.filterWorktypes();
        return;
    }
    var input = document.getElementById("searchWorktype");
    var filter = input.value.toLowerCase();
    var table = document.getElementById("worktypes-table");
    if (!table) return;
    var rows = table.getElementsByTagName("tr");
    for (var i = 1; i < rows.length; i++) {
        var row = rows[i];
        var cells = row.getElementsByTagName("td");
        var matchFound = false;
        for (var j = 0; j < cells.length; j++) {
            var cell = cells[j];
            if (cell.innerText.toLowerCase().includes(filter)) { matchFound = true; break; }
        }
        row.style.display = matchFound ? "" : "none";
    }
    const clearBtn = input.nextElementSibling;
    if (clearBtn && clearBtn.classList.contains('clear-search')) {
        clearBtn.style.display = input.value ? "block" : "none";
    }
}

// Function to handle clearing search input
function handleClearSearch(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.value = '';
        // Trigger the corresponding filter function
        switch (inputId) {
            case 'search':
                filterEmployees();
                break;
            case 'searchProject':
                filterProjects();
                break;
            case 'searchClientCode':
                if (typeof window.filterClientCodes === 'function') window.filterClientCodes(); else dashboardFilterClientCodes();
                break;
            case 'searchWorktype':
                if (typeof window.filterWorktypes === 'function') window.filterWorktypes(); else dashboardFilterWorktypes();
                break;
        }
    }
}

// Add event listeners for search inputs when document loads
document.addEventListener('DOMContentLoaded', function () {
    const searchInputs = ['search', 'searchProject', 'searchClientCode', 'searchWorktype'];

    searchInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            // Create clear button if it doesn't exist
            if (!input.nextElementSibling?.classList.contains('clear-search')) {
                const clearBtn = document.createElement('button');
                clearBtn.type = 'button';
                clearBtn.className = 'clear-search';
                clearBtn.innerHTML = '×';
                clearBtn.style.display = 'none';
                clearBtn.onclick = () => handleClearSearch(inputId);
                input.parentNode.insertBefore(clearBtn, input.nextSibling);
            }

            // Add input event listener to show/hide clear button
            input.addEventListener('input', function () {
                const clearBtn = this.nextElementSibling;
                if (clearBtn && clearBtn.classList.contains('clear-search')) {
                    clearBtn.style.display = this.value ? "block" : "none";
                }
            });
        }
    });
});

document.addEventListener('DOMContentLoaded', function () {
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

// Function to fetch and populate shifts
function fetchShifts(preselectValue = null) {
    fetch('/api/v1/masters/emp_get_shifts/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                console.error('Error fetching shifts:', data.error);
                return;
            }

            const editShiftSelect = document.getElementById("employee-shift_time");
            const addShiftSelect = document.getElementById("new-employee-shift_time");

            // Clear existing options
            editShiftSelect.innerHTML = '';
            addShiftSelect.innerHTML = '';

            // Add a default option
            const defaultOption = document.createElement("option");
            defaultOption.value = "";
            defaultOption.textContent = "Select a shift";
            editShiftSelect.appendChild(defaultOption.cloneNode(true));
            addShiftSelect.appendChild(defaultOption);

            const shifts = data.data || data;

            // Add shifts to both select elements
            shifts.forEach(shift => {
                const editOption = document.createElement("option");
                editOption.value = shift.shift;
                editOption.textContent = `${shift.shift} (${shift.startedAt} - ${shift.endedAt})`;
                editShiftSelect.appendChild(editOption);

                const addOption = document.createElement("option");
                addOption.value = shift.shift;
                addOption.textContent = `${shift.shift} (${shift.startedAt} - ${shift.endedAt})`;
                addShiftSelect.appendChild(addOption);
            });

            // Preselect value if provided
            if (preselectValue !== null) {
                editShiftSelect.value = preselectValue;
            }
        })
        .catch(error => {
            console.error('Error fetching shifts:', error);
            // Add fallback options in case of error
            const shifts = [
                { shift: 'First Shift', startedAt: '07:00:00', endedAt: '18:00:00' },
                { shift: 'General Shift', startedAt: '10:00:00', endedAt: '19:00:00' },
                { shift: 'Second Shift', startedAt: '16:00:00', endedAt: '01:00:00' },
                { shift: 'Night Shift', startedAt: '19:00:00', endedAt: '06:00:00' }
            ];

            const editShiftSelect = document.getElementById("employee-shift_time");
            const addShiftSelect = document.getElementById("new-employee-shift_time");

            editShiftSelect.innerHTML = '';
            addShiftSelect.innerHTML = '';

            const defaultOption = document.createElement("option");
            defaultOption.value = "";
            defaultOption.textContent = "Select a shift";
            editShiftSelect.appendChild(defaultOption.cloneNode(true));
            addShiftSelect.appendChild(defaultOption);

            shifts.forEach(shift => {
                const editOption = document.createElement("option");
                editOption.value = shift.shift;
                editOption.textContent = `${shift.shift} (${shift.startedAt} - ${shift.endedAt})`;
                editShiftSelect.appendChild(editOption);

                const addOption = document.createElement("option");
                addOption.value = shift.shift;
                addOption.textContent = `${shift.shift} (${shift.startedAt} - ${shift.endedAt})`;
                addShiftSelect.appendChild(addOption);
            });
            // Preselect value if provided
            if (preselectValue !== null) {
                editShiftSelect.value = preselectValue;
            }
        });
}

function setupCheckboxList(selectId, listId, searchId, isReadonly = false) {
    const select = document.getElementById(selectId);
    const list = document.getElementById(listId);
    const searchInput = document.getElementById(searchId);
    const clearSearch = document.querySelector(`#${searchId} + .emp-clear-search`);

    // Add select all/deselect functionality
    const selectAllBtn = document.querySelector(`.emp-select-all[data-target="${listId}"]`);
    const deselectAllBtn = document.querySelector(`.emp-deselect-all[data-target="${listId}"]`);

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const visibleCheckboxes = Array.from(list.querySelectorAll('.emp-checkbox-item:not(.hidden) input[type="checkbox"]'));
            visibleCheckboxes.forEach(checkbox => {
                if (!checkbox.disabled && !checkbox.checked) {
                    checkbox.checked = true;
                    // Update corresponding select option
                    const option = Array.from(select.options).find(opt => opt.value === checkbox.value);
                    if (option) option.selected = true;
                }
            });
            // Trigger change event on select
            select.dispatchEvent(new Event('change'));
        });
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', () => {
            const visibleCheckboxes = Array.from(list.querySelectorAll('.emp-checkbox-item:not(.hidden) input[type="checkbox"]'));
            visibleCheckboxes.forEach(checkbox => {
                if (!checkbox.disabled && checkbox.checked) {
                    checkbox.checked = false;
                    // Update corresponding select option
                    const option = Array.from(select.options).find(opt => opt.value === checkbox.value);
                    if (option) option.selected = false;
                }
            });
            // Trigger change event on select
            select.dispatchEvent(new Event('change'));
        });
    }

    // Create checkboxes from select options
    function createCheckboxes() {
        list.innerHTML = '';
        Array.from(select.options).forEach(option => {
            const div = document.createElement('div');
            div.className = 'emp-checkbox-item';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option.value;
            checkbox.checked = option.selected;
            checkbox.disabled = isReadonly;

            const label = document.createElement('label');
            label.textContent = option.text;

            div.appendChild(checkbox);
            div.appendChild(label);
            list.appendChild(div);

            // Update select when checkbox changes
            checkbox.addEventListener('change', () => {
                option.selected = checkbox.checked;
                select.dispatchEvent(new Event('change'));
            });
        });
    }

    // Filter checkboxes based on search
    function filterCheckboxes() {
        const searchTerm = searchInput.value.toLowerCase();
        const items = list.getElementsByClassName('emp-checkbox-item');

        Array.from(items).forEach(item => {
            const label = item.querySelector('label');
            const text = label.textContent.toLowerCase();
            item.classList.toggle('hidden', !text.includes(searchTerm));
        });

        // Show/hide clear button
        clearSearch.style.display = searchTerm ? 'block' : 'none';
    }

    // Clear search
    clearSearch.addEventListener('click', () => {
        searchInput.value = '';
        filterCheckboxes();
    });

    // Search functionality
    searchInput.addEventListener('input', filterCheckboxes);

    return createCheckboxes;
}
