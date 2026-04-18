import os
import sys
from pydantic_settings import BaseSettings
from typing import Optional
# 获取打包后的真实资源路径
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)
class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str]=None
    OPENAI_API_BASE: Optional[str]=None
    HF_TOKEN: Optional[str]=None
    DATABASE_URL: Optional[str]="sqlite:///./dummy.db"
    PDF_PATH: str = "resources/GB500342013.pdf"

    class Config:
        # 动态指定 .env 文件的绝对路径
        env_file = get_resource_path(".env")
        # 加上这行，防止 .env 里有其他无用变量导致报错
        extra = "ignore"

settings = Settings()

# 设置环境变量供底层库使用
# --- 只有值不为 None 时才设置环境变量 ---
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

if settings.OPENAI_API_BASE:
    os.environ["OPENAI_API_BASE"] = settings.OPENAI_API_BASE

if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN

# DATABASE_URL 因为你设置了默认字符串，一般不会报错，但稳妥起见也加上判断
if settings.DATABASE_URL:
    os.environ["DATABASE_URL"] = settings.DATABASE_URL