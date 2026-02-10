// AutoGen Web Tester - Frontend JavaScript

// Initialize Socket.IO
const socket = io();

// DOM Elements
const clearLogBtn = document.getElementById('clear-log');
const browserScreenshot = document.getElementById('browser-screenshot');
const browserStatus = document.getElementById('browser-status');
const browserTestName = document.getElementById('browser-test-name');
const browserLoading = document.getElementById('browser-loading');
const humanLogContainer = document.getElementById('human-log-container');
const technicalLogContainer = document.getElementById('technical-log-container');
const screenshotTimestamp = document.getElementById('screenshot-timestamp');
const logTabs = document.querySelectorAll('.log-tab');

// CodeMirror Editor
let codeMirrorEditor = null;

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

// Output panel elements
const outputPanel = document.getElementById('output-panel');
const toggleOutputBtn = document.getElementById('toggle-output');

// Editor tabs and file explorer (with null checks)
const fileExplorer = document.getElementById('file-explorer');
const fileList = document.getElementById('file-list');
const editorTabsContainer = document.querySelector('.editor-tabs-container');
const editorContent = document.querySelector('.editor-content');
const newTestBtn = document.getElementById('new-test-btn');
const closeAllTabsBtn = document.getElementById('close-all-tabs');
const explorerResizer = document.getElementById('explorer-resizer');

// AI Steps elements
const aiStepsList = document.getElementById('ai-steps-list');
const newAiStepBtn = document.getElementById('new-ai-step-btn');
const aiStepModal = document.getElementById('ai-step-modal');
const aiStepNameInput = document.getElementById('ai-step-name');
const aiStepStepsInput = document.getElementById('ai-step-steps');
const saveAiStepBtn = document.getElementById('save-ai-step-btn');
const cancelAiStepBtn = document.getElementById('cancel-ai-step-btn');
const closeAiStepModal = document.querySelector('.close-ai-step-modal');

let openTabs = []; // Array of {id, name, code, isDirty}
let activeTabId = null;

// Check if file explorer elements exist
const hasFileExplorer = fileExplorer && fileList && editorTabsContainer && newTestBtn && closeAllTabsBtn && explorerResizer;

let currentEditingTest = null;  // Track if we're editing an existing test
let currentRecordingId = null;  // Track active recording
let pendingCodegenTest = null;  // Track test info from codegen
let currentEditingAiStep = null;  // Track if we're editing an existing AI step
let currentRunningTestFilename = null;  // Track which saved test is currently running

let isTestRunning = false;

// Helper function to update browser status
function updateBrowserStatus(status, text) {
    if (!browserStatus) return;

    // Remove all status classes
    browserStatus.className = 'status-badge';

    // Add new status class
    browserStatus.classList.add(`status-${status.toLowerCase()}`);
    browserStatus.textContent = text || status.toUpperCase();
}

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
    // Hide loading state and show screenshot
    if (browserLoading) {
        browserLoading.classList.remove('active');
    }
    if (browserScreenshot) {
        browserScreenshot.style.display = 'block';
    }

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
        updateBrowserStatus('passed', 'PASSED');
    } else if (content.includes('TEST FAILED:')) {
        const statusMsg = content.match(/TEST FAILED:.*$/)?.[0] || content;
        addLogEntry('error', `❌ ${content}`, `❌ ${statusMsg}`);
        updateBrowserStatus('failed', 'FAILED');
    } else if (content.includes('TEST ERROR:')) {
        const statusMsg = content.match(/TEST ERROR:.*$/)?.[0] || content;
        addLogEntry('error', `⚠️ ${content}`, `⚠️ ${statusMsg}`);
        updateBrowserStatus('error', 'ERROR');
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

    if (data.status === 'success') {
        updateBrowserStatus('passed', 'PASSED');
        addLogEntry('success', '✅ Test completed successfully!', '🎉 Test completed!');
    } else if (data.status === 'stopped') {
        updateBrowserStatus('stopped', 'STOPPED');
        addLogEntry('error', '⏹ Test stopped by user', '⏹ Test stopped');
    } else {
        updateBrowserStatus('failed', 'FAILED');
        const errorMsg = data.message || 'Unknown error';
        addLogEntry('error', `❌ Test failed: ${errorMsg}`, `❌ Test failed`);
    }

    // Update saved test status if this was a saved test run
    if (currentRunningTestFilename) {
        fetch(`/api/saved-tests/${currentRunningTestFilename}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: data.status })
        })
        .then(() => {
            // Reload file explorer to show updated status
            if (hasFileExplorer) {
                loadFileExplorer();
            }
            currentRunningTestFilename = null;
        })
        .catch(err => console.error('Error updating test status:', err));
    }
});

socket.on('ai_step_complete_with_code', (data) => {
    // AI step completed successfully - prompt user to save generated code
    isTestRunning = false;
    updateBrowserStatus('passed', 'PASSED');
    addLogEntry('success', '✅ AI Step completed successfully!', '🎉 AI Step completed!');

    // Show confirmation dialog
    const aiStepName = data.ai_step_name;
    const suggestedTestName = `${aiStepName} - Generated Test`;

    if (confirm(`✅ AI Step "${aiStepName}" completed successfully!\n\nWould you like to save the generated Playwright code as a new test?`)) {
        // User wants to save - prompt for test name
        const testName = prompt('Enter a name for the generated test:', suggestedTestName);

        if (testName && testName.trim()) {
            // Save the generated code as a new test
            fetch('/api/save-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: testName.trim(),
                    code: data.code,
                    source: 'ai_step'
                })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    addLogEntry('success', `💾 Saved generated test: ${testName}`);

                    // Reload file explorer
                    if (hasFileExplorer) {
                        loadFileExplorer();
                    }

                    // Open the new test in a tab
                    openTab(result.filename, testName, data.code, 'test');
                } else {
                    alert('Error saving test: ' + (result.error || 'Unknown error'));
                }
            })
            .catch(err => {
                alert('Failed to save test: ' + err);
            });
        }
    } else {
        // User declined - just show the regular test_complete event
        addLogEntry('info', 'Generated code not saved (you can still see it in the editor)');
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

    addLogEntry('success', '✅ Recording complete! Code generated.', '✅ Recording complete!');

    // Scroll to code section
    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        editorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
});

socket.on('codegen_error', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Error';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = '#ef4444';

    addLogEntry('error', `❌ Recording failed: ${data.message}`, '❌ Recording failed');

    alert(`Recording failed:\n${data.message}`);
});

// UI Event Handlers
// Record, Run Test, Load Example, and Refresh buttons removed - use AI Steps section and file explorer instead

// Run Test and Stop Test buttons removed - use AI Steps section instead

// Load Example button removed - use AI Steps section instead

clearLogBtn.addEventListener('click', () => {
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    addLogEntry('info', 'Log cleared');
});

// Save current test - used by Cmd+S keyboard shortcut and context menu
function saveCurrentTest() {
    const code = getPlaywrightCode();
    if (!code) {
        alert('No code to save!');
        return;
    }

    // Check if we're editing an existing tab
    // Temporary tabs start with: 'new_', 'generated_', or 'chat_'
    if (activeTabId && !activeTabId.startsWith('new_') && !activeTabId.startsWith('generated_') && !activeTabId.startsWith('chat_')) {
        // Updating existing saved test
        const tab = openTabs.find(t => t.id === activeTabId);
        if (!tab) return;

        // Handle AI Step saves
        if (tab.fileType === 'ai-step') {
            if (!confirm(`Save changes to AI Step "${tab.name}"?`)) return;

            fetch(`/api/ai-steps/${activeTabId}/markdown`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ markdown: code })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    addLogEntry('success', `💾 Saved AI Step: ${tab.name}`);
                    tab.isDirty = false;
                    tab.code = code;
                    lastSavedCode = code;
                    renderTabs();
                    loadAiSteps();
                } else {
                    alert('Error saving: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => alert('Error saving: ' + err));

            return;
        }

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

                // Close old tab if it was a temporary tab (new, generated, or chat)
                if (activeTabId && (activeTabId.startsWith('new_') || activeTabId.startsWith('generated_') || activeTabId.startsWith('chat_'))) {
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
}

// Refresh and load saved tests functions removed - file explorer handles this now

function runSavedTest(filename, name) {
    if (isTestRunning) {
        alert('A test is already running. Please wait for it to finish.');
        return;
    }

    // Track the running test for status update
    currentRunningTestFilename = filename;

    // Clear previous results
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';

    addLogEntry('info', `🚀 Running: ${name} (no AI tokens used!)`, `🚀 Running: ${name}`);
    isTestRunning = true;

    // Update browser header with test name and status
    if (browserTestName) {
        browserTestName.textContent = name;
    }
    updateBrowserStatus('running', 'RUNNING');

    // Show loading state in browser preview
    if (browserLoading) {
        browserLoading.classList.add('active');
        browserLoading.querySelector('.loading-text').textContent = 'Starting browser...';
        browserLoading.querySelector('.loading-subtext').textContent = 'Initializing Playwright session';
    }
    if (browserScreenshot) {
        browserScreenshot.style.display = 'none';
    }

    // Automatically open browser sidebar
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
        toggleBrowserBtn.classList.add('active');
    }

    // Automatically open output panel to show logs
    openOutputPanel();

    socket.emit('run_saved_test', { filename });
}

// Tab Management Functions
function openTab(filename, name, code, fileType = 'test') {
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
        isDirty: false,
        fileType: fileType  // 'test' or 'ai-step'
    });

    // Hide welcome page before switching to tab
    hideWelcomePage();

    renderTabs();
    switchToTab(filename);
    saveTabsState();  // Save state when opening a new tab
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
    saveTabsState();  // Save state when closing a tab
}

function switchToTab(filename) {
    const tab = openTabs.find(t => t.id === filename);
    if (!tab) return;

    activeTabId = filename;
    lastSavedCode = tab.code;  // Set lastSavedCode to prevent false dirty flag
    setPlaywrightCode(tab.code);

    // Set CodeMirror mode based on file type
    if (codeMirrorEditor) {
        const mode = tab.fileType === 'ai-step' ? 'markdown' : 'python';
        codeMirrorEditor.setOption('mode', mode);
    }

    if (editorContent) editorContent.classList.remove('empty');
    hideWelcomePage();
    renderTabs();
    updateFileListActiveState();
    saveTabsState();  // Save state when switching tabs
}

// Tab State Persistence Functions
function saveTabsState() {
    try {
        const tabsState = {
            openTabs: openTabs.map(tab => ({
                id: tab.id,
                name: tab.name,
                fileType: tab.fileType  // Save file type
                // Don't save code or isDirty, we'll reload fresh from files
            })),
            activeTabId: activeTabId
        };
        localStorage.setItem('editorTabsState', JSON.stringify(tabsState));
    } catch (err) {
        console.error('Error saving tabs state:', err);
    }
}

async function restoreTabsState() {
    try {
        const savedState = localStorage.getItem('editorTabsState');
        if (!savedState) return;

        const tabsState = JSON.parse(savedState);
        if (!tabsState.openTabs || tabsState.openTabs.length === 0) return;

        // Restore each tab
        for (const tabInfo of tabsState.openTabs) {
            // Only restore saved test files (not temporary tabs like new_, generated_, chat_)
            if (!tabInfo.id.startsWith('new_') &&
                !tabInfo.id.startsWith('generated_') &&
                !tabInfo.id.startsWith('chat_')) {

                try {
                    // Handle AI step restoration
                    if (tabInfo.fileType === 'ai-step') {
                        const response = await fetch(`/api/ai-steps/${tabInfo.id}/markdown`);
                        if (response.ok) {
                            const data = await response.json();
                            const existingTab = openTabs.find(t => t.id === tabInfo.id);
                            if (!existingTab) {
                                openTabs.push({
                                    id: tabInfo.id,
                                    name: tabInfo.name,
                                    code: data.markdown,
                                    isDirty: false,
                                    fileType: 'ai-step'
                                });
                            }
                        }
                    } else {
                        // Fetch regular test file content
                        const response = await fetch(`/api/saved-tests/${tabInfo.id}`);
                        if (response.ok) {
                            const data = await response.json();

                            // Open the tab (without triggering saveTabsState recursively)
                            const existingTab = openTabs.find(t => t.id === tabInfo.id);
                            if (!existingTab) {
                                openTabs.push({
                                    id: tabInfo.id,
                                    name: tabInfo.name,
                                    code: data.code,
                                    isDirty: false,
                                    fileType: 'test'
                                });
                            }
                        }
                    }
                } catch (err) {
                    console.error(`Error restoring tab ${tabInfo.id}:`, err);
                }
            }
        }

        // Render all tabs
        if (openTabs.length > 0) {
            hideWelcomePage();
            renderTabs();

            // Switch to the previously active tab
            const activeTab = tabsState.activeTabId && openTabs.find(t => t.id === tabsState.activeTabId);
            if (activeTab) {
                switchToTab(tabsState.activeTabId);
            } else {
                // If active tab no longer exists, switch to first tab
                switchToTab(openTabs[0].id);
            }
        }
    } catch (err) {
        console.error('Error restoring tabs state:', err);
    }
}

// Welcome Page Functions
async function showWelcomePage() {
    if (!codeMirrorEditor) return;

    // Fetch statistics
    const stats = await fetchTestStatistics();

    // Create welcome page HTML
    const welcomeHTML = `
        <div class="welcome-page">
            <div class="welcome-header">
                <h1>🤖 AutoGen Web Tester</h1>
                <p class="welcome-subtitle">AI-powered browser automation and testing</p>
            </div>

            <div class="welcome-stats">
                <div class="stat-card">
                    <div class="stat-icon">📝</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.totalTests}</div>
                        <div class="stat-label">Saved Tests</div>
                    </div>
                </div>

                <div class="stat-card stat-success">
                    <div class="stat-icon">✓</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.passedTests}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                </div>

                <div class="stat-card stat-error">
                    <div class="stat-icon">✗</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.failedTests}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon">🤖</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.aiSteps}</div>
                        <div class="stat-label">AI Steps</div>
                    </div>
                </div>
            </div>

            <div class="welcome-actions">
                <h3>Get Started</h3>
                <div class="action-buttons">
                    <button class="action-btn" onclick="document.getElementById('new-test-btn').click()">
                        <span class="action-icon">➕</span>
                        <div>
                            <div class="action-title">New Test</div>
                            <div class="action-desc">Create a new Playwright test</div>
                        </div>
                    </button>
                    <button class="action-btn" onclick="document.getElementById('new-ai-step-btn').click()">
                        <span class="action-icon">🤖</span>
                        <div>
                            <div class="action-title">New AI Step</div>
                            <div class="action-desc">Write tests in natural language</div>
                        </div>
                    </button>
                </div>
            </div>
        </div>
    `;

    // Hide CodeMirror and show welcome page
    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        const cmWrapper = editorElement.querySelector('.CodeMirror');
        if (cmWrapper) cmWrapper.style.display = 'none';

        // Remove existing welcome page if any
        const existingWelcome = editorElement.querySelector('.welcome-page');
        if (existingWelcome) existingWelcome.remove();

        // Insert welcome page
        editorElement.insertAdjacentHTML('beforeend', welcomeHTML);
    }
}

function hideWelcomePage() {
    if (!codeMirrorEditor) return;

    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        const cmWrapper = editorElement.querySelector('.CodeMirror');
        if (cmWrapper) cmWrapper.style.display = '';

        const welcomePage = editorElement.querySelector('.welcome-page');
        if (welcomePage) welcomePage.remove();
    }
}

async function fetchTestStatistics() {
    try {
        // Fetch saved tests
        const testsResponse = await fetch('/api/saved-tests');
        const tests = await testsResponse.json();

        // Fetch AI steps
        const aiStepsResponse = await fetch('/api/ai-steps');
        const aiSteps = await aiStepsResponse.json();

        // Calculate statistics
        const totalTests = tests.length;
        const passedTests = tests.filter(t => t.last_run_status === 'success').length;
        const failedTests = tests.filter(t => t.last_run_status === 'error' || t.last_run_status === 'stopped').length;
        const aiStepsCount = aiSteps.length;

        return {
            totalTests,
            passedTests,
            failedTests,
            aiSteps: aiStepsCount
        };
    } catch (err) {
        console.error('Error fetching statistics:', err);
        return {
            totalTests: 0,
            passedTests: 0,
            failedTests: 0,
            aiSteps: 0
        };
    }
}

function renderTabs() {
    if (!editorTabsContainer) return;

    editorTabsContainer.innerHTML = '';

    // Show welcome page if no tabs are open
    if (openTabs.length === 0) {
        showWelcomePage();
        return;
    }

    openTabs.forEach(tab => {
        const tabEl = document.createElement('div');
        tabEl.className = 'editor-tab' + (tab.id === activeTabId ? ' active' : '') + (tab.isDirty ? ' dirty' : '');

        const icon = tab.fileType === 'ai-step' ? '🤖' : '📄';
        tabEl.innerHTML = `
            <span class="editor-tab-icon">${icon}</span>
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

    // Also highlight active AI step in sidebar
    if (aiStepsList) {
        const aiStepItems = aiStepsList.querySelectorAll('.file-item');
        aiStepItems.forEach(item => {
            const filename = item.dataset.filename;
            if (filename === activeTabId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }
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

                // Status icon based on last run
                let statusIcon = '';
                if (test.last_run_status === 'success') {
                    statusIcon = '<span class="test-status test-status-success" title="Last run: Passed">✓</span>';
                } else if (test.last_run_status === 'error' || test.last_run_status === 'stopped') {
                    statusIcon = '<span class="test-status test-status-error" title="Last run: Failed">✗</span>';
                }

                fileItem.innerHTML = `
                    <span class="file-item-icon">${sourceIcon}</span>
                    <span class="file-item-name">${escapeHtml(test.name)}</span>
                    ${statusIcon}
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
        saveTabsState();  // Save state when closing all tabs
    });
}

// Track code changes to mark tabs as dirty (handled in CodeMirror change event)
let lastSavedCode = '';

// Load file explorer on page load
window.addEventListener('load', () => {
    if (hasFileExplorer) {
        loadFileExplorer();
        loadAiSteps();
        if (editorContent) editorContent.classList.add('empty');
    }
});

// ========================================
// AI STEPS FUNCTIONALITY
// ========================================

async function loadAiSteps() {
    if (!aiStepsList) {
        console.warn('AI steps list element not found');
        return;
    }

    try {
        const response = await fetch('/api/ai-steps');
        const steps = await response.json();

        aiStepsList.innerHTML = '';

        if (steps.length === 0) {
            aiStepsList.innerHTML = '<div class="file-list-empty">No AI steps yet</div>';
            return;
        }

        steps.forEach(step => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.dataset.filename = step.filename;
            item.innerHTML = `
                <span class="file-item-icon">🤖</span>
                <span class="file-item-name">${escapeHtml(step.name)}</span>
                <div class="file-item-actions">
                    <button class="file-item-action" data-action="run" title="Run AI Step">▶</button>
                    <button class="file-item-action" data-action="edit" title="Edit">✏️</button>
                    <button class="file-item-action" data-action="delete" title="Delete">🗑</button>
                </div>
            `;

            // Event listeners
            const runBtn = item.querySelector('[data-action="run"]');
            const editBtn = item.querySelector('[data-action="edit"]');
            const deleteBtn = item.querySelector('[data-action="delete"]');

            runBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                runAiStep(step.filename, step.name);
            });

            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openAiStepInEditor(step.filename, step.name);
            });

            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteAiStep(step.filename, step.name);
            });

            // Click handler for entire item
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.file-item-actions')) {
                    openAiStepInEditor(step.filename, step.name);
                }
            });

            aiStepsList.appendChild(item);
        });
    } catch (err) {
        console.error('Failed to load AI steps:', err);
        aiStepsList.innerHTML = '<div class="file-list-empty">Error loading AI steps</div>';
    }
}

function runAiStep(filename, name) {
    if (isTestRunning) {
        alert('A test is already running');
        return;
    }

    // Clear previous results
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    setPlaywrightCode('');

    // Update UI
    isTestRunning = true;

    // Update browser header with test name and status
    if (browserTestName) {
        browserTestName.textContent = name;
    }
    updateBrowserStatus('running', 'RUNNING');

    // Show loading state in browser preview
    if (browserLoading) {
        browserLoading.classList.add('active');
        browserLoading.querySelector('.loading-text').textContent = 'Running AI steps...';
        browserLoading.querySelector('.loading-subtext').textContent = 'Agent is automating your test';
    }
    if (browserScreenshot) {
        browserScreenshot.style.display = 'none';
    }

    // Open browser sidebar and output panel
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
        toggleBrowserBtn.classList.add('active');
    }
    openOutputPanel();

    // Emit run AI step event
    socket.emit('run_ai_step', { filename });

    addLogEntry('info', `🤖 Running AI steps: ${name}`);
}

function openAiStepInEditor(filename, name) {
    fetch(`/api/ai-steps/${filename}/markdown`)
        .then(res => res.json())
        .then(data => {
            if (data.markdown) {
                openTab(filename, name, data.markdown, 'ai-step');
            }
        })
        .catch(err => {
            alert('Failed to load AI step: ' + err);
        });
}

function showAiStepModal(filename = null, name = '', steps = '') {
    if (!aiStepModal) return;

    currentEditingAiStep = filename;
    aiStepNameInput.value = name;
    aiStepStepsInput.value = steps;
    aiStepModal.style.display = 'block';
}

function editAiStep(filename, name, steps) {
    showAiStepModal(filename, name, steps);
}

async function saveAiStep() {
    const name = aiStepNameInput.value.trim();
    const steps = aiStepStepsInput.value.trim();

    if (!name || !steps) {
        alert('Please enter both name and steps');
        return;
    }

    const method = currentEditingAiStep ? 'PUT' : 'POST';
    const url = currentEditingAiStep
        ? `/api/ai-steps/${currentEditingAiStep}`
        : '/api/ai-steps';

    try {
        const response = await fetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, steps})
        });

        if (response.ok) {
            loadAiSteps();
            aiStepModal.style.display = 'none';
            addLogEntry('success', `💾 AI step saved: ${name}`);
        } else {
            alert('Failed to save AI step');
        }
    } catch (err) {
        alert('Failed to save AI step: ' + err);
    }
}

async function deleteAiStep(filename, name) {
    if (!confirm(`Delete AI step "${name}"?`)) return;

    try {
        const response = await fetch(`/api/ai-steps/${filename}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadAiSteps();
            addLogEntry('info', `Deleted AI step: ${name}`);
        } else {
            alert('Failed to delete AI step');
        }
    } catch (err) {
        alert('Failed to delete AI step: ' + err);
    }
}

// Event Listeners for AI Steps
if (newAiStepBtn) {
    newAiStepBtn.addEventListener('click', () => {
        showAiStepModal();
    });
}

if (saveAiStepBtn) {
    saveAiStepBtn.addEventListener('click', saveAiStep);
}

if (cancelAiStepBtn) {
    cancelAiStepBtn.addEventListener('click', () => {
        aiStepModal.style.display = 'none';
    });
}

if (closeAiStepModal) {
    closeAiStepModal.addEventListener('click', () => {
        aiStepModal.style.display = 'none';
    });
}

// Modal click handlers
window.addEventListener('click', (event) => {
    if (event.target === aiStepModal) {
        aiStepModal.style.display = 'none';
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

// Close browser sidebar when clicking outside (but not on logs)
document.addEventListener('click', (e) => {
    // Only proceed if browser sidebar is open
    if (!browserSidebar.classList.contains('open')) return;

    // Check if click is inside browser sidebar or its toggle button
    const clickInsideBrowser = browserSidebar.contains(e.target);
    const clickOnToggleButton = toggleBrowserBtn.contains(e.target);

    // Check if click is inside output panel (logs)
    const clickInsideLogs = outputPanel.contains(e.target);

    // Close if clicking outside browser AND not on logs
    if (!clickInsideBrowser && !clickOnToggleButton && !clickInsideLogs) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.remove('open');
        codeEditorContainer.classList.remove('browser-open');
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
        toggleBrowserBtn.classList.remove('active');
    }
});

// Output Panel Toggle (VS Code style)
toggleOutputBtn.addEventListener('click', () => {
    outputPanel.classList.toggle('open');
});

// Function to open output panel automatically
function openOutputPanel() {
    if (!outputPanel.classList.contains('open')) {
        outputPanel.classList.add('open');
    }
}

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
// CodeMirror code editor functions
function setPlaywrightCode(code) {
    if (codeMirrorEditor) {
        codeMirrorEditor.setValue(code || '');
    }
}

function getPlaywrightCode() {
    return codeMirrorEditor ? codeMirrorEditor.getValue() : '';
}

// CodeMirror initialization and change tracking
function initializeCodeMirror() {
    if (typeof CodeMirror !== 'undefined') {
        const editorElement = document.getElementById('codemirror-editor');
        if (editorElement && !codeMirrorEditor) {
            codeMirrorEditor = CodeMirror(editorElement, {
                mode: 'python',
                theme: 'material-darker',
                lineNumbers: true,
                indentUnit: 4,
                tabSize: 4,
                indentWithTabs: false,
                lineWrapping: false,
                autofocus: false,
                styleActiveLine: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                extraKeys: {
                    "Cmd-/": "toggleComment",
                    "Ctrl-/": "toggleComment"
                }
            });

            // Listen for content changes
            codeMirrorEditor.on('change', function(cm) {
                if (activeTabId) {
                    const tab = openTabs.find(t => t.id === activeTabId);
                    if (tab) {
                        const currentCode = cm.getValue();
                        if (currentCode !== lastSavedCode) {
                            tab.isDirty = true;
                            tab.code = currentCode;
                            renderTabs();
                        }
                    }
                }
            });
        }
    }
}

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

// Cmd+S (Mac) / Ctrl+S (Windows/Linux) to save file
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault(); // Prevent default browser save dialog
        saveCurrentTest(); // Save current test
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
window.addEventListener('load', async () => {
    addLogEntry('info', '👋 Welcome to AutoGen Web Tester!');
    addLogEntry('info', '🤖 Create AI Steps in the file explorer to run natural language tests');
    addLogEntry('info', '💬 Use AI Chat to generate and modify Playwright code');

    // Initialize CodeMirror editor
    initializeCodeMirror();

    // Restore previously open tabs
    await restoreTabsState();

    // Show welcome page if no tabs are open
    if (openTabs.length === 0) {
        showWelcomePage();
    }
});
