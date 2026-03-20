# Digi Doctor — Deployment Guide

## Local Setup (Development)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up MySQL database
```bash
mysql -u root -p < database.sql
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in your DB credentials and SECRET_KEY
```

### 4. Run locally
```bash
python app.py
# Visit http://localhost:5000
```

### Default credentials (change after first login!)
- Admin:       username=admin      / password=Admin@123
- Receptionist: username=reception1 / password=Recept@123

---

## Production Deployment: Render (App) + Railway (Database)

### Step 1 — Database on Railway
1. Go to https://railway.app → New Project → MySQL
2. Copy the connection details (host, port, user, password, database)
3. In the Railway MySQL shell, run:
   ```sql
   source database.sql
   ```

### Step 2 — Backend on Render
1. Push your code to GitHub
2. Go to https://render.com → New → Web Service
3. Connect your GitHub repo
4. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
5. Add Environment Variables:
   ```
   SECRET_KEY       = <generate a random 32+ char string>
   FLASK_ENV        = production
   DB_HOST          = <railway host>
   DB_USER          = <railway user>
   DB_PASSWORD      = <railway password>
   DB_NAME          = railway
   DB_PORT          = <railway port>
   ```
6. Deploy → Render gives you a public URL like `https://digi-doctor.onrender.com`

### Step 3 — After Deployment
1. Visit your Render URL
2. Go to `/login` → login with admin credentials
3. Change the default passwords immediately

---

## Architecture Summary

```
Patient (public)          Receptionist/Admin (login required)
     |                              |
     ↓                              ↓
  /  (homepage)              /login → /receptionist
  /doctors-page                      (dashboard)
  /#book (booking form)
     |                              |
     └──────────┬───────────────────┘
                ↓
          Flask Backend (Render)
                ↓
          MySQL (Railway)
```

## Security Checklist
- [x] Passwords hashed with bcrypt
- [x] DB credentials in .env (never in code)
- [x] Login required for receptionist/admin routes
- [x] Double-booking prevented at DB level (UNIQUE constraint)
- [x] Role-based access (admin vs receptionist)
- [ ] Add HTTPS (Render provides this automatically)
- [ ] Rotate SECRET_KEY in production
- [ ] Change default user passwords after first login
