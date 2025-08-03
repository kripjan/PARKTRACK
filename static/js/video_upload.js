// Video Upload JavaScript for Smart Parking System
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');
    const videoInput = document.getElementById('video');
    const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    
    // Initialize Socket.IO connection for real-time updates
    const socket = io();
    
    // Form submission handler
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        const file = videoInput.files[0];
        
        if (!file) {
            alert('Please select a video file');
            return;
        }
        
        // Validate file size (100MB limit)
        if (file.size > 100 * 1024 * 1024) {
            alert('File size exceeds 100MB limit');
            return;
        }
        
        // Show upload modal
        uploadModal.show();
        uploadBtn.disabled = true;
        
        // Create XMLHttpRequest for file upload with progress
        const xhr = new XMLHttpRequest();
        
        // Upload progress
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                uploadProgressBar.style.width = percentComplete + '%';
                uploadProgressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        // Upload complete
        xhr.addEventListener('load', function() {
            uploadModal.hide();
            uploadBtn.disabled = false;
            
            if (xhr.status === 200) {
                // Success
                showAlert('Video uploaded successfully and processing started!', 'success');
                uploadForm.reset();
                showProcessingStatus();
            } else {
                // Error
                showAlert('Error uploading video. Please try again.', 'danger');
            }
        });
        
        // Upload error
        xhr.addEventListener('error', function() {
            uploadModal.hide();
            uploadBtn.disabled = false;
            showAlert('Error uploading video. Please check your connection.', 'danger');
        });
        
        // Send the request
        xhr.open('POST', '/upload_video');
        xhr.send(formData);
    });
    
    // File input change handler
    videoInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Show file info
            const fileSize = (file.size / (1024 * 1024)).toFixed(2);
            const fileInfo = document.createElement('div');
            fileInfo.className = 'alert alert-info mt-2';
            fileInfo.innerHTML = `
                <i class="bi bi-info-circle me-2"></i>
                Selected: <strong>${file.name}</strong> (${fileSize} MB)
            `;
            
            // Remove any existing file info
            const existingInfo = uploadForm.querySelector('.alert-info');
            if (existingInfo) {
                existingInfo.remove();
            }
            
            // Add after file input
            videoInput.parentNode.appendChild(fileInfo);
        }
    });
    
    // Socket event handlers for real-time processing updates
    socket.on('processing_update', function(data) {
        updateProcessingStatus(data);
    });
    
    socket.on('processing_complete', function(data) {
        hideProcessingStatus();
        showAlert(`Video processing completed! Detected ${data.vehicles} vehicles and ${data.license_plates} license plates.`, 'success');
        updateProcessingHistory(data);
    });
    
    socket.on('processing_error', function(data) {
        hideProcessingStatus();
        showAlert(`Processing error: ${data.error}`, 'danger');
    });
    
    function showProcessingStatus() {
        const statusDiv = document.getElementById('processing-status');
        const progressDiv = document.getElementById('processing-progress');
        
        statusDiv.classList.add('d-none');
        progressDiv.classList.remove('d-none');
        
        // Reset counters
        document.getElementById('vehicles-detected').textContent = '0';
        document.getElementById('plates-recognized').textContent = '0';
        document.getElementById('sessions-created').textContent = '0';
        document.getElementById('frames-processed').textContent = '0';
        
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
        // Update progress bar
        if (data.progress !== undefined) {
            const progressBar = document.getElementById('progress-bar');
            progressBar.style.width = data.progress + '%';
            document.getElementById('progress-percentage').textContent = data.progress.toFixed(1) + '%';
        }
        
        // Update counters
        if (data.vehicles_detected !== undefined) {
            document.getElementById('vehicles-detected').textContent = data.vehicles_detected;
        }
        
        if (data.plates_recognized !== undefined) {
            document.getElementById('plates-recognized').textContent = data.plates_recognized;
        }
        
        if (data.sessions_created !== undefined) {
            document.getElementById('sessions-created').textContent = data.sessions_created;
        }
        
        if (data.frames_processed !== undefined) {
            document.getElementById('frames-processed').textContent = data.frames_processed;
        }
    }
    
    function updateProcessingHistory(data) {
        const historyTable = document.getElementById('processing-history');
        
        // Remove "no data" message if it exists
        const noDataRow = historyTable.querySelector('td[colspan="7"]');
        if (noDataRow) {
            noDataRow.parentNode.remove();
        }
        
        // Create new row
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${data.filename}</td>
            <td>${new Date(data.upload_time).toLocaleString()}</td>
            <td>${data.duration || 'N/A'}</td>
            <td><span class="badge bg-primary">${data.vehicles || 0}</span></td>
            <td><span class="badge bg-success">${data.license_plates || 0}</span></td>
            <td><span class="badge bg-success">Completed</span></td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="viewResults('${data.id}')">
                    <i class="bi bi-eye me-1"></i>View
                </button>
            </td>
        `;
        
        // Add to top of table
        historyTable.insertBefore(row, historyTable.firstChild);
    }
    
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert after the main heading
        const container = document.querySelector('.container');
        const heading = container.querySelector('.row');
        container.insertBefore(alertDiv, heading.nextSibling);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    // Drag and drop functionality
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
            
            // Check file type
            const allowedTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'];
            if (allowedTypes.includes(file.type) || file.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
                videoInput.files = files;
                videoInput.dispatchEvent(new Event('change'));
            } else {
                showAlert('Please select a valid video file (MP4, AVI, MOV, MKV)', 'warning');
            }
        }
    });
});

// Global function for viewing processing results
function viewResults(processId) {
    // This would open a modal or navigate to a results page
    alert(`Viewing results for process ${processId} (Feature to be implemented)`);
}
