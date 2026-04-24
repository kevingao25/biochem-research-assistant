from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str = Field(..., description="Service status", examples=["healthy"])
    message: str | None = Field(None, description="Status message")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status", examples=["ok"])
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    service_name: str = Field(..., description="Service identifier")
    services: dict[str, ServiceStatus] | None = Field(None, description="Per-service statuses")
