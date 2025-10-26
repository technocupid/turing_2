This repository contains a FastAPI backend for a simple home decor store (wooden or acrylic items). The "database" is a single Excel file (items.xlsx). Images are stored on disk (e.g. `static/images/`) and the Excel file stores the image filename(s).


Features:
- CRUD endpoints for items
- Image upload endpoint which saves files to `static/images/` and writes filename to Excel
- Simple JWT-based authentication with roles (user / admin)
- Lightweight admin panel (Jinja2 templates)
- Safe Excel read/write using file locking


### Quickstart
1. Create a Python venv and install requirements:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2. Create directories and an initial Excel file (script included).
3. Run the app:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```


Deployment notes: host on EC2 behind an nginx reverse proxy. Use Gunicorn + Uvicorn workers for production. Ensure `static/images/` is on persistent disk and secured.