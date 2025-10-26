### FILE: notes/deployment.md
- Create an AMI with Python 3.11 and deploy code
- Use Gunicorn + Uvicorn workers for production: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app -w 4 --bind 0.0.0.0:8000`
- Use nginx as reverse proxy, serve /static directly.
- Ensure writable `static/images/` and backup `items.xlsx` regularly.

### FILE: .env.example
SECRET_KEY=replace_this_super_secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strongpassword

# End of all files