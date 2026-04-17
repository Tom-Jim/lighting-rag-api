import os
import sys
if getattr(sys, 'frozen', False):
    # 强制将工作目录切换到打包解压后的真实目录，这样所有的相对路径都能正常工作
    os.chdir(sys._MEIPASS)

# 将日志写入 macOS 缓存目录
log_dir = os.path.expanduser("~/Library/Caches/LightingSystem")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")

sys.stdout = open(log_file, "a", encoding="utf-8")
sys.stderr = open(log_file, "a", encoding="utf-8")
import threading
import uvicorn
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl,QTimer
import socket
# 导入你现有的 FastAPI 实例
# 假设你的 FastAPI 实例在 main.py 中定义为 app
from main import app as fastapi_app

def run_server():
    # 以后台静默方式运行 FastAPI
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("光环境策略与灯具管理系统")
        self.resize(1280, 800)
        
        # 内置浏览器视图
        self.browser = QWebEngineView()

        # 刚打开时，展示一个优雅的本地 HTML 加载画面
        loading_html = """
        <body style="display:flex; justify-content:center; align-items:center; height:100vh; background-color:#f8f9fa; font-family:sans-serif;">
            <div style="text-align:center;">
                <h2 style="color:#333;">💡 系统初始化中...</h2>
                <p style="color:#666;">正在加载 AI 模型与国家标准文件，请稍候</p>
            </div>
        </body>
        """
        # 直接指向你的 Swagger 接口地址
        self.browser.setHtml(loading_html)
        self.setCentralWidget(self.browser)

        # 启动一个定时器，每隔 0.1 秒去检查一下后端醒了没
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_server_ready)
        self.check_timer.start(100)

    def check_server_ready(self):
        # 使用 socket 尝试连接 8000 端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            result = sock.connect_ex(('127.0.0.1', 8000))
            
            if result == 0:
                # result 为 0 代表端口通了，后端准备完毕！
                self.check_timer.stop()  # 关掉定时器
                
                # 保险起见，再等 0.1 秒让 FastAPI 完全挂载路由，然后跳转到真实的接口文档界面
                QTimer.singleShot(100, self.load_real_page)

    def load_real_page(self):
        self.browser.setUrl(QUrl("http://127.0.0.1:8000/"))
if __name__ == "__main__":
   # 在后台线程启动 FastAPI 服务
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 启动桌面 GUI
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())