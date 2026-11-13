"""
TwinOps Asset Management Microservice.
"""

from services.asset.api import router
from services.asset.main import app

__all__ = ["app", "router"]
