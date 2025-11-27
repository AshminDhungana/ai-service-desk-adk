# AI Service Desk Agent

A lightweight **multi-agent system** built using **Google ADK + Gemini**, designed to automate repair intake, troubleshooting, inventory lookup, and ticket status tracking.

This project now supports:

- **Local Demo Mode** (offline)
- **Full Gemini Mode** using ADK Agents through a FastAPI backend
- **Streamlit Chat UI**
- **JSON-based tools** (fully offline compatible)

---

# 🚀 Overview

The **AI Service Desk Agent** simplifies customer support tasks commonly found in electronics/IT service centers:

- 📩 Repair ticket creation  
- 🛠️ Troubleshooting suggestions  
- 📦 Inventory & pricing lookup  
- 📊 Checking repair status  
- 🤖 Multi-agent routing & intent detection  

You can run it:

- Offline using local fallback logic  
- With Gemini using a FastAPI backend  
- Using a real chat UI in Streamlit  

---

# ✨ Key Features

### 🧠 Multi-Agent Architecture
- Router Agent  
- Intake Agent  
- Inventory Agent  
- Status Agent  
- Troubleshooting Agent  

### 🔌 Custom Tools (JSON-based)
- `create_ticket`
- `get_ticket_status`
- `inventory_lookup`

### 🧵 State & Session Management
Works in both:
- Streamlit UI  
- FastAPI backend  

### ☁️ Gemini API Support
Using:
- `.env` for `GOOGLE_API_KEY`
- ADK Python agents
- HTTP endpoint for chat `/chat`

### 🖥️ Streamlit Chat UI
Toggle between:
- **Local Demo Mode**
- **Remote Agent / Gemini Mode**

---

# 📁 Project Structure

```
ai-service-desk/
 ├── main.py                  # FastAPI backend (Gemini-enabled)
 ├── app.py                    # Streamlit chat UI
 ├── run.py                     #Runs Backend as well as Frontend together.       
 ├── src/
 │    ├── router_agent.py
 │    ├── agents/
 │    │     ├── intake_agent.py
 │    │     ├── inventory_agent.py
 │    │     ├── troubleshooting_agent.py
 │    │     └── status_agent.py
 │    └── tools/
 │          ├── create_ticket.py
 │          ├── get_ticket_status.py
 │          └── inventory_lookup.py
 ├── data/
 │    ├── inventory.json
 │    └── tickets.json
 ├── notebooks/
 │    └── ai_service_desk_demo.ipynb
 ├── requirements.txt
 ├── .env.example
 └── README.md
```

---

# 🔑 API Keys (Gemini)

Place your Gemini key inside `.env`:

```
GOOGLE_API_KEY=your_real_key_here
```

`main.py` automatically loads `.env` using:

```
from dotenv import load_dotenv
load_dotenv()
```


# 🛠️ Installation

```
pip install -r requirements.txt
```

---

# ▶️ Running the System

## 1️⃣ Start Backend (Gemini-powered)
```
python main.py
```

Backend runs at:

```
http://localhost:8000
```

Endpoints:
- `GET /health`
- `POST /chat`

---

## 2️⃣ Start Streamlit UI
```
python -m streamlit run app.py
```

Inside the UI:
- Toggle **Use remote agent (HTTP)**
- Set API URL: `http://localhost:8000`

You now have a full AI Service Desk Chat system powered by Gemini.

---

# 🔄 Local Demo Mode (No Gemini)
Streamlit also supports an offline mode using local fallback agents and tools.

---

# 🧪 Example Use Cases

**Repair Intake**
```
"My laptop won't turn on. Can I create a repair ticket?"
```

**Inventory Lookup**
```
"Do you have BrandA A123 laptop in stock?"
```

**Troubleshooting**
```
"My printer shows paper jam even when it's empty."
```

**Check Repair Status**
```
"What's the status of ticket TICKET-1234?"
```

---

# 🧩 Tools Summary

### `create_ticket`
Creates a new repair ticket in `tickets.json`.

### `get_ticket_status`
Looks up an existing ticket.

### `inventory_lookup`
Searches the product inventory in `inventory.json`.

---

# ⭐ Support
If this project helps you, consider ⭐ starring the repository!
