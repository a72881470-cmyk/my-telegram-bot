import http.server
import socketserver
import os

PORT = int(os.getenv("PORT", 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("✅ Bot is running!".encode("utf-8"))

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"🌍 Server started on port {PORT}")
    httpd.serve_forever()
