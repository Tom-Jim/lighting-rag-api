import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.database import get_db
from models.domain import LampDB
from models.schemas import LampCreate, LampResponse, RAGRequest
from services.rag_service import LightingRAGSystem
import os
from config.settings import settings
router = APIRouter()
rag_system = None

def init_rag():
    global rag_system
    # 启动时自动加载 PDF 和向量库，初始化 RAG 系统
    if os.path.exists(settings.PDF_PATH):
        print(f"正在初始化 RAG 系统，加载文件: {settings.PDF_PATH}")
        rag_system = LightingRAGSystem(settings.PDF_PATH)
    else:
        print(f"警告：未找到 PDF 文件 {settings.PDF_PATH}")
# --- 业务接口：AI 光环境策略 ---
@router.post("/strategy/", summary="制定策略")
async def generate_strategy(req: RAGRequest):
    if not rag_system:
        raise HTTPException(status_code=500, detail="RAG 系统未初始化。请检查 PDF 文件是否存在。")
    try:
        strategy = rag_system.ask(req.space_type, req.style)
        return {"space": req.space_type, "style": req.style, "strategy": strategy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略生成失败: {str(e)}")
@router.post("/lamps/", response_model=LampResponse, summary="新增灯具")
async def create_lamp(lamp: LampCreate, db: Session = Depends(get_db)):
    lamp_id = str(uuid.uuid4())
    db_lamp = LampDB(id=lamp_id, **lamp.model_dump())
    db.add(db_lamp)
    db.commit()
    db.refresh(db_lamp)
    return db_lamp
# 其他 CRUD 接口的增删改查
@router.get("/lamps/", response_model=List[LampResponse], summary="获取所有灯具列表")
async def get_lamps(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 支持简单的分页查询
    lamps = db.query(LampDB).offset(skip).limit(limit).all()
    return lamps

@router.get("/lamps/{lamp_id}", response_model=LampResponse, summary="查询单个灯具")
async def get_lamp(lamp_id: str, db: Session = Depends(get_db)):
    lamp = db.query(LampDB).filter(LampDB.id == lamp_id).first()
    if not lamp:
        raise HTTPException(status_code=404, detail="灯具未找到")
    return lamp

@router.put("/lamps/{lamp_id}", response_model=LampResponse, summary="更新灯具信息")
async def update_lamp(lamp_id: str, lamp_update: LampCreate, db: Session = Depends(get_db)):
    db_lamp = db.query(LampDB).filter(LampDB.id == lamp_id).first()
    if not db_lamp:
        raise HTTPException(status_code=404, detail="灯具未找到")
    
    # 更新字段
    db_lamp.brand = lamp_update.brand
    db_lamp.model = lamp_update.model
    db_lamp.power = lamp_update.power
    db_lamp.color_temp = lamp_update.color_temp
    
    db.commit()
    db.refresh(db_lamp)
    return db_lamp

@router.delete("/lamps/{lamp_id}", summary="删除灯具")
async def delete_lamp(lamp_id: str, db: Session = Depends(get_db)):
    db_lamp = db.query(LampDB).filter(LampDB.id == lamp_id).first()
    if not db_lamp:
        raise HTTPException(status_code=404, detail="灯具未找到")
    
    db.delete(db_lamp)
    db.commit()
    return {"message": "删除成功"}
