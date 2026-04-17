import uvicorn
from fastapi import FastAPI,Request
import traceback
from fastapi.staticfiles import StaticFiles # 导入静态文件服务
from fastapi.responses import HTMLResponse,JSONResponse
from models.database import engine, Base
from api.routes import router, init_rag
import sys
import os
from config.settings import settings

# 获取打包后的真实资源路径
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)
# 初始化数据库表
Base.metadata.create_all(bind=engine)
app = FastAPI(title="光环境策略与灯具管理系统", version="2.0")

@app.on_event("startup")
async def startup_event():
    try:
        init_rag() # 调用静默初始化
    except Exception as e:
        print(f"启动初始化跳过: {e}")
app.include_router(router)
# 把 / 根路由直接重定向到你的前端页面
# 确保返回 HTMLResponse，防止乱码
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    html_path = get_resource_path("static/index.html")
    try:
        # 直接拿 Python 读文件，不走娇气的 StaticFiles 模块
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        # 如果打包漏了文件，这里会直接在页面上显示具体的路径和原因
        return f"""
        <div style="padding: 40px; font-family: sans-serif;">
            <h1 style="color: red;">⚠️ 前端页面加载失败</h1>
            <p>系统尝试去这里找网页文件，但是没找到：<b>{html_path}</b></p>
            <p>详细报错：{str(e)}</p>
            <p>请检查打包命令中是否带上了 --add-data="static:static"</p>
        </div>
        """
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # 记录详细日志到文件，方便开发者排查
    print(f"🔥 系统崩溃详情: {traceback.format_exc()}") 
    
    # 提取错误信息
    error_msg = str(exc) if str(exc) else "服务器内部未知错误"
    
    # 返回给前端统一的 JSON
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "msg": f"系统故障: {error_msg}",
            "data": None
        }
    )
# 安全挂载 static 文件夹
static_dir = get_resource_path("static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)