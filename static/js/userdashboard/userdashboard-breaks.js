document.addEventListener("DOMContentLoaded", function () {
    const breakSelect = document.getElementById("break-select");
    const breakStartBtn = document.getElementById("break-start-btn");
    const breakTimerDisplay = document.getElementById("break-timer");
    const popup = document.getElementById("breakpopup");
    const submitReason = document.getElementById("submit-reason");
    const reasonInput = document.getElementById("break-reason");
    const dashboardContent = document.querySelector('.dashboard-content');

    let timerInterval;
    let selectedBreak;
    let remainingTime = 0;
    let breakStartTime;

    // Hide timer initially
    if(breakTimerDisplay) breakTimerDisplay.style.display = 'none';

    function showBreakPopup() {
        if(popup) popup.style.display = "flex";
    }

    function hideBreakPopup() {
        if(popup) popup.style.display = "none";
        if(reasonInput) reasonInput.value = "";
    }
    
    if(submitReason) {
        submitReason.addEventListener("click", function () {
            hideBreakPopup();
        });
    }

    function fetchBreakReports() {
        fetch('/api/v1/breaks/?today=true')
            .then(response => response.json())
            .then(res => {
                const data = res.data || res;
                const tableBody = document.getElementById('break-report-body');
                if(!tableBody) return;
                tableBody.innerHTML = ''; 
    
                if (res.error || !Array.isArray(data)) {
                    let errMsg = 'Error fetching breaks';
                    if (res.error && res.error.message) errMsg = res.error.message;
                    else if (typeof res.error === 'string') errMsg = res.error;
                    tableBody.innerHTML = `<tr><td colspan="4" class="error-message">${errMsg}</td></tr>`;
                    return;
                }
    
                data.forEach((breakEntry) => {
                    const formatTime = (isoString) => {
                        if (!isoString) return 'Ongoing';
                        const date = new Date(isoString);
                        return date.toLocaleTimeString('en-IN', { hour12: true });
                    };
    
                    let duration = breakEntry.total_time;
                    if (!duration) {
                        if (breakEntry.live_elapsed_seconds) {
                            const diff = Math.floor(breakEntry.live_elapsed_seconds);
                            const h = Math.floor(diff / 3600);
                            const m = Math.floor((diff % 3600) / 60);
                            const s = diff % 60;
                            duration = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                        } else {
                            duration = 'Ongoing';
                        }
                    } else {
                        // total_time is in seconds
                        const diff = Math.floor(duration);
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        duration = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                    }
    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${breakEntry.break_type}</td>
                        <td>${formatTime(breakEntry.start_time)}</td>
                        <td>${formatTime(breakEntry.end_time)}</td>
                        <td>${duration}</td>
                    `;
    
                    tableBody.appendChild(row);
                });
            })
            .catch(error => console.error('Error fetching break reports:', error));
    }

    function fetchAvailableBreaks() {
        fetch('/api/v1/breaks/types/')
            .then(response => response.json())
            .then(res => {
                const data = res.data || res;
                if(!breakSelect) return;
                breakSelect.innerHTML = `<option value="">Select Break</option>`;
                data.forEach(b => {
                    if (!b.taken_today || b.repeatable) {
                        breakSelect.innerHTML += `<option value="${b.break_type}" data-duration="${b.allotted_seconds}">${b.break_type} (${b.allotted_minutes} mins)</option>`;
                    }
                });
                restoreBreakState(); // Restore selected break if any
            });
    }

    window.startBreak = function startBreak() {
        if(!breakSelect) return;
        const duration = breakSelect.selectedOptions[0].dataset.duration;
        breakStartTime = Date.now();

        // Disable the button immediately to prevent multiple clicks
        breakStartBtn.disabled = true;

        fetch('/api/v1/breaks/', {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            body: JSON.stringify({ break_type: breakSelect.value })
        })
        .then(res => res.json())
        .then(res => {
            const data = res.data || res;
            if (res.error) throw new Error(res.error);
            if(breakTimerDisplay) breakTimerDisplay.style.display = 'block';
            remainingTime = parseInt(duration, 10);
            saveBreakState();
            breakStartBtn.textContent = "End";
            breakStartBtn.style.backgroundColor = "#e74c3c";
            breakSelect.disabled = true;
            runTimer();
            fetchBreakReports();
            if(dashboardContent) dashboardContent.style.display = 'none';
            
            // Re-enable the button after successful start
            breakStartBtn.disabled = false;
            
            // Refresh work data to disable resume buttons
            const today = new Date().toISOString().split('T')[0];
            if (typeof window.fetchWorkData === 'function') {
                window.fetchWorkData(today);
            }
        }).catch(error => {
            console.error('Error starting break:', error);
            // Re-enable the button if there's an error
            breakStartBtn.disabled = false;
        });
    }

    window.endBreak = function endBreak() {
        if(!breakStartBtn) return;
        // Disable the button immediately to prevent multiple clicks
        breakStartBtn.disabled = true;

        fetch('/api/v1/breaks/end/', {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(res => {
            const data = res.data || res;
            if (data.is_overrun) {
                showBreakPopup();
            }

            clearInterval(timerInterval);
            remainingTime = 0;
            if(breakTimerDisplay) {
                breakTimerDisplay.style.display = 'none';
                breakTimerDisplay.textContent = "00:00";
                breakTimerDisplay.style.color = "#00686d";
            }
            breakStartBtn.textContent = "Start";
            breakStartBtn.style.backgroundColor = "";
            breakStartBtn.disabled = true; // Keep disabled until new break is selected
            breakSelect.disabled = false;
            clearBreakState();
            fetchBreakReports();
            fetchAvailableBreaks();
            
            if(dashboardContent) dashboardContent.style.display = 'block';
            
            // Refresh work data to enable resume buttons
            const today = new Date().toISOString().split('T')[0];
            if (typeof window.fetchWorkData === 'function') {
                window.fetchWorkData(today);
            }
        })
        .catch(error => {
            console.error('Error ending break:', error);
            // Re-enable the button if there's an error
            breakStartBtn.disabled = false;
        });
    }

    function runTimer() {
        timerInterval = setInterval(() => {
            let elapsedTime = Math.floor((Date.now() - breakStartTime) / 1000);
            let timeLeft = remainingTime - elapsedTime;
    
            // Update minutes and seconds for the break timer
            let minutes = Math.floor(timeLeft / 60);
            let seconds = timeLeft % 60;
    
            // Display the timer
            if(breakTimerDisplay) breakTimerDisplay.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    
            // Change color to red when time reaches 0
            if (timeLeft <= 0 && breakTimerDisplay && breakTimerDisplay.style.color !== "red") {
                breakTimerDisplay.style.color = "red"; // Change color to red
            }
    
            // Keep the timer running forward even after time reaches 0
            if (timeLeft <= 0) {
                // Continue incrementing the elapsed time to show how much the break is extended
                let extendedTime = elapsedTime - remainingTime; // This shows how much time is added after break ends
                let extendedMinutes = Math.floor(extendedTime / 60);
                let extendedSeconds = extendedTime % 60;
                if(breakTimerDisplay) breakTimerDisplay.textContent = `${String(extendedMinutes).padStart(2, "0")}:${String(extendedSeconds).padStart(2, "0")}`;
            }
    
        }, 1000);
    }

    function saveBreakState() {
        localStorage.setItem("break_state", JSON.stringify({
            breakType: selectedBreak,
            startTime: breakStartTime,
            remainingTime: remainingTime
        }));
    }

    function restoreBreakState() {
        const savedBreak = localStorage.getItem("break_state");
        if (savedBreak) {
            const { breakType, startTime, remainingTime: savedTime } = JSON.parse(savedBreak);
            selectedBreak = breakType;
            breakStartTime = parseInt(startTime, 10);
            remainingTime = parseInt(savedTime, 10);
            if(dashboardContent) dashboardContent.style.display = 'none';

            if (selectedBreak && breakSelect) {
                breakSelect.value = selectedBreak;
                breakStartBtn.textContent = "End";
                breakStartBtn.style.backgroundColor = "#e74c3c";
                breakStartBtn.disabled = false;
                breakSelect.disabled = true;
                if(breakTimerDisplay) breakTimerDisplay.style.display = 'block';
                runTimer();
            }
        }
    }

    function clearBreakState() {
        localStorage.removeItem("break_state");
    }
    
    if(breakSelect) {
        breakSelect.addEventListener("change", function () {
            selectedBreak = breakSelect.value;
            breakStartBtn.disabled = !selectedBreak;
            saveBreakState();  // Save the selected break when it changes
        });
    }

    if(breakStartBtn) {
        breakStartBtn.addEventListener("click", function () {
            const isStarting = breakStartBtn.textContent.trim() === "Start";
            
            if (isStarting) {
                window.startBreak();
            } else {
                window.endBreak();
            }
        });
    }

    fetchAvailableBreaks();
    fetchBreakReports();

});
