document.addEventListener("DOMContentLoaded", () => {
    // Modal handling
    const projectModal = document.getElementById("projectModal");
    const addProjectModal = document.getElementById("addProjectModal");
    const confirmDeleteProjectModal = document.getElementById("confirmDeleteProjectModal");
    const closeButtons = document.querySelectorAll(".close-btn");

    const addClientCodeContainer = document.getElementById("add-client-codes-container");
    const addWorktypesContainer = document.getElementById("add-worktypes-container");

    const editClientCodeContainer = document.getElementById("edit-client-codes-container");
    const editWorktypesContainer = document.getElementById("edit-worktypes-container");

    // Buttons
    const addProjectButton = document.getElementById("addProjectButton");
    const confirmDeleteProjectBtn = document.getElementById("confirmDeleteProjectBtn");
    const cancelDeleteProjectBtn = document.getElementById("cancelDeleteProjectBtn");

    // Forms
    const editProjectForm = document.getElementById("editProjectForm");
    const addProjectForm = document.getElementById("addProjectForm");

    // Table
    const projectsTableBody = document.querySelector("#projects-table tbody");

    // Data
    let currentProjectIdToDelete = null;

    let projects = [];
    let currentPage = 1;
    const rowsPerPage = 15;

    const prevButton = document.getElementById("prevPage");
    const nextButton = document.getElementById("nextPage");
    const pageNumberDisplay = document.getElementById("propageNumber"); // Page number display

    const notify = (message, type = 'info') => {
        const prefix = type === 'error' ? 'Error: ' : type === 'success' ? 'Success: ' : '';
        alert(`${prefix}${message}`);
    };

    // Open Add Project modal directly (single-step add)
    addProjectButton.addEventListener("click", () => {
        openAddProjectModal();
    });

    // Function to open Project modal
    function openAddProjectModal() {
        fetch("/api/v1/masters/projects/next-id/", { credentials: 'same-origin' })
            .then((response) => response.json())
            .then((resp) => {
                const data = resp.data || resp;
                if (data.next_project_id) {
                    document.getElementById("add-project_id").value = data.next_project_id;
                    fetchClientCodes(document.getElementById("add-client-codes-container"));
                    document.getElementById("add-worktypes-container").innerHTML = "<p>Select client codes to load work types</p>";

                    // Initialize search functionality for add form
                    initializeAddProjectSearch();

                    // Add change event listeners for checkbox containers
                    ['add-client-codes-container', 'add-worktypes-container'].forEach(containerId => {
                        document.getElementById(containerId).addEventListener('change', () => updateActiveCounts(true));
                    });

                    addProjectModal.style.display = "block";
                } else {
                    notify('Unable to fetch next Project ID.', 'error');
                }
            })
            .catch(() => notify('Failed to fetch next Project ID.', 'error'));
    }

    // Close modals
    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            addProjectModal.style.display = "none";
        });
    });

    // Helper function to get selected work types
    function getSelectedWorkTypes(containerId) {
        const checkboxes = document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`);
        return Array.from(checkboxes).map((checkbox) => checkbox.value).join("|");
    }

    // Existing functions for fetching and displaying projects with caching
    function fetchClientCodes(container, selectedCodes = []) {
        return new Promise((resolve, reject) => {
            MasterDataCache.getOrFetch('master_clientcodes', '/api/v1/masters/clientcodes/')
                .then(resp => {
                    const data = Array.isArray(resp) ? resp : (resp.results || resp.data || []);
                    container.innerHTML = '';
                    data.forEach(clientCode => {
                        const isChecked = selectedCodes.includes(clientCode.client_code) ? 'checked' : '';
                        container.innerHTML += `
                            <label>
                                <input type="checkbox" value="${clientCode.client_code}" ${isChecked}>
                                ${clientCode.client_code}
                            </label>
                        `;
                    });

                    // Update counts after populating
                    const isAddForm = container.id === 'add-client-codes-container';
                    updateActiveCounts(isAddForm);

                    // Add change event listener for client codes
                    container.addEventListener('change', (e) => {
                        if (e.target.type === 'checkbox') {
                            handleClientCodeChange(container, e.target);
                        }
                    });

                    resolve(); // Resolve the promise after everything is done
                })
                .catch(error => {
                    console.error('Error fetching client codes:', error);
                    reject(error);
                });
        });
    }

    // Fetch work types and populate the checkbox list for Add/Edit forms with caching
    function fetchccWorkTypes(selectedWorkTypes = [], isEditForm = false) {
        MasterDataCache.getOrFetch('master_worktypes', '/api/v1/masters/worktypes/')
            .then(resp => {
                const data = Array.isArray(resp) ? resp : (resp.results || resp.data || []);
                const container = isEditForm
                    ? document.getElementById("editWorkTypesContainer")
                    : document.getElementById("addWorkTypesContainer");

                // Clear the container before populating
                container.innerHTML = "";

                // Create checkboxes dynamically
                data.forEach(workType => {
                    const isChecked = selectedWorkTypes.includes(workType.work_type) ? "checked" : "";
                    container.innerHTML += `
                        <label class="checkbox-label">
                            <input type="checkbox" value="${workType.work_type}" ${isChecked}>
                            ${workType.work_type}
                        </label>
                    `;
                });
            })
            .catch(error => {
                console.error("Error fetching work types:", error);
            });
    }

    function fetchWorkTypes(clientCodes, container, selectedWorktypes = []) {
        return fetch("/api/v1/masters/clientcodes/worktypes-for-clients/", {
            method: "POST",
            credentials: 'same-origin',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "",
            },
            body: JSON.stringify({ client_codes: clientCodes }),
        })
            .then((response) => response.json())
            .then((resp) => {
                const worktypesByClient = resp.data || resp;
                container.innerHTML = ""; // Clear container

                Object.entries(worktypesByClient).forEach(([clientCode, worktypes]) => {
                    const clientHeader = document.createElement("div");
                    clientHeader.classList.add("client-header");
                    clientHeader.textContent = `${clientCode}`;

                    const worktypeContainer = document.createElement("div");
                    worktypeContainer.classList.add("worktype-container");

                    if (worktypes.length > 0) {
                        worktypes.forEach((worktype) => {
                            const checkbox = document.createElement("input");
                            checkbox.type = "checkbox";
                            checkbox.value = worktype;
                            checkbox.id = `worktype-${clientCode}-${worktype}`;
                            // Only check if it's in selectedWorktypes (for initial load)
                            checkbox.checked = selectedWorktypes.includes(worktype);

                            const label = document.createElement("label");
                            label.htmlFor = checkbox.id;
                            label.textContent = worktype;

                            const div = document.createElement("div");
                            div.classList.add("worktype-item");
                            div.appendChild(checkbox);
                            div.appendChild(label);
                            worktypeContainer.appendChild(div);
                        });
                    } else {
                        const noWorktypesMsg = document.createElement("p");
                        noWorktypesMsg.textContent = "No work types available";
                        noWorktypesMsg.classList.add("no-worktypes-msg");
                        worktypeContainer.appendChild(noWorktypesMsg);
                    }

                    container.appendChild(clientHeader);
                    container.appendChild(worktypeContainer);
                });
            });
    }

    function handleClientCodeChange(container, checkbox) {
        const isAddForm = container.id === 'add-client-codes-container';
        const workTypesContainer = document.getElementById(isAddForm ? 'add-worktypes-container' : 'edit-worktypes-container');
        const selectedClientCodes = Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);

        if (selectedClientCodes.length > 0) {
            // Get currently selected work types before fetching new ones
            const currentSelectedWorkTypes = Array.from(workTypesContainer.querySelectorAll('input[type="checkbox"]:checked'))
                .map(cb => ({
                    value: cb.value,
                    clientCode: cb.id.split('-')[1] // Get the client code from the checkbox ID
                }));

            fetchWorkTypes(selectedClientCodes, workTypesContainer)
                .then(() => {
                    // Re-select work types only for existing client codes
                    workTypesContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                        const clientCode = cb.id.split('-')[1];
                        const worktype = cb.value;

                        // Only check if it was previously selected AND from an existing client code
                        const shouldBeChecked = currentSelectedWorkTypes.some(wt =>
                            wt.value === worktype &&
                            wt.clientCode === clientCode
                        );

                        cb.checked = shouldBeChecked;
                    });
                    updateActiveCounts(isAddForm);
                });
        } else {
            workTypesContainer.innerHTML = "<p>Select client codes to load work types</p>";
            updateActiveCounts(isAddForm);
        }
    }

    function fetchProjects() {
        fetch("/api/v1/masters/projects/?active=true", { credentials: 'same-origin' })
            .then((response) => response.json())
            .then((resp) => {
                projects = Array.isArray(resp) ? resp : (resp.results || resp.data || []);
                currentPage = 1; // Reset to first page
                displayProjectsPage(currentPage);
            });
    }

    function displayProjectsPage(page) {
        projectsTableBody.innerHTML = ""; // Clear existing rows
        const startIndex = (page - 1) * rowsPerPage;
        const endIndex = startIndex + rowsPerPage;
        const pageData = projects.slice(startIndex, endIndex);

        pageData.forEach((project, index) => {
            const clientCodesArray = project.client_code ? project.client_code.split("|") : [];
            const clientCodesCount = clientCodesArray.length;

            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${startIndex + index + 1}</td>
                <td>${project.project_id}</td>
                <td>${project.project_name}</td>
                <td>
                    <a href="#" title="View Client Codes" class="client-code-link" data-clientcodes="${project.client_code}">
                       <i class="fas fa-code"></i> ${clientCodesCount}
                    </a>
                </td>
                <td>
                    <a href="#" title="View Work Types" class="worktypes-link" data-worktypes="${project.worktypes}">
                       <i class="fas fa-tasks"></i> ${project.worktypes ? project.worktypes.split("|").length : 0}
                    </a>
                </td>
                <td>
                    <button title="Edit Project" class="proedit-btn" data-id="${project.project_id}">
                        <img src="/static/icons/edit.png" alt="Edit">
                    </button>
                    <button title="Delete Project" class="prodelete-btn" data-id="${project.project_id}">
                        <img src="/static/icons/delete.png" alt="Delete">
                    </button>
                </td>
            `;
            projectsTableBody.appendChild(row);
        });

        attachEventListeners();
        attachClientCodesClickEvent();
        attachWorktypesClickEvent();
        updatePagination();
    }

    function updatePagination() {
        const totalPages = Math.ceil(projects.length / rowsPerPage) || 1;
        prevButton.disabled = currentPage === 1;
        nextButton.disabled = currentPage >= totalPages;
        pageNumberDisplay.textContent = `${currentPage} of ${totalPages}`; // Show current and total pages
    }

    prevButton.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            displayProjectsPage(currentPage);
        }
    });

    nextButton.addEventListener("click", () => {
        const totalPages = Math.ceil(projects.length / rowsPerPage);
        if (currentPage < totalPages) {
            currentPage++;
            displayProjectsPage(currentPage);
        }
    });

    fetchProjects();

    function attachClientCodesClickEvent() {
        document.querySelectorAll(".client-code-link").forEach((link) => {
            link.addEventListener("click", function (event) {
                event.preventDefault();
                const clientCodesData = this.getAttribute("data-clientcodes");
                const clientCodesArray = clientCodesData ? clientCodesData.split("|") : [];

                const projectName = this.closest('tr').querySelector('td:nth-child(3)').textContent;

                let modalContent = `
                    <div class="modal-project-header">Client Codes for "${projectName}"</div>
                    <table border="1" style="width: 100%; border-collapse: collapse;">
                        <tr><th>Sr.No</th><th>Client Code</th></tr>
                `;
                clientCodesArray.forEach((code, index) => {
                    modalContent += `<tr><td>${index + 1}</td><td>${code}</td></tr>`;
                });
                modalContent += `</table>`;

                showModal("", modalContent); // Empty title since we're using custom header
            });
        });
    }

    function attachWorktypesClickEvent() {
        document.querySelectorAll(".worktypes-link").forEach((link) => {
            link.addEventListener("click", function (event) {
                event.preventDefault();
                const worktypesData = this.getAttribute("data-worktypes");
                const worktypesArray = worktypesData ? worktypesData.split("|") : [];

                const projectName = this.closest('tr').querySelector('td:nth-child(3)').textContent;

                let modalContent = `
                    <div class="modal-project-header">Work Types for "${projectName}"</div>
                    <table border="1" style="width: 100%; border-collapse: collapse;">
                        <tr><th>Sr.No</th><th>Work Type</th></tr>
                `;
                worktypesArray.forEach((type, index) => {
                    modalContent += `<tr><td>${index + 1}</td><td>${type}</td></tr>`;
                });
                modalContent += `</table>`;

                showModal("", modalContent); // Empty title since we're using custom header
            });
        });
    }

    function showModal(title, content) {
        const modalHtml = `
            <div id="customModal" class="ppmodal">
                <div class="ppmodal-content">
                    <span class="close-modal">&times;</span>
                    ${content}
                </div>
            </div>
            <style>
                .modal-project-header {
                    background-color: #f0f0f0;
                    padding: 15px;
                    margin: -20px -20px 20px -20px;
                    border-radius: 5px 5px 0 0;
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                    border-bottom: 2px solid #ddd;
                    text-align: center;
                }
            </style>
        `;

        let existingModal = document.getElementById("customModal");
        if (existingModal) {
            existingModal.remove();
        }

        document.body.insertAdjacentHTML("beforeend", modalHtml);
        document.querySelector(".close-modal").addEventListener("click", () => {
            document.getElementById("customModal").remove();
        });

        document.getElementById("customModal").style.display = "block";
    }

    // Attach event listeners to dynamically created buttons
    function attachEventListeners() {
        document.querySelectorAll(".proedit-btn").forEach((button) => {
            button.addEventListener("click", () => {
                const projectId = button.dataset.id;
                handleEditClick(projectId);
            });
        });

        document.querySelectorAll(".prodelete-btn").forEach((button) => {
            button.addEventListener("click", () => {
                currentProjectIdToDelete = button.dataset.id;
                confirmDeleteProjectModal.style.display = "flex";
            });
        });
    }

    // Submit Add Project form
    document.getElementById("addProjectForm").addEventListener("submit", (event) => {
        event.preventDefault();
        const selectedClientCodes = Array.from(addClientCodeContainer.querySelectorAll("input[type='checkbox']:checked")).map((cb) => cb.value);
        const selectedWorktypes = Array.from(addWorktypesContainer.querySelectorAll("input[type='checkbox']:checked")).map((cb) => cb.value);

        const projectData = {
            project_id: document.getElementById("add-project_id").value,
            project_name: document.getElementById("add-project_name").value,
            client_code: selectedClientCodes.join("|"),
            worktypes: selectedWorktypes.join("|"),
        };

        const submitBtn = addProjectForm.querySelector("button[type='submit']");
        if (submitBtn) submitBtn.disabled = true;

        fetch("/api/v1/masters/projects/", {
            method: "POST",
            credentials: 'same-origin',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "",
            },
            body: JSON.stringify(projectData),
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data.error) {
                    MasterDataCache.invalidate('master_projects_v2');
                    MasterDataCache.invalidate('oa_projects');
                    notify('Project added successfully!', 'success');
                    addProjectModal.style.display = "none";
                    fetchProjects();
                } else {
                    notify('Error adding Project: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(() => notify('Failed to add Project.', 'error'))
            .finally(() => {
                if (submitBtn) submitBtn.disabled = false;
            });
    });

    // Submit Edit Project form
    document.getElementById("editProjectForm").addEventListener("submit", (event) => {
        event.preventDefault();
        const projectId = document.getElementById("edit-project_id").value;
        const selectedClientCodes = Array.from(editClientCodeContainer.querySelectorAll("input[type='checkbox']:checked")).map((cb) => cb.value);
        const selectedWorktypes = Array.from(editWorktypesContainer.querySelectorAll("input[type='checkbox']:checked")).map((cb) => cb.value);

        const projectData = {
            project_name: document.getElementById("edit-project_name").value,
            client_code: selectedClientCodes.join("|"),
            worktypes: selectedWorktypes.join("|"),
        };

        fetch(`/api/v1/masters/projects/${projectId}/`, {
            method: "PATCH",
            credentials: 'same-origin',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "",
            },
            body: JSON.stringify(projectData),
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data.error) {
                    MasterDataCache.invalidate('master_projects_v2');
                    MasterDataCache.invalidate('oa_projects');
                    notify('Project updated successfully!', 'success');
                    document.getElementById('editProjectModal').style.display = "none";
                    fetchProjects();
                } else {
                    notify('Error updating Project: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(() => notify('Failed to update Project.', 'error'));
    });

    // Delete project
    confirmDeleteProjectBtn.addEventListener("click", () => {
        fetch(`/api/v1/masters/projects/${currentProjectIdToDelete}/`, {
            method: "DELETE",
            credentials: 'same-origin',
            headers: { "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "" },
        })
            .then((response) => {
                if (response.ok) {
                    MasterDataCache.invalidate('master_projects_v2');
                    MasterDataCache.invalidate('oa_projects');
                    confirmDeleteProjectModal.style.display = "none";
                    fetchProjects();
                } else {
                    alert("Error deleting project");
                }
            });
    });

    cancelDeleteProjectBtn.addEventListener("click", () => {
        confirmDeleteProjectModal.style.display = "none";
    });

    // Initial fetch of projects
    fetchProjects();

    function initializeProjectSearch() {
        const searchInputs = document.querySelectorAll('.search-box input');
        const clearIcons = document.querySelectorAll('.clear-search-icon');

        searchInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const container = e.target.closest('.form-group').querySelector('.checkbox-container');
                const searchTerm = e.target.value.toLowerCase();

                const labels = container.querySelectorAll('label');
                labels.forEach(label => {
                    const text = label.textContent.toLowerCase();
                    label.style.display = text.includes(searchTerm) ? 'flex' : 'none';
                });
            });
        });

        clearIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                const input = e.target.previousElementSibling;
                input.value = '';
                const container = e.target.closest('.form-group').querySelector('.checkbox-container');
                const labels = container.querySelectorAll('label');
                labels.forEach(label => label.style.display = 'flex');
            });
        });
    }

    function updateActiveCounts(isAddForm = false) {
        const clientCodeContainer = isAddForm ? 'add-client-codes-container' : 'edit-client-codes-container';
        const workTypeContainer = isAddForm ? 'add-worktypes-container' : 'edit-worktypes-container';

        const clientCodeCount = document.querySelectorAll(`#${clientCodeContainer} input[type="checkbox"]:checked`).length;
        const workTypeCount = document.querySelectorAll(`#${workTypeContainer} input[type="checkbox"]:checked`).length;

        if (isAddForm) {
            // Update counts in add form
            const accElem = document.getElementById('add-active-clientcodes');
            if (accElem) accElem.textContent = clientCodeCount;
            const awtElem = document.getElementById('add-active-project-worktypes');
            if (awtElem) awtElem.textContent = workTypeCount;
        } else {
            // Update counts in edit form
            const ccElem = document.getElementById('active-clientcodes');
            if (ccElem) ccElem.textContent = clientCodeCount;
            const wtElem = document.getElementById('active-project-worktypes');
            if (wtElem) wtElem.textContent = workTypeCount;
        }
    }

    function handleEditClick(projectId) {
        fetch(`/api/v1/masters/projects/${projectId}/`, { credentials: 'same-origin' })
            .then(response => response.json())
            .then(resp => {
                const data = resp.data || resp;
                if (data.error) {
                    notify(data.error, 'error');
                    return;
                }
                
                // Set basic project info
                document.getElementById('edit-project_id').value = data.project_id;
                document.getElementById('edit-project_name').value = data.project_name;
                document.getElementById('edit-requires_attendance').checked = data.requires_attendance || false;
                document.getElementById('edit-is_simplified_project').checked = data.is_simplified_project || false;


                // Store selected work types for reference
                const selectedWorkTypes = data.worktypes ? data.worktypes.split('|') : [];
                const selectedClientCodes = data.client_code ? data.client_code.split('|') : [];

                // First fetch client codes and pre-select them
                fetchClientCodes(editClientCodeContainer, selectedClientCodes)
                    .then(() => {
                        // After client codes are loaded, fetch work types
                        return fetchWorkTypes(selectedClientCodes, editWorktypesContainer, selectedWorkTypes);
                    })
                    .then(() => {
                        // Update counts after everything is loaded
                        updateActiveCounts(false);

                        // Add change event listeners for checkbox containers
                        ['edit-client-codes-container', 'edit-worktypes-container'].forEach(containerId => {
                            document.getElementById(containerId).addEventListener('change', () => updateActiveCounts(false));
                        });
                    });

                // Initialize search functionality
                initializeProjectSearch();

                // Show the modal
                document.getElementById('editProjectModal').style.display = 'block';
            });
    }

    // Add new function to initialize search for add form
    function initializeAddProjectSearch() {
        const searchInputs = document.querySelectorAll('#addProjectModal .search-box input');
        const clearIcons = document.querySelectorAll('#addProjectModal .clear-search-icon');

        searchInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const container = e.target.closest('.form-group').querySelector('.checkbox-container');
                const searchTerm = e.target.value.toLowerCase();

                const labels = container.querySelectorAll('label');
                labels.forEach(label => {
                    const text = label.textContent.toLowerCase();
                    label.style.display = text.includes(searchTerm) ? 'flex' : 'none';
                });
            });
        });

        clearIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                const input = e.target.previousElementSibling;
                input.value = '';
                const container = e.target.closest('.form-group').querySelector('.checkbox-container');
                const labels = container.querySelectorAll('label');
                labels.forEach(label => label.style.display = 'flex');
            });
        });
    }
});

// Search functionality for filtering projects
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

        if (matchFound) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    }
}
