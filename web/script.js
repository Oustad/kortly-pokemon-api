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
        
        // Show preview section and options
        document.getElementById('previewSection').style.display = 'block';
        document.getElementById('optionsPanel').style.display = 'block';
        
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
    
    // Show preview section and options
    document.getElementById('previewSection').style.display = 'block';
    document.getElementById('optionsPanel').style.display = 'block';
    
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
                optimize_for_speed: document.getElementById('optimizeSpeed').checked,
                include_cost_tracking: document.getElementById('trackCost').checked,
                retry_on_truncation: true,
                prefer_speed: document.getElementById('optimizeSpeed').checked,
                max_processing_time: document.getElementById('optimizeSpeed').checked ? 1500 : null
            }
        };
        
        // Update loading status with processing tier info
        const optimizeSpeed = document.getElementById('optimizeSpeed').checked;
        if (optimizeSpeed) {
            updateLoadingStatus('Fast processing mode - analyzing card...');
        } else {
            updateLoadingStatus('High quality mode - analyzing card thoroughly...');
        }
        
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
            throw new Error(data.detail || `API Error: ${response.status}`);
        }
        
        if (data.success) {
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
    hideAllSections();
    document.getElementById('resultsSection').style.display = 'block';
    
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

function displayIdentification(identification) {
    if (!identification) return;
    
    const geminiResult = document.getElementById('geminiResult');
    geminiResult.innerHTML = ''; // Clear previous content
    
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

function displayMatches(matches, bestMatch) {
    const matchesDiv = document.getElementById('tcgMatches');
    matchesDiv.innerHTML = '';
    
    if (!matches || matches.length === 0) {
        matchesDiv.innerHTML = '<p style="color: var(--text-secondary);">No matches found in the Pokemon TCG database.</p>';
        return;
    }
    
    // Display matches
    matches.slice(0, 5).forEach((card, index) => {
        const isBestMatch = bestMatch && card.id === bestMatch.id;
        const matchCard = createMatchCard(card, isBestMatch);
        matchesDiv.appendChild(matchCard);
    });
    
    if (matches.length > 5) {
        const moreDiv = document.createElement('div');
        moreDiv.style.cssText = 'text-align: center; padding: 15px; color: var(--text-secondary);';
        moreDiv.textContent = `... and ${matches.length - 5} more matches`;
        matchesDiv.appendChild(moreDiv);
    }
}

function createMatchCard(card, isBestMatch) {
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
    
    div.innerHTML = `
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
        </div>
    `;
    
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

function resetUpload() {
    selectedFile = null;
    document.getElementById('imageInput').value = '';
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('previewSection').style.display = 'none';
    document.getElementById('optionsPanel').style.display = 'none';
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
