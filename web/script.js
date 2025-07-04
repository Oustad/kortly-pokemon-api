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
                max_processing_time: null,  // No time limit for better results
                response_format: "detailed"  // Get detailed response with all matches
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
    
    // Debug logging
    console.log('Received scan data:', data);
    console.log('Has all_tcg_matches:', !!data.all_tcg_matches);
    console.log('All TCG matches count:', data.all_tcg_matches?.length || 0);
    console.log('Regular TCG matches count:', data.tcg_matches?.length || 0);
    
    hideAllSections();
    document.getElementById('resultsSection').style.display = 'block';
    
    // Check if we have a simplified response
    if (data.name && !data.card_identification) {
        // Simplified response
        console.log('Using simplified response display');
        displaySimplifiedResults(data);
    } else {
        // Detailed response (legacy)
        console.log('Using detailed response display');
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
    
    // Display TCG matches (with new detailed scoring if available)
    displayMatches(data.tcg_matches, data.best_match, data.all_tcg_matches);
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

function displayIdentification(identification) {
    if (!identification) return;
    
    const geminiResult = document.getElementById('geminiResult');
    geminiResult.innerHTML = ''; // Clear previous content
    
    // Language detection info (new!)
    if (identification.language_info) {
        const langInfo = identification.language_info;
        const languageNames = {
            'en': 'English',
            'fr': 'French',
            'ja': 'Japanese',
            'de': 'German',
            'es': 'Spanish',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ko': 'Korean',
            'zh': 'Chinese'
        };
        
        const languageName = languageNames[langInfo.detected_language] || langInfo.detected_language.toUpperCase();
        const isNonEnglish = langInfo.detected_language !== 'en';
        
        const languageDiv = document.createElement('div');
        languageDiv.className = 'language-info';
        languageDiv.innerHTML = `
            <div class="language-detection" style="background: ${isNonEnglish ? '#fef3c7' : 'var(--bg-secondary)'}; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid ${isNonEnglish ? '#f59e0b' : '#10b981'};">
                <h4 style="margin: 0 0 0.5rem 0; color: var(--primary-color);">🌍 Language Detection</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
                    <div>
                        <div style="font-weight: bold; color: ${isNonEnglish ? '#d97706' : '#059669'};">${languageName}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Detected Language</div>
                    </div>
                    ${langInfo.original_name ? `
                    <div>
                        <div style="font-weight: bold;">${langInfo.original_name}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Original Name</div>
                    </div>
                    ` : ''}
                    ${langInfo.is_translation ? `
                    <div>
                        <div style="font-weight: bold; color: #3b82f6;">${langInfo.translated_name}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">English Translation</div>
                    </div>
                    ` : ''}
                </div>
                ${langInfo.is_translation ? `
                <div style="margin-top: 0.75rem; padding: 0.5rem; background: rgba(59, 130, 246, 0.1); border-radius: 4px; font-size: 0.9rem;">
                    <strong>📝 Note:</strong> ${langInfo.translation_note || 'Card name was translated for database search'}
                </div>
                ` : ''}
                ${isNonEnglish && !langInfo.is_translation ? `
                <div style="margin-top: 0.75rem; padding: 0.5rem; background: rgba(245, 158, 11, 0.1); border-radius: 4px; font-size: 0.9rem;">
                    <strong>⚠️ Notice:</strong> Non-English card detected - showing English equivalent pricing data
                </div>
                ` : ''}
            </div>
        `;
        geminiResult.appendChild(languageDiv);
    }

    // Token usage details
    if (identification.tokens_used) {
        const tokens = identification.tokens_used;
        const totalTokens = (tokens.prompt || 0) + (tokens.response || 0);
        
        const tokenInfo = document.createElement('div');
        tokenInfo.className = 'token-info';
        tokenInfo.innerHTML = `
            <div class="token-breakdown" style="background: var(--bg-secondary); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <h4 style="margin: 0 0 0.5rem 0; color: var(--primary-color);">🎯 Token Usage</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #8b5cf6;">${tokens.prompt || 0}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Prompt Tokens</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #8b5cf6;">${tokens.response || 0}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Response Tokens</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #8b5cf6;">${totalTokens}</div>
                        <div style="font-size: 0.9rem; color: var(--text-secondary);">Total Tokens</div>
                    </div>
                </div>
            </div>
        `;
        geminiResult.appendChild(tokenInfo);
    }
    
    // Show raw response
    const contentDiv = document.createElement('div');
    contentDiv.className = 'gemini-content';
    contentDiv.textContent = identification.raw_response;
    geminiResult.appendChild(contentDiv);
    
    // Show extracted data if available
    if (identification.structured_data && Object.keys(identification.structured_data).length > 0) {
        const extractedDiv = document.createElement('div');
        extractedDiv.className = 'extracted-data';
        extractedDiv.innerHTML = '<h4>📋 Extracted Information</h4>';
        
        const dataGrid = document.createElement('div');
        dataGrid.className = 'data-grid';
        
        const data = identification.structured_data;
        if (data.name) {
            dataGrid.innerHTML += createDataItem('Name', data.name);
        }
        if (data.set_name) {
            dataGrid.innerHTML += createDataItem('Set', data.set_name);
        }
        if (data.number) {
            dataGrid.innerHTML += createDataItem('Number', data.number);
        }
        if (data.hp) {
            dataGrid.innerHTML += createDataItem('HP', data.hp);
        }
        if (data.types && data.types.length > 0) {
            dataGrid.innerHTML += createDataItem('Types', data.types.join(', '));
        }
        
        extractedDiv.appendChild(dataGrid);
        geminiResult.appendChild(extractedDiv);
    }
}

function createDataItem(label, value) {
    return `
        <div class="data-item">
            <span class="data-label">${label}:</span>
            <span>${value}</span>
        </div>
    `;
}

function displayMatches(matches, bestMatch, allScoredMatches) {
    const matchesDiv = document.getElementById('tcgMatches');
    matchesDiv.innerHTML = '';
    
    // Debug logging
    console.log('displayMatches called with:');
    console.log('- matches:', matches?.length || 0, 'items');
    console.log('- bestMatch:', bestMatch?.name || 'none');
    console.log('- allScoredMatches:', allScoredMatches?.length || 0, 'items');
    
    // Use detailed scored matches if available, otherwise fall back to regular matches
    const matchesToDisplay = allScoredMatches || matches;
    
    if (!matchesToDisplay || matchesToDisplay.length === 0) {
        matchesDiv.innerHTML = '<p style="color: var(--text-secondary);">No matches found in the Pokemon TCG database.</p>';
        return;
    }
    
    // Add header with toggle for showing all matches
    const headerDiv = document.createElement('div');
    headerDiv.className = 'matches-header';
    headerDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
                <span style="font-weight: bold;">Found ${matchesToDisplay.length} potential matches</span>
                ${allScoredMatches ? '<span style="color: var(--text-secondary); font-size: 0.9rem; margin-left: 0.5rem;">(with scoring details)</span>' : ''}
            </div>
            ${matchesToDisplay.length > 3 ? `
                <button class="btn-secondary btn-sm" onclick="toggleAllMatches()" id="toggleMatchesBtn">
                    Show All Matches
                </button>
            ` : ''}
        </div>
    `;
    matchesDiv.appendChild(headerDiv);
    
    // Display matches container
    const matchesContainer = document.createElement('div');
    matchesContainer.id = 'matchesContainer';
    matchesDiv.appendChild(matchesContainer);
    
    // Display initial matches (top 3)
    displayMatchesSet(matchesToDisplay, bestMatch, matchesContainer, 3);
}

function displayMatchesSet(matchesToDisplay, bestMatch, container, limit) {
    container.innerHTML = '';
    
    const matchesToShow = limit ? matchesToDisplay.slice(0, limit) : matchesToDisplay;
    
    matchesToShow.forEach((matchItem, index) => {
        const isScored = matchItem.card && matchItem.score !== undefined;
        const card = isScored ? matchItem.card : matchItem;
        const isBestMatch = bestMatch && card.id === bestMatch.id;
        
        const matchCard = createMatchCard(card, isBestMatch, isScored ? matchItem : null, index + 1);
        container.appendChild(matchCard);
    });
}

function toggleAllMatches() {
    const container = document.getElementById('matchesContainer');
    const button = document.getElementById('toggleMatchesBtn');
    const allMatches = window.lastScanResult?.all_tcg_matches || window.lastScanResult?.tcg_matches || [];
    const bestMatch = window.lastScanResult?.best_match;
    
    if (button.textContent === 'Show All Matches') {
        displayMatchesSet(allMatches, bestMatch, container);
        button.textContent = 'Show Top 3';
    } else {
        displayMatchesSet(allMatches, bestMatch, container, 3);
        button.textContent = 'Show All Matches';
    }
}

function createMatchCard(card, isBestMatch, scoredMatch, rank) {
    const div = document.createElement('div');
    div.className = 'match-card' + (isBestMatch ? ' best-match' : '');
    
    const imageHtml = card.images?.small ? 
        `<div class="match-image">
            <img src="${card.images.small}" alt="${card.name}" loading="lazy">
        </div>` : '';
    
    const priceHtml = card.market_prices ? 
        `<div class="match-price">
            <strong>Market Price:</strong> ${formatPrices(card.market_prices)}
        </div>` : '';
    
    // Scoring information if available
    let scoringHtml = '';
    if (scoredMatch) {
        const confidenceColor = {
            'high': '#10b981',
            'medium': '#f59e0b', 
            'low': '#ef4444'
        }[scoredMatch.confidence] || '#6b7280';
        
        scoringHtml = `
            <div class="match-scoring" style="margin-top: 0.75rem; padding: 0.75rem; background: var(--bg-secondary); border-radius: 6px; border-left: 4px solid ${confidenceColor};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-weight: bold; color: ${confidenceColor};">Match Score: ${scoredMatch.score}</span>
                    <span style="font-size: 0.9rem; color: ${confidenceColor};">${scoredMatch.confidence.toUpperCase()} confidence</span>
                </div>
                ${scoredMatch.reasoning && scoredMatch.reasoning.length > 0 ? `
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">
                        <strong>Why this match:</strong>
                        <ul style="margin: 0.25rem 0 0 1rem; padding: 0;">
                            ${scoredMatch.reasoning.map(reason => `<li>${reason}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                <button class="btn-sm" onclick="toggleScoreBreakdown('${card.id}')" style="margin-top: 0.5rem; font-size: 0.8rem;">
                    Show Score Breakdown
                </button>
                <div id="breakdown-${card.id}" style="display: none; margin-top: 0.5rem; font-size: 0.8rem;">
                    ${formatScoreBreakdown(scoredMatch.score_breakdown)}
                </div>
            </div>
        `;
    }
    
    div.innerHTML = `
        ${rank ? `<div class="match-rank" style="position: absolute; top: 0.5rem; left: 0.5rem; background: var(--primary-color); color: white; width: 1.5rem; height: 1.5rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: bold;">${rank}</div>` : ''}
        ${imageHtml}
        <div class="match-info">
            <div class="match-name">${card.name} ${isBestMatch ? '⭐' : ''}</div>
            <div class="match-meta">
                <strong>Set:</strong> ${card.set_name || 'Unknown'} | 
                <strong>Number:</strong> ${card.number || 'N/A'}
            </div>
            <div class="match-meta">
                <strong>HP:</strong> ${card.hp || 'N/A'} | 
                <strong>Types:</strong> ${card.types ? card.types.join(', ') : 'N/A'}
            </div>
            <div class="match-meta">
                <strong>Rarity:</strong> ${card.rarity || 'Unknown'}
            </div>
            ${priceHtml}
            ${scoringHtml}
        </div>
    `;
    
    // Make the card position relative for the rank number
    if (rank) {
        div.style.position = 'relative';
    }
    
    return div;
}

function formatPrices(prices) {
    if (!prices) return 'N/A';
    
    const parts = [];
    if (prices.normal) {
        parts.push(`Normal: $${prices.normal.market || prices.normal.mid || 'N/A'}`);
    }
    if (prices.holofoil) {
        parts.push(`Holo: $${prices.holofoil.market || prices.holofoil.mid || 'N/A'}`);
    }
    
    return parts.join(' | ') || 'N/A';
}

function formatScoreBreakdown(breakdown) {
    if (!breakdown) return 'No breakdown available';
    
    const items = [];
    for (const [key, value] of Object.entries(breakdown)) {
        if (value !== 0) {
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            const sign = value > 0 ? '+' : '';
            const color = value > 0 ? '#10b981' : '#ef4444';
            items.push(`<span style="color: ${color};">${label}: ${sign}${value}</span>`);
        }
    }
    
    return items.length > 0 ? items.join('<br>') : 'No score components';
}

function toggleScoreBreakdown(cardId) {
    const breakdown = document.getElementById(`breakdown-${cardId}`);
    const button = event.target;
    
    if (breakdown.style.display === 'none') {
        breakdown.style.display = 'block';
        button.textContent = 'Hide Score Breakdown';
    } else {
        breakdown.style.display = 'none';
        button.textContent = 'Show Score Breakdown';
    }
}

// Image processing utilities
async function resizeImage(file, maxWidth = 1024, maxHeight = 1024, quality = 0.85) {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = () => {
            // Calculate new dimensions maintaining aspect ratio
            let { width, height } = img;
            
            if (width > height) {
                if (width > maxWidth) {
                    height = (height * maxWidth) / width;
                    width = maxWidth;
                }
            } else {
                if (height > maxHeight) {
                    width = (width * maxHeight) / height;
                    height = maxHeight;
                }
            }
            
            // Set canvas dimensions
            canvas.width = width;
            canvas.height = height;
            
            // Enable high-quality resizing
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            
            // Draw resized image
            ctx.drawImage(img, 0, 0, width, height);
            
            // Check WebP support and convert
            canvas.toBlob((blob) => {
                if (blob) {
                    const resizedFile = new File([blob], file.name, { 
                        type: blob.type,
                        lastModified: Date.now()
                    });
                    resolve({
                        file: resizedFile,
                        originalSize: file.size,
                        newSize: blob.size,
                        compressionRatio: ((file.size - blob.size) / file.size * 100).toFixed(1),
                        dimensions: { width, height },
                        originalDimensions: { width: img.width, height: img.height }
                    });
                } else {
                    // Fallback to original file if conversion fails
                    resolve({
                        file: file,
                        originalSize: file.size,
                        newSize: file.size,
                        compressionRatio: '0',
                        dimensions: { width: img.width, height: img.height },
                        originalDimensions: { width: img.width, height: img.height }
                    });
                }
            }, supportsWebP() ? 'image/webp' : 'image/jpeg', quality);
        };
        
        img.onerror = () => {
            // If image fails to load, return original file
            resolve({
                file: file,
                originalSize: file.size,
                newSize: file.size,
                compressionRatio: '0',
                dimensions: { width: 0, height: 0 },
                originalDimensions: { width: 0, height: 0 }
            });
        };
        
        img.src = URL.createObjectURL(file);
    });
}

function supportsWebP() {
    // Check WebP support
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    return canvas.toDataURL('image/webp').indexOf('image/webp') === 5;
}

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

function updateLoadingStatus(status) {
    document.getElementById('loadingStatus').textContent = status;
}

function hideAllSections() {
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
}

function showError(message) {
    hideAllSections();
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorSection').style.display = 'block';
}

function showEnhancedError(errorDetail) {
    // Store error data globally for JSON view
    window.lastErrorResult = errorDetail;
    
    hideAllSections();
    const errorSection = document.getElementById('errorSection');
    errorSection.style.display = 'block';
    
    // Build enhanced error display
    let html = `
        <div class="error-card">
            <div class="card-header">
                <h3>❌ ${errorDetail.message || 'Error'}</h3>
                <button class="btn-json" onclick="toggleErrorJsonView()">View JSON</button>
            </div>
            <div class="error-content" id="errorContent">
    `;
    
    // Show quality feedback if available
    if (errorDetail.quality_feedback) {
        const feedback = errorDetail.quality_feedback;
        
        html += `
            <div class="quality-feedback-error">
                <div class="feedback-overall">
                    <strong>Quality Assessment:</strong> 
                    <span class="quality-${feedback.overall}">${feedback.overall.toUpperCase()}</span>
                </div>
        `;
        
        if (feedback.issues && feedback.issues.length > 0) {
            html += `
                <div class="feedback-section">
                    <h4>Issues Detected:</h4>
                    <ul class="feedback-list issues">
                        ${feedback.issues.map(issue => `<li>${issue}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        if (feedback.suggestions && feedback.suggestions.length > 0) {
            html += `
                <div class="feedback-section">
                    <h4>Improvement Suggestions:</h4>
                    <ul class="feedback-list suggestions">
                        ${feedback.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        html += '</div>';
    }
    
    html += `
            </div>
            <div class="json-view" id="errorJsonView" style="display: none;">
                <pre>${JSON.stringify(errorDetail, null, 2)}</pre>
            </div>
            <button class="btn-secondary" onclick="resetUpload()">
                Try Again
            </button>
        </div>
    `;
    
    errorSection.innerHTML = html;
}

function toggleErrorJsonView() {
    const jsonView = document.getElementById('errorJsonView');
    const errorContent = document.getElementById('errorContent');
    const button = document.querySelector('#errorSection .btn-json');
    
    if (jsonView.style.display === 'none') {
        jsonView.style.display = 'block';
        errorContent.style.display = 'none';
        button.textContent = 'View Error';
    } else {
        jsonView.style.display = 'none';
        errorContent.style.display = 'block';
        button.textContent = 'View JSON';
    }
}

function resetUpload() {
    selectedFile = null;
    document.getElementById('imageInput').value = '';
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('previewSection').style.display = 'none';
    hideAllSections();
}

// Camera functions
async function openCamera() {
    const modal = document.getElementById('cameraModal');
    const video = document.getElementById('cameraVideo');
    
    try {
        // Request camera permission
        const constraints = {
            video: {
                facingMode: { ideal: 'environment' }, // Use rear camera on mobile
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        };
        
        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = cameraStream;
        modal.style.display = 'flex';
        
    } catch (error) {
        console.error('Camera error:', error);
        let errorMessage = 'Unable to access camera. ';
        
        if (error.name === 'NotAllowedError') {
            errorMessage += 'Please grant camera permission and try again.';
        } else if (error.name === 'NotFoundError') {
            errorMessage += 'No camera found on this device.';
        } else {
            errorMessage += 'Please ensure your browser supports camera access.';
        }
        
        showError(errorMessage);
    }
}

function closeCamera() {
    const modal = document.getElementById('cameraModal');
    const video = document.getElementById('cameraVideo');
    
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    video.srcObject = null;
    modal.style.display = 'none';
}

function capturePhoto() {
    const video = document.getElementById('cameraVideo');
    const canvas = document.getElementById('cameraCanvas');
    const context = canvas.getContext('2d');
    
    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw video frame to canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert canvas to blob
    canvas.toBlob((blob) => {
        if (blob) {
            // Create a file from the blob
            const file = new File([blob], 'camera-capture.jpg', { type: 'image/jpeg' });
            
            // Process the captured image
            processFile(file);
            
            // Close camera
            closeCamera();
        }
    }, 'image/jpeg', 0.9);
}
