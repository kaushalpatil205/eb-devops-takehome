from http.server import BaseHTTPRequestHandler, HTTPServer
import os

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            app_name = os.environ.get('APP_NAME', 'Unknown')
            version = os.environ.get('VERSION', 'Unknown')
            
            response = f"Hello World from {app_name} (Version: {version})\n"
            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), SimpleHandler)
    print(f"Starting server on port {port}...")
    server.serve_forever()
