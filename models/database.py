from sqlalchemy import create_engine, Column, String, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config.settings import settings
import os
# 获取 macOS 的标准应用数据存储路径
data_dir = os.path.expanduser("~/Library/Application Support/LightingSystem")
# 确保文件夹存在
os.makedirs(data_dir, exist_ok=True)
# 将 SQLite 数据库文件存放在这里
db_path = os.path.join(data_dir, "lighting.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

# 初始化 Engine (SQLite 需要 check_same_thread=False)
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# # 数据库连接配置 (根据“大模型光环境策略.py”中的配置)
# # 注意：请确保你的 MySQL 中已创建名为 lighting_db 的数据库
# SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# # 创建数据库引擎
# # pool_recycle: 循环回收连接，防止 MySQL 默认的 8 小时断连问题
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, 
#     pool_recycle=3600,
#     echo=False  # 如果需要调试 SQL 语句，可设为 True
# )

# # 创建会话工厂
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # 创建基类供模型继承
# Base = declarative_base()

# 依赖注入函数：用于在 FastAPI 接口中获取数据库连接
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 初始化数据库表的函数 (通常在 main.py 启动时调用，或者在此处执行一次)
def init_db():
    # 注意：这里导入 LampDB 是为了确保 Base 知道有哪些表需要创建
    from models.domain import LampDB
    Base.metadata.create_all(bind=engine)