import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import unittest
from burhan.ollama import OllamaClient

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'models':[{'name':'test:7b'}]}).encode())
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        body=json.loads(self.rfile.read(length))
        self.server.last_request=body
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        ans={'status':'answered','answer':'تم','citations':['D01-P1']}
        self.wfile.write(json.dumps({'message':{'content':json.dumps(ans,ensure_ascii=False)}}).encode())

class TestTransport(unittest.TestCase):
    def test_http_json_schema_and_local_model(self):
        with HTTPServer(('127.0.0.1',0), Handler) as srv:
            th=Thread(target=srv.serve_forever,daemon=True)
            th.start()
            try:
                c=OllamaClient('test:7b',base_url=f'http://127.0.0.1:{srv.server_port}')
                self.assertEqual(c.installed_models(),['test:7b'])
                ans=c.chat('system','user')
                self.assertEqual(ans['citations'],['D01-P1'])
                self.assertEqual(srv.last_request['model'],'test:7b')
                self.assertEqual(srv.last_request['options']['temperature'],0)
                self.assertIn('format',srv.last_request)
            finally:
                srv.shutdown()
                th.join(timeout=2)
    def test_reject_remote_endpoint(self):
        with self.assertRaises(ValueError):
            OllamaClient('test:7b','https://remote.example.com')

if __name__=='__main__':unittest.main()
