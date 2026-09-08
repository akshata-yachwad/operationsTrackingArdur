$(document).ready(function() {
    // Initialize Select2
    $('#projectSelect').select2({
        width: '100%',
        dropdownParent: $('#targetModal'),
        placeholder: 'Select a project'
    });

    // Load initial data
    loadProjects();

    // Sidebar toggle
    $('#sidebarToggle').on('click', function() {
        $('.sidebar').toggleClass('active');
    });

    // Close sidebar when clicking outside on mobile
    $(document).on('click', function(e) {
        if ($(window).width() <= 1024) {
            if (!$(e.target).closest('.sidebar').length && !$(e.target).closest('#sidebarToggle').length) {
                $('.sidebar').removeClass('active');
            }
        }
    });

    // Navigation
    $('.nav-item').on('click', function() {
        const section = $(this).data('section');
        if (!section) return; // Skip for regular links (like Dashboard)

        $('.nav-item').removeClass('active');
        $(this).addClass('active');
        $('.content-section').removeClass('active');
        $(`#${section}`).addClass('active');

        // Update page title
        updatePageTitle(section);

        // Load section data if needed
        if (section === 'sessions') {
            loadActiveSessions();
        } else if (section === 'users') {
            loadAllUsers();
        }
        
        window.location.hash = section;
    });

    // Check hash on load
    const hash = window.location.hash.substring(1);
    if (hash && $(`.nav-item[data-section="${hash}"]`).length) {
        $(`.nav-item[data-section="${hash}"]`).click();
    } else {
        loadActiveSessions();
    }

    // Search functionality
    $('#sessionSearch').on('input', function() {
        filterSessions($(this).val().toLowerCase());
    });

    $('#userSearch').on('input', function() {
        filterUsers($(this).val().toLowerCase());
    });

    // Refresh sessions button
    $('#refreshSessions').on('click', function() {
        const button = $(this);
        button.find('i').addClass('fa-spin');
        loadActiveSessions().always(function() {
            setTimeout(() => button.find('i').removeClass('fa-spin'), 500);
        });
    });

    // Refresh users button
    $('#refreshUsers').on('click', function() {
        const button = $(this);
        button.find('i').addClass('fa-spin');
        loadAllUsers().always(function() {
            setTimeout(() => button.find('i').removeClass('fa-spin'), 500);
        });
    });

    // System actions
    $('#clearCacheBtn').on('click', function() {
        if (confirm('Are you sure you want to clear the cache? This may affect application performance temporarily.')) {
            clearCache();
        }
    });

    $('#exportDataBtn').on('click', exportAllData);

    // Theme preview hover effect
    $('.theme-option').hover(
        function() { $(this).addClass('hover'); },
        function() { $(this).removeClass('hover'); }
    );

    // Font size slider
    $('#fontSize').on('input', function() {
        updateFontSizePreview($(this).val());
    });
});

// Update page title based on section
function updatePageTitle(section) {
    const titles = {
        sessions: 'Active Sessions',
        users: 'Manage Users',
        system: 'System Settings'
    };
    $('#pageTitle').text(titles[section] || 'Settings');
}

// Load projects into dropdown
function loadProjects() {
    try {
    $.get('/api/v1/masters/emp_get_projects/')
            .done(function(response) {
                try {
                    // Ensure response is valid
                    if (!response || typeof response !== 'object') {
                        throw new Error('Invalid response from server');
                    }

                    const data = response.projects || (Array.isArray(response) ? response : (response.results || []));
            const select = $('#projectSelect');
            select.empty().append('<option value="">Select Project</option>');
            
            data.forEach(project => {
                        if (project && project.project_id && project.project_name) {
                            select.append(`<option value="${project.project_id}">${escapeHtml(project.project_name)}</option>`);
                        }
            });
                } catch (err) {
                    console.error('Error processing projects:', err);
                    showToast('Error loading projects: ' + err.message, 'error');
                }
        })
        .fail(function(xhr, status, error) {
                showToast('Error loading projects: ' + (error || 'Unknown error'), 'error');
        });
    } catch (err) {
        console.error('Error in loadProjects:', err);
        showToast('Error loading projects', 'error');
    }
}

// Save email settings
function saveEmailSettings(data) {
    $.post('/api/settings/notifications', data, function(response) {
        showToast('Notification settings saved successfully');
    }).fail(function(error) {
        showToast('Error saving notification settings', true);
    });
}

// Save display settings
function saveDisplaySettings(data) {
    $.post('/api/settings/display', data, function(response) {
        showToast('Display settings saved successfully');
        applyDisplaySettings(data);
    }).fail(function(error) {
        showToast('Error saving display settings', true);
    });
}

// System functions
function resetLoginStatus() {
    $.post('/api/settings/reset-login', function(response) {
        showToast('Login status reset successfully');
    }).fail(function(error) {
        showToast('Error resetting login status', true);
    });
}

function forceLogoutAllUsers() {
    $.post('/api/settings/force-logout', function(response) {
        showToast('All users have been logged out');
    }).fail(function(error) {
        showToast('Error logging out users', true);
    });
}

function exportAllData() {
    window.location.href = '/api/settings/export-data';
}

function clearCache() {
    $.post('/api/settings/clear-cache', function(response) {
        showToast('Cache cleared successfully');
    }).fail(function(error) {
        showToast('Error clearing cache', true);
    });
}

// UI Helpers
function showToast(message, type = 'success') {
    try {
    const toast = $('#toast');
        toast.removeClass('error success').addClass(type);
        $('#toastMessage').text(message || 'An error occurred');
    
    toast.fadeIn(300);
    setTimeout(() => toast.fadeOut(300), 3000);
    } catch (err) {
        console.error('Error showing toast:', err);
    }
}

function updateFontSizePreview(size) {
    const preview = $('.font-size-preview');
    preview.css('font-size', `${size}px`);
}

// Apply display settings
function applyDisplaySettings(settings) {
    document.documentElement.setAttribute('data-theme', settings.theme);
    document.documentElement.style.fontSize = `${settings.fontSize}px`;
}

// Filter sessions
function filterSessions(searchText = '') {
    try {
        const items = $('.session-item');
        
        items.each(function() {
            const item = $(this);
            const nameElement = item.find('h4');
            const name = nameElement.length ? nameElement.text() : '';
            
            // Safely convert searchText to lowercase, defaulting to empty string if undefined
            const searchLower = (searchText || '').toLowerCase();
            const nameLower = name.toLowerCase();
            
            const matchesSearch = !searchLower || nameLower.includes(searchLower);
            
            item.toggle(matchesSearch);
        });

        // Show/hide empty state
        const visibleItems = items.filter(':visible').length;
        if (visibleItems === 0) {
            if (!$('.empty-state').length) {
                $('.sessions-list').append(`
                    <div class="empty-state">
                        <i class="fas fa-search fa-3x"></i>
                        <p>No matching sessions found</p>
                    </div>
                `);
            }
        } else {
            $('.empty-state').remove();
        }
    } catch (err) {
        console.error('Error filtering sessions:', err);
        showToast('Error filtering sessions', 'error');
    }
}

// Load active sessions
function loadActiveSessions() {
    return $.get('/api/v1/presence/')
        .done(function(data) {
            const sessionsList = $('.sessions-list');
            sessionsList.empty();
            
            let sessions = data.data || data;
            if (Array.isArray(sessions)) {
                sessions = sessions.filter(user => user.status && user.status !== 'offline');
            }

            if (!Array.isArray(sessions) || sessions.length === 0) {
                sessionsList.append(`
                    <div class="empty-state">
                        <i class="fas fa-users fa-3x"></i>
                        <p>No active sessions found</p>
                    </div>
                `);
                return;
            }

            sessions.forEach(user => {
                if (!user || !user.emp_id || !user.name) return;
                
                const name = escapeHtml(user.name);
                const empId = escapeHtml(user.emp_id);
                const role = escapeHtml(user.role || 'Employee');
                
                let metaHtml = `<span>${empId}</span><span>${role}</span>`;
                if (user.login_time) {
                    const loginTime = new Date(user.login_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    metaHtml += `<span>Login: ${loginTime}</span>`;
                }
                
                const statusStr = user.status || 'active';
                const displayStatus = statusStr.charAt(0).toUpperCase() + statusStr.slice(1).replace('_', ' ');
                
                sessionsList.append(`
                    <div class="session-item" data-emp-id="${empId}">
                        <div class="session-info">
                            <div class="session-avatar">
                                ${name.charAt(0).toUpperCase()}
                            </div>
                            <div class="session-details">
                                <h4>${name}</h4>
                                <div class="session-meta">
                                    ${metaHtml}
                                </div>
                            </div>
                        </div>
                        <div class="session-actions">
                            <span class="session-badge active">
                                <i class="fas fa-circle"></i>
                                ${displayStatus}
                            </span>
                            <button class="btn-danger btn-sm" onclick="showResetConfirmation('${empId}', '${name}')">
                                <i class="fas fa-power-off"></i>
                                Reset
                            </button>
                        </div>
                    </div>
                `);
            });

            // Reapply current filters
            const searchValue = $('#sessionSearch').val();
            const searchText = searchValue ? searchValue.toLowerCase() : '';
            filterSessions(searchText);
        })
        .fail(function(xhr, status, error) {
            showToast('Error loading active sessions: ' + (error || 'Unknown error'), 'error');
        });
}

// Show reset confirmation modal
function showResetConfirmation(empId, name) {
    if (!empId || !name) {
        showToast('Invalid session data', 'error');
        return;
    }

    const modal = $('#resetSessionModal');
    modal.find('.modal-message').text(`Are you sure you want to reset the session for ${name}?`);
    
    // Update confirm button click handler
    $('#confirmResetBtn').off('click').on('click', function() {
        resetUserSession(empId);
        modal.fadeOut(300);
    });
    
    modal.fadeIn(300);
}

// Reset user session
function resetUserSession(empId) {
    if (!empId) {
        showToast('Invalid employee ID', 'error');
        return;
    }

    $.ajax({
        url: `/api/v1/auth/force-logout/${empId}/`,
        method: 'POST',
        headers: {
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
        },
        success: function(response) {
            showToast('Session reset successfully');
            loadActiveSessions(); // Reload the sessions list
        },
        error: function(xhr, status, error) {
            showToast('Error resetting session: ' + (xhr.responseJSON?.error || error || 'Unknown error'), 'error');
        }
    });
}

// Load all users
function loadAllUsers() {
    return $.get('/api/v1/auth/employees/')
        .done(function(data) {
            const usersList = $('.users-list');
            usersList.empty();
            
            const users = data.data || data;

            if (!Array.isArray(users) || users.length === 0) {
                usersList.append(`
                    <div class="empty-state">
                        <i class="fas fa-users fa-3x"></i>
                        <p>No users found</p>
                    </div>
                `);
                return;
            }

            users.forEach(user => {
                if (!user || !user.employee_id || !user.name) return;
                
                const name = escapeHtml(user.name);
                const empId = escapeHtml(user.employee_id);
                const role = escapeHtml(user.role || 'Employee');
                const status = escapeHtml(user.status || 'Active');
                
                usersList.append(`
                    <div class="session-item user-item" data-emp-id="${empId}">
                        <div class="session-info">
                            <div class="session-avatar">
                                ${name.charAt(0).toUpperCase()}
                            </div>
                            <div class="session-details">
                                <h4>${name}</h4>
                                <div class="session-meta">
                                    <span>${empId}</span>
                                    <span>${role}</span>
                                </div>
                            </div>
                        </div>
                        <div class="session-actions">
                            <span class="status-badge ${status.toLowerCase()}">${status}</span>
                            <button class="btn-primary btn-sm" onclick="showChangePasswordModal('${empId}', '${name}')" style="margin-right: 8px;">
                                <i class="fas fa-edit"></i>
                                Change Password
                            </button>
                            <button class="btn-danger btn-sm" onclick="showResetPasswordConfirmation('${empId}', '${name}')">
                                <i class="fas fa-key"></i>
                                Reset Password
                            </button>
                        </div>
                    </div>
                `);
            });

            // Reapply current filters
            const searchValue = $('#userSearch').val();
            const searchText = searchValue ? searchValue.toLowerCase() : '';
            filterUsers(searchText);
        })
        .fail(function(xhr, status, error) {
            showToast('Error loading users: ' + (error || 'Unknown error'), 'error');
        });
}

// Filter users
function filterUsers(searchText = '') {
    try {
        const items = $('.user-item');
        
        items.each(function() {
            const item = $(this);
            const nameElement = item.find('h4');
            const name = nameElement.length ? nameElement.text() : '';
            
            // Safely convert searchText to lowercase, defaulting to empty string if undefined
            const searchLower = (searchText || '').toLowerCase();
            const nameLower = name.toLowerCase();
            
            const matchesSearch = !searchLower || nameLower.includes(searchLower);
            
            item.toggle(matchesSearch);
        });

        // Show/hide empty state
        const visibleItems = items.filter(':visible').length;
        if (visibleItems === 0 && items.length > 0) {
            if (!$('.users-list .empty-state').length) {
                $('.users-list').append(`
                    <div class="empty-state">
                        <i class="fas fa-search fa-3x"></i>
                        <p>No matching users found</p>
                    </div>
                `);
            }
        } else {
            $('.users-list .empty-state').remove();
        }
    } catch (err) {
        console.error('Error filtering users:', err);
        showToast('Error filtering users', 'error');
    }
}

// Show reset password confirmation modal
function showResetPasswordConfirmation(empId, name) {
    if (!empId || !name) {
        showToast('Invalid user data', 'error');
        return;
    }

    const modal = $('#resetPasswordModal');
    modal.find('.modal-message').text(`Are you sure you want to reset the password for ${name} to 1122?`);
    
    // Update confirm button click handler
    $('#confirmResetPasswordBtn').off('click').on('click', function() {
        resetUserPassword(empId);
        modal.fadeOut(300);
    });
    
    modal.fadeIn(300);
}

// Show change password modal
function showChangePasswordModal(empId, name) {
    if (!empId || !name) {
        showToast('Invalid user data', 'error');
        return;
    }

    const modal = $('#changePasswordModal');
    modal.find('.modal-message').text(`Enter the new password for ${name}:`);
    $('#newPasswordInput').val(''); // Clear previous input
    
    // Update confirm button click handler
    $('#confirmChangePasswordBtn').off('click').on('click', function() {
        const newPassword = $('#newPasswordInput').val().trim();
        if (!newPassword) {
            showToast('Password cannot be empty', 'error');
            return;
        }
        resetUserPassword(empId, newPassword);
        modal.fadeOut(300);
    });
    
    modal.fadeIn(300);
}

// Reset or change user password
function resetUserPassword(empId, newPassword = '1122') {
    if (!empId) {
        showToast('Invalid employee ID', 'error');
        return;
    }

    $.ajax({
        url: `/api/v1/auth/password/reset/`,
        method: 'POST',
        contentType: 'application/json',
        headers: {
            'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
        },
        data: JSON.stringify({
            emp_id: empId,
            new_password: newPassword
        }),
        success: function(response) {
            showToast(newPassword === '1122' ? 'Password reset successfully to 1122' : 'Password changed successfully');
            loadAllUsers(); // Reload the users list
        },
        error: function(xhr, status, error) {
            showToast('Error resetting password: ' + (xhr.responseJSON?.error || error || 'Unknown error'), 'error');
        }
    });
}

// Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return '';
    try {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    } catch (err) {
        console.error('Error escaping HTML:', err);
        return '';
    }
} 
