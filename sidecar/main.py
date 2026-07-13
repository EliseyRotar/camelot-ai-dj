import uvicorn
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

# TODO: Add WebSocket endpoint for Tauri communication
