from typing import Dict, Optional

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str = Field(..., description="Service status", examples=["healthy"])
    message: Optional[str] = Field(None, description="Status message")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status", examples=["ok"])
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    service_name: str = Field(..., description="Service identifier")
    services: Optional[Dict[str, ServiceStatus]] = Field(None, description="Per-service statuses")
