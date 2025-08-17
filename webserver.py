from http.server import BaseHTTPRequestHandler, HTTPServer
import os

PORT = int(os.getenv("PORT", 8080))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"✅ Bot is running!")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"✅ Web server running on port {PORT}")
    server.serve_forever()
