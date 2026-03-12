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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
APP_USERNAME = os.getenv("APP_USERNAME", "morgane")
APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
DB_PATH = os.getenv("DB_PATH", "tasks.db")

# Debug: print config on startup
print(f"[CONFIG] APP_USERNAME: {APP_USERNAME}")
print(f"[CONFIG] JWT_SECRET length: {len(JWT_SECRET) if JWT_SECRET else 'None'}")
print(f"[CONFIG] DB_PATH: {DB_PATH}")

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
        # Salons table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS salons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table with hierarchy support
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_id INTEGER NOT NULL,
                parent_task_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                urls TEXT,
                priority INTEGER NOT NULL DEFAULT 2,
                deadline TIMESTAMP,
                completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (salon_id) REFERENCES salons (id) ON DELETE CASCADE,
                FOREIGN KEY (parent_task_id) REFERENCES tasks (id) ON DELETE CASCADE
            )
        """)

        conn.commit()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str

# Salon models
class SalonCreate(BaseModel):
    name: str
    year: int
    description: Optional[str] = None

class SalonUpdate(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None

class Salon(BaseModel):
    id: int
    name: str
    year: int
    description: Optional[str]
    created_at: str

# Task models
class TaskCreate(BaseModel):
    salon_id: int
    parent_task_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    urls: Optional[str] = None
    priority: int = 2
    deadline: Optional[str] = None

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    urls: Optional[str] = None
    priority: Optional[int] = None
    deadline: Optional[str] = None
    completed: Optional[bool] = None

class Task(BaseModel):
    id: int
    salon_id: int
    parent_task_id: Optional[int]
    name: str
    description: Optional[str]
    urls: Optional[str]
    priority: int
    deadline: Optional[str]
    completed: bool
    created_at: str

# Auth functions
def create_token(username: str) -> str:
    """Create a simple token (username|timestamp|signature)"""
    import hashlib
    import hmac

    timestamp = datetime.utcnow().isoformat()
    data = f"{username}|{timestamp}"
    # Create HMAC signature using JWT_SECRET
    signature = hmac.new(
        JWT_SECRET.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{data}|{signature}"

def verify_token(token: str) -> Optional[str]:
    """Verify token and return username if valid"""
    import hashlib
    import hmac

    try:
        parts = token.split("|")
        if len(parts) != 3:
            print(f"[AUTH] Invalid token format: {len(parts)} parts")
            return None
        username, timestamp, signature = parts

        # Verify signature
        data = f"{username}|{timestamp}"
        expected_signature = hmac.new(
            JWT_SECRET.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            print(f"[AUTH] Invalid signature")
            return None

        # Check if token is not too old (7 days)
        token_time = datetime.fromisoformat(timestamp)
        if datetime.utcnow() - token_time > timedelta(days=7):
            print(f"[AUTH] Token expired")
            return None

        print(f"[AUTH] Token valid for user: {username}")
        return username
    except Exception as e:
        print(f"[AUTH] Token verification error: {e}")
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

# Salon routes
@app.get("/api/salons", response_model=list[Salon])
async def get_salons(username: str = Depends(require_auth)):
    """Get all salons"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, year, description, created_at
            FROM salons
            ORDER BY year DESC, created_at DESC
        """)
        rows = cursor.fetchall()

        salons = []
        for row in rows:
            salons.append(Salon(
                id=row["id"],
                name=row["name"],
                year=row["year"],
                description=row["description"],
                created_at=row["created_at"]
            ))

        return salons

@app.post("/api/salons", response_model=Salon)
async def create_salon(salon: SalonCreate, username: str = Depends(require_auth)):
    """Create a new salon"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO salons (name, year, description)
            VALUES (?, ?, ?)
        """, (salon.name, salon.year, salon.description))
        conn.commit()

        salon_id = cursor.lastrowid

        cursor = conn.execute("""
            SELECT id, name, year, description, created_at
            FROM salons
            WHERE id = ?
        """, (salon_id,))
        row = cursor.fetchone()

        return Salon(
            id=row["id"],
            name=row["name"],
            year=row["year"],
            description=row["description"],
            created_at=row["created_at"]
        )

@app.get("/api/salons/{salon_id}", response_model=Salon)
async def get_salon(salon_id: int, username: str = Depends(require_auth)):
    """Get a salon by ID"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, year, description, created_at
            FROM salons
            WHERE id = ?
        """, (salon_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salon not found"
            )

        return Salon(
            id=row["id"],
            name=row["name"],
            year=row["year"],
            description=row["description"],
            created_at=row["created_at"]
        )

@app.patch("/api/salons/{salon_id}", response_model=Salon)
async def update_salon(salon_id: int, salon: SalonUpdate, username: str = Depends(require_auth)):
    """Update a salon"""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM salons WHERE id = ?", (salon_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salon not found"
            )

        updates = []
        values = []
        if salon.name is not None:
            updates.append("name = ?")
            values.append(salon.name)
        if salon.year is not None:
            updates.append("year = ?")
            values.append(salon.year)
        if salon.description is not None:
            updates.append("description = ?")
            values.append(salon.description)

        if updates:
            values.append(salon_id)
            conn.execute(f"UPDATE salons SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        cursor = conn.execute("""
            SELECT id, name, year, description, created_at
            FROM salons
            WHERE id = ?
        """, (salon_id,))
        row = cursor.fetchone()

        return Salon(
            id=row["id"],
            name=row["name"],
            year=row["year"],
            description=row["description"],
            created_at=row["created_at"]
        )

@app.delete("/api/salons/{salon_id}")
async def delete_salon(salon_id: int, username: str = Depends(require_auth)):
    """Delete a salon"""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM salons WHERE id = ?", (salon_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Salon not found"
            )

        conn.execute("DELETE FROM salons WHERE id = ?", (salon_id,))
        conn.commit()

    return {"message": "Salon deleted"}

# Task routes
@app.get("/api/salons/{salon_id}/tasks", response_model=list[Task])
async def get_salon_tasks(salon_id: int, username: str = Depends(require_auth)):
    """Get all tasks for a salon"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, salon_id, parent_task_id, name, description, urls, priority, deadline, completed, created_at
            FROM tasks
            WHERE salon_id = ?
            ORDER BY completed ASC, priority ASC, created_at DESC
        """, (salon_id,))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            tasks.append(Task(
                id=row["id"],
                salon_id=row["salon_id"],
                parent_task_id=row["parent_task_id"],
                name=row["name"],
                description=row["description"],
                urls=row["urls"],
                priority=row["priority"],
                deadline=row["deadline"],
                completed=bool(row["completed"]),
                created_at=row["created_at"]
            ))

        return tasks

@app.post("/api/tasks", response_model=Task)
async def create_task(task: TaskCreate, username: str = Depends(require_auth)):
    """Create a new task"""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO tasks (salon_id, parent_task_id, name, description, urls, priority, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task.salon_id, task.parent_task_id, task.name, task.description, task.urls, task.priority, task.deadline))
        conn.commit()

        task_id = cursor.lastrowid

        cursor = conn.execute("""
            SELECT id, salon_id, parent_task_id, name, description, urls, priority, deadline, completed, created_at
            FROM tasks
            WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        return Task(
            id=row["id"],
            salon_id=row["salon_id"],
            parent_task_id=row["parent_task_id"],
            name=row["name"],
            description=row["description"],
            urls=row["urls"],
            priority=row["priority"],
            deadline=row["deadline"],
            completed=bool(row["completed"]),
            created_at=row["created_at"]
        )

@app.patch("/api/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task: TaskUpdate, username: str = Depends(require_auth)):
    """Update a task"""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        updates = []
        values = []
        if task.name is not None:
            updates.append("name = ?")
            values.append(task.name)
        if task.description is not None:
            updates.append("description = ?")
            values.append(task.description)
        if task.urls is not None:
            updates.append("urls = ?")
            values.append(task.urls)
        if task.priority is not None:
            updates.append("priority = ?")
            values.append(task.priority)
        if task.deadline is not None:
            updates.append("deadline = ?")
            values.append(task.deadline)
        if task.completed is not None:
            updates.append("completed = ?")
            values.append(1 if task.completed else 0)

        if updates:
            values.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

        cursor = conn.execute("""
            SELECT id, salon_id, parent_task_id, name, description, urls, priority, deadline, completed, created_at
            FROM tasks
            WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        return Task(
            id=row["id"],
            salon_id=row["salon_id"],
            parent_task_id=row["parent_task_id"],
            name=row["name"],
            description=row["description"],
            urls=row["urls"],
            priority=row["priority"],
            deadline=row["deadline"],
            completed=bool(row["completed"]),
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

# Stats route
@app.get("/api/stats")
async def get_stats(username: str = Depends(require_auth)):
    """Get global statistics"""
    with get_db() as conn:
        from datetime import datetime, timedelta

        # Total salons
        cursor = conn.execute("SELECT COUNT(*) as count FROM salons")
        total_salons = cursor.fetchone()["count"]

        # Total tasks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tasks")
        total_tasks = cursor.fetchone()["count"]

        # Incomplete tasks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE completed = 0")
        incomplete_tasks = cursor.fetchone()["count"]

        # Completed tasks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE completed = 1")
        completed_tasks = cursor.fetchone()["count"]

        # Tasks due within 7 days
        seven_days_later = (datetime.now() + timedelta(days=7)).isoformat()
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE completed = 0
            AND deadline IS NOT NULL
            AND deadline <= ?
        """, (seven_days_later,))
        upcoming_deadlines = cursor.fetchone()["count"]

        # Urgent tasks (passed deadline or due today/tomorrow)
        tomorrow = (datetime.now() + timedelta(days=1)).isoformat()
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE completed = 0
            AND deadline IS NOT NULL
            AND deadline <= ?
        """, (tomorrow,))
        urgent_tasks = cursor.fetchone()["count"]

        # Stats per salon
        cursor = conn.execute("""
            SELECT
                s.id,
                s.name,
                s.year,
                COUNT(t.id) as total_tasks,
                SUM(CASE WHEN t.completed = 0 THEN 1 ELSE 0 END) as incomplete_tasks,
                SUM(CASE WHEN t.completed = 0 AND t.deadline IS NOT NULL AND t.deadline <= ? THEN 1 ELSE 0 END) as urgent_tasks,
                SUM(CASE WHEN t.completed = 0 AND t.deadline IS NOT NULL AND t.deadline <= ? THEN 1 ELSE 0 END) as upcoming_tasks
            FROM salons s
            LEFT JOIN tasks t ON s.id = t.salon_id
            GROUP BY s.id, s.name, s.year
            ORDER BY s.year DESC, s.created_at DESC
        """, (tomorrow, seven_days_later))

        salon_stats = []
        for row in cursor.fetchall():
            salon_stats.append({
                "id": row["id"],
                "name": row["name"],
                "year": row["year"],
                "total_tasks": row["total_tasks"] or 0,
                "incomplete_tasks": row["incomplete_tasks"] or 0,
                "urgent_tasks": row["urgent_tasks"] or 0,
                "upcoming_tasks": row["upcoming_tasks"] or 0
            })

        return {
            "total_salons": total_salons,
            "total_tasks": total_tasks,
            "incomplete_tasks": incomplete_tasks,
            "completed_tasks": completed_tasks,
            "upcoming_deadlines": upcoming_deadlines,
            "urgent_tasks": urgent_tasks,
            "salons": salon_stats
        }

# Static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
