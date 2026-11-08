from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import json
import socket

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Read from environment variables first (per Part 1 spec)
            app_name = os.environ.get('APP_NAME', 'demo-app')
            version = os.environ.get('VERSION', '1.0.0')
            
            # If ConfigMap is mounted as a volume, read live file updates (per Part 2/3 spec for runtime patches)
            for path, var in [('/etc/config/APP_NAME', 'app_name'), ('/etc/config/VERSION', 'version')]:
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                if var == 'app_name':
                                    app_name = content
                                elif var == 'version':
                                    version = content
                    except Exception:
                        pass
            
            pod = socket.gethostname()
            
            payload = {
                "app": app_name,
                "version": version,
                "pod": pod
            }
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), SimpleHandler)
    print(f"Starting server on port {port}...")
    server.serve_forever()
