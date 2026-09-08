document.addEventListener("DOMContentLoaded", function () {
    const logoutBtn = document.getElementById('logout-btn');
    const logoutPopup = document.getElementById('logout-popup');
    const userNameBtn = document.getElementById('user-name');
    const userMenu = document.getElementById('user-menu');
    const openResetLink = document.getElementById('open-reset-link');
    const resetPopup = document.getElementById('reset-popup');
    const closeReset = document.querySelector('.close-reset');
    const resetForm = document.getElementById('reset-form');
    const resetCancel = document.getElementById('reset-cancel');
    const confirmLogout = document.getElementById('confirm-logout');
    const cancelLogout = document.getElementById('cancel-logout');


    // Show popup when logout button is clicked
    logoutBtn.addEventListener('click', () => {
        // Then check for active break
        const savedBreak = localStorage.getItem("break_state");
        if (savedBreak) {
            const { breakType } = JSON.parse(savedBreak);
            const userConfirm = confirm(`You have an ongoing ${breakType}. Do you want to end the break first?`);
            if (userConfirm) {
                if (typeof window.endBreak === 'function') {
                    window.endBreak();
                } else if (typeof endBreak === 'function') {
                    endBreak();
                }
            }
        } else {
            logoutPopup.classList.remove('hidden');
        }
    });

    // Handle confirm logout
    confirmLogout.addEventListener('click', () => {
        sessionStorage.removeItem('softwareShiftRunning');
        
        // Pause software shift if running before destroying the session
        fetch('/api/v1/tracking/software-shifts/pause/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        }).finally(() => {
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
    });

    // Close popup when cancel is clicked
    cancelLogout.addEventListener('click', () => {
        logoutPopup.classList.add('hidden');
    });

    // Toggle mini user menu on name click
    if (userNameBtn && userMenu) {
        userNameBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userMenu.classList.toggle('hidden');
        });
    }
    // Open reset form from menu
    if (openResetLink && resetPopup && userMenu) {
        openResetLink.addEventListener('click', (e) => {
            e.preventDefault();
            userMenu.classList.add('hidden');
            resetPopup.classList.remove('hidden');
        });
    }
    // Close user menu when clicking outside
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
    let isSubmitting = false;
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
        resetForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (isSubmitting) return;
            const oldPassword = document.getElementById('old-password').value.trim();
            const newPassword = document.getElementById('new-password').value.trim();
            const confirmPassword = document.getElementById('confirm-password').value.trim();
            if (!oldPassword || !newPassword || !confirmPassword) {
                alert('Please fill all fields');
                return;
            }
            if (newPassword.length < 6) {
                alert('New password must be at least 6 characters');
                return;
            }
            if (newPassword !== confirmPassword) {
                alert('New password and confirm password do not match');
                return;
            }
            const submitBtn = document.getElementById('reset-submit');
            const originalHTML = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            isSubmitting = true;
            fetch('/reset_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
                },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Password updated successfully');
                    resetForm.reset();
                    resetPopup.classList.add('hidden');
                } else {
                    alert(data.error || 'Failed to update password');
                }
            })
            .catch(err => {
                console.error('Error updating password:', err);
                alert('Error updating password');
            })
            .finally(() => {
                isSubmitting = false;
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;
            });
        });
    }

    window.addEventListener('storage', function(event) {
        if (event.key === 'work-ended-notify' && event.newValue) {
            // Only update if the event is for this user
            try {
                const data = JSON.parse(event.newValue);
                const myEmpId = sessionStorage.getItem('emp_id');
                if (data && data.emp_id && data.emp_id === myEmpId) {
                    const today = new Date().toISOString().split('T')[0];
                    fetchWorkData(today);
                    checkActiveWorkSession(); // Also reset timer and end button
                }
            } catch (e) {}
        }
    });
 
    // Listen for work-paused-notify localStorage event to show pause notification immediately
    window.addEventListener('storage', function(event) {
        if (event.key === 'work-paused-notify' && event.newValue) {
            try {
                const data = JSON.parse(event.newValue);
                const myEmpId = sessionStorage.getItem('emp_id');
                if (data && data.emp_id && data.emp_id === myEmpId) {
                    showPauseNotification(data.pauser || '');
                    // Optionally, refresh work data and session state
                    const today = new Date().toISOString().split('T')[0];
                    fetchWorkData(today);
                    checkActiveWorkSession();
                }
            } catch (e) {}
        }
    });
});

fetch('/api/v1/masters/selections/')
    .then(response => {
        return response.json();
    })
    .then(data => {
        if (data.error) {
            return;
        }
        if (data.projects) {

            // Populate Projects dropdown
            const projectSelect = document.getElementById('project-select');
            if (!projectSelect) {
                return;
            }

            data.projects.forEach(project => {

                const option = document.createElement('option');
                option.value = project.project_id;  // Keep project ID as value
                option.textContent = project.project_name;  // Display project name
                projectSelect.appendChild(option);
            });
        } else {
            console.warn("No projects found in the response.");
        }
    })
    .catch(error => console.error('Error fetching user selections:', error));

// Handle Project Selection
const projectSelectEl = document.getElementById('project-select');
if (projectSelectEl) {
    projectSelectEl.addEventListener('change', function () {
        const selectedProject = this.value;
        const workUnitsLabel = document.querySelector('label[for="work-units"]');
    const pagesLabel = document.getElementById('pages-label');
    const pagesInput = document.getElementById('pages');

    // If a project is selected, enable and fetch client codes
    if (selectedProject) {
        document.getElementById('client-code-select').disabled = false;

        // Show/hide pages field based on project
        const projectSelect = document.getElementById('project-select');
        const selectedOption = projectSelect.options[projectSelect.selectedIndex];
        const isProvenAirAAR = selectedOption.textContent === 'ProvenAir-AAR';
        
        pagesLabel.style.display = isProvenAirAAR ? 'block' : 'none';
        pagesInput.style.display = isProvenAirAAR ? 'block' : 'none';
        if (isProvenAirAAR) {
            pagesInput.required = true;
        } else {
            pagesInput.required = false;
            pagesInput.value = '';
        }

        // Fetch client codes
        fetch(`/get_client_codes_for_project?project=${selectedProject}`)
            .then(response => response.json())
            .then(data => {
                const clientCodeSelect = document.getElementById('client-code-select');
                clientCodeSelect.innerHTML = '<option value="">Select Client Code</option>';

                data.client_codes.forEach(clientCode => {
                    const option = document.createElement('option');
                    option.value = clientCode;
                    option.textContent = clientCode;
                    clientCodeSelect.appendChild(option);
                });
            })
            .catch(error => console.error('Error fetching client codes:', error));
    } else {
        // Reset and disable client code select if no project is selected
        document.getElementById('client-code-select').disabled = true;
        document.getElementById('client-code-select').innerHTML = '<option value="">Select Client Code</option>';
        document.getElementById('work-type-select').disabled = true;
        document.getElementById('work-type-select').innerHTML = '<option value="">Select Work Type</option>';
    }
});
}

// Handle Client Code Selection
const clientCodeSelectEl = document.getElementById('client-code-select');
if (clientCodeSelectEl) {
    clientCodeSelectEl.addEventListener('change', function () {
    const selectedClientCode = this.value;

    // If a client code is selected, enable and fetch work types
    if (selectedClientCode) {
        document.getElementById('work-type-select').disabled = false;

        // Fetch work types for the selected client code
        fetch(`/get_work_types_for_client_code?client_code=${selectedClientCode}`)
            .then(response => response.json())
            .then(data => {
                const workTypeSelect = document.getElementById('work-type-select');
                workTypeSelect.innerHTML = '<option value="">Select Work Type</option>';  // Clear previous options

                data.work_types.forEach(workType => {
                    const option = document.createElement('option');
                    option.value = workType;
                    option.textContent = workType;
                    workTypeSelect.appendChild(option);
                });
            })
            .catch(error => console.error('Error fetching work types:', error));
    } else {
        // Reset and disable work type select if no client code is selected
        document.getElementById('work-type-select').disabled = true;
        document.getElementById('work-type-select').innerHTML = '<option value="">Select Work Type</option>';
    }
    });
}

function showContent(contentId) {
    // Hide all content sections first
    const leftSection = document.querySelector('.left-section');
    const reportsContent = document.querySelector('.reports-content');
    const feedbackSection = document.getElementById('feedback-section');
    
    if (leftSection) leftSection.style.display = 'none';
    if (reportsContent) reportsContent.style.display = 'none';
    if (feedbackSection) feedbackSection.style.display = 'none';

    // Remove active class from all nav buttons
    const navButtons = document.querySelectorAll('.side-nav-btn');
    navButtons.forEach(btn => btn.classList.remove('active'));

    // Add active class to clicked button
    const clickedButton = document.querySelector(`.side-nav-btn[onclick*="${contentId}"]`);
    if (clickedButton) {
        clickedButton.classList.add('active');
    }

    // Show selected content
    if (contentId === 'feedback') {
        if (feedbackSection) {
            feedbackSection.style.display = 'block';
            
            // Show feedback reports and hide detail preview
            const feedbackReports = document.querySelector('.feedback-reports');
            const feedbackDetailPreview = document.querySelector('.feedback-detail-preview');
            
            if (feedbackReports && feedbackDetailPreview) {
                feedbackReports.style.display = 'block';
                feedbackDetailPreview.style.display = 'none';
            }
            
            // Fetch feedback reports
            if (typeof fetchFeedbackReports === 'function') fetchFeedbackReports();
            if (typeof fetchFeedbackCounts === 'function') fetchFeedbackCounts();
        }
    } else if (contentId === 'dashboard') {
        if (leftSection) leftSection.style.display = 'flex';
        if (reportsContent) {
            reportsContent.style.display = 'block';
            reportsContent.style.width = '78%';
        }
    }
}



