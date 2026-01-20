// Video Upload JavaScript - License Plate Detection & OCR
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');
    const videoInput = document.getElementById('video');
    const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
    const plateDetailModal = new bootstrap.Modal(document.getElementById('plateDetailModal'));
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const exportResultsBtn = document.getElementById('export-results-btn');
    
    let detectedPlates = [];
    let currentProcessingId = null;
    
    // Initialize Socket.IO
    const socket = io();
    
    // Form submission handler
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = videoInput.files[0];
        
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
        uploadBtn.disabled = true;
        
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
            uploadBtn.disabled = false;
            
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                if (response.success) {
                    showAlert('Video uploaded successfully! Processing started...', 'success');
                    uploadForm.reset();
                    showProcessingStatus();
                    detectedPlates = [];
                    updatePlatesDisplay();
                } else {
                    showAlert(response.message || 'Error uploading video', 'danger');
                }
            } else {
                showAlert('Error uploading video. Please try again.', 'danger');
            }
        });
        
        xhr.addEventListener('error', function() {
            uploadModal.hide();
            uploadBtn.disabled = false;
            showAlert('Error uploading video. Please check your connection.', 'danger');
        });
        
        xhr.open('POST', '/upload_video_for_plates');
        xhr.send(formData);
    });
    
    // File input change handler
    videoInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const fileSize = (file.size / (1024 * 1024)).toFixed(2);
            showAlert(`Selected: <strong>${file.name}</strong> (${fileSize} MB)`, 'info');
        }
    });
    
    // Socket event handlers
    socket.on('plate_detected', function(data) {
        console.log('Plate detected:', data);
        addDetectedPlate(data);
    });
    
    socket.on('new_detection', function(data) {
        console.log('Detection update:', data);
        
        // Handle different types of detection updates
        if (data.type === 'processing_update') {
            updateProcessingStatus(data);
        } else if (data.type === 'processing_complete') {
            hideProcessingStatus();
            showAlert(`Processing complete! Detected ${data.plates_detected} license plates with ${data.plates_recognized} successfully recognized.`, 'success');
            exportResultsBtn.disabled = detectedPlates.length === 0;
        } else if (data.type === 'error') {
            hideProcessingStatus();
            showAlert(`Processing error: ${data.message}`, 'danger');
        }
    });
    
    socket.on('processing_error', function(data) {
        hideProcessingStatus();
        showAlert(`Processing error: ${data.error}`, 'danger');
    });
    
    // Export results handler
    exportResultsBtn.addEventListener('click', function() {
        if (detectedPlates.length === 0) {
            showAlert('No plates to export', 'warning');
            return;
        }
        
        // Create CSV content
        let csv = 'Plate Number,Confidence,Frame,Timestamp\n';
        detectedPlates.forEach(plate => {
            csv += `${plate.plate_number},${plate.confidence},${plate.frame},${plate.timestamp}\n`;
        });
        
        // Download CSV
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `license_plates_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        
        showAlert('Results exported successfully!', 'success');
    });
    
    function showProcessingStatus() {
        const statusDiv = document.getElementById('processing-status');
        const progressDiv = document.getElementById('processing-progress');
        
        statusDiv.classList.add('d-none');
        progressDiv.classList.remove('d-none');
        
        // Reset counters
        document.getElementById('frames-processed').textContent = '0';
        document.getElementById('plates-detected').textContent = '0';
        document.getElementById('plates-recognized').textContent = '0';
        
        // Reset progress bar
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = '0%';
        document.getElementById('progress-percentage').textContent = '0%';
    }
    
    function hideProcessingStatus() {
        const statusDiv = document.getElementById('processing-status');
        const progressDiv = document.getElementById('processing-progress');
        
        statusDiv.classList.remove('d-none');
        progressDiv.classList.add('d-none');
    }
    
    function updateProcessingStatus(data) {
        if (data.progress !== undefined) {
            const progressBar = document.getElementById('progress-bar');
            progressBar.style.width = data.progress + '%';
            document.getElementById('progress-percentage').textContent = data.progress.toFixed(1) + '%';
        }
        
        if (data.frames_processed !== undefined) {
            document.getElementById('frames-processed').textContent = data.frames_processed;
        }
        
        if (data.plates_detected !== undefined) {
            document.getElementById('plates-detected').textContent = data.plates_detected;
        }
        
        if (data.plates_recognized !== undefined) {
            document.getElementById('plates-recognized').textContent = data.plates_recognized;
        }
    }
    
    function addDetectedPlate(plateData) {
        detectedPlates.push(plateData);
        updatePlatesDisplay();
        
        // Update counter
        document.getElementById('plates-detected').textContent = detectedPlates.length;
        
        if (plateData.plate_number) {
            const recognized = detectedPlates.filter(p => p.plate_number).length;
            document.getElementById('plates-recognized').textContent = recognized;
        }
    }
    
    function updatePlatesDisplay() {
        const container = document.getElementById('detected-plates-container');
        const grid = document.getElementById('plates-grid');
        
        if (detectedPlates.length === 0) {
            container.style.display = 'block';
            grid.style.display = 'none';
            return;
        }
        
        container.style.display = 'none';
        grid.style.display = 'flex';
        grid.innerHTML = '';
        
        detectedPlates.forEach((plate, index) => {
            const card = createPlateCard(plate, index);
            grid.appendChild(card);
        });
        
        exportResultsBtn.disabled = false;
    }
    
    function createPlateCard(plateData, index) {
        const col = document.createElement('div');
        col.className = 'col-md-4 col-lg-3';
        
        const confidence = plateData.confidence ? (plateData.confidence * 100).toFixed(1) : 'N/A';
        const plateNumber = plateData.plate_number || 'Unrecognized';
        const badgeClass = plateData.plate_number ? 'bg-success' : 'bg-warning text-dark';
        
        col.innerHTML = `
            <div class="card h-100 plate-card" data-plate-id="${index}" style="cursor: pointer;">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge ${badgeClass}">#${index + 1}</span>
                        <small class="text-muted">Frame ${plateData.frame || 'N/A'}</small>
                    </div>
                    
                    ${plateData.image_url ? `
                        <img src="${plateData.image_url}" class="img-fluid rounded mb-2" alt="License Plate">
                    ` : `
                        <div class="bg-secondary rounded d-flex align-items-center justify-content-center" style="height: 100px;">
                            <i class="bi bi-image text-white" style="font-size: 2rem;"></i>
                        </div>
                    `}
                    
                    <h6 class="card-title mb-1">${plateNumber}</h6>
                    <small class="text-muted">Confidence: ${confidence}%</small>
                </div>
            </div>
        `;
        
        // Add click handler
        col.querySelector('.plate-card').addEventListener('click', () => {
            showPlateDetail(plateData, index);
        });
        
        return col;
    }
    
    function showPlateDetail(plateData, index) {
        // Populate modal
        if (plateData.image_url) {
            document.getElementById('modal-plate-image').src = plateData.image_url;
        }
        
        document.getElementById('modal-plate-number').textContent = plateData.plate_number || 'Unrecognized';
        document.getElementById('modal-confidence').textContent = plateData.confidence 
            ? (plateData.confidence * 100).toFixed(1) + '%' 
            : 'N/A';
        document.getElementById('modal-frame').textContent = plateData.frame || 'N/A';
        document.getElementById('modal-timestamp').textContent = plateData.timestamp 
            ? new Date(plateData.timestamp).toLocaleString() 
            : 'N/A';
        
        // Download button
        const downloadBtn = document.getElementById('download-plate-btn');
        downloadBtn.onclick = function() {
            if (plateData.image_url) {
                const a = document.createElement('a');
                a.href = plateData.image_url;
                a.download = `plate_${index + 1}_${plateData.plate_number || 'unknown'}.jpg`;
                a.click();
            }
        };
        
        plateDetailModal.show();
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
    
    // Drag and drop
    const uploadArea = uploadForm.querySelector('.card-body');
    
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('bg-light');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('bg-light');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('bg-light');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            const allowedTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];
            if (allowedTypes.includes(file.type) || file.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
                videoInput.files = files;
                videoInput.dispatchEvent(new Event('change'));
            } else {
                showAlert('Please drop a valid video file', 'warning');
            }
        }
    });
    
    // Poll for status updates if processing
    function checkProcessingStatus() {
        fetch('/api/processing_status')
            .then(response => response.json())
            .then(data => {
                if (data.is_processing) {
                    showProcessingStatus();
                }
            })
            .catch(error => {
                console.error('Error checking status:', error);
            });
    }
    
    // Check on page load
    checkProcessingStatus();
});