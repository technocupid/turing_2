### FILE: run.sh
#!/usr/bin/env bash
# Run the app locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000