import os
import httpx
from config.settings import settings
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from models.database import get_db
from models.domain import LampDB
from models.schemas import LampCreate, LampResponse, RAGRequest

router = APIRouter()
rag_system = None
# 检查配置状态的接口
@router.get("/config/status")
async def get_config_status():
    is_ready = all([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_API_BASE"),
        os.getenv("HF_TOKEN"),
        os.getenv("DATABASE_URL")
    ])
    return {"is_configured": is_ready}

# 保存配置并激活系统的接口
@router.post("/config/save")
def save_config(config: dict = Body(...)):
    global rag_system
    try:
        # 动态注入环境变量到当前进程
        os.environ["OPENAI_API_KEY"] = config.get("OPENAI_API_KEY", "")
        os.environ["OPENAI_API_BASE"] = config.get("OPENAI_API_BASE", "") or "https://api.siliconflow.cn/v1"
        os.environ["HF_TOKEN"] = config.get("HF_TOKEN", "")
        os.environ["DATABASE_URL"] = config.get("DATABASE_URL", "")
        
        # 验证必填项
        if not os.environ["OPENAI_API_KEY"] or not os.environ["HF_TOKEN"]:
            raise ValueError("API Key 和 Token 不能为空")
        # 关键：在这里才真正触发 RAG 的初始化
        from services.rag_service import LightingRAGSystem
        from config.settings import settings
        # 立即触发 RAG 系统初始化（因为现在有了 Key）
        print("⚙️ 收到前端配置，正在动态初始化 RAG 系统...")
        print("⚙️ 正在执行向量化（这一步需要联网）...")
        rag_system = LightingRAGSystem(settings.PDF_PATH)
        
        return {"status": "success", "message": "配置已生效"}
    except Exception as e:
        print(f"❌ RAG 初始化崩溃详情: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
def init_rag():
    global rag_system
    # 启动时仅打印状态，绝对不要 raise HTTPException
    if os.path.exists(settings.PDF_PATH):
        if os.getenv("OPENAI_API_KEY"):
            print(f"检测到环境变量，正在加载 RAG 系统...")
            try:
                from services.rag_service import LightingRAGSystem
                rag_system = LightingRAGSystem(settings.PDF_PATH)
            except Exception as e:
                print(f"RAG 初始化失败: {e}")
                rag_system = None
        else:
            print("💡 环境变量缺失，等待用户通过前端配置...")
            rag_system = None
    else:
        print(f"警告：未找到 PDF 文件 {settings.PDF_PATH}")
# --- 业务接口：AI 光环境策略 ---
@router.post("/strategy/", summary="制定策略")
def generate_strategy(req: RAGRequest):
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
