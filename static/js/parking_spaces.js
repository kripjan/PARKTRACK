// Parking Spaces Management JavaScript for Smart Parking System
document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('parking-canvas');
    const ctx = canvas.getContext('2d');
    const addSpaceForm = document.getElementById('add-space-form');
    const addSpaceBtn = document.getElementById('add-space-btn');
    const clearSelectionBtn = document.getElementById('clear-selection');
    
    // Drawing state
    let isDrawing = false;
    let startX, startY, endX, endY;
    let currentRect = null;
    let existingSpaces = [];
    
    // Canvas setup
    canvas.style.backgroundColor = '#212529';
    
    // Mouse event handlers for drawing rectangles
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseleave', stopDrawing);
    
    // Form submission handler
    addSpaceForm.addEventListener('submit', addParkingSpace);
    
    // Clear selection handler
    clearSelectionBtn.addEventListener('click', clearSelection);
    
    // Highlight space buttons
    document.querySelectorAll('.highlight-space-btn').forEach(btn => {
        btn.addEventListener('click', highlightSpace);
    });
    
    // Delete space buttons
    document.querySelectorAll('.delete-space-btn').forEach(btn => {
        btn.addEventListener('click', deleteSpace);
    });
    
    function getCanvasCoordinates(event) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        return {
            x: (event.clientX - rect.left) * scaleX,
            y: (event.clientY - rect.top) * scaleY
        };
    }
    
    function startDrawing(event) {
        event.preventDefault();
        const coords = getCanvasCoordinates(event);
        
        isDrawing = true;
        startX = coords.x;
        startY = coords.y;
        
        canvas.style.cursor = 'crosshair';
    }
    
    function draw(event) {
        if (!isDrawing) return;
        
        event.preventDefault();
        const coords = getCanvasCoordinates(event);
        
        endX = coords.x;
        endY = coords.y;
        
        // Clear canvas and redraw everything
        redrawCanvas();
        
        // Draw current rectangle being drawn
        drawRectangle(startX, startY, endX, endY, '#ffc107', 2, true);
        
        // Update form fields
        updateFormFields();
    }
    
    function stopDrawing(event) {
        if (!isDrawing) return;
        
        isDrawing = false;
        canvas.style.cursor = 'crosshair';
        
        // Ensure we have a valid rectangle
        if (Math.abs(endX - startX) > 10 && Math.abs(endY - startY) > 10) {
            currentRect = {
                x1: Math.min(startX, endX),
                y1: Math.min(startY, endY),
                x2: Math.max(startX, endX),
                y2: Math.max(startY, endY)
            };
            
            updateFormFields();
            addSpaceBtn.disabled = false;
        }
    }
    
    function redrawCanvas() {
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Set dark background
        ctx.fillStyle = '#212529';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw grid for better visualization
        drawGrid();
        
        // Draw existing spaces
        existingSpaces.forEach(space => {
            const color = space.highlighted ? '#dc3545' : '#6c757d';
            const width = space.highlighted ? 3 : 1;
            drawRectangle(space.x1, space.y1, space.x2, space.y2, color, width, false);
            
            // Draw space label
            drawSpaceLabel(space);
        });
    }
    
    function drawGrid() {
        ctx.strokeStyle = '#495057';
        ctx.lineWidth = 0.5;
        
        // Vertical lines
        for (let x = 0; x <= canvas.width; x += 50) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }
        
        // Horizontal lines
        for (let y = 0; y <= canvas.height; y += 50) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
    }
    
    function drawRectangle(x1, y1, x2, y2, color, lineWidth, dashed) {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        
        if (dashed) {
            ctx.setLineDash([5, 5]);
        } else {
            ctx.setLineDash([]);
        }
        
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        
        // Add semi-transparent fill
        ctx.fillStyle = color + '20';
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
    }
    
    function drawSpaceLabel(space) {
        const centerX = (space.x1 + space.x2) / 2;
        const centerY = (space.y1 + space.y2) / 2;
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // Draw background for text
        const textWidth = ctx.measureText(space.name).width;
        ctx.fillStyle = '#000000aa';
        ctx.fillRect(centerX - textWidth/2 - 4, centerY - 8, textWidth + 8, 16);
        
        // Draw text
        ctx.fillStyle = '#ffffff';
        ctx.fillText(space.name, centerX, centerY);
    }
    
    function updateFormFields() {
        if (currentRect) {
            document.getElementById('x1').value = Math.round(currentRect.x1);
            document.getElementById('y1').value = Math.round(currentRect.y1);
            document.getElementById('x2').value = Math.round(currentRect.x2);
            document.getElementById('y2').value = Math.round(currentRect.y2);
        }
    }
    
    function clearSelection() {
        currentRect = null;
        isDrawing = false;
        
        // Clear form
        document.getElementById('space-name').value = '';
        document.getElementById('x1').value = '';
        document.getElementById('y1').value = '';
        document.getElementById('x2').value = '';
        document.getElementById('y2').value = '';
        
        addSpaceBtn.disabled = true;
        
        // Clear any highlights
        existingSpaces.forEach(space => space.highlighted = false);
        
        redrawCanvas();
    }
    
    function addParkingSpace(event) {
        event.preventDefault();
        
        if (!currentRect) {
            alert('Please draw a parking space on the canvas first');
            return;
        }
        
        const spaceName = document.getElementById('space-name').value.trim();
        if (!spaceName) {
            alert('Please enter a space name');
            return;
        }
        
        const data = {
            name: spaceName,
            x1: currentRect.x1,
            y1: currentRect.y1,
            x2: currentRect.x2,
            y2: currentRect.y2
        };
        
        // Disable form during submission
        addSpaceBtn.disabled = true;
        addSpaceBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Adding...';
        
        fetch('/add_parking_space', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Parking space added successfully!', 'success');
                
                // Add to existing spaces
                existingSpaces.push({
                    name: spaceName,
                    x1: currentRect.x1,
                    y1: currentRect.y1,
                    x2: currentRect.x2,
                    y2: currentRect.y2,
                    highlighted: false
                });
                
                // Clear form and selection
                clearSelection();
                
                // Reload page to update the table
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert('Error adding parking space: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error adding parking space. Please try again.', 'danger');
        })
        .finally(() => {
            addSpaceBtn.disabled = false;
            addSpaceBtn.innerHTML = '<i class="bi bi-plus-lg me-2"></i>Add Parking Space';
        });
    }
    
    function highlightSpace(event) {
        const btn = event.target.closest('.highlight-space-btn');
        const spaceId = btn.dataset.spaceId;
        const x1 = parseInt(btn.dataset.x1);
        const y1 = parseInt(btn.dataset.y1);
        const x2 = parseInt(btn.dataset.x2);
        const y2 = parseInt(btn.dataset.y2);
        
        // Clear previous highlights
        existingSpaces.forEach(space => space.highlighted = false);
        
        // Find and highlight the space
        let found = false;
        existingSpaces.forEach(space => {
            if (space.x1 === x1 && space.y1 === y1 && space.x2 === x2 && space.y2 === y2) {
                space.highlighted = true;
                found = true;
            }
        });
        
        // If not found in existing spaces, add it temporarily
        if (!found) {
            existingSpaces.push({
                name: btn.closest('tr').querySelector('td:first-child strong').textContent,
                x1: x1,
                y1: y1,
                x2: x2,
                y2: y2,
                highlighted: true
            });
        }
        
        redrawCanvas();
        
        // Scroll canvas into view
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    function deleteSpace(event) {
        const btn = event.target.closest('.delete-space-btn');
        const spaceId = btn.dataset.spaceId;
        const spaceName = btn.dataset.spaceName;
        
        // Show confirmation modal
        const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
        document.getElementById('delete-space-name').textContent = spaceName;
        
        // Set up confirm button
        const confirmBtn = document.getElementById('confirm-delete-btn');
        confirmBtn.onclick = function() {
            performDelete(spaceId, modal);
        };
        
        modal.show();
    }
    
    function performDelete(spaceId, modal) {
        const confirmBtn = document.getElementById('confirm-delete-btn');
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="bi bi-hourglass me-2"></i>Deleting...';
        
        fetch(`/delete_parking_space/${spaceId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            modal.hide();
            
            if (data.success) {
                showAlert('Parking space deleted successfully!', 'success');
                
                // Remove from DOM
                const row = document.getElementById(`space-row-${spaceId}`);
                if (row) {
                    row.remove();
                }
                
                // Remove from existing spaces
                existingSpaces = existingSpaces.filter(space => 
                    space.id !== parseInt(spaceId)
                );
                
                redrawCanvas();
            } else {
                showAlert('Error deleting parking space: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error deleting parking space. Please try again.', 'danger');
            modal.hide();
        })
        .finally(() => {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="bi bi-trash me-2"></i>Delete Space';
        });
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
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    // Initialize canvas
    redrawCanvas();
    
    // Load existing spaces from the table
    document.querySelectorAll('.highlight-space-btn').forEach(btn => {
        const spaceName = btn.closest('tr').querySelector('td:first-child strong').textContent;
        existingSpaces.push({
            name: spaceName,
            x1: parseInt(btn.dataset.x1),
            y1: parseInt(btn.dataset.y1),
            x2: parseInt(btn.dataset.x2),
            y2: parseInt(btn.dataset.y2),
            highlighted: false
        });
    });
    
    // Redraw with existing spaces
    redrawCanvas();
});
