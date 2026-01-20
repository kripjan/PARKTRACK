// Dashboard JavaScript for Smart Parking System - Live Video Processing
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO connection
    const socket = io();
    
    // Video upload elements
    const videoUploadForm = document.getElementById('video-upload-form');
    const videoFileInput = document.getElementById('video-file');
    const uploadVideoBtn = document.getElementById('upload-video-btn');
    const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    
    // Live processing elements
    const liveProcessingContainer = document.getElementById('live-processing-container');
    const cameraFrame = document.getElementById('camera-frame');
    const schematicFrame = document.getElementById('schematic-frame');
    const cameraPlaceholder = document.getElementById('camera-placeholder');
    const schematicPlaceholder = document.getElementById('schematic-placeholder');
    const processingProgress = document.getElementById('processing-progress');
    const progressText = document.getElementById('progress-text');
    const framesProcessedLive = document.getElementById('frames-processed-live');
    const occupiedLive = document.getElementById('occupied-live');
    const availableLive = document.getElementById('available-live');
    const downloadOutputBtn = document.getElementById('download-output-btn');
    
    let outputVideoFilename = null;
    
    // Check parking configuration on page load
    checkParkingConfiguration();
    
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
                        
                        // Show live processing container
                        showLiveProcessing();
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
        console.log('Connected to server');
        updateVideoStatus('Connected to Smart Parking System', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateVideoStatus('Disconnected from server', 'danger');
    });
    
    socket.on('parking_update', function(data) {
        handleParkingUpdate(data);
    });
    
    socket.on('new_detection', function(data) {
        handleNewDetection(data);
    });
    
    function checkParkingConfiguration() {
        fetch('/api/parking_config_status')
            .then(response => response.json())
            .then(data => {
                if (!data.configured) {
                    // Show warning alert
                    document.getElementById('config-status-alert').style.display = 'block';
                    
                    // Disable upload button
                    uploadVideoBtn.disabled = true;
                    uploadVideoBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Configuration Required';
                    uploadVideoBtn.classList.remove('btn-success');
                    uploadVideoBtn.classList.add('btn-warning');
                } else {
                    console.log(`Parking configuration loaded: ${data.slot_count} slots`);
                    console.log(`Database has ${data.database_spaces} parking spaces`);
                }
            })
            .catch(error => {
                console.error('Error checking parking configuration:', error);
            });
    }
    
    function showLiveProcessing() {
        liveProcessingContainer.style.display = 'block';
        
        // Reset progress
        processingProgress.style.width = '0%';
        progressText.textContent = '0%';
        framesProcessedLive.textContent = '0';
        occupiedLive.textContent = '0';
        availableLive.textContent = '0';
        
        // Hide placeholders, show images
        cameraPlaceholder.style.display = 'block';
        schematicPlaceholder.style.display = 'block';
        cameraFrame.style.display = 'none';
        schematicFrame.style.display = 'none';
        
        // Hide download button
        downloadOutputBtn.style.display = 'none';
        outputVideoFilename = null;
        
        // Scroll to live view
        liveProcessingContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    function handleNewDetection(data) {
        console.log('New detection:', data);
        
        // Handle live frames
        if (data.type === 'live_frame') {
            updateLiveFrames(data);
        }
        
        // Handle parking stats update
        else if (data.type === 'parking_stats_update') {
            updateParkingStats(data);
        }
        
        // Handle processing updates
        else if (data.type === 'processing_update') {
            updateProcessingProgress(data);
        }
        
        // Handle completion
        else if (data.type === 'processing_complete') {
            handleProcessingComplete(data);
        }
        
        // Handle errors
        else if (data.type === 'error') {
            showAlert(`Processing error: ${data.message}`, 'danger');
            liveProcessingContainer.style.display = 'none';
        }
        
        // Handle license plate detections (from plates mode)
        else if (data.type === 'license_plate' || data.license_plate) {
            addRecentActivity({
                type: 'license_plate',
                license_plate: data.license_plate,
                timestamp: data.timestamp
            });
        }
    }
    
    function updateLiveFrames(data) {
        // Update camera view
        if (data.camera_frame) {
            cameraFrame.src = 'data:image/jpeg;base64,' + data.camera_frame;
            cameraFrame.style.display = 'block';
            cameraPlaceholder.style.display = 'none';
        }
        
        // Update schematic view
        if (data.schematic_frame) {
            schematicFrame.src = 'data:image/jpeg;base64,' + data.schematic_frame;
            schematicFrame.style.display = 'block';
            schematicPlaceholder.style.display = 'none';
        }
        
        // Update live stats
        if (data.stats) {
            occupiedLive.textContent = data.stats.occupied;
            availableLive.textContent = data.stats.available;
            
            // Also update main dashboard stats
            document.getElementById('occupied-spaces').textContent = data.stats.occupied;
            document.getElementById('available-spaces').textContent = data.stats.available;
            document.getElementById('total-spaces').textContent = data.stats.total;
        }
    }
    
    function updateParkingStats(data) {
        // Update live stats counters
        if (data.occupied !== undefined) {
            occupiedLive.textContent = data.occupied;
            document.getElementById('occupied-spaces').textContent = data.occupied;
        }
        
        if (data.available !== undefined) {
            availableLive.textContent = data.available;
            document.getElementById('available-spaces').textContent = data.available;
        }
        
        if (data.total !== undefined) {
            document.getElementById('total-spaces').textContent = data.total;
        }
    }
    
    function updateProcessingProgress(data) {
        if (data.progress !== undefined) {
            processingProgress.style.width = data.progress + '%';
            progressText.textContent = data.progress.toFixed(1) + '%';
        }
        
        if (data.frames_processed !== undefined) {
            framesProcessedLive.textContent = data.frames_processed;
        }
    }
    
    function handleProcessingComplete(data) {
        showAlert(`Processing complete! Processed ${data.total_frames} frames.`, 'success');
        
        // Update progress to 100%
        processingProgress.style.width = '100%';
        progressText.textContent = '100%';
        processingProgress.classList.remove('progress-bar-animated');
        
        // Show download button if output video is available
        if (data.output_video) {
            outputVideoFilename = data.output_video;
            downloadOutputBtn.style.display = 'inline-block';
            downloadOutputBtn.onclick = function() {
                window.location.href = `/download_processed_video/${outputVideoFilename}`;
            };
        }
        
        // Refresh statistics
        updateStatistics();
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