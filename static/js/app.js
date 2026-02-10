// AutoGen Web Tester - Frontend JavaScript

// Initialize Socket.IO
const socket = io();

// DOM Elements
const testStepsTextarea = document.getElementById('test-steps');
const runTestBtn = document.getElementById('run-test');
const stopTestBtn = document.getElementById('stop-test');
const recordTestBtn = document.getElementById('record-test');
const loadExampleBtn = document.getElementById('load-example');
const clearLogBtn = document.getElementById('clear-log');
const browserScreenshot = document.getElementById('browser-screenshot');
const browserStatus = document.getElementById('browser-status');
const humanLogContainer = document.getElementById('human-log-container');
const technicalLogContainer = document.getElementById('technical-log-container');
const screenshotTimestamp = document.getElementById('screenshot-timestamp');
const exampleModal = document.getElementById('example-modal');
const exampleList = document.getElementById('example-list');
const closeModal = document.querySelector('.close');
const recordModal = document.getElementById('record-modal');
const closeRecordModal = document.querySelector('.close-record');
const recordUrlInput = document.getElementById('record-url');
const recordNameInput = document.getElementById('record-name');
const startRecordingBtn = document.getElementById('start-recording');
const cancelRecordingBtn = document.getElementById('cancel-recording');
const logTabs = document.querySelectorAll('.log-tab');
const playwrightCodeElement = document.getElementById('playwright-code');
const runCodeBtn = document.getElementById('run-code');
const copyCodeBtn = document.getElementById('copy-code');
const saveTestBtn = document.getElementById('save-test');
const refreshTestsBtn = document.getElementById('refresh-tests');
const savedTestsList = document.getElementById('saved-tests-list');

// Chat elements
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat');
const clearChatBtn = document.getElementById('clear-chat-btn');
const toggleChatBtn = document.getElementById('toggle-chat');
const closeChatSidebarBtn = document.getElementById('close-chat-sidebar');
const aiChatSidebar = document.getElementById('ai-chat-sidebar');
const codeEditorSection = document.querySelector('.code-editor-section');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreview = document.getElementById('image-preview');
const removeImageBtn = document.getElementById('remove-image');

let currentImage = null; // Store current image as base64

// Browser sidebar elements
const toggleBrowserBtn = document.getElementById('toggle-browser');
const closeBrowserSidebarBtn = document.getElementById('close-browser-sidebar');
const browserSidebar = document.getElementById('browser-sidebar');

// Editor tabs and file explorer (with null checks)
const fileExplorer = document.getElementById('file-explorer');
const fileList = document.getElementById('file-list');
const editorTabsContainer = document.querySelector('.editor-tabs-container');
const editorContent = document.querySelector('.editor-content');
const newTestBtn = document.getElementById('new-test-btn');
const closeAllTabsBtn = document.getElementById('close-all-tabs');
const explorerResizer = document.getElementById('explorer-resizer');

let openTabs = []; // Array of {id, name, code, isDirty}
let activeTabId = null;

// Check if file explorer elements exist
const hasFileExplorer = fileExplorer && fileList && editorTabsContainer && newTestBtn && closeAllTabsBtn && explorerResizer;

let currentEditingTest = null;  // Track if we're editing an existing test
let currentRecordingId = null;  // Track active recording
let pendingCodegenTest = null;  // Track test info from codegen

let isTestRunning = false;

// Socket.IO Event Handlers
socket.on('connect', () => {
    addLogEntry('info', 'Connected to server');
});

socket.on('playwright_code', (data) => {
    // Display generated Playwright code with syntax highlighting
    setPlaywrightCode(data.code);
    addLogEntry('success', '💻 Playwright code generated!', '💻 Code generated');

    // Open as new tab
    const tempId = 'generated_' + Date.now();
    const name = 'Generated Test';
    openTab(tempId, name, data.code);
    const tab = openTabs.find(t => t.id === tempId);
    if (tab) {
        tab.isDirty = true;
        lastSavedCode = '';
    }
    renderTabs();
});

socket.on('log', (data) => {
    // Simplify certain log messages for human view
    let humanMsg = data.message;
    if (data.message.includes('Initializing browser')) {
        humanMsg = '🚀 Starting browser...';
    } else if (data.message.includes('Browser initialized')) {
        humanMsg = '✅ Browser ready';
    } else if (data.message.includes('Initializing AI model')) {
        humanMsg = '🤖 Loading AI agent...';
    } else if (data.message.includes('Starting test execution')) {
        humanMsg = '▶️ Test started';
    } else if (data.message.includes('Test completed successfully')) {
        humanMsg = '✅ Test finished';
    } else if (data.type === 'agent_action') {
        // For agent action logs, don't show the technical details
        if (data.message.includes("source='user'")) {
            humanMsg = '📝 Test instructions received';
        } else if (data.message.includes("source='web_tester'")) {
            humanMsg = '🤖 Agent is analyzing...';
        } else {
            humanMsg = '🤖 Agent is working...';
        }
    }
    addLogEntry(data.type, data.message, humanMsg);
});

socket.on('screenshot', (data) => {
    // Update browser screenshot (JPEG format for faster loading)
    browserScreenshot.src = `data:image/jpeg;base64,${data.image}`;

    // Update timestamp
    const timestamp = new Date(data.timestamp).toLocaleTimeString();

    // Show "LIVE" indicator for stream, or action name for specific actions
    if (data.action === 'stream') {
        screenshotTimestamp.textContent = `🔴 LIVE - ${timestamp}`;
    } else {
        screenshotTimestamp.textContent = `${data.action} - ${timestamp}`;
    }

    // Only log action screenshots, not continuous stream frames
    if (data.action !== 'stream') {
        // Human-friendly action descriptions
        const humanActions = {
            'navigate': '🌐 Opened webpage',
            'click_text': '👆 Clicked button',
            'fill_form': '✍️ Filled form field'
        };
        const humanMessage = humanActions[data.action] || `📸 ${data.action}`;

        addLogEntry('info', `📸 Screenshot captured: ${data.action}`, humanMessage);
    }
});

socket.on('agent_message', (data) => {
    // Display agent's reasoning and actions
    const content = data.content;

    // Check for test status messages
    if (content.includes('TEST PASSED:')) {
        const statusMsg = content.match(/TEST PASSED:.*$/)?.[0] || content;
        addLogEntry('success', `✅ ${content}`, `✅ ${statusMsg}`);
        // Highlight in UI
        browserStatus.textContent = 'PASSED';
        browserStatus.style.background = '#10b981';
    } else if (content.includes('TEST FAILED:')) {
        const statusMsg = content.match(/TEST FAILED:.*$/)?.[0] || content;
        addLogEntry('error', `❌ ${content}`, `❌ ${statusMsg}`);
        browserStatus.textContent = 'FAILED';
        browserStatus.style.background = '#ef4444';
    } else if (content.includes('TEST ERROR:')) {
        const statusMsg = content.match(/TEST ERROR:.*$/)?.[0] || content;
        addLogEntry('error', `⚠️ ${content}`, `⚠️ ${statusMsg}`);
        browserStatus.textContent = 'ERROR';
        browserStatus.style.background = '#f59e0b';
    } else {
        // Extract meaningful info for human-readable view
        let humanMsg = '🤖 Agent is working...';

        // Check for tool calls/results
        if (content.includes('FunctionCall')) {
            const toolMatch = content.match(/name='([^']+)'/);
            if (toolMatch) {
                const toolName = toolMatch[1];
                humanMsg = `🔧 Calling tool: ${toolName}`;

                // Extract arguments for better context
                if (toolName === 'fill_form') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `✍️ Filling "${args.selector}" with: "${args.value}"`;
                        } catch {
                            humanMsg = `✍️ Filling form: ${argsMatch[1]}`;
                        }
                    }
                } else if (toolName === 'navigate') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `🌐 Navigating to: ${args.url}`;
                        } catch {
                            humanMsg = `🌐 Navigating to page`;
                        }
                    }
                } else if (toolName === 'click_text') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `👆 Clicking button: "${args.text}"`;
                        } catch {
                            humanMsg = `👆 Clicking button`;
                        }
                    }
                } else if (toolName === 'find_inputs') {
                    humanMsg = `🔍 Finding form inputs on page`;
                } else if (toolName === 'get_page_content') {
                    humanMsg = `📄 Reading page content`;
                } else if (toolName === 'get_current_url') {
                    humanMsg = `🔗 Checking current URL`;
                }
            }
        } else if (content.includes('FunctionExecutionResult')) {
            const resultMatch = content.match(/content='([^']+)'/);
            if (resultMatch) {
                const result = resultMatch[1];
                // Show more of the result for debugging
                humanMsg = `📥 ${result.substring(0, 200)}${result.length > 200 ? '...' : ''}`;
            }
        } else if (content.includes("source='web_tester'")) {
            // Extract actual reasoning text
            const reasoningMatch = content.match(/content='([^']+)'/);
            if (reasoningMatch) {
                const reasoning = reasoningMatch[1];
                humanMsg = `💭 ${reasoning.substring(0, 250)}${reasoning.length > 250 ? '...' : ''}`;
            }
        }

        addLogEntry('agent_action', content, humanMsg);
    }
});

socket.on('test_complete', (data) => {
    isTestRunning = false;
    runTestBtn.disabled = false;
    runTestBtn.textContent = '▶ Run Test';
    runTestBtn.style.display = 'block';
    stopTestBtn.style.display = 'none';
    runCodeBtn.disabled = false;
    runCodeBtn.textContent = '▶ Run Code';
    browserStatus.textContent = 'Completed';
    browserStatus.classList.remove('running');

    if (data.status === 'success') {
        addLogEntry('success', '✅ Test completed successfully!', '🎉 Test completed!');
    } else if (data.status === 'stopped') {
        addLogEntry('error', '⏹ Test stopped by user', '⏹ Test stopped');
        browserStatus.textContent = 'Stopped';
        browserStatus.style.background = '#f59e0b';
    } else {
        const errorMsg = data.message || 'Unknown error';
        addLogEntry('error', `❌ Test failed: ${errorMsg}`, `❌ Test failed`);
    }
});

socket.on('codegen_status', (data) => {
    if (data.status === 'recording') {
        browserStatus.textContent = 'Recording';
        browserStatus.classList.add('recording');
        browserStatus.style.background = '#8b5cf6';
        addLogEntry('info', data.message, '🎥 Recording in progress...');
    }
});

socket.on('codegen_complete', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Complete';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = '#10b981';

    // Display generated code
    setPlaywrightCode(data.code);

    // Store test info for saving with 'codegen' source
    pendingCodegenTest = {
        name: data.name,
        source: 'codegen'
    };

    // Pre-fill save button
    saveTestBtn.textContent = '💾 Save Recorded Test';

    addLogEntry('success', '✅ Recording complete! Code generated.', '✅ Recording complete!');

    // Close modal
    recordModal.style.display = 'none';

    // Scroll to code section
    playwrightCodeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

socket.on('codegen_error', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Error';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = '#ef4444';

    addLogEntry('error', `❌ Recording failed: ${data.message}`, '❌ Recording failed');

    // Close modal
    recordModal.style.display = 'none';

    alert(`Recording failed:\n${data.message}`);
});

// UI Event Handlers
recordTestBtn.addEventListener('click', () => {
    // Show record modal
    recordModal.style.display = 'block';
    recordUrlInput.value = '';
    recordNameInput.value = '';
    recordUrlInput.focus();
});

startRecordingBtn.addEventListener('click', async () => {
    const url = recordUrlInput.value.trim();
    const name = recordNameInput.value.trim();

    if (!url) {
        alert('Please enter a URL');
        recordUrlInput.focus();
        return;
    }

    // Disable button during request
    startRecordingBtn.disabled = true;
    startRecordingBtn.textContent = '⏳ Starting...';

    try {
        const response = await fetch('/api/start-codegen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, name })
        });

        const data = await response.json();

        if (data.success) {
            currentRecordingId = data.recording_id;
            addLogEntry('info', `🎥 Starting recording for ${url}`, '🎥 Recording starting...');

            // Keep modal open with status message
            startRecordingBtn.textContent = '🎥 Recording... (Close Playwright window when done)';
        } else {
            const errorMsg = data.error || 'Unknown error';

            // Show user-friendly message
            if (errorMsg.includes('not available in cloud')) {
                alert('⚠️ Recording Feature Unavailable\n\n' +
                      'The Playwright codegen recording feature requires a local environment with GUI support.\n\n' +
                      'In Cloud Run/cloud deployments, please use the AI-driven test creation instead:\n' +
                      '• Write test steps in natural language\n' +
                      '• Click "Run Test"\n' +
                      '• AI will execute and generate code\n\n' +
                      'Recording is available when running locally.');
            } else {
                alert(`Failed to start recording:\n${errorMsg}`);
            }

            startRecordingBtn.disabled = false;
            startRecordingBtn.textContent = 'Start Recording';
            recordModal.style.display = 'none';
        }
    } catch (error) {
        alert(`Failed to start recording: ${error.message}`);
        startRecordingBtn.disabled = false;
        startRecordingBtn.textContent = 'Start Recording';
    }
});

cancelRecordingBtn.addEventListener('click', () => {
    recordModal.style.display = 'none';
    startRecordingBtn.disabled = false;
    startRecordingBtn.textContent = 'Start Recording';
});

closeRecordModal.addEventListener('click', () => {
    recordModal.style.display = 'none';
    startRecordingBtn.disabled = false;
    startRecordingBtn.textContent = 'Start Recording';
});

runTestBtn.addEventListener('click', () => {
    const task = testStepsTextarea.value.trim();

    if (!task) {
        alert('Please enter test steps');
        return;
    }

    if (isTestRunning) {
        alert('A test is already running');
        return;
    }

    // Clear previous results
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    setPlaywrightCode('');

    // Reset editing state
    currentEditingTest = null;
    pendingCodegenTest = null;
    saveTestBtn.textContent = '💾 Save';

    // Update UI
    isTestRunning = true;
    runTestBtn.style.display = 'none';
    stopTestBtn.style.display = 'block';
    browserStatus.textContent = 'Running';
    browserStatus.classList.add('running');
    browserStatus.style.background = '';

    // Automatically open browser sidebar when test starts
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
        toggleBrowserBtn.classList.add('active');
    }

    // Send test to server
    socket.emit('run_test', { task });

    addLogEntry('info', '🚀 Starting test execution...');
});

stopTestBtn.addEventListener('click', () => {
    if (!isTestRunning) {
        return;
    }

    addLogEntry('info', '⏹ Stopping test...');
    socket.emit('stop_test');

    // Update UI immediately
    stopTestBtn.disabled = true;
    stopTestBtn.textContent = '⏳ Stopping...';
});

loadExampleBtn.addEventListener('click', async () => {
    // Load example tests from server
    try {
        const response = await fetch('/api/example-tests');
        const examples = await response.json();

        // Display examples in modal
        exampleList.innerHTML = '';
        examples.forEach(example => {
            const div = document.createElement('div');
            div.className = 'example-item';
            div.innerHTML = `
                <h3>${example.name}</h3>
                <p>${example.url}</p>
            `;
            div.onclick = () => {
                testStepsTextarea.value = example.steps;
                exampleModal.style.display = 'none';
                addLogEntry('info', `Loaded example: ${example.name}`);
            };
            exampleList.appendChild(div);
        });

        exampleModal.style.display = 'block';
    } catch (error) {
        addLogEntry('error', `Failed to load examples: ${error.message}`);
    }
});

clearLogBtn.addEventListener('click', () => {
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    addLogEntry('info', 'Log cleared');
});

// Run Code button - Execute Playwright code with live browser preview
runCodeBtn.addEventListener('click', () => {
    const code = getPlaywrightCode();
    if (!code || code.trim() === '') {
        alert('No code to run. Please write or generate some Playwright code first.');
        return;
    }

    if (isTestRunning) {
        alert('A test is already running');
        return;
    }

    // Clear previous results
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';

    // Update UI
    isTestRunning = true;
    runCodeBtn.disabled = true;
    runCodeBtn.textContent = '⏳ Running...';
    browserStatus.textContent = 'Running';
    browserStatus.classList.add('running');
    browserStatus.style.background = '';

    // Automatically open browser sidebar
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
        toggleBrowserBtn.classList.add('active');
    }

    // Send code to backend for execution
    socket.emit('run_playwright_code', { code });

    addLogEntry('info', '▶️ Executing Playwright code...');
});

copyCodeBtn.addEventListener('click', () => {
    const code = getPlaywrightCode();
    if (code) {
        navigator.clipboard.writeText(code).then(() => {
            copyCodeBtn.textContent = '✓ Copied!';
            setTimeout(() => {
                copyCodeBtn.textContent = '📋 Copy';
            }, 2000);
        }).catch(err => {
            alert('Failed to copy code: ' + err);
        });
    } else {
        alert('No code to copy yet. Run a test first!');
    }
});

saveTestBtn.addEventListener('click', () => {
    const code = getPlaywrightCode();
    if (!code) {
        alert('No code to save!');
        return;
    }

    // Check if we're editing an existing tab
    if (activeTabId && !activeTabId.startsWith('new_')) {
        // Updating existing saved test
        const tab = openTabs.find(t => t.id === activeTabId);
        if (!tab) return;

        if (!confirm(`Save changes to "${tab.name}"?`)) return;

        fetch(`/api/saved-tests/${activeTabId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: tab.name,
                code: code
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                tab.isDirty = false;
                tab.code = code;
                lastSavedCode = code;
                renderTabs();
                addLogEntry('success', `💾 Saved: ${tab.name}`);
            } else {
                alert('Error saving: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            alert('Failed to save: ' + err);
        });
    } else {
        // Saving as new test
        let defaultName = '';
        if (activeTabId) {
            const tab = openTabs.find(t => t.id === activeTabId);
            if (tab) defaultName = tab.name;
        }

        const name = prompt('Save as:', defaultName);
        if (!name) return;

        fetch('/api/save-test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, code, source: 'ai' })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addLogEntry('success', `💾 Saved: ${name}`);

                // Close old tab if it was a "new" tab
                if (activeTabId && activeTabId.startsWith('new_')) {
                    const oldTabIndex = openTabs.findIndex(t => t.id === activeTabId);
                    if (oldTabIndex !== -1) {
                        openTabs.splice(oldTabIndex, 1);
                    }
                }

                // Reload file explorer
                loadFileExplorer();

                // Open as new tab
                openTab(data.filename, name, code);
                lastSavedCode = code;
            } else {
                alert('Error saving: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            alert('Failed to save: ' + err);
        });
    }
});

refreshTestsBtn.addEventListener('click', () => {
    loadFileExplorer();
});

function loadSavedTests() {
    // Load both file explorer and saved tests list
    loadFileExplorer();

    // Also update the top-left saved tests list
    fetch('/api/saved-tests')
        .then(res => res.json())
        .then(tests => {
            savedTestsList.innerHTML = '';
            if (tests.length === 0) {
                savedTestsList.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 20px;">No saved tests yet. Save a test after it passes!</p>';
                return;
            }

            tests.forEach(test => {
                const item = document.createElement('div');
                item.className = 'saved-test-item';

                const created = new Date(test.created).toLocaleString();
                const source = test.source || 'ai';
                const sourceBadge = source === 'codegen'
                    ? '<span class="saved-test-source codegen">🎥 Recorded</span>'
                    : '<span class="saved-test-source ai">🤖 AI Generated</span>';

                item.innerHTML = `
                    <div class="saved-test-info">
                        <div class="saved-test-name">${escapeHtml(test.name)} ${sourceBadge}</div>
                        <div class="saved-test-date">Saved: ${created}</div>
                    </div>
                    <div class="saved-test-actions">
                        <button class="btn btn-primary btn-small test-run-btn" data-filename="${test.filename}" data-name="${escapeHtml(test.name)}">▶ Run</button>
                        <button class="btn btn-secondary btn-small test-open-btn" data-filename="${test.filename}" data-name="${escapeHtml(test.name)}">📂 Open</button>
                    </div>
                `;

                // Add event listeners
                const runBtn = item.querySelector('.test-run-btn');
                const openBtn = item.querySelector('.test-open-btn');

                runBtn.addEventListener('click', () => {
                    runSavedTest(test.filename, test.name);
                });

                openBtn.addEventListener('click', () => {
                    openFileFromExplorer(test.filename, test.name);
                    // Scroll to code editor
                    playwrightCodeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                });

                savedTestsList.appendChild(item);
            });
        })
        .catch(err => {
            console.error('Failed to load saved tests:', err);
        });
}

function runSavedTest(filename, name) {
    if (isTestRunning) {
        alert('A test is already running. Please wait for it to finish.');
        return;
    }

    addLogEntry('info', `🚀 Running: ${name} (no AI tokens used!)`, `🚀 Running: ${name}`);
    isTestRunning = true;
    runTestBtn.style.display = 'none';
    stopTestBtn.style.display = 'block';
    browserStatus.textContent = 'Running';
    browserStatus.classList.add('running');

    socket.emit('run_saved_test', { filename });
}

// Tab Management Functions
function openTab(filename, name, code) {
    // Check if tab is already open
    const existingTab = openTabs.find(tab => tab.id === filename);
    if (existingTab) {
        switchToTab(filename);
        return;
    }

    // Add new tab
    openTabs.push({
        id: filename,
        name: name,
        code: code,
        isDirty: false
    });

    renderTabs();
    switchToTab(filename);
}

function closeTab(filename) {
    const tabIndex = openTabs.findIndex(tab => tab.id === filename);
    if (tabIndex === -1) return;

    const tab = openTabs[tabIndex];

    // Check if dirty (unsaved changes)
    if (tab.isDirty) {
        if (!confirm(`Close ${tab.name}?\nYou have unsaved changes.`)) {
            return;
        }
    }

    // Remove tab
    openTabs.splice(tabIndex, 1);

    // Switch to another tab if this was active
    if (activeTabId === filename) {
        if (openTabs.length > 0) {
            // Switch to previous tab or first tab
            const newActiveTab = openTabs[Math.max(0, tabIndex - 1)];
            switchToTab(newActiveTab.id);
        } else {
            activeTabId = null;
            setPlaywrightCode('');
            if (editorContent) editorContent.classList.add('empty');
        }
    }

    renderTabs();
}

function switchToTab(filename) {
    const tab = openTabs.find(t => t.id === filename);
    if (!tab) return;

    activeTabId = filename;
    setPlaywrightCode(tab.code);
    if (editorContent) editorContent.classList.remove('empty');
    renderTabs();
    updateFileListActiveState();
}

function renderTabs() {
    if (!editorTabsContainer) return;

    editorTabsContainer.innerHTML = '';

    openTabs.forEach(tab => {
        const tabEl = document.createElement('div');
        tabEl.className = 'editor-tab' + (tab.id === activeTabId ? ' active' : '') + (tab.isDirty ? ' dirty' : '');

        tabEl.innerHTML = `
            <span class="editor-tab-icon">📄</span>
            <span class="editor-tab-name">${escapeHtml(tab.name)}</span>
            <button class="editor-tab-close" data-tab-id="${tab.id}">×</button>
        `;

        // Click tab to switch
        tabEl.addEventListener('click', (e) => {
            if (!e.target.classList.contains('editor-tab-close')) {
                switchToTab(tab.id);
            }
        });

        // Close button
        const closeBtn = tabEl.querySelector('.editor-tab-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeTab(tab.id);
        });

        editorTabsContainer.appendChild(tabEl);
    });
}

function updateFileListActiveState() {
    document.querySelectorAll('.file-item').forEach(item => {
        const filename = item.dataset.filename;
        if (filename === activeTabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// File Explorer Functions
function loadFileExplorer() {
    if (!hasFileExplorer || !fileList) {
        console.warn('File explorer elements not found, skipping load');
        return;
    }

    fetch('/api/saved-tests')
        .then(res => res.json())
        .then(tests => {
            fileList.innerHTML = '';

            if (tests.length === 0) {
                fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: #858585; font-size: 12px;">No saved tests</div>';
                return;
            }

            tests.forEach(test => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.dataset.filename = test.filename;

                const sourceIcon = test.source === 'codegen' ? '🎥' : '🤖';

                fileItem.innerHTML = `
                    <span class="file-item-icon">${sourceIcon}</span>
                    <span class="file-item-name">${escapeHtml(test.name)}</span>
                    <div class="file-item-actions">
                        <button class="file-item-action" data-action="run" title="Run Test">▶</button>
                        <button class="file-item-action" data-action="delete" title="Delete">🗑</button>
                    </div>
                `;

                // Click to open
                fileItem.addEventListener('click', (e) => {
                    const action = e.target.dataset.action;
                    if (action === 'delete') {
                        deleteFileFromExplorer(test.filename, test.name);
                    } else if (action === 'run') {
                        e.stopPropagation();
                        runSavedTest(test.filename, test.name);
                    } else {
                        openFileFromExplorer(test.filename, test.name);
                    }
                });

                fileList.appendChild(fileItem);
            });

            updateFileListActiveState();
        })
        .catch(err => {
            console.error('Failed to load file explorer:', err);
        });
}

function openFileFromExplorer(filename, name) {
    fetch(`/api/saved-tests/${filename}`)
        .then(res => res.json())
        .then(data => {
            if (data.code) {
                openTab(filename, name, data.code);
            }
        })
        .catch(err => {
            alert('Failed to load test: ' + err);
        });
}

function deleteFileFromExplorer(filename, name) {
    if (!confirm(`Delete "${name}"?`)) return;

    fetch(`/api/saved-tests/${filename}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Close tab if open
                closeTab(filename);
                // Reload file explorer
                loadFileExplorer();
                addLogEntry('info', `Deleted: ${name}`);
            }
        })
        .catch(err => {
            alert('Failed to delete test: ' + err);
        });
}

// Explorer Resizer
if (hasFileExplorer && explorerResizer) {
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    explorerResizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = fileExplorer.offsetWidth;
        explorerResizer.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const diff = e.clientX - startX;
        const newWidth = Math.max(150, Math.min(400, startWidth + diff));
        fileExplorer.style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            explorerResizer.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

// New Test Button
if (newTestBtn) {
    newTestBtn.addEventListener('click', () => {
    const name = prompt('Enter test name:');
    if (!name) return;

    const code = `from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Your code here

        await browser.close()

asyncio.run(run())`;

    // Create a temporary filename
    const tempId = 'new_' + Date.now();
    openTab(tempId, name, code);

        // Mark as dirty since it's not saved yet
        const tab = openTabs.find(t => t.id === tempId);
        if (tab) tab.isDirty = true;
        renderTabs();
    });
}

// Close All Tabs
if (closeAllTabsBtn) {
    closeAllTabsBtn.addEventListener('click', () => {
    if (openTabs.length === 0) return;

    const dirtyTabs = openTabs.filter(tab => tab.isDirty);
    if (dirtyTabs.length > 0) {
        if (!confirm(`Close all tabs?\nYou have ${dirtyTabs.length} unsaved change(s).`)) {
            return;
        }
    }

        openTabs = [];
        activeTabId = null;
        setPlaywrightCode('');
        if (editorContent) editorContent.classList.add('empty');
        renderTabs();
        updateFileListActiveState();
    });
}

// Track code changes to mark tabs as dirty
let lastSavedCode = '';
playwrightCodeElement.addEventListener('input', () => {
    const currentCode = getPlaywrightCode();
    if (activeTabId && currentCode !== lastSavedCode) {
        const tab = openTabs.find(t => t.id === activeTabId);
        if (tab) {
            tab.isDirty = true;
            tab.code = currentCode;
            renderTabs();
        }
    }
});

// Load file explorer on page load
window.addEventListener('load', () => {
    if (hasFileExplorer) {
        loadFileExplorer();
        if (editorContent) editorContent.classList.add('empty');
    }
});

closeModal.addEventListener('click', () => {
    exampleModal.style.display = 'none';
});

window.addEventListener('click', (event) => {
    if (event.target === exampleModal) {
        exampleModal.style.display = 'none';
    }
    if (event.target === recordModal) {
        recordModal.style.display = 'none';
        startRecordingBtn.disabled = false;
        startRecordingBtn.textContent = 'Start Recording';
    }
});

// AI Chat Sidebar Toggle
toggleChatBtn.addEventListener('click', () => {
    const isOpen = aiChatSidebar.classList.toggle('open');
    codeEditorSection.classList.toggle('chat-open');

    // Update button appearance
    if (isOpen) {
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Chat';
        toggleChatBtn.classList.add('active');
        // Focus on chat input
        setTimeout(() => chatInput.focus(), 300);
    } else {
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
        toggleChatBtn.classList.remove('active');
    }
});

closeChatSidebarBtn.addEventListener('click', () => {
    aiChatSidebar.classList.remove('open');
    codeEditorSection.classList.remove('chat-open');
    toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
    toggleChatBtn.classList.remove('active');
});

// Live Browser Sidebar Toggle
toggleBrowserBtn.addEventListener('click', () => {
    const isOpen = browserSidebar.classList.toggle('open');
    const codeEditorContainer = document.querySelector('.code-editor-container');

    if (isOpen) {
        codeEditorContainer.classList.add('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
        toggleBrowserBtn.classList.add('active');
    } else {
        codeEditorContainer.classList.remove('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
        toggleBrowserBtn.classList.remove('active');
    }
});

closeBrowserSidebarBtn.addEventListener('click', () => {
    const codeEditorContainer = document.querySelector('.code-editor-container');
    browserSidebar.classList.remove('open');
    codeEditorContainer.classList.remove('browser-open');
    toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
    toggleBrowserBtn.classList.remove('active');
});

// Tab switching (log tabs)
logTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active class from all tabs and containers
        logTabs.forEach(t => t.classList.remove('active'));
        humanLogContainer.classList.remove('active');
        technicalLogContainer.classList.remove('active');

        // Add active class to clicked tab
        tab.classList.add('active');

        // Show corresponding container
        if (tab.dataset.tab === 'human') {
            humanLogContainer.classList.add('active');
        } else {
            technicalLogContainer.classList.add('active');
        }
    });
});

// Helper Functions
function addLogEntry(type, message, humanMessage = null) {
    const timestamp = new Date().toLocaleTimeString();

    // Add to technical log (full detail)
    const technicalEntry = document.createElement('div');
    technicalEntry.className = `log-entry ${type}`;
    technicalEntry.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${escapeHtml(message)}</span>
    `;
    technicalLogContainer.appendChild(technicalEntry);
    technicalLogContainer.scrollTop = technicalLogContainer.scrollHeight;

    // Add to human log (simplified)
    const humanEntry = document.createElement('div');
    humanEntry.className = `log-entry ${type}`;
    const displayMessage = humanMessage || simplifyMessage(message);
    humanEntry.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${escapeHtml(displayMessage)}</span>
    `;
    humanLogContainer.appendChild(humanEntry);
    humanLogContainer.scrollTop = humanLogContainer.scrollHeight;
}

function simplifyMessage(message) {
    // Simplify technical messages for human readability
    if (message.includes('source=')) {
        // Extract key info from agent messages
        if (message.includes('TEST PASSED:')) {
            return message.match(/TEST PASSED:.*$/)?.[0] || message;
        }
        if (message.includes('TEST FAILED:')) {
            return message.match(/TEST FAILED:.*$/)?.[0] || message;
        }
        if (message.includes('TEST ERROR:')) {
            return message.match(/TEST ERROR:.*$/)?.[0] || message;
        }

        // Extract content from structured messages
        const contentMatch = message.match(/content='([^']*)/);
        if (contentMatch) {
            const content = contentMatch[1];
            // Determine message type from source
            if (message.includes("source='user'")) {
                return '📝 Test instructions received';
            } else if (message.includes("source='web_tester'")) {
                return '🤖 Agent is thinking...';
            }
        }

        // For other agent actions, just return a generic message
        return '🤖 Agent is working...';
    }

    // Handle [agent_action] messages
    if (message.startsWith('[') && message.includes(']')) {
        return '🤖 Agent is working...';
    }

    return message;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper functions for Playwright code editor
function setPlaywrightCode(code) {
    playwrightCodeElement.textContent = code;
    if (code && typeof Prism !== 'undefined') {
        Prism.highlightElement(playwrightCodeElement);
    }
}

function getPlaywrightCode() {
    return playwrightCodeElement.textContent.trim();
}

// Add Tab key support for code editor
playwrightCodeElement.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
        e.preventDefault();

        // Insert 4 spaces instead of tab
        const selection = window.getSelection();
        const range = selection.getRangeAt(0);
        const tabNode = document.createTextNode('    ');
        range.insertNode(tabNode);

        // Move cursor after the inserted spaces
        range.setStartAfter(tabNode);
        range.setEndAfter(tabNode);
        selection.removeAllRanges();
        selection.addRange(range);
    }
});

// Re-apply syntax highlighting when editing
playwrightCodeElement.addEventListener('input', () => {
    if (playwrightCodeElement.textContent && typeof Prism !== 'undefined') {
        // Debounce to avoid too many re-renders
        clearTimeout(playwrightCodeElement.highlightTimeout);
        playwrightCodeElement.highlightTimeout = setTimeout(() => {
            Prism.highlightElement(playwrightCodeElement);
        }, 300);
    }
});

// Chat functionality
function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message && !currentImage) return;

    // Open chat sidebar if not already open
    if (!aiChatSidebar.classList.contains('open')) {
        aiChatSidebar.classList.add('open');
        codeEditorSection.classList.add('chat-open');
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Chat';
        toggleChatBtn.classList.add('active');
    }

    // Get existing code from bottom panel
    const existingCode = getPlaywrightCode();

    // Add user message to chat (with image if present)
    if (currentImage) {
        appendChatMessageWithImage('user', message || 'Analyze this image', currentImage);
    } else {
        appendChatMessage('user', message);
    }

    chatInput.value = '';

    // Send to backend
    socket.emit('chat_message', {
        message: message || 'Analyze this image and generate relevant Playwright code',
        existing_code: existingCode || null,
        image: currentImage
    });

    // Clear image after sending
    if (currentImage) {
        currentImage = null;
        imagePreviewContainer.style.display = 'none';
        imagePreview.src = '';
        fileInput.value = '';
    }

    // Show loading indicator
    appendChatMessage('system', 'Thinking...');
}

function appendChatMessage(type, content, isCode = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    if (isCode) {
        messageDiv.className = 'chat-message code';

        // Add code header
        const codeHeader = document.createElement('div');
        codeHeader.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #2d2d2d; border-bottom: 1px solid #1e1e1e;';
        codeHeader.innerHTML = '<span style="font-size: 11px; color: #858585; text-transform: uppercase; letter-spacing: 0.5px;">Python</span>';

        // Add copy button
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = '📋';
        copyBtn.style.cssText = 'background: transparent; border: none; color: #858585; cursor: pointer; padding: 2px 6px; border-radius: 3px; font-size: 12px;';
        copyBtn.onmouseover = () => copyBtn.style.background = '#3c3c3c';
        copyBtn.onmouseout = () => copyBtn.style.background = 'transparent';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(content);
            copyBtn.innerHTML = '✓';
            setTimeout(() => copyBtn.innerHTML = '📋', 2000);
        };
        codeHeader.appendChild(copyBtn);
        messageDiv.appendChild(codeHeader);

        const codeBlock = document.createElement('pre');
        const code = document.createElement('code');
        code.className = 'language-python';
        code.textContent = content;
        codeBlock.appendChild(code);
        messageDiv.appendChild(codeBlock);
        if (typeof Prism !== 'undefined') {
            Prism.highlightElement(code);
        }
    } else {
        const contentSpan = document.createElement('span');
        contentSpan.textContent = content;
        messageDiv.appendChild(contentSpan);
    }

    chatMessages.appendChild(messageDiv);
    // Smooth scroll to bottom
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

function appendChatMessageWithImage(type, content, imageSrc) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    // Add text content
    const contentSpan = document.createElement('span');
    contentSpan.textContent = content;
    messageDiv.appendChild(contentSpan);

    // Add image
    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = 'Attached image';
    messageDiv.appendChild(img);

    chatMessages.appendChild(messageDiv);
    // Smooth scroll to bottom
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

// Socket.IO event handlers for chat
socket.on('chat_response', (data) => {
    // Remove loading indicator
    const systemMessages = chatMessages.querySelectorAll('.chat-message.system');
    systemMessages.forEach(msg => {
        if (msg.textContent.includes('thinking')) {
            msg.remove();
        }
    });

    // Add AI response
    appendChatMessage('ai', data.message);
});

socket.on('code_generated', (data) => {
    // Show code in chat
    appendChatMessage('code', data.code, true);

    // Insert code into bottom panel
    setPlaywrightCode(data.code);

    // Open as new tab or update existing
    if (activeTabId) {
        // Update current tab
        const tab = openTabs.find(t => t.id === activeTabId);
        if (tab) {
            tab.code = data.code;
            tab.isDirty = true;
            renderTabs();
        }
    } else {
        // Create new tab
        const tempId = 'chat_' + Date.now();
        const name = 'AI Generated';
        openTab(tempId, name, data.code);
        const tab = openTabs.find(t => t.id === tempId);
        if (tab) {
            tab.isDirty = true;
            lastSavedCode = '';
        }
        renderTabs();
    }

    // Add explanation if provided
    if (data.explanation) {
        appendChatMessage('system', `Code updated: ${data.explanation}`);
    }
});

socket.on('chat_error', (data) => {
    // Remove loading indicator
    const systemMessages = chatMessages.querySelectorAll('.chat-message.system');
    systemMessages.forEach(msg => {
        if (msg.textContent.includes('thinking')) {
            msg.remove();
        }
    });

    appendChatMessage('system', `Error: ${data.message}`);
});

// Event listeners for chat
sendChatBtn.addEventListener('click', sendChatMessage);

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendChatMessage();
    }
});

// ESC to close chat
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && aiChatSidebar.classList.contains('open')) {
        aiChatSidebar.classList.remove('open');
        codeEditorSection.classList.remove('chat-open');
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
        toggleChatBtn.classList.remove('active');
    }
});

clearChatBtn.addEventListener('click', () => {
    if (confirm('Clear all chat messages?')) {
        chatMessages.innerHTML = '';
        socket.emit('clear_chat');
        appendChatMessage('system', 'Chat history cleared');
    }
});

// Drag and Drop functionality
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleImageFile(files[0]);
    }
});

// File input functionality
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleImageFile(e.target.files[0]);
    }
});

// Remove image
removeImageBtn.addEventListener('click', () => {
    currentImage = null;
    imagePreviewContainer.style.display = 'none';
    imagePreview.src = '';
    fileInput.value = '';
});

// Handle image file
function handleImageFile(file) {
    // Check if it's an image
    if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
    }

    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('Image size must be less than 10MB');
        return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        imagePreview.src = currentImage;
        imagePreviewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

// Load default example on page load
window.addEventListener('load', () => {
    testStepsTextarea.value = `Complete the signup process on https://sunny-staging.vercel.app/:

1. Go to the website
2. Click the "Sign Up" button at the header
3. Fill out the signup form with:
   - Full Name: Test User
   - Email: test+(random 10 characters)@example.com
4. Submit the form by clicking the "Sign Up" button
5. Verify the success page contains:
   - Heading: "Just a couple of questions to save you time"
   - Subheading: "Bedrooms help us find your perfect fit"
   - 4 bedroom option cards`;

    addLogEntry('info', '👋 Welcome to AutoGen Web Tester!');
    addLogEntry('info', '📝 Write test steps and click "Run Test" to see AI automation');
    addLogEntry('info', '💬 Click "Chat" button (bottom panel) for conversational code generation');
});
