from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalyticsOut
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def get_analytics(db: Session = Depends(get_db)):
    return analytics_service.compute_analytics(db)
