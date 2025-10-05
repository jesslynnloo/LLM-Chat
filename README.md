# LLM Chat Application

An **LLM-powered conversational web application** built with **FastAPI**, **LangChain**, **Gradio**, and **SQLite**.  
This application allows users to create and manage multiple chat sessions with persistent conversation history.  
It is fully containerized using **Docker Compose** for simple deployment.

---

## Core Features & Tech Stack

- **FastAPI backend** for chat handling and history management  
- **Gradio UI** for an interactive, browser-based chat interface  
- **SQLite database** to persist chat sessions and chat history
- **Streaming LLM responses** for real-time conversation updates  
- **Support for multiple sessions** (create, switch, delete chat session)  
- **Containerized setup** via Docker Compose for easy deployment  
- **Pytest unit tests** for backend functionality  

---

## Architecture Overview


- **Frontend:** Gradio  
- **Backend:** FastAPI + LangChain + OpenAI API  
- **Database:** SQLite 
- **Containerization:** Docker Compose

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker**
- **Docker Compose**
- **Git**
- An **OpenAI API key**

---

## Setup Instructions

### 1️⃣ Clone the Repository

```commandline
git clone https://github.com/jesslynnloo/LLM-Chat.git
cd LLM-Chat
```

### 2️⃣ Set Up Environment Variables

Copy the provided example environment file `.env.example` and rename it to `.env` in the project root directory:

```commandline
cp .env.example .env
```

Then, open the new `.env` file and fill in your own configuration values:

```text
OPENAI_API_KEY = <your_openai_api_key>
OPENAI_MODEL = gpt-5-nano
DB_URL = "sqlite+aiosqlite:///data/chat.db"

API = http://backend:8000
```
The database file (`chat.db`) will be automatically created in the `data/` directory when the application first runs.

### 3️⃣ Build and Start the Application with Docker Compose

From the root folder of your project, run:

```commandline
docker compose build
docker compose up
```
Once built, the services will start automatically.
- Gradio UI: http://127.0.0.1:7860
- FastAPI API Docs: http://127.0.0.1:8000/docs

To stop the containers:

```commandline
docker compose down
```

---

## Using the Application

1. Open the Gradio UI at http://127.0.0.1:7860
2. Create a new chat session or select an existing one from the dropdown.
3. Type your question in the message box and hit Enter or click the ➤ button.
4. The model will stream responses.

You can:
- Create a new chat session
- Clear chat
- Delete the entire chat session

---

## Running Tests (Optional)

To run the backend unit tests **without Docker**:

### 1️⃣ Create and Activate a Virtual Environment

Create a virtual environment in the project **root folder**.

```commandline
python -m venv test_venv
source test_venv/bin/activate
```

### 2️⃣ Install Development Dependencies
```commandline
pip install -r requirements-dev.txt
```

### 3️⃣ Run Tests
Go to the project **root folder**.
```commandline
pytest -v
```

### This will test:

- /health endpoint
- Session creation, deletion
- Chat streaming
- End-to-End workflow
