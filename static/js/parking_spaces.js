// ROI Configuration JavaScript for Smart Parking System
document.addEventListener('DOMContentLoaded', function() {
    const configUploadForm = document.getElementById('config-upload-form');
    const frameUploadForm = document.getElementById('frame-upload-form');
    const configFile = document.getElementById('config-file');
    const frameFile = document.getElementById('frame-file');
    const generatePreviewBtn = document.getElementById('generate-preview-btn');
    const framePreview = document.getElementById('frame-preview');
    const framePreviewContainer = document.getElementById('frame-preview-container');
    
    let configUploaded = false;
    let frameUploaded = false;
    
    // Configuration file upload
    configUploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const file = configFile.files[0];
        if (!file) {
            showAlert('config-status', 'Please select a configuration file', 'danger');
            return;
        }
        
        // Validate JSON before uploading
        try {
            const text = await file.text();
            const json = JSON.parse(text);
            
            // Validate structure
            if (!Array.isArray(json)) {
                throw new Error('Configuration must be an array');
            }
            
            for (const roi of json) {
                if (!roi.type || !roi.name || !roi.points) {
                    throw new Error('Each ROI must have type, name, and points');
                }
                if (!Array.isArray(roi.points)) {
                    throw new Error('Points must be an array');
                }
            }
            
        } catch (error) {
            showAlert('config-status', `Invalid JSON: ${error.message}`, 'danger');
            return;
        }
        
        // Upload configuration
        const formData = new FormData();
        formData.append('config_file', file);
        
        const uploadBtn = document.getElementById('upload-config-btn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Uploading...';
        
        try {
            const response = await fetch('/upload_roi_config', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('config-status', 
                    `Configuration uploaded successfully! ${result.roi_count} ROIs loaded.`, 
                    'success');
                configUploaded = true;
                updateGenerateButton();
                
                // Reload configuration list
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAlert('config-status', `Error: ${result.message}`, 'danger');
            }
            
        } catch (error) {
            showAlert('config-status', `Upload failed: ${error.message}`, 'danger');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload me-2"></i>Upload Configuration';
        }
    });
    
    // Frame file upload
    frameUploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const file = frameFile.files[0];
        if (!file) {
            showAlert('frame-status', 'Please select a frame image', 'danger');
            return;
        }
        
        // Upload frame
        const formData = new FormData();
        formData.append('frame_file', file);
        
        const uploadBtn = document.getElementById('upload-frame-btn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Uploading...';
        
        try {
            const response = await fetch('/upload_cctv_frame', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('frame-status', 'Frame uploaded successfully!', 'success');
                frameUploaded = true;
                updateGenerateButton();
            } else {
                showAlert('frame-status', `Error: ${result.message}`, 'danger');
            }
            
        } catch (error) {
            showAlert('frame-status', `Upload failed: ${error.message}`, 'danger');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload me-2"></i>Upload Frame';
        }
    });
    
    // Frame file preview
    frameFile.addEventListener('change', function(e) {
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
    
    // Config file info
    configFile.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (file) {
            try {
                const text = await file.text();
                const json = JSON.parse(text);
                
                const roiCount = json.length;
                const types = {};
                
                json.forEach(roi => {
                    types[roi.type] = (types[roi.type] || 0) + 1;
                });
                
                const typesSummary = Object.entries(types)
                    .map(([type, count]) => `${count} ${type}${count > 1 ? 's' : ''}`)
                    .join(', ');
                
                showAlert('config-status', 
                    `File loaded: ${roiCount} ROI${roiCount > 1 ? 's' : ''} (${typesSummary})`, 
                    'info');
                
            } catch (error) {
                showAlert('config-status', `Invalid JSON file: ${error.message}`, 'warning');
            }
        }
    });
    
    // Generate preview button
    generatePreviewBtn.addEventListener('click', async function() {
        const noPreview = document.getElementById('no-preview');
        const previewLoading = document.getElementById('preview-loading');
        const previewImageContainer = document.getElementById('preview-image-container');
        const previewImage = document.getElementById('preview-image');
        
        // Show loading
        noPreview.style.display = 'none';
        previewImageContainer.style.display = 'none';
        previewLoading.style.display = 'block';
        
        generatePreviewBtn.disabled = true;
        
        try {
            const response = await fetch('/generate_preview');
            const result = await response.json();
            
            if (result.success) {
                // Load preview image
                previewImage.src = result.preview_url + '?t=' + new Date().getTime();
                previewImageContainer.style.display = 'block';
                previewLoading.style.display = 'none';
                
                // Show success message
                showToast('Preview generated successfully!', 'success');
            } else {
                throw new Error(result.message);
            }
            
        } catch (error) {
            previewLoading.style.display = 'none';
            noPreview.style.display = 'block';
            showToast(`Failed to generate preview: ${error.message}`, 'danger');
        } finally {
            generatePreviewBtn.disabled = false;
        }
    });
    
    // Update generate button state
    function updateGenerateButton() {
        if (configUploaded && frameUploaded) {
            generatePreviewBtn.disabled = false;
        }
    }
    
    // Check if both files are already uploaded
    checkExistingFiles();
    
    async function checkExistingFiles() {
        try {
            const response = await fetch('/get_roi_config');
            const result = await response.json();
            
            if (result.success) {
                configUploaded = true;
                updateGenerateButton();
            }
        } catch (error) {
            console.log('No existing configuration');
        }
        
        // Check for existing frame (this would need additional backend support)
        // For now, assume if config exists, frame might exist too
        if (configUploaded) {
            frameUploaded = true;
            updateGenerateButton();
        }
    }
    
    // Helper functions
    function showAlert(containerId, message, type) {
        const container = document.getElementById(containerId);
        container.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                Rs{message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
    
    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center border-0 position-fixed top-0 end-0 m-3 bg-${type}`;
        toast.setAttribute('role', 'alert');
        toast.style.zIndex = '9999';
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body text-white">
                    Rs{message}
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
    
    // Drag and drop for config file
    setupDragAndDrop('config-upload-form', configFile);
    
    // Drag and drop for frame file
    setupDragAndDrop('frame-upload-form', frameFile);
    
    function setupDragAndDrop(formId, inputElement) {
        const form = document.getElementById(formId);
        
        form.addEventListener('dragover', function(e) {
            e.preventDefault();
            form.classList.add('border-primary');
        });
        
        form.addEventListener('dragleave', function(e) {
            e.preventDefault();
            form.classList.remove('border-primary');
        });
        
        form.addEventListener('drop', function(e) {
            e.preventDefault();
            form.classList.remove('border-primary');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                inputElement.files = files;
                inputElement.dispatchEvent(new Event('change'));
            }
        });
    }
});