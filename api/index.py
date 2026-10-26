"""
Vercel Serverless Function Entrypoint.
Exposes WSGI `app` callable for the @vercel/python runtime.
"""

import sys
import os

# Ensure the root directory is on Python's module search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.routes import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
