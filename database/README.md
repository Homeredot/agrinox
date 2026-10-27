# Database operations

The application database is generated at `backend/agrinox.db` by Alembic.

Backup while the API is stopped:

```powershell
Copy-Item backend\agrinox.db ("backend\backup-" + (Get-Date -Format yyyyMMdd-HHmmss) + ".db")
```

Run `PRAGMA integrity_check;` after restoring a backup and before restarting the API.

