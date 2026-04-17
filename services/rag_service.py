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
class LightingRAGSystem:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        # 替换为硅基流动的云端 Embedding API
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            model="BAAI/bge-m3",  # 使用智源的 BGE 模型
            check_embedding_ctx_length=False  # 强制关闭本地 token 检查，绕过 tiktoken！
        )
        self.bm25_retriever = None
        self.vector_db = self._prepare_vector_db()
        # 初始化 LLM (DeepSeek)
        self.llm = ChatOpenAI(model_name="deepseek-ai/DeepSeek-V3", temperature=0.1)
        
    def _prepare_vector_db(self):
        # A. 加载 PDF (PyMuPDFLoader 对排版解析最稳)
        loader = PyMuPDFLoader(self.pdf_path)
        data = loader.load()
        print(f"📄 成功加载 PDF，共 {len(data)} 页")
        
        # B. 文档分块 (Chunking)
        # 为什么选 500？因为国标条文一般很短，500 能包住一条完整的规定且带上下文
        # chunk_size=500: 每块 500 字。太大会导致噪音多，太小会导致语义丢失。
        # chunk_overlap=50: 相邻两块之间有 50 字重叠，防止重要的标准（如数值）刚好被切断。
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_documents(data)
        print(f"✂️ 成功将 PDF 切分为 {len(chunks)} 个文本块")
        
        if len(chunks) == 0:
            raise ValueError(f"严重错误：从 {self.pdf_path} 中没有提取到任何文本！请检查该 PDF 是否为纯图片扫描件，或者文件路径是否正确。")
        
        self.bm25_retriever = BM25Retriever.from_documents(chunks)
        self.bm25_retriever.k = 3  # 设置返回最相关的 3 条

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
        你是一位精通《建筑照明设计标准》的专家。
        用户输入了一个日常使用的空间名称：“{raw_space}”。
        请将其转换为国标中最准确、最规范的建筑空间术语。
        
        【参考示例】：
        - 客厅 / 大厅 / 厅 -> 起居室
        - 洗手间 / 厕所 / 茅房 -> 卫生间
        - 走廊 / 过道 -> 走道
        - 吃饭的地方 -> 餐厅
        
        【规则】：如果用户输入的词已经很标准（比如“主卧”、“办公室”），则原样输出。
        【强制】：只能输出转换后的标准术语，绝不能包含任何其他文字或标点符号！
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
        vector_retriever = self.vector_db.as_retriever(search_kwargs={"k": 3})
        
        # 构建混合检索器 (Hybrid Search)
        # weights=[0.5, 0.5] 表示关键词硬匹配和语义软匹配各占 50% 权重
        # 遇到具体的编号（如 5.2.2）BM25 起主要作用；遇到模糊描述（如 卧室灯光）向量起主要作用。
        ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, vector_retriever],
            weights=[0.5, 0.5] 
        )
        query = f"查找《建筑照明设计标准》中关于'{standard_space}'（注意同义词如起居室、卫生间等）的照度标准值、显色指数等条文及表格数据。"
        # 手动调用检索器获取文档块
        retrieved_docs = ensemble_retriever.invoke(query)
        context = "\n---\n".join([doc.page_content for doc in retrieved_docs])
        print(f"📊 [阶段 2/3] LLM 提取硬指标 (参数剥离)...")
        extract_prompt = f"""
        任务：从以下国标条文中，严格提取与【{standard_space}】（或其同义词）相关的照明物理参数。
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
            "ra": "显色指数要求"
        }}}}
        """
        
        extractor_llm = self.llm.with_structured_output(HardSpecsObj)
        # 尝试解析 JSON，加入容错机制（这是体现工程能力的地方）
        try:
            # invoke 直接返回的就是 HardSpecsObj 对象，而不是字符串！
            hard_specs_obj = extractor_llm.invoke(extract_prompt)
            # 转成字典供后续使用
            hard_specs = hard_specs_obj.model_dump()
            print(f"   成功提取参数 -> 照度: {hard_specs.get('lux')}, Ra: {hard_specs.get('ra')}")
        except Exception as e:
            print(f"   ⚠️ JSON 解析失败，回退到安全模式: {e}")
            hard_specs = {"space": standard_space, "lux": "需参考经验值", "ra": "需参考经验值"}
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
        {{context}}

        【用户需求】：
        {{question}}

        【从数据库提取的不可逾越的硬指标】：
        照度必须满足：{hard_specs.get('lux')}
        显色指数必须满足：{hard_specs.get('ra')}

        请基于以上硬指标，结合【{style}】风格的特点，输出最终的 JSON 方案：
        {{{{
            "space": "{standard_space}",
            "style": "{style}",
            "standard_id": "<填入具体的标准条文编号，如 GB50034 5.2.2。若原文没写则填'无参考文档'>",
            "standard_lux": "{hard_specs.get('lux')}",
            "min_lux": "<填入具体的数字，若无则填'无'>",
            "ra_requirement": "{hard_specs.get('ra')}",
            "standard_ra": "{hard_specs.get('ra')}",
            "cct_suggest": "色温建议（如3000K，结合风格说明原因）",
            "brand_suggest": "推荐灯具品牌",
            "design_logic": "基于风格和国标的设计思路",
            "layout_strategy": "布灯策略（基础照明+重点照明的具体点位）"
        }}}}
        
        【强制要求】：必须严格以 JSON 格式输出，不要包含任何 Markdown 标记 (如 ```json)。
        如果硬指标显示"无参考文档"，说明国标未明确，请依靠你的行业经验生成设计思路，并在设计逻辑中注明。
        """
        QA_CHAIN_PROMPT = PromptTemplate(
            input_variables=["context", "question"],
            template=system_prompt,
        )

        # 构建 RAG Chain：将搜索到的知识塞进 Prompt
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff", # 简单直接的合并方式
            retriever=ensemble_retriever,
            chain_type_kwargs={"prompt": QA_CHAIN_PROMPT}, # 找最相关的3条
            return_source_documents=True  # 关键：必须返回参考的原文数据
        )
        
        initial_res = qa_chain.invoke(query)
    
        sources = "\n---\n".join([doc.page_content for doc in initial_res['source_documents']])
        answer = initial_res['result']

        # 我们把原始条文和 AI 刚才写的答案都发给它
        verification_prompt = f"""
        【任务：照明设计建议审计】
        你现在的身份是首席审核官。请对比“参考原文”核查“初版建议”。

        [参考原文]：
        {sources}

        [初版建议]：
        {answer}

        要求：
        1. 严谨性核查：初版建议中的照度（Lux）、功率等数值是否在原文中有据可查？数据来源是否准确指明
        2. 幻觉修正：如果原文未提及该空间，必须将描述改为“参考行业经验建议”而非“根据国标标准”。
        3. 输出要求：直接输出修正后的最终专业版本，不要输出审核过程。
        4. 核对草稿中的“照度”与“显色指数”，必须与“依据的原文”一致，违规直接报错。
        5. 原文若无出处，对应的 standard_id、standard_lux 等字段必须保留为“无参考文档”。
        【强制字段填充规则 - 绝不允许留空】：
        1. standard_id (国标条文)：仔细阅读[参考原文]，提取具体的表号或条文号（例如：表5.2.2、第5.3.1条等）。如果原文中完全没有出现任何编号，你必须严格填入 "无参考文档"，绝不允许输出空字符串！
        2. standard_lux (照度)：必须与原文数值严格一致，未找到填 "无参考文档"。
        3. standard_ra (显色指数)：必须与原文数值严格一致，未找到填 "无参考文档"。
        4. 幻觉修正：如果原文未提及该空间，design_logic 必须注明“原文无数据，依据行业经验设计”。
        5. 你必须完整填充 FinalStrategyObj 模型中的所有字段，任何字段不得留空。
        """
    
        # 核心修改点：绑定最终输出的 Pydantic 模型
        auditor_llm = self.llm.with_structured_output(FinalStrategyObj)
        
        # 调用大模型，得到严格的 FinalStrategyObj 对象
        final_output_obj = auditor_llm.invoke(verification_prompt)
        final_dict = final_output_obj.model_dump()
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