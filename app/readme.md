# Decor Store API

Small FastAPI-based backend for a decor store. Uses a simple file-backed (CSV/XLSX) persistence layer for users, products, carts, orders, wishlists and reviews. Tests are included and use a temporary data directory so they can run without modifying local data.

This README covers repo layout, setup, how to run the app, and the main API contracts (including the wishlist and reviews features).

## Project overview

- FastAPI app under `app/`
- File-backed DB layer in `app/database.py`; tables correspond to files in the `data/` directory (CSV by default)
- Simple OAuth2 dependency used in tests where the Bearer token is treated as the user id (replace with proper auth in production)
- Feature highlights:
  - Products (CRUD + images)
  - Carts & Orders
  - Wishlists (per-user)
  - Product Reviews & Ratings

## Requirements

- Python 3.10+
- Windows (development instructions below assume Windows)
- Recommended: virtual environment

## Quick setup (Windows)

1. Create & activate venv:
```bash
python -m venv .venv
.venv\Scripts\Activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Copy or edit `.env` to override defaults:
- `DATA_DIR` — directory for CSV/XLSX files (default `data`)
- Filenames: `USERS_FILE`, `PRODUCTS_FILE`, `ORDERS_FILE`, `CARTS_FILE`, `WISHLISTS_FILE`, `REVIEWS_FILE`

## Run the app (development)

From repo root:
```bash
uvicorn app.main:app --reload
```

Default OpenAPI docs: http://127.0.0.1:8000/docs

## Tests

Run tests with pytest:
```bash
pytest -vv
```

Notes:
- Tests use `tests/conftest.py` which sets up a temporary data directory (no pollution of repo `data/`).
- The test client uses a minimal auth approach: `Authorization: Bearer <user_id>` where the token is interpreted as the user id.

## Data storage

- By default, CSV files live in `data/` (create automatically).
- Table -> file mapping is configurable in `app/config.py` via settings.
- Files used by app (defaults): `users.csv`, `products.csv`, `orders.csv`, `carts.csv`, `wishlists.csv`, `reviews.csv`.

## API (important endpoints)

Authentication note: current test-friendly auth treats the Bearer token as the user id. Replace with real JWT/user lookup for production.

Wishlist (per-user)
- GET /api/wishlist
  - Headers: `Authorization: Bearer <user_id>`
  - Response: 200 JSON array of wishlist items for current user
  - Item shape: `{ "id": "<id>", "user_id": "<user>", "product_id": "<product_id>", "added_at": "..." }`

- POST /api/wishlist
  - Headers: `Authorization: Bearer <user_id>`
  - Body: `{ "product_id": "<id>" }`
  - Success: 201 returns created wishlist item (includes `id`, `user_id`, `product_id`)

- DELETE /api/wishlist/{item_id}
  - Headers: `Authorization: Bearer <user_id>`
  - Success: 204 (only owner may delete; non-owner -> 403)

Reviews & Ratings (per-product)
- POST /api/products/{product_id}/reviews
  - Headers: `Authorization: Bearer <user_id>`
  - Body: `{ "rating": <1-5>, "body": "optional text" }`
  - Success: 201 returns created review: `{ "id", "product_id", "user_id", "rating", "body", "created_at" }`
  - Errors: 400 for invalid rating, 404 if product missing

- GET /api/products/{product_id}/reviews
  - Public in current implementation
  - Returns list of review objects for that product

- GET /api/products/{product_id}/reviews/summary
  - Returns `{ "count": <int>, "average": <float> }` (0/0.0 when no reviews)

- DELETE /api/products/{product_id}/reviews/{review_id}
  - Headers: `Authorization: Bearer <user_id>`
  - Only the review owner may delete (owner -> 204, non-owner -> 403)

Products (summary)
- GET /api/products
- GET /api/products/{product_id}
- POST/PUT/DELETE product endpoints exist and are typically admin-protected in the codebase

Refer to the OpenAPI docs at `/docs` for full schemas.

## Development notes & next steps

- Auth: replace the "token == user_id" stub with proper JWT/lookup (update `app/api/deps.py`).
- Reviews: currently allow multiple reviews per user/product — consider add/update semantics or prevent duplicates.
- Reviews: add pagination, input length checks, and moderation/admin endpoints.
- Wishlists: consider dedup prevention, timestamps, and move-to-cart integration.
- Consider swapping CSV for a real DB for production (Postgres/SQLite) if concurrency and scale matter.

## Contributing

- Follow the existing project layout.
- Add tests for new features and run full test suite.
- Keep changes small and well scoped.

## Troubleshooting

- If uvicorn fails: ensure dependencies installed and Python path points to the project root.
- If tests fail due to file locking: ensure no other processes are holding files in the repo `data/` directory.
