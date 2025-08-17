import http.server
import socketserver
import os
import threading
import main  # импортируем твой бот

PORT = int(os.getenv("PORT", 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("✅ Bot is running!".encode("utf-8"))

def run_web():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌍 Server started on port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    # запускаем бота в фоне
    threading.Thread(target=main.start_bot, daemon=True).start()

    # запускаем веб-сервер
    run_web()
