// Pokemon Card Scanner - Frontend JavaScript

let selectedFile = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    // File input
    const imageInput = document.getElementById('imageInput');
    imageInput.addEventListener('change', handleFileSelect);
    
    // Drag and drop
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('click', () => imageInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
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
    
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('imagePreview').src = e.target.result;
        document.getElementById('fileName').textContent = file.name;
        
        // Show preview section and options
        document.getElementById('previewSection').style.display = 'block';
        document.getElementById('optionsPanel').style.display = 'block';
        
        // Hide upload area
        document.getElementById('uploadArea').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

// Scan card
async function scanCard() {
    if (!selectedFile) return;
    
    // Hide sections
    hideAllSections();
    document.getElementById('loadingSection').style.display = 'block';
    
    try {
        // Update loading status
        updateLoadingStatus('Converting image to base64...');
        const base64 = await fileToBase64(selectedFile);
        
        // Prepare request
        const requestData = {
            image: base64.split(',')[1], // Remove data URL prefix
            filename: selectedFile.name,
            options: {
                optimize_for_speed: document.getElementById('optimizeSpeed').checked,
                include_cost_tracking: document.getElementById('trackCost').checked,
                retry_on_truncation: true
            }
        };
        
        // Update loading status
        updateLoadingStatus('Analyzing card with AI...');
        
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
    
    // Display Gemini identification
    displayIdentification(data.card_identification);
    
    // Display TCG matches
    displayMatches(data.tcg_matches, data.best_match);
}

function displaySummary(data) {
    const summaryGrid = document.getElementById('summaryGrid');
    summaryGrid.innerHTML = '';
    
    // Processing time
    const timeItem = createSummaryItem(
        `${data.processing_info.total_time_ms}ms`,
        'Processing Time'
    );
    summaryGrid.appendChild(timeItem);
    
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
}

function createSummaryItem(value, label) {
    const div = document.createElement('div');
    div.className = 'summary-item';
    div.innerHTML = `
        <div class="summary-value">${value}</div>
        <div class="summary-label">${label}</div>
    `;
    return div;
}

function displayIdentification(identification) {
    if (!identification) return;
    
    const geminiResult = document.getElementById('geminiResult');
    
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

// Utility functions
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
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