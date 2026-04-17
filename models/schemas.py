from pydantic import BaseModel, Field
from typing import Optional
from typing import Any

class UnifiedResponse(BaseModel):
    code: int
    msg: str
    data: Any = None
class HardSpecsObj(BaseModel):
    space: str = Field(description="空间类型")
    lux: str = Field(description="具体的照度值或范围，未明确则输出'需参考经验值'")
    ra: str = Field(description="显色指数要求，未明确则输出'需参考经验值'")

class FinalStrategyObj(BaseModel):
    space: str = Field(description="空间类型")
    style: str = Field(description="装修风格")
    standard_reference: str = Field(description="明确指出引用的具体国标及条文编号，例如'GB 50034-2013 第5.2.2条'或'GB/T 31831-2025 第X条'。没有则填'无'")
    standard_lux: str = Field(description="照度硬指标")
    min_lux: str = Field(description="数值")
    ra_requirement: str = Field(description="显色指数文字要求")
    standard_ra: str = Field(description="显色指数硬指标")
    cct_suggest: str = Field(description="色温建议（结合风格说明原因）")
    brand_suggest: str = Field(description="推荐灯具品牌")
    design_logic: str = Field(description="基于风格和指定国标的设计思路")
    layout_strategy: str = Field(description="布灯策略（基础照明+重点照明的具体点位）")

class LampCreate(BaseModel):
    brand: str
    model: str
    power: float
    color_temp: int

class LampResponse(LampCreate):
    id: str
    model_config = {"from_attributes": True}

class RAGRequest(BaseModel):
    space_type: str
    style: str