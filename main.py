import os, shutil, sqlite3, zipfile, socket, json
from flask import Flask, request, send_from_directory, render_template_string, abort, redirect, url_for
from flask_cors import CORS
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QListWidget, QFileDialog, QTextBrowser, QHBoxLayout
)
from multiprocessing import Process
from werkzeug.utils import secure_filename

# === Константы ===
ROOT = "D:/AIWebHost/servers"
DB = "D:/AIWebHost/servers.db"
SAVE_FILE = "D:/AIWebHost/servers.json"
os.makedirs(ROOT, exist_ok=True)

# === Инициализация базы данных ===
def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                name TEXT UNIQUE, mode TEXT, max_gb REAL,
                port INTEGER, host TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT UNIQUE, password TEXT
            )
        ''')
init_db()

# === Утилита для определения IP ===
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# === Сохранение и загрузка списка серверов ===
def save_server_list(servers):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(servers, f, ensure_ascii=False, indent=2)

def load_server_list():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# === Flask-сервер (функция для процесса) ===
def run_flask(name, mode, max_gb, host, port):
    app = Flask(name)
    CORS(app)

    path = os.path.join(ROOT, name)
    storage = os.path.join(path, "storage")
    site = os.path.join(path, "site")
    os.makedirs(storage, exist_ok=True)
    os.makedirs(site, exist_ok=True)

    def read_site_config():
        config_file = os.path.join(site, "site.conf")
        domain, title, desc = "", "", ""
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("domain="):
                        domain = line.strip().split("=", 1)[1]
                    elif line.startswith("title="):
                        title = line.strip().split("=", 1)[1]
                    elif line.startswith("description="):
                        desc = line.strip().split("=", 1)[1]
        return domain, title, desc

    @app.route("/")
    def home():
        domain, title, desc = read_site_config()
        if mode == "site":
            index = os.path.join(site, "index.html")
            if os.path.exists(index):
                content = open(index, encoding="utf-8").read()
                return content.replace("<title>", f"<title>{title} | ")
            return f"""
                <html><head><title>{title or 'Сайт'}</title><meta name='description' content='{desc}'></head><body>
                <h2>Файл index.html не найден</h2>
                <a href='/site-manager'>Управление сайтом</a> |
                <a href='/settings'>Настройки сайта</a></body></html>
            """
        elif mode == "storage":
            files = os.listdir(storage)
            return render_template_string("""
                <html><head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                body { font-family: sans-serif; padding: 20px; }
                h1 { color: #333; }
                ul { list-style: none; padding: 0; }
                li { margin: 10px 0; }
                a { color: #007BFF; text-decoration: none; font-size: 18px; }
                a:hover { text-decoration: underline; }
                input[type=file], input[type=submit] {
                  width: 100%; padding: 10px; margin-top: 10px; font-size: 16px;
                }
                </style><title>{{name}}</title></head><body>
                <h1>{{name}}: Хранилище</h1>
                <form method="POST" enctype="multipart/form-data" action="/upload">
                    <input type="file" name="files" multiple>
                    <input type="submit" value="Загрузить">
                </form>
                <ul>{% for f in files %}<li><a href="/files/{{f}}">{{f}}</a></li>{% endfor %}</ul>
                </body></html>
            """, name=name, files=files)
        elif mode == "neuro":
            return "<h2>Нейросеть: Введите сообщение</h2><form method='POST' action='/chat'><input name='msg'><input type='submit'></form>"

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        config_file = os.path.join(site, "site.conf")
        domain, title, desc = read_site_config()
        if request.method == "POST":
            domain = request.form.get("domain", domain)
            title = request.form.get("title", title)
            desc = request.form.get("description", desc)
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(f"domain={domain}\n")
                f.write(f"title={title}\n")
                f.write(f"description={desc}\n")
            return redirect("/settings")
        return f"""
            <h2>Настройки сайта</h2>
            <form method='POST'>
                Домен: <input name='domain' value='{domain}'><br>
                Название: <input name='title' value='{title}'><br>
                Описание: <input name='description' value='{desc}'><br>
                <input type='submit' value='Сохранить'>
            </form>
            <a href='/'>Назад</a>
        """

    @app.route("/upload", methods=["POST"])
    def upload():
        files = request.files.getlist("files")
        for file in files:
            filename = secure_filename(file.filename)
            if filename.endswith(".zip"):
                zip_path = os.path.join(storage, filename)
                file.save(zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(storage)
                os.remove(zip_path)
            else:
                file.save(os.path.join(storage, filename))
        return f"<p>Загружено {len(files)} файлов. <a href='/'>Назад</a></p>"

    @app.route("/files/<path:f>")
    def files(f):
        return send_from_directory(storage, f)

    @app.route("/chat", methods=["POST"])
    def chat():
        msg = request.form.get("msg", "")
        return f"<p>ИИ получил: {msg}</p><a href='/'>Назад</a>"

    @app.route("/site-manager")
    def site_manager():
        files = os.listdir(site)
        return render_template_string("""
            <h2>Управление сайтом</h2>
            <form method="POST" enctype="multipart/form-data" action="/upload-site">
                <input type="file" name="files" multiple>
                <input type="submit" value="Загрузить HTML/ZIP">
            </form>
            <h3>Текущие файлы:</h3>
            <ul>{% for f in files %}<li>{{f}}</li>{% endfor %}</ul>
            <a href="/settings">Настройки сайта</a>
        """, files=files)

    @app.route("/upload-site", methods=["POST"])
    def upload_site():
        files = request.files.getlist("files")
        for file in files:
            filename = secure_filename(file.filename)
            save_path = os.path.join(site, filename)
            if filename.endswith(".zip"):
                zip_path = save_path
                file.save(zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(site)
                os.remove(zip_path)
            else:
                file.save(save_path)
        return redirect("/site-manager")

    app.run(host=host, port=port, use_reloader=False)

class GUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Web Host")
        self.layout = QVBoxLayout(self)

        self.server_list = QListWidget()
        self.layout.addWidget(self.server_list)

        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Название сервера")
        self.mode_box = QComboBox(); self.mode_box.addItems(["site", "storage", "neuro"])
        self.port_input = QLineEdit(); self.port_input.setPlaceholderText("Порт")
        self.max_gb_input = QLineEdit(); self.max_gb_input.setPlaceholderText("Макс. ГБ")
        self.layout.addWidget(self.name_input)
        self.layout.addWidget(self.mode_box)
        self.layout.addWidget(self.port_input)
        self.layout.addWidget(self.max_gb_input)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Создать сервер")
        self.stop_btn = QPushButton("Остановить")
        self.del_btn = QPushButton("Удалить")
        self.edit_btn = QPushButton("Редактировать")
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.edit_btn)
        self.layout.addLayout(btn_layout)

        self.output = QTextBrowser()
        self.layout.addWidget(self.output)

        self.processes = {}
        self.servers = load_server_list()
        self.update_list()

        self.start_btn.clicked.connect(self.create_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.del_btn.clicked.connect(self.delete_server)
        self.edit_btn.clicked.connect(self.edit_server)

    def update_list(self):
        self.server_list.clear()
        for s in self.servers:
            self.server_list.addItem(f"{s['name']} [{s['mode']}] http://{s['host']}:{s['port']}")

    def create_server(self):
        name = self.name_input.text().strip()
        mode = self.mode_box.currentText()
        port = int(self.port_input.text().strip()) if self.port_input.text().strip().isdigit() else 5000
        max_gb = float(self.max_gb_input.text().strip()) if self.max_gb_input.text().strip() else 1.0
        host = get_local_ip()

        for s in self.servers:
            if s["name"] == name:
                self.output.append(f"❌ Сервер '{name}' уже существует.")
                return

        self.servers.append({"name": name, "mode": mode, "port": port, "host": host})
        save_server_list(self.servers)
        p = Process(target=run_flask, args=(name, mode, max_gb, host, port))
        p.start()
        self.processes[name] = p
        self.output.append(f"✅ Сервер {name} запущен на http://{host}:{port}")
        self.update_list()

    def stop_server(self):
        current = self.server_list.currentRow()
        if current >= 0:
            name = self.servers[current]["name"]
            if name in self.processes:
                self.processes[name].terminate()
                del self.processes[name]
                self.output.append(f"🛑 Сервер {name} остановлен")

    def delete_server(self):
        current = self.server_list.currentRow()
        if current >= 0:
            name = self.servers[current]["name"]
            if name in self.processes:
                self.processes[name].terminate()
                del self.processes[name]
            del self.servers[current]
            save_server_list(self.servers)
            self.update_list()
            self.output.append(f"🗑️ Сервер {name} удалён")

    def edit_server(self):
        current = self.server_list.currentRow()
        if current >= 0:
            s = self.servers[current]
            self.name_input.setText(s["name"])
            self.port_input.setText(str(s["port"]))
            self.max_gb_input.setText(str(s["max_gb"]))
            index = self.mode_box.findText(s["mode"])
            if index >= 0:
                self.mode_box.setCurrentIndex(index)

if __name__ == "__main__":
    app = QApplication([])
    gui = GUI()
    gui.resize(520, 700)
    gui.show()
    app.exec()
