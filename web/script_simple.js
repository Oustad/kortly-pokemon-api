// Pokemon Card Scanner - Frontend JavaScript

let selectedFile = null;
let cameraStream = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkCameraSupport();
});

function setupEventListeners() {
    // File input
    const imageInput = document.getElementById('imageInput');
    imageInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('click', (e) => {
        // Don't trigger file input if camera button was clicked
        if (!e.target.closest('.camera-btn')) {
            imageInput.click();
        }
    });
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
}

// Check if device supports camera
function checkCameraSupport() {
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    
    if (isMobile && hasGetUserMedia) {
        const cameraBtn = document.getElementById('cameraBtn');
        if (cameraBtn) {
            cameraBtn.style.display = 'inline-block';
        }
    }
}

// File handling
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        processFile(file);
    }
}

function handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add('drag-over');
}

function handleDragLeave(event) {
    event.currentTarget.classList.remove('drag-over');
}

function handleDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    
    const file = event.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
        processFile(file);
    }
}

function processFile(file) {
    selectedFile = file;
    
    // Check if it's a HEIC file
    const isHeic = file.name.toLowerCase().endsWith('.heic') || 
                   file.name.toLowerCase().endsWith('.heif') ||
                   file.type === 'image/heic' ||
                   file.type === 'image/heif';
    
    if (isHeic) {
        // For HEIC files, show a placeholder since browsers can't preview them
        showHeicPreview(file);
    } else {
        // For other image formats, show normal preview
        showImagePreview(file);
    }
}

function showImagePreview(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const imagePreview = document.getElementById('imagePreview');
        imagePreview.src = e.target.result;
        imagePreview.style.display = 'block';
        
        // Hide HEIC placeholder if it was shown
        const heicPlaceholder = document.getElementById('heicPlaceholder');
        if (heicPlaceholder) {
            heicPlaceholder.style.display = 'none';
        }
        
        document.getElementById('fileName').textContent = file.name;
        
        // Show preview section
        document.getElementById('previewSection').style.display = 'block';
        
        // Hide upload area
        document.getElementById('uploadArea').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

function showHeicPreview(file) {
    // Hide the regular image preview
    const imagePreview = document.getElementById('imagePreview');
    imagePreview.style.display = 'none';
    
    // Create or show HEIC placeholder
    let heicPlaceholder = document.getElementById('heicPlaceholder');
    if (!heicPlaceholder) {
        heicPlaceholder = document.createElement('div');
        heicPlaceholder.id = 'heicPlaceholder';
        heicPlaceholder.className = 'heic-placeholder';
        heicPlaceholder.innerHTML = `
            <div class="heic-icon">📷</div>
            <div class="heic-text">
                <h4>HEIC Image Selected</h4>
                <p>iPhone photos can't be previewed in browsers, but they work perfectly for scanning!</p>
                <p class="heic-tip">💡 Your HEIC image will be automatically converted during processing</p>
            </div>
        `;
        
        // Insert after the h3 in preview-card
        const previewCard = document.querySelector('.preview-card');
        const h3 = previewCard.querySelector('h3');
        h3.insertAdjacentElement('afterend', heicPlaceholder);
    }
    
    heicPlaceholder.style.display = 'flex';
    
    document.getElementById('fileName').textContent = file.name;
    
    // Show preview section
    document.getElementById('previewSection').style.display = 'block';
    
    // Hide upload area
    document.getElementById('uploadArea').style.display = 'none';
}

// Scan card
async function scanCard() {
    if (!selectedFile) return;
    
    // Hide sections
    hideAllSections();
    document.getElementById('loadingSection').style.display = 'block';
    
    try {
        let processedFile = selectedFile;
        let resizeInfo = null;
        
        // Check if we should resize (skip for HEIC as they need server processing)
        const isHeic = selectedFile.name.toLowerCase().endsWith('.heic') || 
                       selectedFile.name.toLowerCase().endsWith('.heif') ||
                       selectedFile.type === 'image/heic' ||
                       selectedFile.type === 'image/heif';
        
        if (!isHeic && selectedFile.size > 100 * 1024) { // Only resize if > 100KB
            updateLoadingStatus('Optimizing image for faster upload...');
            resizeInfo = await resizeImage(selectedFile);
            processedFile = resizeInfo.file;
            
            // Show compression info
            if (resizeInfo.compressionRatio > 0) {
                console.log(`📦 Image optimized: ${resizeInfo.compressionRatio}% size reduction`);
                console.log(`📏 Resized from ${resizeInfo.originalDimensions.width}x${resizeInfo.originalDimensions.height} to ${resizeInfo.dimensions.width}x${resizeInfo.dimensions.height}`);
            }
        }
        
        // Update loading status
        updateLoadingStatus('Converting image to base64...');
        const base64 = await fileToBase64(processedFile);
        
        // Prepare request with optimization info
        const requestData = {
            image: base64.split(',')[1], // Remove data URL prefix
            filename: selectedFile.name,
            options: {
                optimize_for_speed: false,  // Use standard tier instead
                include_cost_tracking: true,  // Default to tracking costs
                retry_on_truncation: true,
                prefer_speed: false,
                max_processing_time: null  // No time limit for better results
            }
        };
        
        // Update loading status
        updateLoadingStatus('Analyzing card...');
        
        // Call API
        const response = await fetch('/api/v1/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            // Handle structured error responses
            if (typeof data.detail === 'string') {
                try {
                    const errorDetail = JSON.parse(data.detail);
                    showEnhancedError(errorDetail);
                    return;
                } catch {
                    // If parsing fails, use the string as-is
                    throw new Error(data.detail || `API Error: ${response.status}`);
                }
            } else {
                throw new Error(data.detail || `API Error: ${response.status}`);
            }
        }
        
        // For simplified responses, success is implicit if we got a 200 status
        if (data.name || data.success) {
            // Add client-side optimization info to results
            if (resizeInfo) {
                data.clientOptimization = resizeInfo;
            }
            displayResults(data);
        } else {
            throw new Error(data.error || 'Scan failed');
        }
        
    } catch (error) {
        console.error('Scan error:', error);
        showError(error.message);
    }
}

// Display results
function displayResults(data) {
    // Store the response data globally for JSON view
    window.lastScanResult = data;
    
    hideAllSections();
    document.getElementById('resultsSection').style.display = 'block';
    
    // Check if we have a simplified response
    if (data.name && !data.card_identification) {
        // Simplified response
        displaySimplifiedResults(data);
    } else {
        // Detailed response (legacy)
        displayDetailedResults(data);
    }
}

function displaySimplifiedResults(data) {
    // Create a single card display
    const resultsSection = document.getElementById('resultsSection');
    
    // Build the simplified card view
    let html = `
        <div class="result-card main-card">
            <div class="card-header">
                <h2>${data.name || 'Unknown Card'}</h2>
                <button class="btn-json" onclick="toggleJsonView()">View JSON</button>
            </div>
            <div class="card-content" id="cardContent">
    `;
    
    // Card image
    if (data.image) {
        html += `
            <div class="card-image-section">
                <img src="${data.image}" alt="${data.name}" class="card-image-large">
            </div>
        `;
    }
    
    // Card details
    html += '<div class="card-details">';
    
    // Basic info section
    html += '<div class="detail-section">';
    if (data.set_name) html += `<div class="detail-item"><strong>Set:</strong> ${data.set_name}</div>`;
    if (data.number) html += `<div class="detail-item"><strong>Number:</strong> ${data.number}</div>`;
    if (data.hp) html += `<div class="detail-item"><strong>HP:</strong> ${data.hp}</div>`;
    if (data.types && data.types.length > 0) html += `<div class="detail-item"><strong>Types:</strong> ${data.types.join(', ')}</div>`;
    if (data.rarity) html += `<div class="detail-item"><strong>Rarity:</strong> ${data.rarity}</div>`;
    html += '</div>';
    
    // Market prices
    if (data.market_prices) {
        html += '<div class="price-section">';
        html += '<h3>Market Prices</h3>';
        html += '<div class="price-grid">';
        if (data.market_prices.low !== undefined) html += `<div class="price-item"><span class="price-label">Low</span><span class="price-value">$${data.market_prices.low.toFixed(2)}</span></div>`;
        if (data.market_prices.mid !== undefined) html += `<div class="price-item"><span class="price-label">Mid</span><span class="price-value">$${data.market_prices.mid.toFixed(2)}</span></div>`;
        if (data.market_prices.high !== undefined) html += `<div class="price-item"><span class="price-label">High</span><span class="price-value">$${data.market_prices.high.toFixed(2)}</span></div>`;
        if (data.market_prices.market !== undefined) html += `<div class="price-item featured"><span class="price-label">Market</span><span class="price-value">$${data.market_prices.market.toFixed(2)}</span></div>`;
        html += '</div>';
        html += '</div>';
    }
    
    // Quality score
    html += `
        <div class="quality-section">
            <div class="quality-score" style="color: ${getQualityColor(data.quality_score)}">
                Quality Score: ${data.quality_score.toFixed(1)}
            </div>
        </div>
    `;
    
    html += '</div>'; // card-details
    html += '</div>'; // card-content
    
    // JSON view (hidden by default)
    html += `
            <div class="json-view" id="jsonView" style="display: none;">
                <pre>${JSON.stringify(data, null, 2)}</pre>
            </div>
        </div>
        <div class="actions-section">
            <button class="btn-primary" onclick="resetUpload()">
                Scan Another Card
            </button>
        </div>
    `;
    
    resultsSection.innerHTML = html;
}

function toggleJsonView() {
    const jsonView = document.getElementById('jsonView');
    const cardContent = document.getElementById('cardContent');
    const button = document.querySelector('.btn-json');
    
    if (jsonView.style.display === 'none') {
        jsonView.style.display = 'block';
        cardContent.style.display = 'none';
        button.textContent = 'View Card';
    } else {
        jsonView.style.display = 'none';
        cardContent.style.display = 'block';
        button.textContent = 'View JSON';
    }
}

function displayDetailedResults(data) {
    // Display summary
    displaySummary(data);
    
    // Display processed images for comparison  
    displayProcessedImages(data.processing_info || data.processing);
    
    // Display quality feedback (new!)
    displayQualityFeedback(data.processing);
    
    // Display Gemini identification
    displayIdentification(data.card_identification);
    
    // Display TCG matches
    displayMatches(data.tcg_matches, data.best_match);
}

function displayUploadedImage() {
    // Find or create the uploaded image section
    let uploadedSection = document.getElementById('uploadedImageCard');
    
    if (!uploadedSection) {
        uploadedSection = document.createElement('div');
        uploadedSection.id = 'uploadedImageCard';
        uploadedSection.className = 'result-card';
        uploadedSection.innerHTML = '<h3>📸 Your Upload</h3><div id="uploadedImageContent"></div>';
        
        // Insert after summary card
        const summaryCard = document.querySelector('.summary-card');
        summaryCard.insertAdjacentElement('afterend', uploadedSection);
    }
    
    const content = document.getElementById('uploadedImageContent');
    
    if (selectedFile) {
        const isHeic = selectedFile.name.toLowerCase().endsWith('.heic') || 
                       selectedFile.name.toLowerCase().endsWith('.heif');
        
        if (isHeic) {
            // Show HEIC placeholder
            content.innerHTML = `
                <div class="uploaded-image-container">
                    <div class="heic-placeholder" style="display: flex; flex-direction: column; align-items: center; padding: 2rem; background: var(--bg-secondary); border-radius: 8px; text-align: center;">
                        <div style="font-size: 4rem; margin-bottom: 1rem;">📷</div>
                        <div style="font-weight: bold; margin-bottom: 0.5rem;">HEIC Image: ${selectedFile.name}</div>
                        <div style="color: var(--text-secondary); font-size: 0.9rem;">iPhone photos can't be previewed in browsers</div>
                        <div style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.5rem;">Size: ${formatBytes(selectedFile.size)}</div>
                    </div>
                </div>
            `;
        } else {
            // Show actual image preview from the preview section
            const previewImg = document.getElementById('imagePreview');
            const imgSrc = previewImg ? previewImg.src : '';
            
            content.innerHTML = `
                <div class="uploaded-image-container">
                    <img src="${imgSrc}" alt="Uploaded image" class="uploaded-image" style="max-width: 300px; max-height: 400px; object-fit: contain; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="margin-top: 1rem; text-align: center;">
                        <div style="font-weight: bold;">${selectedFile.name}</div>
                        <div style="color: var(--text-secondary); font-size: 0.9rem;">Size: ${formatBytes(selectedFile.size)}</div>
                    </div>
                </div>
            `;
        }
    } else {
        content.innerHTML = '<p style="color: var(--text-secondary);">No uploaded image available.</p>';
    }
}

function displayProcessedImages(processingInfo) {
    // Find or create the processed images section
    let processedSection = document.getElementById('processedImagesCard');
    
    if (!processedSection) {
        processedSection = document.createElement('div');
        processedSection.id = 'processedImagesCard';
        processedSection.className = 'result-card';
        processedSection.innerHTML = '<h3>📸 Image Processing</h3><div id="processedImagesContent"></div>';
        
        // Insert after summary card like in the old view
        const summaryCard = document.querySelector('.summary-card');
        summaryCard.insertAdjacentElement('afterend', processedSection);
    }
    
    const content = document.getElementById('processedImagesContent');
    content.innerHTML = '';
    
    // Try to fetch the latest processed images from the API
    fetch('/api/v1/processed-images/list')
        .then(response => response.json())
        .then(data => {
            if (data.images && data.images.length > 0) {
                // Get the most recent images (first 2 of each type)
                const recentImages = data.images.slice(0, 6);
                // Check filename instead of stage since stage parsing is broken
                const originalImage = recentImages.find(img => img.filename.includes('_original_'));
                const processedImage = recentImages.find(img => img.filename.includes('_processed_'));
                
                if (originalImage && processedImage) {
                    // Classic side-by-side layout from old view
                    content.innerHTML = `
                        <div class="image-comparison" style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 2rem; align-items: center;">
                            <div class="comparison-item" style="text-align: center;">
                                <h4 style="margin-bottom: 1rem;">Original Image</h4>
                                <div style="background: #f8f9fa; padding: 2rem; border-radius: 8px; margin-bottom: 1rem;">
                                    <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">Original</div>
                                    <div style="color: #666; font-size: 0.9rem;">Format: ${selectedFile?.name?.toLowerCase().endsWith('.heic') ? 'HEIF' : 'Unknown'}</div>
                                    <div style="color: #666; font-size: 0.9rem;">Size: ${selectedFile ? formatBytes(selectedFile.size) : 'Unknown'}</div>
                                </div>
                            </div>
                            
                            <div class="comparison-arrow" style="font-size: 2rem; color: #007bff;">➡️</div>
                            
                            <div class="comparison-item" style="text-align: center;">
                                <h4 style="margin-bottom: 1rem;">Processed Image</h4>
                                <img src="${processedImage.url}" 
                                     alt="Processed" 
                                     class="comparison-image" 
                                     loading="lazy"
                                     style="max-width: 100%; max-height: 300px; object-fit: contain; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem;">
                                <div style="color: #666; font-size: 0.9rem;">Format: JPEG (optimized)</div>
                                <div style="color: #666; font-size: 0.9rem;">Size: ${formatBytes(processedImage.size)}</div>
                                <div style="color: #28a745; font-size: 0.9rem; margin-top: 0.5rem;">✅ Resized for optimal processing</div>
                            </div>
                        </div>
                    `;
                } else if (originalImage || processedImage) {
                    // Show what we have
                    const image = originalImage || processedImage;
                    content.innerHTML = `
                        <div style="text-align: center;">
                            <h4>${image.filename.includes('_original_') ? 'Original Image' : 'Processed Image'}</h4>
                            <img src="${image.url}" 
                                 alt="${image.stage}" 
                                 class="comparison-image" 
                                 loading="lazy"
                                 style="max-width: 300px; max-height: 300px; object-fit: contain; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem;">
                            <div style="color: #666; font-size: 0.9rem;">Size: ${formatBytes(image.size)}</div>
                            <div style="color: #666; font-size: 0.9rem;">${new Date(image.modified * 1000).toLocaleTimeString()}</div>
                        </div>
                    `;
                } else {
                    content.innerHTML = '<p style="color: var(--text-secondary);">No processed images found on server.</p>';
                }
            } else {
                content.innerHTML = '<p style="color: var(--text-secondary);">No processed images available.</p>';
            }
        })
        .catch(error => {
            console.warn('Could not fetch processed images:', error);
            content.innerHTML = '<p style="color: var(--text-secondary);">Image processing information not available.</p>';
        });
}

function displayQualityFeedback(processing) {
    if (!processing?.quality_feedback) return;
    
    // Find or create the quality feedback section
    let qualitySection = document.getElementById('qualityFeedbackCard');
    
    if (!qualitySection) {
        qualitySection = document.createElement('div');
        qualitySection.id = 'qualityFeedbackCard';
        qualitySection.className = 'result-card';
        qualitySection.innerHTML = '<h3>🎯 Image Quality Assessment</h3><div id="qualityFeedbackContent"></div>';
        
        // Insert after processed images section
        const processedSection = document.getElementById('processedImagesCard');
        if (processedSection) {
            processedSection.insertAdjacentElement('afterend', qualitySection);
        } else {
            // Fallback: insert after summary
            const summaryCard = document.querySelector('.summary-card');
            summaryCard.insertAdjacentElement('afterend', qualitySection);
        }
    }
    
    const content = document.getElementById('qualityFeedbackContent');
    const feedback = processing.quality_feedback;
    
    // Overall quality rating
    const qualityScore = Math.round(processing.quality_score || 0);
    const qualityClass = getQualityClass(processing.quality_score);
    
    let feedbackHtml = `
        <div class="quality-overview">
            <div class="quality-score ${qualityClass}">
                <div class="score-value">${qualityScore}/100</div>
                <div class="score-label">Overall Quality: ${feedback.overall}</div>
            </div>
        </div>
    `;
    
    // Processing details
    feedbackHtml += `
        <div class="processing-details">
            <div class="detail-item">
                <span class="detail-label">Processing Tier:</span>
                <span class="detail-value tier-${processing.processing_tier}">${processing.processing_tier?.toUpperCase()}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Model Used:</span>
                <span class="detail-value">${processing.model_used || 'N/A'}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Image Enhanced:</span>
                <span class="detail-value">${processing.image_enhanced ? 'Yes' : 'No'}</span>
            </div>
        </div>
    `;
    
    // Issues and suggestions
    if (feedback.issues?.length > 0) {
        feedbackHtml += '<div class="feedback-section"><h4>⚠️ Quality Issues</h4><ul class="feedback-list issues">';
        feedback.issues.forEach(issue => {
            feedbackHtml += `<li>${issue}</li>`;
        });
        feedbackHtml += '</ul></div>';
    }
    
    if (feedback.suggestions?.length > 0) {
        feedbackHtml += '<div class="feedback-section"><h4>💡 Suggestions</h4><ul class="feedback-list suggestions">';
        feedback.suggestions.forEach(suggestion => {
            feedbackHtml += `<li>${suggestion}</li>`;
        });
        feedbackHtml += '</ul></div>';
    }
    
    // Processing log (for debugging)
    if (processing.processing_log?.length > 0) {
        feedbackHtml += `
            <details class="processing-log">
                <summary>🔧 Processing Log</summary>
                <div class="log-content">
                    ${processing.processing_log.map(entry => `<div class="log-entry">${entry}</div>`).join('')}
                </div>
            </details>
        `;
    }
    
    content.innerHTML = feedbackHtml;
}

function getQualityClass(score) {
    if (score >= 80) return 'excellent';
    if (score >= 60) return 'good';
    if (score >= 40) return 'fair';
    return 'poor';
}

function displaySummary(data) {
    const summaryGrid = document.getElementById('summaryGrid');
    summaryGrid.innerHTML = '';
    
    // Quality score (new!)
    if (data.processing?.quality_score !== undefined) {
        const qualityItem = createSummaryItem(
            `${Math.round(data.processing.quality_score)}`,
            'Quality Score',
            getQualityColor(data.processing.quality_score)
        );
        summaryGrid.appendChild(qualityItem);
    }
    
    // Processing tier (new!)
    if (data.processing?.processing_tier) {
        const tierItem = createSummaryItem(
            data.processing.processing_tier.charAt(0).toUpperCase() + data.processing.processing_tier.slice(1),
            'Processing Tier',
            getTierColor(data.processing.processing_tier)
        );
        summaryGrid.appendChild(tierItem);
    }
    
    // Processing time
    const processingTime = data.processing?.actual_time_ms || data.processing_info?.total_time_ms || 0;
    const timeItem = createSummaryItem(
        `${Math.round(processingTime)}ms`,
        'Processing Time',
        getTimeColor(processingTime, data.processing?.target_time_ms)
    );
    summaryGrid.appendChild(timeItem);
    
    // Performance rating (new!)
    if (data.processing?.performance_rating) {
        const perfItem = createSummaryItem(
            data.processing.performance_rating.charAt(0).toUpperCase() + data.processing.performance_rating.slice(1),
            'Performance',
            getPerformanceColor(data.processing.performance_rating)
        );
        summaryGrid.appendChild(perfItem);
    }
    
    // Cost
    if (data.cost_info) {
        const costItem = createSummaryItem(
            `$${data.cost_info.total_cost.toFixed(6)}`,
            'Scan Cost'
        );
        summaryGrid.appendChild(costItem);
    }
    
    // Matches found
    const matchCount = data.tcg_matches ? data.tcg_matches.length : 0;
    const matchItem = createSummaryItem(
        matchCount.toString(),
        'Cards Found'
    );
    summaryGrid.appendChild(matchItem);
    
    // Confidence
    if (data.card_identification?.confidence) {
        const confidenceItem = createSummaryItem(
            `${Math.round(data.card_identification.confidence * 100)}%`,
            'Confidence'
        );
        summaryGrid.appendChild(confidenceItem);
    }
    
    // Token usage (new!)
    if (data.card_identification?.tokens_used) {
        const tokens = data.card_identification.tokens_used;
        const totalTokens = (tokens.prompt || 0) + (tokens.response || 0);
        const tokenItem = createSummaryItem(
            totalTokens.toString(),
            'Tokens Used',
            '#8b5cf6' // Purple for token info
        );
        summaryGrid.appendChild(tokenItem);
    }
    
    // Client optimization info
    if (data.clientOptimization && data.clientOptimization.compressionRatio > 0) {
        const compressionItem = createSummaryItem(
            `${data.clientOptimization.compressionRatio}%`,
            'Size Reduced',
            '#10b981' // Green for good optimization
        );
        summaryGrid.appendChild(compressionItem);
    }
}

function createSummaryItem(value, label, color = null) {
    const div = document.createElement('div');
    div.className = 'summary-item';
    
    const valueStyle = color ? `style="color: ${color}; font-weight: bold;"` : '';
    
    div.innerHTML = `
        <div class="summary-value" ${valueStyle}>${value}</div>
        <div class="summary-label">${label}</div>
    `;
    return div;
}

// Color helper functions for quality indicators
function getQualityColor(score) {
    if (score >= 80) return '#10b981'; // Green - excellent
    if (score >= 60) return '#f59e0b'; // Yellow - good  
    if (score >= 40) return '#f97316'; // Orange - fair
    return '#ef4444'; // Red - poor
}

function getTierColor(tier) {
    switch (tier) {
        case 'fast': return '#10b981'; // Green - fast
        case 'standard': return '#3b82f6'; // Blue - standard
        case 'enhanced': return '#8b5cf6'; // Purple - enhanced
        default: return '#6b7280'; // Gray - unknown
    }
}

function getTimeColor(actualTime, targetTime) {
    if (!targetTime) return null;
    const ratio = actualTime / targetTime;
    if (ratio <= 0.8) return '#10b981'; // Green - excellent
    if (ratio <= 1.0) return '#f59e0b'; // Yellow - on target
    if (ratio <= 1.5) return '#f97316'; // Orange - acceptable
    return '#ef4444'; // Red - slow
}

function getPerformanceColor(rating) {
    switch (rating) {
        case 'excellent': return '#10b981'; // Green
        case 'good': return '#f59e0b'; // Yellow
        case 'acceptable': return '#f97316'; // Orange
        case 'slow': return '#ef4444'; // Red
        default: return '#6b7280'; // Gray
    }
}

function displayIdentification(cardId) {
    if (!cardId) return;
    
    const geminiResult = document.getElementById('geminiResult');
    const geminiData = cardId.structured_data;
    
    let identificationHtml = '';
    
    // Card type info with appropriate styling
    if (cardId.card_type_info) {
        const typeInfo = cardId.card_type_info;
        const cardTypeClass = getCardTypeClass(typeInfo.card_type);
        
        identificationHtml += `
            <div class="card-type-section">
                <div class="card-type ${cardTypeClass}">
                    <span class="type-icon">${getCardTypeIcon(typeInfo.card_type)}</span>
                    <span class="type-label">${formatCardType(typeInfo.card_type)}</span>
                </div>
            </div>
        `;
    }
    
    // Basic identification
    if (geminiData) {
        identificationHtml += '<div class="identification-grid">';
        
        if (geminiData.name) {
            identificationHtml += `<div class="id-item"><strong>Name:</strong> ${geminiData.name}</div>`;
        }
        if (geminiData.set_name) {
            identificationHtml += `<div class="id-item"><strong>Set:</strong> ${geminiData.set_name}</div>`;
        }
        if (geminiData.number) {
            identificationHtml += `<div class="id-item"><strong>Number:</strong> ${geminiData.number}</div>`;
        }
        if (geminiData.hp) {
            identificationHtml += `<div class="id-item"><strong>HP:</strong> ${geminiData.hp}</div>`;
        }
        if (geminiData.types && geminiData.types.length > 0) {
            identificationHtml += `<div class="id-item"><strong>Types:</strong> ${geminiData.types.join(', ')}</div>`;
        }
        if (geminiData.rarity) {
            identificationHtml += `<div class="id-item"><strong>Rarity:</strong> ${geminiData.rarity}</div>`;
        }
        
        identificationHtml += '</div>';
    }
    
    // Language info
    if (cardId.language_info) {
        const langInfo = cardId.language_info;
        identificationHtml += '<div class="language-section">';
        identificationHtml += `<h4>🌍 Language Information</h4>`;
        identificationHtml += `<div class="language-details">`;
        identificationHtml += `<div><strong>Detected Language:</strong> ${langInfo.detected_language}</div>`;
        if (langInfo.original_name) {
            identificationHtml += `<div><strong>Original Name:</strong> ${langInfo.original_name}</div>`;
        }
        if (langInfo.is_translation && langInfo.translated_name) {
            identificationHtml += `<div><strong>English Translation:</strong> ${langInfo.translated_name}</div>`;
        }
        identificationHtml += '</div></div>';
    }
    
    // Confidence and token info
    const metaInfo = [];
    if (cardId.confidence) {
        metaInfo.push(`Confidence: ${Math.round(cardId.confidence * 100)}%`);
    }
    if (cardId.tokens_used) {
        const totalTokens = (cardId.tokens_used.prompt || 0) + (cardId.tokens_used.response || 0);
        metaInfo.push(`Tokens: ${totalTokens}`);
    }
    
    if (metaInfo.length > 0) {
        identificationHtml += `<div class="meta-info">${metaInfo.join(' • ')}</div>`;
    }
    
    // Raw response toggle
    identificationHtml += `
        <details class="raw-response">
            <summary>🔍 View Raw AI Response</summary>
            <pre class="raw-text">${cardId.raw_response || 'No raw response available'}</pre>
        </details>
    `;
    
    geminiResult.innerHTML = identificationHtml;
}

function getCardTypeClass(cardType) {
    switch (cardType) {
        case 'pokemon_front': return 'type-pokemon-front';
        case 'pokemon_back': return 'type-pokemon-back';
        case 'non_pokemon': return 'type-non-pokemon';
        default: return 'type-unknown';
    }
}

function getCardTypeIcon(cardType) {
    switch (cardType) {
        case 'pokemon_front': return '🎴';
        case 'pokemon_back': return '🔄';
        case 'non_pokemon': return '❓';
        default: return '❔';
    }
}

function formatCardType(cardType) {
    switch (cardType) {
        case 'pokemon_front': return 'Pokemon Card (Front)';
        case 'pokemon_back': return 'Pokemon Card (Back)';
        case 'non_pokemon': return 'Non-Pokemon Card';
        default: return 'Unknown Card Type';
    }
}

function displayMatches(tcgMatches, bestMatch) {
    const matchesDiv = document.getElementById('tcgMatches');
    
    if (!tcgMatches || tcgMatches.length === 0) {
        matchesDiv.innerHTML = '<p>No matching cards found in database.</p>';
        return;
    }
    
    let matchesHtml = '';
    
    // Show best match prominently if available
    if (bestMatch) {
        matchesHtml += `
            <div class="best-match-section">
                <h4>🏆 Best Match</h4>
                ${createCardDisplay(bestMatch, true)}
            </div>
        `;
    }
    
    // Show all matches
    matchesHtml += '<div class="all-matches-section">';
    matchesHtml += `<h4>📋 All Matches (${tcgMatches.length})</h4>`;
    
    tcgMatches.forEach((card, index) => {
        const isBest = bestMatch && card.id === bestMatch.id;
        matchesHtml += createCardDisplay(card, isBest, index + 1);
    });
    
    matchesHtml += '</div>';
    
    matchesDiv.innerHTML = matchesHtml;
}

function createCardDisplay(card, isBest = false, rank = null) {
    const cardClass = isBest ? 'card-match best-match' : 'card-match';
    const rankLabel = rank ? `#${rank}` : '';
    const bestLabel = isBest ? '🏆 Best Match' : '';
    
    let cardHtml = `
        <div class="${cardClass}">
            <div class="card-header">
                <div class="card-title">
                    <h5>${card.name}</h5>
                    <span class="match-labels">${bestLabel} ${rankLabel}</span>
                </div>
            </div>
            <div class="card-body">
    `;
    
    // Card image
    if (card.images && (card.images.large || card.images.small)) {
        const imageUrl = card.images.large || card.images.small;
        cardHtml += `
            <div class="card-image-container">
                <img src="${imageUrl}" alt="${card.name}" class="card-image" loading="lazy">
            </div>
        `;
    }
    
    // Card details
    cardHtml += '<div class="card-details">';
    
    if (card.set_name) cardHtml += `<div class="detail-row"><strong>Set:</strong> ${card.set_name}</div>`;
    if (card.number) cardHtml += `<div class="detail-row"><strong>Number:</strong> ${card.number}</div>`;
    if (card.hp) cardHtml += `<div class="detail-row"><strong>HP:</strong> ${card.hp}</div>`;
    if (card.types && card.types.length > 0) cardHtml += `<div class="detail-row"><strong>Types:</strong> ${card.types.join(', ')}</div>`;
    if (card.rarity) cardHtml += `<div class="detail-row"><strong>Rarity:</strong> ${card.rarity}</div>`;
    
    // Market prices
    if (card.market_prices) {
        cardHtml += '<div class="price-section">';
        cardHtml += '<strong>Market Prices:</strong>';
        cardHtml += '<div class="price-grid">';
        
        // Handle different price structures from TCG API
        let priceData = card.market_prices;
        
        // Check for variants (normal, holofoil, etc.)
        if (priceData.normal || priceData.holofoil || priceData.reverseHolofoil) {
            // Use the first available variant
            priceData = priceData.normal || priceData.holofoil || priceData.reverseHolofoil || priceData;
        }
        
        if (priceData.low !== undefined) cardHtml += `<span class="price-item">Low: $${priceData.low}</span>`;
        if (priceData.mid !== undefined) cardHtml += `<span class="price-item">Mid: $${priceData.mid}</span>`;
        if (priceData.high !== undefined) cardHtml += `<span class="price-item">High: $${priceData.high}</span>`;
        if (priceData.market !== undefined) cardHtml += `<span class="price-item market-price">Market: $${priceData.market}</span>`;
        
        cardHtml += '</div></div>';
    }
    
    cardHtml += '</div>'; // card-details
    cardHtml += '</div>'; // card-body
    cardHtml += '</div>'; // card-match
    
    return cardHtml;
}

// Error handling
function showError(message) {
    hideAllSections();
    document.getElementById('errorSection').style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}

function showEnhancedError(errorDetail) {
    hideAllSections();
    document.getElementById('errorSection').style.display = 'block';
    
    // Store the error data globally for JSON view
    window.lastErrorResult = errorDetail;
    
    // Build enhanced error display
    let errorHtml = `
        <div class="error-header">
            <h3>❌ ${getErrorIcon(errorDetail.error_type)} Error</h3>
            <button class="btn-json-error" onclick="toggleErrorJsonView()">View Details</button>
        </div>
        <div class="error-content" id="errorContent">
    `;
    
    // Main error message
    let mainMessage = errorDetail.message || errorDetail.error || 'An unknown error occurred';
    errorHtml += `<div class="error-main-message">${mainMessage}</div>`;
    
    // Add specific details for different error types
    if (errorDetail.error_type === 'card_not_found' && errorDetail.details) {
        errorHtml += `
            <div class="error-details">
                <h4>📊 Matching Details</h4>
                <div class="score-info">
                    <div class="score-item">
                        <span class="score-label">Best Match Score:</span>
                        <span class="score-value">${errorDetail.details.highest_score}</span>
                    </div>
                    <div class="score-item">
                        <span class="score-label">Required Score:</span>
                        <span class="score-value">${errorDetail.details.required_score}</span>
                    </div>
                    <div class="score-item">
                        <span class="score-label">Gap:</span>
                        <span class="score-value">${errorDetail.details.score_gap} points short</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Quality feedback for image quality errors
    if (errorDetail.quality_feedback) {
        const feedback = errorDetail.quality_feedback;
        errorHtml += `
            <div class="error-quality-feedback">
                <h4>🎯 Image Quality Assessment</h4>
                <div class="quality-status">Overall Quality: <strong>${feedback.overall}</strong></div>
        `;
        
        if (feedback.issues && feedback.issues.length > 0) {
            errorHtml += `
                <div class="quality-issues">
                    <h5>⚠️ Issues Found:</h5>
                    <ul>
                        ${feedback.issues.map(issue => `<li>${issue}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        if (feedback.suggestions && feedback.suggestions.length > 0) {
            errorHtml += `
                <div class="quality-suggestions">
                    <h5>💡 Suggestions:</h5>
                    <ul>
                        ${feedback.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        errorHtml += `</div>`;
    }
    
    // General suggestions
    if (errorDetail.suggestions && errorDetail.suggestions.length > 0) {
        errorHtml += `
            <div class="error-suggestions">
                <h4>💡 How to Fix This</h4>
                <ul>
                    ${errorDetail.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    errorHtml += `
        </div>
        <div class="error-json-view" id="errorJsonView" style="display: none;">
            <h4>🔍 Raw Error Data</h4>
            <pre>${JSON.stringify(errorDetail, null, 2)}</pre>
        </div>
        <div class="error-actions">
            <button class="btn-secondary" onclick="resetUpload()">
                Try Another Image
            </button>
        </div>
    `;
    
    document.getElementById('errorMessage').innerHTML = errorHtml;
}

function getErrorIcon(errorType) {
    switch (errorType) {
        case 'card_not_found': return '🔍';
        case 'not_pokemon_card': return '❓';
        case 'pokemon_card_back': return '🔄';
        case 'image_quality': return '🎯';
        default: return '⚠️';
    }
}

function toggleErrorJsonView() {
    const jsonView = document.getElementById('errorJsonView');
    const errorContent = document.getElementById('errorContent');
    const button = document.querySelector('.btn-json-error');
    
    if (jsonView.style.display === 'none') {
        jsonView.style.display = 'block';
        errorContent.style.display = 'none';
        button.textContent = 'View Error';
    } else {
        jsonView.style.display = 'none';
        errorContent.style.display = 'block';
        button.textContent = 'View Details';
    }
}

function hideAllSections() {
    document.getElementById('previewSection').style.display = 'none';
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
    document.getElementById('uploadArea').style.display = 'block';
}

function resetUpload() {
    selectedFile = null;
    hideAllSections();
    
    // Clear file input
    document.getElementById('imageInput').value = '';
    
    // Clear preview
    const imagePreview = document.getElementById('imagePreview');
    imagePreview.src = '';
    imagePreview.style.display = 'none';
    
    // Hide HEIC placeholder if present
    const heicPlaceholder = document.getElementById('heicPlaceholder');
    if (heicPlaceholder) {
        heicPlaceholder.style.display = 'none';
    }
    
    // Show upload area
    document.getElementById('uploadArea').style.display = 'block';
}

function updateLoadingStatus(status) {
    const statusElement = document.getElementById('loadingStatus');
    if (statusElement) {
        statusElement.textContent = status;
    }
}

// Camera functions
async function openCamera() {
    const modal = document.getElementById('cameraModal');
    const video = document.getElementById('cameraVideo');
    
    try {
        // Request camera access
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment', // Use back camera if available
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        });
        
        video.srcObject = cameraStream;
        modal.style.display = 'block';
        
    } catch (error) {
        console.error('Camera access error:', error);
        alert('Unable to access camera. Please ensure you have granted camera permissions.');
    }
}

function closeCamera() {
    const modal = document.getElementById('cameraModal');
    
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    modal.style.display = 'none';
}

function capturePhoto() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('cameraCanvas');
    const ctx = canvas.getContext('2d');
    
    // Set canvas size to video size
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw video frame to canvas
    ctx.drawImage(video, 0, 0);
    
    // Convert to blob and create file
    canvas.toBlob((blob) => {
        const file = new File([blob], `camera-capture-${Date.now()}.jpg`, { type: 'image/jpeg' });
        
        // Close camera and process file
        closeCamera();
        processFile(file);
    }, 'image/jpeg', 0.8);
}

// Utility functions
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Image optimization function
async function resizeImage(file, maxWidth = 1200, maxHeight = 1200, quality = 0.8) {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = () => {
            // Store original dimensions
            const originalWidth = img.width;
            const originalHeight = img.height;
            
            // Calculate new dimensions
            let { width, height } = calculateNewDimensions(originalWidth, originalHeight, maxWidth, maxHeight);
            
            // Set canvas size
            canvas.width = width;
            canvas.height = height;
            
            // Draw resized image
            ctx.drawImage(img, 0, 0, width, height);
            
            // Convert to blob
            canvas.toBlob((blob) => {
                const resizedFile = new File([blob], file.name, {
                    type: 'image/jpeg',
                    lastModified: Date.now()
                });
                
                // Calculate compression ratio
                const compressionRatio = Math.round((1 - blob.size / file.size) * 100);
                
                resolve({
                    file: resizedFile,
                    originalSize: file.size,
                    newSize: blob.size,
                    compressionRatio: compressionRatio,
                    originalDimensions: { width: originalWidth, height: originalHeight },
                    dimensions: { width, height }
                });
            }, 'image/jpeg', quality);
        };
        
        img.src = URL.createObjectURL(file);
    });
}

function calculateNewDimensions(originalWidth, originalHeight, maxWidth, maxHeight) {
    let width = originalWidth;
    let height = originalHeight;
    
    // Calculate scaling factor
    const scaleX = maxWidth / width;
    const scaleY = maxHeight / height;
    const scale = Math.min(scaleX, scaleY, 1); // Don't upscale
    
    // Apply scaling
    width = Math.round(width * scale);
    height = Math.round(height * scale);
    
    return { width, height };
}