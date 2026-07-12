Study Commander Bot V5 speed patch

Replace these three files in your GitHub repository:

app/db.py
app/services/buttons.py
app/bot.py

What changed:
1. Button configs are cached in memory for 30 seconds instead of hitting the database on every message.
2. Cache is invalidated when admin renames/deletes/restores/adds buttons.
3. PostgreSQL engine now uses a real connection pool.
4. Telegram app builder uses concurrent updates and larger connection pool.

Optional Railway variables:
BUTTON_CACHE_TTL=60
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

After replacing files:
1. Commit to GitHub.
2. Railway -> Redeploy.
3. Test /start and the admin panel.
