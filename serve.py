"""Build and serve the current branch: python serve.py --port 8000."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from build_site import build


def main():
    parser = argparse.ArgumentParser(description='Uruchom katalog Północ z bieżącej gałęzi.')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    output = build()
    handler = partial(SimpleHTTPRequestHandler, directory=str(output))
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        parser.exit(1, f'Nie można uruchomić serwera: {exc}. Spróbuj --port 8001.\n')
    print(f'Północ: http://{args.host}:{args.port} (Ctrl+C kończy pracę)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
