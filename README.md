# CodeFlow

AI-powered Control Flow Graph (CFG) Generator and Static Code Analysis System for Python Programs.

---

# 📌 Project Overview

CodeFlow is a Final Year Project designed to perform:

- Control Flow Graph (CFG) generation from Python source code
- Static code analysis using Abstract Syntax Tree (AST)
- Cyclomatic Complexity calculation
- Cognitive Complexity calculation
- Nesting Depth analysis
- Data Flow Analysis
- Code Smell Detection
- AI-based code explanation
- AI-based refactoring suggestions
- AI-assisted partial automated refactoring

The system provides both:
- Interactive frontend visualization
- Backend analysis APIs

---

# 🚀 Features

## ✅ Control Flow Graph Generation
- Generates CFG from Python code using AST parsing
- Detects:
  - Sequential flow
  - Conditional branches
  - Loops
  - Function definitions
  - Nested blocks
  - Return statements

## ✅ Static Code Analysis
- Cyclomatic Complexity
- Cognitive Complexity
- Nesting Depth
- Halstead Metrics
- Data Flow Analysis
- Hotspot Detection
- Unreachable Code Detection

## ✅ AI Features
Integrated with Google Gemini API for:
- CFG explanations
- Code understanding
- Refactoring suggestions
- AI-based code improvement

## ✅ Visualization
- Interactive CFG rendering
- Node-based graph structure
- Block numbering support (B1, B2, B3...)

## ✅ Authentication System
- JWT Authentication
- Access Tokens
- Refresh Tokens

## ✅ Database Support
- PostgreSQL database integration
- Persistent analysis storage

---

# 🛠️ Tech Stack

## Backend
- FastAPI
- Python
- SQLAlchemy
- Pydantic
- Uvicorn

## Database
- PostgreSQL

## AI Integration
- Google Gemini API

## Deployment
- Render (Backend)
- Vercel (Frontend)
- Azure PostgreSQL Flexible Server

---

# 📂 Project Structure

```bash
CFG-Generator/
│
├── backend/
│   ├── ai/
│   ├── cfg_logic/
│   ├── models/
│   ├── auth.py
│   ├── database.py
│   ├── db_models.py
│   ├── dependencies.py
│   ├── main.py
│   └── ...
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── ...
```

---

# ⚙️ System Workflow

```text
Source Code
    ↓
AST Parsing
    ↓
Basic Block Detection
    ↓
CFG Construction
    ↓
Complexity Analysis
    ↓
Data Flow Analysis
    ↓
AI Processing (Gemini)
    ↓
Visualization & Suggestions
```

---

# 📊 Metrics Supported

The project computes:

- Cyclomatic Complexity
- Nesting Depth
- Halstead Metrics
- Maintainability Indicators

---

# 🔐 Authentication

The backend uses JWT Authentication with:

- Access Token
- Refresh Token
- Protected Endpoints

---

# 🧠 AI Integration

Google Gemini API is used for:

- Code explanation
- CFG explanation
- Refactoring suggestions
- Code optimization recommendations

Model used:

```text
gemini-2.5-flash
```

---

# 💾 Database Configuration

Database used:

```text
PostgreSQL
```

The backend connects using SQLAlchemy ORM.

---

# 📦 Dependencies

Main dependencies used:

```text
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pydantic
python-dotenv
python-jose
passlib
google-generativeai
networkx
matplotlib
```

---

# 🔧 Installation & Setup

## 1️⃣ Clone Repository

```bash
git clone <repository-url>
cd CFG-Generator
```

---

## 2️⃣ Backend Setup

Create virtual environment:

```bash
python -m venv .venv
```

Activate environment:

### Windows
```bash
.venv\Scripts\activate
```

### Linux/Mac
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 3️⃣ Configure Environment Variables

Create `.env` file inside backend directory.

Example:

```env
DATABASE_URL=your_database_url
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

---

## 4️⃣ Run Backend Server

```bash
uvicorn backend.main:app --reload
```

Backend runs on:

```text
http://127.0.0.1:8000
```

---

# 🌐 Deployment

## Backend Deployment
- Render

## Frontend Deployment
- Vercel

## Database Hosting
- Azure PostgreSQL Flexible Server

---

# 📈 Future Scope

- Multi-language CFG support
  - Java
  - C++
  - JavaScript
- AI-generated test cases
- Advanced automated refactoring
- CFG path simulation

---

# 📸 Project Outputs

The system generates:
- CFG diagrams
- Complexity reports
- Refactoring suggestions
- AI explanations
- Static analysis summaries

---

# 📄 License

This project is developed for academic and educational purposes.
