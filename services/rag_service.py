from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from models.schemas import HardSpecsObj, FinalStrategyObj
from config.settings import settings
import os
import httpx
class LightingRAGSystem:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE") or "https://api.siliconflow.cn/v1"
        # 替换为硅基流动的云端 Embedding API
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE") or "https://api.siliconflow.cn/v1",
            model="BAAI/bge-m3",  # 使用智源的 BGE 模型
            http_client=httpx.Client(),
            check_embedding_ctx_length=False,  # 强制关闭本地 token 检查，绕过 tiktoken！
            chunk_size=64
        )
        self.bm25_retriever = None
        self.vector_db = self._prepare_vector_db()
        # 初始化 LLM (DeepSeek)
        self.llm = ChatOpenAI(
            model_name="deepseek-ai/DeepSeek-V3", 
            temperature=0.1,
            openai_api_key=api_key,
            openai_api_base=api_base,
            http_client=httpx.Client() #强制指定同步客户端
        )
        
    def _prepare_vector_db(self):
        # A. 加载 PDF (PyMuPDFLoader 对排版解析最稳)
        loader = PyMuPDFLoader(self.pdf_path)
        data = loader.load()
        print(f"📄 成功加载 PDF，共 {len(data)} 页")
        
        # B. 文档分块 (Chunking)
        # 为什么选 1000？因为国标条文一般很短，1000 能包住一条完整的规定且带上下文
        # chunk_size=100: 每块 100 字。太大会导致噪音多，太小会导致语义丢失。
        # chunk_overlap=100: 相邻两块之间有 100 字重叠，防止重要的标准（如数值）刚好被切断。
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(data)
        print(f"✂️ 成功将 PDF 切分为 {len(chunks)} 个文本块")
        
        if len(chunks) == 0:
            raise ValueError(f"严重错误：从 {self.pdf_path} 中没有提取到任何文本！请检查该 PDF 是否为纯图片扫描件，或者文件路径是否正确。")
        
        self.bm25_retriever = BM25Retriever.from_documents(chunks)
        self.bm25_retriever.k = 10  # 设置返回最相关的 10 条

        import os
        chroma_dir = os.path.expanduser("~/Library/Application Support/LightingSystem/chroma_db")
        os.makedirs(chroma_dir, exist_ok=True)
        # C. 存入向量数据库 (Chroma)
        # persist_directory 会在本地生成一个文件夹，这就是“数据库”
        return Chroma.from_documents(
            documents=chunks, 
            embedding=self.embeddings,
            persist_directory=chroma_dir
        )
    # === 让大模型自动做术语映射 ===
    def normalize_space_name(self, raw_space):
        print(f"🔄 正在标准化术语: '{raw_space}' ...")
        # 利用大模型的知识储备，强制将其映射为国标专业词汇
        prompt = f"""
        你是一位精通《GB 50034-2013 建筑照明设计标准》的专家。
        用户输入了一个建筑空间名称：“{raw_space}”。
        你的任务是：将其严格转换为该国标（特别是表5.2.1至表5.5.1）中出现的最准确、最规范的单一专业术语。
        
        【强制映射示例】：
        - 客厅 / 大厅 / 厅 / 起居空间 -> 起居室
        - 洗手间 / 厕所 / 卫浴 / 盥洗室 -> 卫生间
        - 主卧 / 次卧 / 房间 / 客房 -> 卧室
        - 走廊 / 过道 -> 走道
        
        【规则】：只能输出转换后的标准术语，绝不能包含任何其他文字、解释或标点符号！
        """
        try:
            # 使用大模型直接输出文本
            standard_space = self.llm.invoke(prompt).content.strip()
            print(f"   ✅ 术语映射: '{raw_space}' -> '{standard_space}'")
            return standard_space
        except Exception as e:
            print(f"   ⚠️ 术语映射失败，使用原词: {e}")
            return raw_space
    def ask(self, space_type, style):
        standard_space = self.normalize_space_name(space_type)
        print(f"\n🚀 [阶段 1/3] 开始混合检索: {standard_space} 的国标数据...")
        vector_retriever = self.vector_db.as_retriever(search_kwargs={"k": 10})
        
        # 构建混合检索器 (Hybrid Search)
        # weights=[0.5, 0.5] 表示关键词硬匹配和语义软匹配各占 50% 权重
        # 遇到具体的编号（如 5.2.2）BM25 起主要作用；遇到模糊描述（如 卧室灯光）向量起主要作用。
        ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, vector_retriever],
            weights=[0.5, 0.5] 
        )
        query = f"查询 {standard_space} 照度标准值 显色指数 Ra 照明功率密度"
        # 手动调用检索器获取文档块
        retrieved_docs = ensemble_retriever.invoke(query)
        context = "\n---\n".join([doc.page_content for doc in retrieved_docs])
        print(f"📊 [阶段 2/3] LLM 提取硬指标 (参数剥离)...")
        extract_prompt = f"""
        任务：从以下国标条文中，提取与【{standard_space}】相关的照明参数。

        如果原文没有提到该空间，请将对应字段设为 "标准未明确，需参考经验值"。
        
        参考条文：
        {context}

        【强制要求】：必须严格以 JSON 格式输出，不要包含任何 Markdown 标记 (如 ```json) 和其他解释性文字。
        【强制纪律】：
        1. 如果条文中有明确数值，请提取具体数字。
        2. 如果条文中完全没查到该空间的数据，请严格填入 "无参考文档"。
        3. 严禁照抄占位符，输出必须是纯 JSON。
        {{{{
            "space": "{standard_space}",
            "lux": "具体的照度值或范围",
            "ra": "显色指数要求",
            "standard_id": "该数据所在的表号或条文号（如 表5.2.1）。若无则填'无参考文档'"
        }}}}
        """
        
        extractor_llm = self.llm.with_structured_output(HardSpecsObj)
        # 尝试解析 JSON，加入容错机制（这是体现工程能力的地方）
        try:
            # invoke 直接返回的就是 HardSpecsObj 对象，而不是字符串！
            hard_specs_obj = extractor_llm.invoke(extract_prompt)
            # 转成字典供后续使用
            hard_specs = hard_specs_obj.model_dump()
            print(f"   ✅ 溯源成功 -> {hard_specs.get('standard_id')}: 照度 {hard_specs.get('lux')}, Ra {hard_specs.get('ra')}")
        except Exception as e:
            print(f"   ⚠️ JSON 解析失败，回退到安全模式: {e}")
            hard_specs = {"space": standard_space, "lux": "需参考经验值", "ra": "需参考经验值", "standard_id": "无参考文档"}
        print(f"🎨 [阶段 3/3] 风格融合与方案生成...")
        #一层括号 {python_var}：Python 立刻把变量值塞进去。
        #两层括号 {{langchain_var}}：留给 LangChain 以后塞数据（比如 {{context}} 和 {{question}}）。
        #四层括号 {{{{ json_key: value }}}}：输出真正的 JSON 大括号。
        system_prompt = f"""
        你是一位资深室内建筑照明设计师，熟悉国家相关的《建筑照明设计标准》。
            1. 照度标准值：参考数据库内文件标准。
            2. 色温建议：根据风格匹配（比如3000K-暖色，4000K-自然光，5000K+-冷光）。
            3. 灯具选型：品牌建议使用 Philips, OSRAM 或国内高端如 Opple, NVC等类似品牌。
        【要求】：
        1. 必须在输出中明确标明引用的数据是来自哪一个具体的标准文件，绝对不可混淆。
        2. 基于硬指标和【{style}】风格特点输出方案。
        当用户提供空间和风格时，请严格按照以下标准逻辑输出：
        
        【用户需求】：
        空间类型：{standard_space}
        装修风格：{style}
        【参考国标原文】：
        {context}

        【从数据库提取的不可逾越的硬指标】：
        依据条文：{hard_specs.get('standard_id')}
        照度必须满足：{hard_specs.get('lux')}
        显色指数必须满足：{hard_specs.get('ra')}

        请基于以上硬指标，结合【{style}】风格的特点，输出最终的 JSON 方案：
        {{{{
            "space": "{standard_space}",
            "style": "{style}",
            "standard_id": "{hard_specs.get('standard_id')}",
            "standard_lux": "{hard_specs.get('lux')}",
            "min_lux": "<填入具体的数字，若无则填'无'>",
            "ra_requirement": "{hard_specs.get('ra')}",
            "standard_ra": "{hard_specs.get('ra')}",
            "cct_suggest": "请给出类似 '3000K(具体原因)' 的专业建议",
            "brand_suggest": "推荐灯具品牌",
            "design_logic": "基于风格和国标的设计思路",
            "layout_strategy": "布灯策略（基础照明+重点照明的具体点位）"
        }}}}
        
        【强制要求】：必须严格以 JSON 格式输出，不要包含任何 Markdown 标记 (如 ```json)。
        如果硬指标显示"无参考文档"，说明国标未明确，请依靠你的行业经验生成设计思路，并在设计逻辑中注明。
        """
        print(f"🎨 [阶段 3/4] 风格融合与方案草拟...")
        draft_llm = self.llm.with_structured_output(FinalStrategyObj)
        draft_strategy_obj = draft_llm.invoke(system_prompt)
        draft_strategy = draft_strategy_obj.model_dump()
        print(f"🛡️ [阶段 4/4] 启动专家审计与数据对齐...")
        verification_prompt = f"""
        【任务：照明方案专家评审】
        你现在是资深照明总工程师。请根据《GB 50034-2013》原文和提取的硬指标，对初版方案进行最终审计。
        
        【参考国标原文】：
        {context}
        
        【必须锁死的硬指标】：
        依据条文：{hard_specs.get('standard_id')}
        标准照度：{hard_specs.get('lux')} lx
        显色指数：{hard_specs.get('ra')}
        
        【初版待审方案】：
        {draft_strategy}
        
        【审计规则】：
        1. 数据一致性：如果“初版方案”里的照度或条文号与“硬指标”不符，必须按“硬指标”修正。
        2. 理由丰满度：检查 cct_suggest 是否包含理由，若无请根据【{style}】风格补全。
        3. 逻辑自洽：确保 design_logic 能够解释为何如此布灯。
        
        请输出最终修正后的 JSON 方案。
        """
        auditor_llm = self.llm.with_structured_output(FinalStrategyObj)
        final_output_obj = auditor_llm.invoke(verification_prompt)
        final_dict = final_output_obj.model_dump()
        final_dict["standard_id"] = hard_specs.get('standard_id', "无参考文档")
        final_dict["standard_lux"] = hard_specs.get('lux', "无参考文档")
        final_dict["standard_ra"] = hard_specs.get('ra', "无参考文档")
        # model_dump() 将对象转为标准 Python 字典
        # FastAPI 接收到字典后，会自动将其序列化为完美的 JSON 返回给前端
        required_keys = [
            "space", "style", "standard_id", "standard_lux", "min_lux", 
            "ra_requirement", "standard_ra", "cct_suggest", "brand_suggest", 
            "design_logic", "layout_strategy"
        ]
        
        for k in required_keys:
            val = final_dict.get(k)
            # 如果字段不存在、为 None、或者只输出个空字符串/“无”，全部强行覆盖！
            if val is None or str(val).strip() in ["", "无", "null"]:
                final_dict[k] = "无参考文档"
                
        # 确保空间和风格这两个词不出错
        final_dict["space"] = standard_space
        final_dict["style"] = style
        return final_dict