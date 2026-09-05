from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent import agent
from app.database import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    sess = agent.get_or_create_session(db, req.session_id, req.user_id, req.demo_scenario)
    turn = agent.handle_turn(db, sess, req.user_id, req.message)
    return ChatResponse(session_id=sess.id, order_id=turn.order_id, messages=turn.messages)
