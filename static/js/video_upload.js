document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');
    const imageInput = document.getElementById('vehicle-image');
    const detectionTypeSelect = document.getElementById('detection-type');
    const imagePreview = document.getElementById('image-preview');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const exitInfoSection = document.getElementById('exit-info-section');
    
    let currentDetectionData = null;
    
    // Image preview on selection
    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                imagePreviewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
    
    // Form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = imageInput.files[0];
        const detectionType = detectionTypeSelect.value;
        
        if (!file) {
            showAlert('Please select an image file', 'warning');
            return;
        }
        
        // Show processing
        processingSection.style.display = 'block';
        resultsSection.style.display = 'none';
        uploadBtn.disabled = true;
        
        const formData = new FormData();
        formData.append('image', file);
        formData.append('type', detectionType);
        
        // Upload and process
        fetch('/detect_license_plate', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            processingSection.style.display = 'none';
            
            if (data.success) {
                displayResults(data);
            } else {
                showAlert(data.message || 'Error detecting license plate', 'danger');
                uploadBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            processingSection.style.display = 'none';
            showAlert('Error processing image. Please try again.', 'danger');
            uploadBtn.disabled = false;
        });
    });
    
    function displayResults(data) {
        currentDetectionData = data;
        
        // Show results section
        resultsSection.style.display = 'block';
        
        // Display cropped plate image
        document.getElementById('cropped-plate').src = data.cropped_plate_url;
        
        // Display detected plate number
        const detectedText = data.plate_number || 'Not Recognized';
        document.getElementById('detected-plate-number').textContent = detectedText;
        
        // Pre-fill manual input
        document.getElementById('manual-plate-number').value = detectedText;
        
        // Display confidence
        const confidence = (data.confidence * 100).toFixed(1);
        const confidenceBar = document.getElementById('confidence-bar');
        confidenceBar.style.width = confidence + '%';
        document.getElementById('confidence-text').textContent = confidence + '%';
        
        // Color code confidence
        confidenceBar.className = 'progress-bar';
        if (data.confidence >= 0.7) {
            confidenceBar.classList.add('bg-success');
        } else if (data.confidence >= 0.4) {
            confidenceBar.classList.add('bg-warning');
        } else {
            confidenceBar.classList.add('bg-danger');
        }
        
        // Display detection type
        document.getElementById('type-text').textContent = data.detection_type === 'entry' ? 'Entry' : 'Exit';
        
        const detectionTypeDisplay = document.getElementById('detection-type-display');
        if (data.detection_type === 'entry') {
            detectionTypeDisplay.className = 'alert alert-success';
            detectionTypeDisplay.innerHTML = '<i class="bi bi-arrow-right-circle me-2"></i>Detection Type: <strong>Entry</strong>';
        } else {
            detectionTypeDisplay.className = 'alert alert-warning';
            detectionTypeDisplay.innerHTML = '<i class="bi bi-arrow-left-circle me-2"></i>Detection Type: <strong>Exit</strong>';
        }
        
        // Show exit information if applicable
        if (data.detection_type === 'exit' && data.session_info) {
            exitInfoSection.style.display = 'block';
            displaySessionInfo(data.session_info);
        } else {
            exitInfoSection.style.display = 'none';
        }
        
        uploadBtn.disabled = false;
    }
    
    function displaySessionInfo(session) {
        document.getElementById('entry-time').textContent = session.entry_time || 'N/A';
        document.getElementById('exit-time').textContent = session.exit_time || new Date().toLocaleString();
        document.getElementById('duration').textContent = session.duration || 'N/A';
        document.getElementById('parking-space').textContent = session.parking_space || 'Not Assigned';
        document.getElementById('toll-fee').textContent = 'Rs. ' + (session.toll_fee || 0).toFixed(2);
    }
    
    // Save button
    document.getElementById('save-btn').addEventListener('click', function() {
        const manualPlateNumber = document.getElementById('manual-plate-number').value.trim();
        
        if (!manualPlateNumber) {
            showAlert('Please enter a license plate number', 'warning');
            return;
        }
        
        if (!currentDetectionData) {
            showAlert('No detection data available', 'danger');
            return;
        }
        
        // Save to database
        const saveData = {
            plate_number: manualPlateNumber,
            detection_type: currentDetectionData.detection_type,
            confidence: currentDetectionData.confidence,
            cropped_plate_path: currentDetectionData.cropped_plate_path,
            session_id: currentDetectionData.session_id
        };
        
        fetch('/save_detection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(saveData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Detection saved successfully!', 'success');
                refreshHistory();
                
                // Reset form after 2 seconds
                setTimeout(() => {
                    resetForm();
                }, 2000);
            } else {
                showAlert(data.message || 'Error saving detection', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error saving detection. Please try again.', 'danger');
        });
    });
    
    // Reset button
    document.getElementById('reset-btn').addEventListener('click', resetForm);
    
    function resetForm() {
        uploadForm.reset();
        imagePreviewContainer.style.display = 'none';
        resultsSection.style.display = 'none';
        currentDetectionData = null;
        uploadBtn.disabled = false;
    }
    
    // Refresh history button
    document.getElementById('refresh-history-btn').addEventListener('click', refreshHistory);
    
    function refreshHistory() {
        fetch('/api/detection_history')
            .then(response => response.json())
            .then(data => {
                const tbody = document.getElementById('history-table-body');
                tbody.innerHTML = '';
                
                if (data.detections && data.detections.length > 0) {
                    data.detections.forEach(detection => {
                        const row = createHistoryRow(detection);
                        tbody.appendChild(row);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No detections yet</td></tr>';
                }
            })
            .catch(error => {
                console.error('Error refreshing history:', error);
            });
    }
    
    function createHistoryRow(detection) {
        const row = document.createElement('tr');
        
        const typeClass = detection.type === 'entry' ? 'success' : 'warning';
        const typeIcon = detection.type === 'entry' ? 'arrow-right-circle' : 'arrow-left-circle';
        
        row.innerHTML = `
            <td>${new Date(detection.timestamp).toLocaleString()}</td>
            <td><strong class="font-monospace">${detection.plate_number}</strong></td>
            <td>
                <span class="badge bg-${typeClass}">
                    <i class="bi bi-${typeIcon} me-1"></i>
                    ${detection.type.toUpperCase()}
                </span>
            </td>
            <td>${(detection.confidence * 100).toFixed(1)}%</td>
            <td><strong>Rs. ${detection.toll_fee ? detection.toll_fee.toFixed(2) : '0.00'}</strong></td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="viewDetection(${detection.id})">
                    <i class="bi bi-eye"></i>
                </button>
            </td>
        `;
        
        return row;
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
    
    // Load history on page load
    refreshHistory();
});