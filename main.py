from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Union
import redis
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

DATABASE_URL = "postgresql://user:password@db:5432/mydb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    completed = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

class Task(BaseModel):
    id: Union[int, None] = None
    title: str
    completed: bool = False

@app.get("/")
def read_root():
    return {"message": "Welcome to the To-Do API! Visit /docs for Swagger UI."}

@app.post("/tasks/", response_model=Task)
def create_task(task: Task):
    db = SessionLocal()
    db_task = TaskDB(title=task.title, completed=task.completed)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    redis_client.delete("tasks")
    db.close()
    return db_task

@app.get("/tasks/", response_model=List[Task])
def get_tasks():
    cached_tasks = redis_client.get("tasks")
    if cached_tasks:
        import json
        return json.loads(cached_tasks)

    db = SessionLocal()
    tasks = db.query(TaskDB).all()
    db.close()

    import json
    redis_client.set("tasks", json.dumps([task.__dict__ for task in tasks]), ex=60)
    return tasks

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    db = SessionLocal()
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    db.close()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: Task):
    db = SessionLocal()
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if db_task is None:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.title = task.title
    db_task.completed = task.completed
    db.commit()
    db.refresh(db_task)
    redis_client.delete("tasks")
    db.close()
    return db_task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    db = SessionLocal()
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if db_task is None:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    redis_client.delete("tasks")
    db.close()
    return {"message": "Task deleted"}