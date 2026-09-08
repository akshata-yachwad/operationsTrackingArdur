$(document).ready(function() {
    let currentSessionId = null;
    let timerInterval = null;
    let sessionStartTime = null;

    function showToast(message, type = 'success') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else if (window.Toastify) {
            Toastify({
                text: message,
                duration: 3000,
                close: true,
                gravity: "top",
                position: "right",
                backgroundColor: type === 'error' ? "#ef4444" : "#10b981",
            }).showToast();
        } else {
            alert(message);
        }
    }

    // Initialize
    fetchCurrentSession();

    function fetchCurrentSession() {
        $.ajax({
            url: '/api/v1/allocations/indexing/my_active/',
            method: 'GET',
            success: function(response) {
                if (response && response.data) {
                    // Active session exists
                    currentSessionId = response.data.id;
                    sessionStartTime = new Date(response.data.started_at);
                    startTimerUI();
                    $('#btn-start-indexing').hide();
                    $('#btn-submit-indexing').show();
                } else {
                    // No active session
                    currentSessionId = null;
                    stopTimerUI();
                    $('#main-timer').text('00:00:00');
                    $('#btn-start-indexing').show();
                    $('#btn-submit-indexing').hide();
                }
            },
            error: function(err) {
                showToast('Failed to load current session', 'error');
            }
        });
    }

    window.startIndexingSession = function() {
        $('#btn-start-indexing').prop('disabled', true);
        
        $.ajax({
            url: '/api/v1/allocations/indexing/start/',
            method: 'POST',
            headers: {
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            contentType: 'application/json',
            data: JSON.stringify({
                project: 'TITLE INDEXING',
                client_code: 'DEFAULT', // Fallback or needs to be selected
                work_type: 'INDEXING'
            }),
            success: function(response) {
                if (response && response.data) {
                    currentSessionId = response.data.id;
                    sessionStartTime = new Date(response.data.started_at);
                } else {
                    currentSessionId = response.id;
                    sessionStartTime = new Date(response.started_at);
                }
                startTimerUI();
                $('#btn-start-indexing').hide().prop('disabled', false);
                $('#btn-submit-indexing').show();
                showToast('Work started!');
            },
            error: function(xhr) {
                $('#btn-start-indexing').prop('disabled', false);
                showToast('Error starting work: ' + (xhr.responseJSON?.error || 'Unknown error'), 'error');
            }
        });
    };

    window.openSubmitModal = function() {
        $('#units-completed').val('');
        $('#submitUnitsModal').fadeIn(200);
        $('#units-completed').focus();
    };

    window.closeSubmitModal = function() {
        $('#submitUnitsModal').fadeOut(200);
    };

    $('#submit-units-form').on('submit', function(e) {
        e.preventDefault();
        
        if (!currentSessionId) {
            showToast('No active session found', 'error');
            return;
        }

        const units = parseInt($('#units-completed').val(), 10);
        if (isNaN(units) || units <= 0) {
            showToast('Please enter a valid number of units', 'error');
            return;
        }

        $('#btn-confirm-submit').prop('disabled', true);

        $.ajax({
            url: `/api/v1/allocations/indexing/${currentSessionId}/submit/`,
            method: 'POST',
            headers: {
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            contentType: 'application/json',
            data: JSON.stringify({ work_units_completed: units }),
            success: function(response) {
                closeSubmitModal();
                $('#btn-confirm-submit').prop('disabled', false);
                
                showToast(`Successfully submitted ${units} units!`);
                
                // Stop timer and reset UI
                currentSessionId = null;
                sessionStartTime = null;
                stopTimerUI();
                $('#main-timer').text('00:00:00');
                $('#btn-start-indexing').show();
                $('#btn-submit-indexing').hide();
                fetchIndexingData();
            },
            error: function(xhr) {
                $('#btn-confirm-submit').prop('disabled', false);
                showToast('Error submitting units: ' + (xhr.responseJSON?.error || 'Unknown error'), 'error');
            }
        });
    });

    function startTimerUI() {
        if (timerInterval) clearInterval(timerInterval);
        updateTimerDisplay();
        timerInterval = setInterval(updateTimerDisplay, 1000);
    }

    function stopTimerUI() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function updateTimerDisplay() {
        if (!sessionStartTime) return;
        
        const now = new Date();
        const diffMs = Math.max(0, now - sessionStartTime);
        
        const totalSeconds = Math.floor(diffMs / 1000);
        const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
        const s = (totalSeconds % 60).toString().padStart(2, '0');
        
        $('#main-timer').text(`${h}:${m}:${s}`);
    }

    function fetchIndexingData() {
        if (!$('#indexing-data-table').length) return; // Not on the indexing dashboard
        
        $.ajax({
            url: '/api/v1/allocations/indexing/',
            method: 'GET',
            success: function(response) {
                const data = response.data || response;
                
                if ($.fn.DataTable.isDataTable('#indexing-data-table')) {
                    $('#indexing-data-table').DataTable().destroy();
                }

                const tableBody = document.getElementById('indexing-data-body');
                if (!tableBody) return;
                
                tableBody.innerHTML = '';
                
                if (Array.isArray(data)) {
                    data.forEach(row => {
                        const tr = document.createElement('tr');
                        
                        const dateStr = row.started_at ? row.started_at.substring(0, 10) : '';
                        const startTimeStr = row.started_at ? new Date(row.started_at).toLocaleTimeString('en-IN', { hour12: true }) : '';
                        const endTimeStr = row.completed_at ? new Date(row.completed_at).toLocaleTimeString('en-IN', { hour12: true }) : '-';
                        let totalTimeFormatted = '00:00:00';
                        if (row.time_taken) {
                            if (typeof row.time_taken === 'string') {
                                totalTimeFormatted = row.time_taken.split('.')[0]; // Handle "0:00:23.123"
                                if (totalTimeFormatted.length < 8) {
                                    totalTimeFormatted = '0' + totalTimeFormatted; // Pad "0:00:23" to "00:00:23" if needed
                                }
                            } else {
                                totalTimeFormatted = new Date(row.time_taken * 1000).toISOString().substr(11, 8);
                            }
                        }
                        
                        let statusBadge = '';
                        if (row.status === 'COMPLETED') {
                            statusBadge = '<span class="status-badge status-completed">Completed</span>';
                        } else {
                            statusBadge = '<span class="status-badge status-inprogress">In Progress</span>';
                        }

                        tr.innerHTML = `
                            <td>${dateStr}</td>
                            <td>${row.project || 'TITLE INDEXING'}</td>
                            <td>${row.client_code || '-'}</td>
                            <td>${row.work_type || '-'}</td>
                            <td>${row.work_units_completed || 0}</td>
                            <td>${startTimeStr}</td>
                            <td>${endTimeStr}</td>
                            <td>${totalTimeFormatted}</td>
                            <td>${statusBadge}</td>
                        `;
                        tableBody.appendChild(tr);
                    });
                }
                
                $('#indexing-data-table').DataTable({
                    pageLength: 10,
                    lengthChange: false,
                    dom: '<"top">rt<"bottom"p><"clear">',
                    order: [[0, 'desc'], [5, 'desc']],
                    language: {
                        emptyTable: "No indexing sessions available"
                    }
                });
            }
        });
    }

    // Call it initially
    fetchIndexingData();
});
