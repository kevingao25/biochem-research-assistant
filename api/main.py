from fastapi import FastAPI

# This is the FastAPI application instance.
# Everything — routes, middleware, startup logic — hangs off this object.
app = FastAPI(
    title="Biochem Research Assistant API",
    description="Search and query biochemistry papers for research",
    version="0.1.0",
)


@app.get("/health")
def health():
    """
    Health check endpoint.
    Returns 200 OK when the API is running.
    Used by Docker to know when the container is ready.
    """
    return {"status": "ok"}
