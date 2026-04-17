import os
import sys
from pydantic_settings import BaseSettings
# 获取打包后的真实资源路径
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)
class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_API_BASE: str
    HF_TOKEN: str
    DATABASE_URL: str
    PDF_PATH: str = "resources/GBT31831—2025.pdf"

    class Config:
        # 动态指定 .env 文件的绝对路径
        env_file = get_resource_path(".env")
        # 加上这行，防止 .env 里有其他无用变量导致报错
        extra = "ignore"

settings = Settings()

# 设置环境变量供底层库使用
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = settings.OPENAI_API_BASE
os.environ["HF_TOKEN"] = settings.HF_TOKEN
os.environ["DATABASE_URL"]= settings.DATABASE_URL