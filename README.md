# 🤖 AutoGen Web Tester

AI-powered web testing automation with a modern VS Code-style interface. Write tests in natural language or generate them conversationally with AI chat.

## ✨ Features

- **Natural Language Testing** - Write test steps in plain English
- **AI Code Generation** - Chat with AI to generate Playwright code
- **Live Browser Preview** - Watch automation happen in real-time
- **VS Code Interface** - File explorer, tabs, and professional UI
- **Drag & Drop Images** - Upload screenshots for AI analysis
- **Save & Reuse Tests** - No AI tokens needed for saved tests
- **Record Tests** - Playwright codegen integration

## 🚀 Quick Start

### Prerequisites

- Python 3.10-3.13
- OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/autogen-web-tester.git
cd autogen-web-tester

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Run

```bash
python3 web_ui.py
```

Open http://localhost:8080 in your browser.

## 📖 Usage

### Method 1: Natural Language Tests

1. Write test steps in the left panel
2. Click "▶ Run Test"
3. Watch AI automate the browser
4. Get generated Playwright code

### Method 2: AI Chat

1. Click "💬 Chat" button (bottom panel)
2. Type: "Generate code to test login form"
3. AI generates code instantly
4. Save and reuse

### Method 3: Drag & Drop

1. Take a screenshot of a UI
2. Drag to AI Chat
3. AI analyzes and generates code

## 🎨 Interface

```
┌─────────────────┬────────────────────┐
│ Test Steps      │ Live Browser       │
│                 │ Agent Logs         │
└─────────────────┴────────────────────┘
┌────────┬───────────────────────────────┐
│ Tests  │ Code Editor (Tabs)            │
│ 🤖 T1  │ [Your generated code]         │
│ 🎥 T2  │                               │
└────────┴───────────────────────────────┘
```

## 📚 Documentation

- **START.md** - Getting started guide
- **VSCODE_DESIGN.md** - UI design system
- **IMAGE_UPLOAD_GUIDE.md** - Drag & drop images
- **TABS_AND_EXPLORER_GUIDE.md** - File explorer & tabs
- **AI_CHAT_QUICK_START.md** - AI chat usage

## 🛠️ Tech Stack

- **Backend**: Flask + Socket.IO
- **AI**: AutoGen + OpenAI GPT-4o
- **Browser**: Playwright
- **Frontend**: Vanilla JS + Prism.js

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Feel free to open issues or pull requests.

## ⭐ Star this repo if you find it useful!
