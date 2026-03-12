import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
from contextlib import contextmanager

# Configuration
APP_USERNAME = os.getenv("APP_USERNAME", "morgane")
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
DB_PATH = os.getenv("DB_PATH", "tasks.db")

app = FastAPI(title="Event Task Manager")

# Security
basic_security = HTTPBasic(auto_error=False)
bearer_security = HTTPBearer(auto_error=False)

# Database
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_name TEXT NOT NULL,
                task_name TEXT NOT NULL,
                description TEXT,
                urls TEXT,
                priority INTEGER NOT NULL DEFAULT 2,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

class TaskCreate(BaseModel):
    salon_name: str
    task_name: str
    description: Optional[str] = None
    urls: Optional[str] = None
    priority: int = 2

class Task(BaseModel):
    id: int
    salon_name: str
    task_name: str
    description: Optional[str]
    urls: Optional[str]
    priority: int
    created_at: str

# Auth functions
def create_token(username: str) -> str:
    """Create a simple token (username:timestamp:signature)"""
    timestamp = datetime.utcnow().isoformat()
    data = f"{username}:{timestamp}"
    signature = secrets.token_urlsafe(32)
    return f"{data}:{signature}"

def verify_token(token: str) -> Optional[str]:
    """Verify token and return username if valid"""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, timestamp, signature = parts

        # Check if token is not too old (7 days)
        token_time = datetime.fromisoformat(timestamp)
        if datetime.utcnow() - token_time > timedelta(days=7):
            return None

        return username
    except Exception:
        return None

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_security)) -> str:
    """Verify bearer token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return username

# Routes
@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login endpoint"""
    username_ok = secrets.compare_digest(request.username, APP_USERNAME)
    password_ok = secrets.compare_digest(request.password, APP_PASSWORD)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_token(request.username)
    return LoginResponse(token=token)

@app.get("/api/tasks", response_model=list[Task])
async def get_tasks(username: str = Depends(require_auth)):
    """Get all tasks"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, salon_name, task_name, description, urls, priority, created_at
            FROM tasks
            ORDER BY priority ASC, created_at DESC
        """)
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            tasks.append(Task(
                id=row["id"],
                salon_name=row["salon_name"],
                task_name=row["task_name"],
                description=row["description"],
                urls=row["urls"],
                priority=row["priority"],
                created_at=row["created_at"]
            ))

        return tasks

@app.post("/api/tasks", response_model=Task)
async def create_task(task: TaskCreate, username: str = Depends(require_auth)):
    """Create a new task"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO tasks (salon_name, task_name, description, urls, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (task.salon_name, task.task_name, task.description, task.urls, task.priority))
        conn.commit()

        task_id = cursor.lastrowid

        cursor = conn.execute("""
            SELECT id, salon_name, task_name, description, urls, priority, created_at
            FROM tasks
            WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        return Task(
            id=row["id"],
            salon_name=row["salon_name"],
            task_name=row["task_name"],
            description=row["description"],
            urls=row["urls"],
            priority=row["priority"],
            created_at=row["created_at"]
        )

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_auth)):
    """Delete a task"""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()

    return {"message": "Task deleted"}

# Static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
