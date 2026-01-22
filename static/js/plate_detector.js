// Plate Detector JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const imageInput = document.getElementById('image-input');
    const detectionTypeSelect = document.getElementById('detection-type');
    const uploadBtn = document.getElementById('upload-btn');
    const imagePreview = document.getElementById('image-preview');
    const previewContainer = document.getElementById('preview-container');
    const resultsSection = document.getElementById('results-section');
    const croppedPlateImage = document.getElementById('cropped-plate-image');
    const detectedPlateText = document.getElementById('detected-plate-text');
    const correctedPlateInput = document.getElementById('corrected-plate-input');
    const savePlateBtn = document.getElementById('save-plate-btn');
    const resetBtn = document.getElementById('reset-btn');
    const refreshTableBtn = document.getElementById('refresh-table-btn');
    
    const processingModal = new bootstrap.Modal(document.getElementById('processing-modal'));
    const successModal = new bootstrap.Modal(document.getElementById('success-modal'));
    const imagePreviewModal = new bootstrap.Modal(document.getElementById('image-preview-modal'));
    
    let currentCroppedPlatePath = '';
    let currentDetectedText = '';
    let currentDetectionType = 'entry';
    
    // Image preview
    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
    
    // Form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = imageInput.files[0];
        if (!file) {
            showAlert('Please select an image', 'warning');
            return;
        }
        
        currentDetectionType = detectionTypeSelect.value;
        
        const formData = new FormData();
        formData.append('image', file);
        formData.append('detection_type', currentDetectionType);
        
        uploadBtn.disabled = true;
        processingModal.show();
        
        fetch('/upload_plate_image', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            processingModal.hide();
            uploadBtn.disabled = false;
            
            if (data.success) {
                displayResults(data);
                showAlert(data.message, 'success');
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            processingModal.hide();
            uploadBtn.disabled = false;
            console.error('Error:', error);
            showAlert('Error processing image', 'danger');
        });
    });
    
    // Display results
    function displayResults(data) {
        // Show results section
        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ behavior: 'smooth' });
        
        // Display cropped plate
        if (data.cropped_plate) {
            croppedPlateImage.src = data.cropped_plate;
            currentCroppedPlatePath = data.cropped_plate_path || data.cropped_plate;
        }
        
        // Display detected text
        currentDetectedText = data.plate_text || '';
        detectedPlateText.textContent = currentDetectedText || 'No text detected';
        
        // Pre-fill correction input with detected text
        correctedPlateInput.value = currentDetectedText;
        
        // Update detection type badge
        updateDetectionTypeBadge(data.detection_type);
        
        // Focus on input for easy editing
        setTimeout(() => correctedPlateInput.focus(), 300);
    }
    
    // Update detection type badge
    function updateDetectionTypeBadge(type) {
        const badge = document.getElementById('type-badge');
        if (type === 'entry') {
            badge.className = 'badge bg-success';
            badge.innerHTML = '<i class="bi bi-arrow-right-circle me-1"></i> Entry';
        } else {
            badge.className = 'badge bg-warning text-dark';
            badge.innerHTML = '<i class="bi bi-arrow-left-circle me-1"></i> Exit';
        }
    }
    
    // Save plate to database
    savePlateBtn.addEventListener('click', function() {
        const correctedText = correctedPlateInput.value.trim();
        
        if (!correctedText) {
            showAlert('Please enter the plate number', 'warning');
            correctedPlateInput.focus();
            return;
        }
        
        savePlateBtn.disabled = true;
        savePlateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
        
        fetch('/save_corrected_plate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                detected_text: currentDetectedText,
                corrected_text: correctedText,
                cropped_plate_path: currentCroppedPlatePath,
                detection_type: currentDetectionType
            })
        })
        .then(response => response.json())
        .then(data => {
            savePlateBtn.disabled = false;
            savePlateBtn.innerHTML = '<i class="bi bi-save me-2"></i>Save to Database';
            
            if (data.success) {
                document.getElementById('saved-plate-number').textContent = data.plate_number;
                document.getElementById('saved-detection-type').textContent = data.detection_type.toUpperCase();
                successModal.show();
                
                // Refresh table after short delay
                setTimeout(() => {
                    refreshDetectionsTable();
                }, 1000);
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            savePlateBtn.disabled = false;
            savePlateBtn.innerHTML = '<i class="bi bi-save me-2"></i>Save to Database';
            console.error('Error:', error);
            showAlert('Error saving plate', 'danger');
        });
    });
    
    // Reset form
    resetBtn.addEventListener('click', function() {
        uploadForm.reset();
        previewContainer.style.display = 'none';
        resultsSection.style.display = 'none';
        currentCroppedPlatePath = '';
        currentDetectedText = '';
        currentDetectionType = 'entry';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    
    // Refresh detections table
    refreshTableBtn.addEventListener('click', refreshDetectionsTable);
    
    function refreshDetectionsTable() {
        refreshTableBtn.disabled = true;
        refreshTableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading...';
        
        fetch('/api/recent_detections')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateDetectionsTable(data.detections);
                } else {
                    showAlert('Error loading detections', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error loading detections', 'danger');
            })
            .finally(() => {
                refreshTableBtn.disabled = false;
                refreshTableBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
            });
    }
    
    function updateDetectionsTable(detections) {
        const tbody = document.getElementById('detections-table-body');
        tbody.innerHTML = '';
        
        if (detections.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No detections yet</td></tr>';
            return;
        }
        
        detections.forEach((detection, index) => {
            const row = document.createElement('tr');
            
            // Confidence badge
            let confidenceBadge = '<span class="badge bg-secondary">N/A</span>';
            if (detection.confidence !== null) {
                const confidence = (detection.confidence * 100).toFixed(1);
                let badgeClass = 'bg-danger';
                if (detection.confidence >= 0.7) badgeClass = 'bg-success';
                else if (detection.confidence >= 0.4) badgeClass = 'bg-warning';
                confidenceBadge = `<span class="badge ${badgeClass}">${confidence}%</span>`;
            }
            
            // Format timestamp
            const timestamp = new Date(detection.timestamp).toLocaleString();
            
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${timestamp}</td>
                <td><strong class="font-monospace">${detection.license_plate}</strong></td>
                <td>${confidenceBadge}</td>
                <td>
                    ${detection.frame_path ? 
                        `<button class="btn btn-sm btn-outline-primary" onclick="viewPlateImage('${detection.frame_path}')">
                            <i class="bi bi-eye"></i>
                        </button>` : 
                        '<span class="text-muted">-</span>'}
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }
    
    // View plate image in modal
    window.viewPlateImage = function(framePath) {
        const modalImage = document.getElementById('modal-plate-image');
        modalImage.src = `/uploads/detected_plates/${framePath}`;
        imagePreviewModal.show();
    };
    
    // Show alert
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        const firstRow = container.querySelector('.row');
        container.insertBefore(alertDiv, firstRow);
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    // Drag and drop
    const uploadCard = uploadForm.closest('.card-body');
    
    uploadCard.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadCard.classList.add('bg-light');
    });
    
    uploadCard.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadCard.classList.remove('bg-light');
    });
    
    uploadCard.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadCard.classList.remove('bg-light');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.type.startsWith('image/')) {
                imageInput.files = files;
                imageInput.dispatchEvent(new Event('change'));
            } else {
                showAlert('Please drop a valid image file', 'warning');
            }
        }
    });
});