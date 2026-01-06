// Dashboard JavaScript for Smart Parking System
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO connection
    const socket = io();
    
    // Chart configuration
    let detectionChart;
    const chartData = {
        labels: [],
        datasets: [{
            label: 'Vehicle Count',
            data: [],
            borderColor: 'rgb(13, 110, 253)',
            backgroundColor: 'rgba(13, 110, 253, 0.1)',
            tension: 0.4,
            fill: true
        }]
    };
    
    // Initialize real-time chart
    initializeChart();
    
    // Duration and cost counters
    updateDurationCounters();
    setInterval(updateDurationCounters, 1000); // Update every second
    
    // Socket event handlers
    socket.on('connect', function() {
        console.log('Connected to server');
        updateFeedStatus('Connected to Smart Parking System', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateFeedStatus('Disconnected from server', 'danger');
    });
    
    socket.on('parking_update', function(data) {
        handleParkingUpdate(data);
    });
    
    socket.on('new_detection', function(data) {
        handleNewDetection(data);
    });
    
    function initializeChart() {
        const ctx = document.getElementById('detectionChart').getContext('2d');
        detectionChart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Real-time Vehicle Detection'
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                second: 'HH:mm:ss'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Vehicle Count'
                        }
                    }
                },
                animation: {
                    duration: 0
                }
            }
        });
    }
    
    function handleParkingUpdate(data) {
        console.log('Parking update:', data);
        
        // Update statistics cards
        if (data.type === 'entry' || data.type === 'exit') {
            updateStatistics();
            addRecentActivity(data);
        }
        
        // Update space-specific information
        if (data.space_id) {
            updateSpaceStatus(data.space_id, data.is_occupied);
        }
        
        // Show notification
        showNotification(data);
    }
    
    function handleNewDetection(data) {
        console.log('New detection:', data);
        
        if (data.type === 'license_plate') {
            addRecentActivity({
                type: 'license_plate',
                license_plate: data.license_plate,
                timestamp: data.timestamp
            });
        } else if (data.vehicle_count !== undefined) {
            // Update real-time chart
            updateChart(data.vehicle_count, data.timestamp);
        }
    }
    
    function updateChart(vehicleCount, timestamp) {
        const now = new Date(timestamp || Date.now());
        
        // Add new data point
        chartData.labels.push(now);
        chartData.datasets[0].data.push(vehicleCount);
        
        // Keep only last 50 data points
        if (chartData.labels.length > 50) {
            chartData.labels.shift();
            chartData.datasets[0].data.shift();
        }
        
        // Update chart
        detectionChart.update('none');
    }
    
    function updateStatistics() {
        // This would typically fetch updated statistics from the server
        // For now, we'll increment/decrement based on activity
        console.log('Updating statistics...');
    }
    
    function addRecentActivity(data) {
        const activityContainer = document.getElementById('recent-activity');
        const activityItem = createActivityItem(data);
        
        // Add to top of activity list
        activityContainer.insertBefore(activityItem, activityContainer.firstChild);
        
        // Remove oldest items if more than 10
        const items = activityContainer.children;
        if (items.length > 10) {
            activityContainer.removeChild(items[items.length - 1]);
        }
    }
    
    function createActivityItem(data) {
        const item = document.createElement('div');
        item.className = 'd-flex align-items-center mb-3';
        
        let icon = 'bi-eye';
        let iconClass = 'text-info';
        let description = 'Detection';
        
        if (data.type === 'entry') {
            icon = 'bi-arrow-right-circle';
            iconClass = 'text-success';
            description = `${data.license_plate} entered`;
        } else if (data.type === 'exit') {
            icon = 'bi-arrow-left-circle';
            iconClass = 'text-danger';
            description = `${data.license_plate} exited (${data.duration_minutes}min, $${data.toll_amount})`;
        } else if (data.type === 'license_plate') {
            icon = 'bi-credit-card';
            iconClass = 'text-warning';
            description = `Plate detected: ${data.license_plate}`;
        }
        
        const timestamp = new Date(data.timestamp).toLocaleTimeString();
        
        item.innerHTML = `
            <div class="flex-shrink-0">
                <i class="bi ${icon} ${iconClass}" style="font-size: 1.5rem;"></i>
            </div>
            <div class="flex-grow-1 ms-3">
                <div class="small text-muted">${timestamp}</div>
                <div>${description}</div>
            </div>
        `;
        
        return item;
    }
    
    function updateSpaceStatus(spaceId, isOccupied) {
        // Update space status indicators if they exist on the page
        const spaceElements = document.querySelectorAll(`[data-space-id="${spaceId}"]`);
        spaceElements.forEach(element => {
            if (isOccupied) {
                element.classList.remove('available');
                element.classList.add('occupied');
            } else {
                element.classList.remove('occupied');
                element.classList.add('available');
            }
        });
    }
    
    function showNotification(data) {
        // Create a toast notification for important events
        if (data.type === 'entry' || data.type === 'exit') {
            const toast = document.createElement('div');
            toast.className = 'toast align-items-center border-0 position-fixed top-0 end-0 m-3';
            toast.setAttribute('role', 'alert');
            toast.style.zIndex = '9999';
            
            const bgClass = data.type === 'entry' ? 'bg-success' : 'bg-primary';
            toast.classList.add(bgClass);
            
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body text-white">
                        <strong>${data.license_plate}</strong> ${data.type === 'entry' ? 'entered' : 'exited'}
                        ${data.space_name ? ` - ${data.space_name}` : ''}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `;
            
            document.body.appendChild(toast);
            
            const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
            bsToast.show();
            
            // Remove from DOM after it's hidden
            toast.addEventListener('hidden.bs.toast', () => {
                document.body.removeChild(toast);
            });
        }
    }
    
    function updateFeedStatus(message, type) {
        const statusDiv = document.getElementById('feed-status');
        const statusText = document.getElementById('feed-status-text');
        
        if (statusDiv && statusText) {
            statusDiv.className = `alert alert-${type} d-block`;
            statusText.textContent = message;
        }
    }
    
    function updateDurationCounters() {
        const counters = document.querySelectorAll('.duration-counter');
        const costCounters = document.querySelectorAll('.cost-counter');
        
        counters.forEach(counter => {
            const entryTime = new Date(counter.dataset.entryTime);
            const now = new Date();
            const diffMs = now - entryTime;
            const diffMins = Math.floor(diffMs / (1000 * 60));
            const hours = Math.floor(diffMins / 60);
            const minutes = diffMins % 60;
            
            counter.textContent = `${hours}h ${minutes}m`;
        });
        
        costCounters.forEach(counter => {
            const entryTime = new Date(counter.dataset.entryTime);
            const now = new Date();
            const diffMs = now - entryTime;
            const diffMins = Math.floor(diffMs / (1000 * 60));
            
            // Calculate estimated cost based on duration
            let cost = 0;
            if (diffMins <= 60) {
                cost = 2.0;
            } else {
                const additionalHours = Math.ceil((diffMins - 60) / 60);
                cost = 2.0 + (additionalHours * 1.0);
            }
            
            counter.textContent = `$${cost.toFixed(2)}`;
        });
    }
});
