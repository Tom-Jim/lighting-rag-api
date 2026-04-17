# 💡 AI 光环境策略与灯具管理系统 (Lighting RAG & CRUD API)

基于 **FastAPI + LangChain + Vue3 + SQLlite** 构建的智能照明领域综合服务接口。本项目包含两个核心模块：基于真实关系型数据库的灯具信息管理（CRUD），以及基于《建筑照明设计标准》的智能光环境策略生成系统（RAG）。本项目实现了“开箱即用”的本地化部署，内置关系型数据库与向量检索系统。

## ✨ 核心亮点 (Engineering Highlights)

1. **工业级 RAG 架构 (Anti-Hallucination Design)**
   * **智能路由前置**：利用 LLM 自动将用户俗语（如“大厅”）映射为国标专业术语（如“起居室”）。
   * **混合检索 (Hybrid Retrieval)**：结合 `Chroma` (语义向量搜索) 与 `BM25` (TF-IDF 关键词硬匹配)，以 1:1 权重精准命中类似“照度”、“眩光值”等纯数字硬指标条文，从底层阻断大模型幻觉。
   * **多步推理与关注点分离 (CoT & Decoupling)**：抛弃黑盒 QA Chain，手动构建“**文献检索 -> 参数提取 -> 风格融合**”流水线。强制 AI 输出 JSON，将物理硬指标作为系统级常量注入生成模板，彻底分离“参数准确性”与“美学描述”。
   * **自验证回溯 (Self-Correction)**：系统自带“首席审核官”二次校验逻辑，将生成的建议与 Source Documents（原始文档）对撞核查。
   * **兜底防线**：结合 Python 正则提取与空值强制覆写机制，确保前端接收到的 JSON 格式 100% 严密。
2. **规范的后端工程化 (Backend Best Practices)**
   * **ORM 数据映射**：采用 `SQLAlchemy`，杜绝 SQL 注入，实现数据层与逻辑层解耦。
   * **依赖注入连接池**：利用 FastAPI 的 `Depends` 机制按需分配数据库 Session，确保高并发下的连接释放。
3. **跨平台桌面端应用**：使用 PyInstaller 独立打包，内置 Web 服务与 Qt 浏览器核心。用户无需配置 Python 或数据库环境，双击即可运行。
4. **零配置本地持久化**：
   - 弃用臃肿的 MySQL，改用轻量级 **SQLite** 存储灯具数据。
   - 使用本地化的 **ChromaDB** 存储国标切片向量，数据自动持久化至系统的应用缓存目录，安全且防篡改。
## 🛠️ 技术栈 (Tech Stack)

* **前端**: Vue 3 + Element Plus (极速 CDN 构建)
* **后端引擎**: FastAPI, Uvicorn, SQLite, SQLAlchemy
* **AI 与检索**: DeepSeek-V3 (经 SiliconFlow API), LangChain, BM25, ChromaDB, BAAI/bge-m3
* **打包与 GUI**: PyInstaller, PySide6
---
## 🚀 快速使用 (下载即可运行)

1. 前往右侧的 **Releases** 页面。
2. 下载对应操作系统的压缩包（例如 `LightingSystem-macOS.zip`）。
3. 解压后，直接双击 `LightingSystem.app` 即可启动可视化控制台。
*(注：首次生成策略时需请求云端 API，请确保网络通畅。)*

## 💻 开发者本地构建指南
若需二次开发，请确保本地安装 Python 3.11+：
**克隆项目并安装依赖：**
```bash
# 建议在虚拟环境中运行 (如 conda 或 venv)
pip install -r requirements.txt 
# 配置环境变量
# 请在项目根目录创建 .env 文件并填入以下内容：
OPENAI_API_KEY=你的硅基流动API_KEY
OPENAI_API_BASE=你的硅基流动API_BASE
HF_TOKEN=你的HuggingFace_TOKEN
DATABASE_URL=sqlite:///./dummy.db
# 准备知识库文件
请确保项目resources目录下包含国家标准 PDF 文件：GBT31831—2025.pdf或其他PDF文件,但不要存放如文件下50-GB50034-2013.pdf类似的纯图片扫描件,否则将报错。系统启动时会自动进行解析、切片(Chunking) 并构建本地向量数据库。
# 运行测试
python3 desktop_app.py
```

### 接口文档与测试 (API Documentation)
得益于 FastAPI 的特性，项目启动后，直接在浏览器中访问以下地址即可查看可视化的接口文档，并可直接进行在线调试 (Try it out)：

## 👉 UI 测试地址: http://127.0.0.1:8000/ ##

## 主要接口列表：
*** POST /lamps/ - 新增灯具信息（品牌、型号、功率、色温）**

*** GET /lamps/ - 分页查询灯具列表**

*** GET /lamps/{lamp_id} - 精确查询单条灯具**

*** PUT /lamps/{lamp_id} - 更新灯具信息**

*** DELETE /lamps/{lamp_id} - 删除灯具**

*** POST /strategy/ - [核心] 输入空间与风格，基于 RAG 生成专业的光环境策略**

## 日志存放于macOS的~/Library/Caches/LightingSystem