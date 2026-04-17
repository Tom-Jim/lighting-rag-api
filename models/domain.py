from sqlalchemy import Column, String, Float, Integer
from models.database import Base

class LampDB(Base):
    """
    灯具数据库模型
    """
    __tablename__ = "lamps"

    # 主键 ID 使用 UUID 字符串
    id = Column(String(50), primary_key=True, index=True)
    # 品牌
    brand = Column(String(50), index=True)
    # 型号
    model = Column(String(100))
    # 功率 (W)
    power = Column(Float)
    # 色温 (K)
    color_temp = Column(Integer)