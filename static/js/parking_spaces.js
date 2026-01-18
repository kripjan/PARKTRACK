// ROI Configuration JavaScript for Smart Parking System
document.addEventListener('DOMContentLoaded', function() {
    const configUploadForm = document.getElementById('config-upload-form');
    const frameUploadForm = document.getElementById('frame-upload-form');
    const configFileInput = document.getElementById('config-file');
    const frameFileInput = document.getElementById('frame-file');
    const generatePreviewBtn = document.getElementById('generate-preview-btn');
    const framePreview = document.getElementById('frame-preview');
    const framePreviewContainer = document.getElementById('frame-preview-container');
    
    let configUploaded = false;
    let frameUploaded = false;
    
    // Config file upload handler
    configUploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = configFileInput.files[0];
        if (!file) {
            showAlert('Please select a configuration file', 'warning');
            return;
        }
        
        const formData = new FormData();
        formData.append('config_file', file);
        
        const uploadBtn = document.getElementById('upload-config-btn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Uploading...';
        
        fetch('/upload_roi_config', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                configUploaded = true;
                updateConfigStatus(data);
                checkPreviewReady();
                
                // Reload page to show config in table
                setTimeout(() => window.location.reload(), 1500);
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error uploading configuration file', 'danger');
        })
        .finally(() => {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload me-2"></i>Upload Configuration';
        });
    });
    
    // Frame file upload handler
    frameUploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = frameFileInput.files[0];
        if (!file) {
            showAlert('Please select a frame image', 'warning');
            return;
        }
        
        const formData = new FormData();
        formData.append('frame_file', file);
        
        const uploadBtn = document.getElementById('upload-frame-btn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Uploading...';
        
        fetch('/upload_cctv_frame', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                frameUploaded = true;
                updateFrameStatus(data);
                checkPreviewReady();
            } else {
                showAlert(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error uploading frame image', 'danger');
        })
        .finally(() => {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload me-2"></i>Upload Frame';
        });
    });
    
    // Frame file preview
    frameFileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                framePreview.src = e.target.result;
                framePreviewContainer.style.display = 'block';
            };
            
            reader.readAsDataURL(file);
        }
    });
    
    // Generate preview button handler
    generatePreviewBtn.addEventListener('click', function() {
        generatePreviewBtn.disabled = true;
        generatePreviewBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Generating...';
        
        // Show loading state
        document.getElementById('no-preview').style.display = 'none';
        document.getElementById('preview-loading').style.display = 'block';
        document.getElementById('preview-image-container').style.display = 'none';
        
        fetch('/generate_roi_preview', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                
                // Display preview image
                const previewImage = document.getElementById('preview-image');
                previewImage.src = data.preview_url + '?t=' + new Date().getTime(); // Cache bust
                
                document.getElementById('preview-loading').style.display = 'none';
                document.getElementById('preview-image-container').style.display = 'block';
            } else {
                showAlert(data.message, 'danger');
                document.getElementById('preview-loading').style.display = 'none';
                document.getElementById('no-preview').style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error generating preview', 'danger');
            document.getElementById('preview-loading').style.display = 'none';
            document.getElementById('no-preview').style.display = 'block';
        })
        .finally(() => {
            generatePreviewBtn.disabled = false;
            generatePreviewBtn.innerHTML = '<i class="bi bi-arrow-repeat me-2"></i>Generate Preview';
        });
    });
    
    // Check if both files are uploaded to enable preview button
    function checkPreviewReady() {
        // Check via API
        fetch('/api/roi_summary')
            .then(response => response.json())
            .then(data => {
                if (data.exists && data.frame_uploaded) {
                    generatePreviewBtn.disabled = false;
                    
                    // Auto-generate preview if both are available
                    if (configUploaded || frameUploaded) {
                        generatePreviewBtn.click();
                    }
                }
            })
            .catch(error => {
                console.error('Error checking ROI status:', error);
            });
    }
    
    function updateConfigStatus(data) {
        const statusDiv = document.getElementById('config-status');
        statusDiv.innerHTML = `
            <div class="alert alert-success">
                <i class="bi bi-check-circle me-2"></i>
                Configuration uploaded: ${data.roi_count} ROI entries
            </div>
        `;
    }
    
    function updateFrameStatus(data) {
        const statusDiv = document.getElementById('frame-status');
        statusDiv.innerHTML = `
            <div class="alert alert-success">
                <i class="bi bi-check-circle me-2"></i>
                Frame uploaded successfully
            </div>
        `;
    }
    
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert at the top of the container
        const container = document.querySelector('.container');
        const firstRow = container.querySelector('.row');
        container.insertBefore(alertDiv, firstRow);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    // Load existing preview if available
    function loadExistingPreview() {
        fetch('/api/roi_summary')
            .then(response => response.json())
            .then(data => {
                if (data.preview_available) {
                    const previewImage = document.getElementById('preview-image');
                    previewImage.src = '/roi_preview?t=' + new Date().getTime();
                    
                    document.getElementById('no-preview').style.display = 'none';
                    document.getElementById('preview-image-container').style.display = 'block';
                }
                
                if (data.exists && data.frame_uploaded) {
                    generatePreviewBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error loading preview:', error);
            });
    }
    
    // Drag and drop for config file
    const configCard = document.querySelector('#config-upload-form').closest('.card-body');
    
    configCard.addEventListener('dragover', function(e) {
        e.preventDefault();
        configCard.classList.add('bg-light');
    });
    
    configCard.addEventListener('dragleave', function(e) {
        e.preventDefault();
        configCard.classList.remove('bg-light');
    });
    
    configCard.addEventListener('drop', function(e) {
        e.preventDefault();
        configCard.classList.remove('bg-light');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.name.endsWith('.json') || file.name.endsWith('.txt')) {
                configFileInput.files = files;
            } else {
                showAlert('Please drop a JSON or TXT file', 'warning');
            }
        }
    });
    
    // Drag and drop for frame file
    const frameCard = document.querySelector('#frame-upload-form').closest('.card-body');
    
    frameCard.addEventListener('dragover', function(e) {
        e.preventDefault();
        frameCard.classList.add('bg-light');
    });
    
    frameCard.addEventListener('dragleave', function(e) {
        e.preventDefault();
        frameCard.classList.remove('bg-light');
    });
    
    frameCard.addEventListener('drop', function(e) {
        e.preventDefault();
        frameCard.classList.remove('bg-light');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp'];
            if (validTypes.includes(file.type)) {
                frameFileInput.files = files;
                frameFileInput.dispatchEvent(new Event('change'));
            } else {
                showAlert('Please drop a valid image file (JPG, PNG, BMP)', 'warning');
            }
        }
    });
    
    // Initialize
    loadExistingPreview();
    checkPreviewReady();
});