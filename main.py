from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers.tickets import router as ticket_router

app = FastAPI(
    title="Customer Support Ticket Router",
    description="ReAct-based agent for classifying and routing support tickets",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(ticket_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")


@app.get("/health")
def health_check():
    return {"status": "ok"}
