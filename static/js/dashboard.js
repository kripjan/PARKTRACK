

// Dashboard JavaScript for Smart Parking System with Live Video Feed
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO connection
    const socket = io();
    
    // Video upload elements
    const videoUploadForm = document.getElementById('video-upload-form');
    const videoFileInput = document.getElementById('video-file');
    const uploadVideoBtn = document.getElementById('upload-video-btn');
    const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    
    // Live feed elements
    const liveFeedSection = document.getElementById('live-feed-section');
    const cameraFeed = document.getElementById('camera-feed');
    const schematicFeed = document.getElementById('schematic-feed');
    const cameraPlaceholder = document.getElementById('camera-placeholder');
    const schematicPlaceholder = document.getElementById('schematic-placeholder');
    

    
    // Duration and cost counters
    updateDurationCounters();
    setInterval(updateDurationCounters, 1000); // Update every second
    
    // Video upload form handler
    if (videoUploadForm) {
        videoUploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const file = videoFileInput.files[0];
            if (!file) {
                showAlert('Please select a video file', 'warning');
                return;
            }
            
            // Validate file size (100MB limit)
            if (file.size > 100 * 1024 * 1024) {
                showAlert('File size exceeds 100MB limit', 'danger');
                return;
            }
            
            // Show upload modal
            uploadModal.show();
            uploadVideoBtn.disabled = true;
            
            const formData = new FormData();
            formData.append('video', file);
            
            // Create XMLHttpRequest for upload progress
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    uploadProgressBar.style.width = percentComplete + '%';
                }
            });
            
            xhr.addEventListener('load', function() {
                uploadModal.hide();
                uploadVideoBtn.disabled = false;
                
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.success) {
                        showAlert('Video uploaded successfully! Processing started...', 'success');
                        videoUploadForm.reset();
                        updateVideoStatus('Processing video...', 'info');
                        
                        // Show live feed section immediately
                        console.log('Showing live feed section');
                        liveFeedSection.style.display = 'block';
                        
                        // Scroll to live feed
                        liveFeedSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    } else {
                        showAlert(response.message || 'Error uploading video', 'danger');
                    }
                } else {
                    showAlert('Error uploading video. Please try again.', 'danger');
                }
            });
            
            xhr.addEventListener('error', function() {
                uploadModal.hide();
                uploadVideoBtn.disabled = false;
                showAlert('Error uploading video. Please check your connection.', 'danger');
            });
            
            xhr.open('POST', '/upload_video');
            xhr.send(formData);
        });
    }
    
    // Socket event handlers
    socket.on('connect', function() {
        console.log('✅ Connected to server');
        updateVideoStatus('Connected to Smart Parking System', 'success');
        
        // Test message
        socket.emit('test', { message: 'Dashboard connected' });
    });
    
    socket.on('disconnect', function() {
        console.log('❌ Disconnected from server');
        updateVideoStatus('Disconnected from server', 'danger');
    });
    
    socket.on('parking_update', function(data) {
        handleParkingUpdate(data);
    });
    
    socket.on('new_detection', function(data) {
        handleNewDetection(data);
    });
    
   
    
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
        
        // Handle live frame updates
        if (data.type === 'live_frame') {
            updateLiveFeeds(data);
            return;
        }
        
        // Handle parking stats updates
        if (data.type === 'parking_stats_update') {
            updateLiveStats(data);
        }
        
        if (data.type === 'license_plate' || data.license_plate) {
            addRecentActivity({
                type: 'license_plate',
                license_plate: data.license_plate,
                timestamp: data.timestamp
            });
        }
        
        if (data.vehicle_count !== undefined) {
            // Update real-time chart
            updateChart(data.vehicle_count, data.timestamp);
        }
        
        // Handle processing updates
        if (data.type === 'processing_update') {
            updateVideoStatus(`Processing: ${data.progress?.toFixed(1)}% - ${data.frames_processed} frames`, 'info');
        } else if (data.type === 'processing_complete') {
            updateVideoStatus('Processing complete!', 'success');
            showAlert(`Video processing complete!`, 'success');
            
            // Hide live feed section after a delay
            setTimeout(() => {
                liveFeedSection.style.display = 'none';
            }, 5000);
        }
    }
    
    function updateLiveFeeds(data) {
        console.log('📹 Updating live feeds...');
        console.log('Camera frame present:', !!data.camera_frame);
        console.log('Schematic frame present:', !!data.schematic_frame);
        
        // Make sure section is visible
        liveFeedSection.style.display = 'block';
        
        // Update camera feed
        if (data.camera_frame) {
            console.log('✅ Updating camera feed');
            cameraFeed.src = 'data:image/jpeg;base64,' + data.camera_frame;
            cameraFeed.style.display = 'block';
            cameraPlaceholder.style.display = 'none';
        } else {
            console.log('❌ No camera frame data');
        }
        
        // Update schematic feed
        if (data.schematic_frame) {
            console.log('✅ Updating schematic feed');
            schematicFeed.src = 'data:image/jpeg;base64,' + data.schematic_frame;
            schematicFeed.style.display = 'block';
            schematicPlaceholder.style.display = 'none';
        } else {
            console.log('❌ No schematic frame data');
        }
        
        // Update live stats
        if (data.stats) {
            console.log('📊 Updating stats:', data.stats);
            document.getElementById('live-total-spaces').textContent = data.stats.total;
            document.getElementById('live-occupied-spaces').textContent = data.stats.occupied;
            document.getElementById('live-available-spaces').textContent = data.stats.available;
            
            const occupancyRate = data.stats.total > 0 
                ? ((data.stats.occupied / data.stats.total) * 100).toFixed(1) 
                : 0;
            document.getElementById('live-occupancy-rate').textContent = occupancyRate + '%';
        }
    }
    
    function updateLiveStats(data) {
        // Update live statistics bar
        document.getElementById('live-total-spaces').textContent = data.total || 0;
        document.getElementById('live-occupied-spaces').textContent = data.occupied || 0;
        document.getElementById('live-available-spaces').textContent = data.available || 0;
        
        const occupancyRate = data.total > 0 
            ? ((data.occupied / data.total) * 100).toFixed(1) 
            : 0;
        document.getElementById('live-occupancy-rate').textContent = occupancyRate + '%';
        
        // Also update main statistics cards
        if (data.vehicle_count !== undefined) {
            updateChart(data.vehicle_count, new Date().toISOString());
        }
    }
    
    function updateChart(vehicleCount, timestamp) {
        if (!detectionChart) return;
        
        const now = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        
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
        // Fetch updated statistics
        fetch('/api/parking_statistics')
            .then(response => response.json())
            .then(data => {
                if (data.total_spaces !== undefined) {
                    document.getElementById('total-spaces').textContent = data.total_spaces;
                }
                if (data.occupied_spaces !== undefined) {
                    document.getElementById('occupied-spaces').textContent = data.occupied_spaces;
                }
                if (data.available_spaces !== undefined) {
                    document.getElementById('available-spaces').textContent = data.available_spaces;
                }
            })
            .catch(error => {
                console.error('Error updating statistics:', error);
            });
    }
    
    function addRecentActivity(data) {
        const activityContainer = document.getElementById('recent-activity');
        if (!activityContainer) return;
        
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
        item.className = 'd-flex align-items-center mb-3 activity-item new-item';
        
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
            description = `${data.license_plate} exited`;
        } else if (data.type === 'license_plate' || data.license_plate) {
            icon = 'bi-credit-card';
            iconClass = 'text-warning';
            description = `Plate detected: ${data.license_plate}`;
        }
        
        const timestamp = new Date(data.timestamp || Date.now()).toLocaleTimeString();
        
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
            
            toast.addEventListener('hidden.bs.toast', () => {
                document.body.removeChild(toast);
            });
        }
    }
    
    function updateVideoStatus(message, type) {
        const statusDiv = document.getElementById('video-status');
        const statusText = document.getElementById('video-status-text');
        
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
            
            // Calculate estimated cost
            let cost = 0;
            if (diffMins <= 60) {
                cost = 50.0; // Rs. 50 for first hour
            } else {
                const additionalHours = Math.ceil((diffMins - 60) / 60);
                cost = 50.0 + (additionalHours * 30.0); // Rs. 30 per additional hour
            }
            
            counter.textContent = `Rs. ${cost.toFixed(2)}`;
        });
    }
    
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        const heading = container.querySelector('.row');
        container.insertBefore(alertDiv, heading.nextSibling);
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
});
