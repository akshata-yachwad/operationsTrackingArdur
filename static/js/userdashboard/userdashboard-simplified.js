function openLeaveModal() {
    document.getElementById('markLeaveModal').style.display = 'block';
}
function closeLeaveModal() {
    document.getElementById('markLeaveModal').style.display = 'none';
}

$(document).ready(function() {
    const csrftoken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
    
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });
    
    // Load attendance history
    function loadAttendance() {
        $.get('/api/v1/tracking/attendance-history/', function(res) {
            const data = res.data || res;
            const tbody = $('#attendance-history-body');
            tbody.empty();
            
            if (data.length === 0) {
                tbody.html('<tr><td colspan="4" style="text-align:center;">No records for this month</td></tr>');
                return;
            }

            data.forEach(function(day) {
                const dateObj = new Date(day.date);
                const dateStr = dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                
                let loginStr = '--:--';
                if (day.login_time) {
                    loginStr = new Date(day.login_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                }
                
                let logoutStr = '--:--';
                if (day.logout_time) {
                    logoutStr = new Date(day.logout_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                }
                
                // Helper to format seconds to hh:mm:ss
                const formatTime = (seconds) => {
                    const h = Math.floor(seconds / 3600);
                    const m = Math.floor((seconds % 3600) / 60);
                    const s = seconds % 60;
                    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
                };
                
                const netStr = formatTime(day.net_seconds || 0);
                const netColor = (day.net_seconds > 0) ? '#2ecc71' : 'inherit';

                tbody.append(`
                    <tr>
                        <td style="font-size: 0.85rem; padding: 6px;">${dateStr}</td>
                        <td style="font-size: 0.85rem; padding: 6px;">${loginStr}</td>
                        <td style="font-size: 0.85rem; padding: 6px;">${logoutStr}</td>
                        <td style="font-size: 0.85rem; padding: 6px; font-weight: 600; color: ${netColor};">${netStr}</td>
                    </tr>
                `);
            });
        });
    }
    loadAttendance();

    // Handle Leave Submit
    $('#mark-leave-form').on('submit', function(e) {
        e.preventDefault();
        const date = $('#leave-date').val();
        $.ajax({
            url: '/api/v1/tracking/attendance/mark-leave/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ date: date }),
            success: function() {
                alert("Leave marked successfully");
                closeLeaveModal();
                loadAttendance();
            },
            error: function(err) {
                alert("Error marking leave: " + (err.responseJSON?.error || err.statusText));
            }
        });
    });

    // Shift Timer Logic
    let shiftTimerInterval = null;
    let accumulatedSeconds = 0;
    let shiftStatus = 'UNSTARTED'; // UNSTARTED, RUNNING, PAUSED, ENDED
    let lastResumeTime = null;

    function formatShiftTime(totalSeconds) {
        const hrs = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
        const mins = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
        const secs = String(Math.floor(totalSeconds % 60)).padStart(2, '0');
        return `${hrs}:${mins}:${secs}`;
    }

    function updateShiftTimerDisplay() {
        if (shiftStatus === 'RUNNING' && lastResumeTime) {
            const now = new Date();
            const diff = Math.floor((now - lastResumeTime) / 1000);
            $('#shift-timer').text(formatShiftTime(accumulatedSeconds + diff));
        } else {
            $('#shift-timer').text(formatShiftTime(accumulatedSeconds));
        }
    }

    function syncStatusFromServer() {
        $.get('/api/v1/tracking/software-shifts/status/', function(res) {
            let data = res.data || res;
            shiftStatus = data.status || 'UNSTARTED';
            accumulatedSeconds = data.accumulated_seconds || 0;
            
            clearInterval(shiftTimerInterval);
            
            if (shiftStatus === 'RUNNING') {
                const currentCsrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || 'true';
                sessionStorage.setItem('softwareShiftRunning', currentCsrf);
                lastResumeTime = new Date(); // start counting difference from now
                shiftTimerInterval = setInterval(updateShiftTimerDisplay, 1000);
                $('#btn-start-shift').hide();
                $('#btn-resume-shift').hide();
                $('#btn-end-shift').show();
            } else if (shiftStatus === 'PAUSED') {
                const currentCsrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || 'true';
                if (sessionStorage.getItem('softwareShiftRunning') === currentCsrf) {
                    // Auto-resume if it was running before this refresh (within same login session)
                    resumeShift();
                    return;
                }
                $('#btn-start-shift').hide();
                $('#btn-resume-shift').show();
                $('#btn-end-shift').show();
            } else if (shiftStatus === 'ENDED') {
                sessionStorage.removeItem('softwareShiftRunning');
                $('#btn-start-shift').hide();
                $('#btn-resume-shift').hide();
                $('#btn-end-shift').hide();
                if (data.total_time) {
                    $('#shift-timer').text(data.total_time);
                }
            } else {
                sessionStorage.removeItem('softwareShiftRunning');
                $('#btn-start-shift').show();
                $('#btn-resume-shift').hide();
                $('#btn-end-shift').hide();
            }
            if (shiftStatus !== 'ENDED') {
                updateShiftTimerDisplay();
            }
        });
    }

    // Check current shift status on load
    syncStatusFromServer();

    window.startShift = function() {
        $.post('/api/v1/tracking/software-shifts/start-shift/', function(res) {
            syncStatusFromServer();
            loadAttendance();
        }).fail(function(err) {
            alert(err.responseJSON?.error || 'Failed to start shift');
        });
    };

    window.resumeShift = function() {
        $.post('/api/v1/tracking/software-shifts/resume/', function() {
            syncStatusFromServer();
        });
    };

    window.endShift = function() {
        document.getElementById('end-shift-popup').classList.remove('hidden');
    };

    document.getElementById('confirm-end-shift')?.addEventListener('click', function() {
        document.getElementById('end-shift-popup').classList.add('hidden');
        $.post('/api/v1/tracking/software-shifts/end-shift/', function(res) {
            syncStatusFromServer();
            loadAttendance();
        });
    });

    document.getElementById('cancel-end-shift')?.addEventListener('click', function() {
        document.getElementById('end-shift-popup').classList.add('hidden');
    });

    // Auto-pause when tab is closed or navigated away (not just hidden/switched)
    window.addEventListener('pagehide', function() {
        if (shiftStatus === 'RUNNING') {
            const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
            if (csrfMatch) {
                fetch('/api/v1/tracking/software-shifts/pause/', {
                    method: 'POST',
                    keepalive: true,
                    headers: {
                        'X-CSRFToken': csrfMatch[1]
                    }
                });
            }
            // Transition locally to paused immediately
            shiftStatus = 'PAUSED';
            clearInterval(shiftTimerInterval);
            if (lastResumeTime) {
                accumulatedSeconds += Math.floor((new Date() - lastResumeTime) / 1000);
            }
        } else if (document.visibilityState === 'visible') {
            // Re-sync with server state when user returns
            syncStatusFromServer();
        }
    });
});
