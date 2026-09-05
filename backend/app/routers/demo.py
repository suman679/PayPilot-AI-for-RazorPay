from fastapi import APIRouter
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import get_db
from app.models import SimulationRun
from app.services.simulation import run_simulation

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/simulate")
def simulate(num_sessions: int = 100, seed: int = 42):
    """Runs the synthetic batch-session evaluation. Clearly labelled
    SYNTHETIC/SIMULATED in the response - never presented as real
    production performance (section 15)."""
    return run_simulation(num_sessions=num_sessions, seed=seed)


@router.get("/simulate/latest")
def latest_simulation(db: Session = Depends(get_db)):
    run = db.query(SimulationRun).order_by(SimulationRun.created_at.desc()).first()
    if not run:
        return {"note": "No simulation has been run yet. POST /api/demo/simulate first."}
    return {"created_at": run.created_at.isoformat(), **run.results}
