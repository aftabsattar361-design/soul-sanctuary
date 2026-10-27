# Soul Sanctuary Integrated Digital Platform for Research and Community Engagement

FastAPI + PostgreSQL backend, Streamlit + Plotly frontend.
Modules: sign-up/login (JWT), surveys (from the PDF), dashboard, analytics, data, social media.

## 1. Prerequisites
- Python 3.11+ and PostgreSQL for local development.
- Copy `.env.example` to `.env` and set `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`.
- Keep `.env` private; it is ignored by Git. Never use a default or shared admin password.

## 2. Install
```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# frontend (second terminal)
cd frontend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## 3. Run
```bash
cd backend  && uvicorn main:app --reload      # http://localhost:8000/docs
cd frontend && streamlit run app.py           # http://localhost:8501
```
On backend start you should see `Database connected`, `Tables ready (create_all).`, the admin seed line and
`Survey in DB: 2 sections, 25 questions (PDF: 2 sections, 25 questions)`.
With `SEED_DEMO_DATA=true` the first start also bulk-creates the demo data (takes several seconds).

## 4. Logins
- The admin account is seeded from `ADMIN_EMAIL` and `ADMIN_PASSWORD` on first startup.
- Demo users (`demoN@demo.local` / `DemoPass123`) are created only when `SEED_DEMO_DATA=true`; do not enable demo data for a production deployment.
- Anyone can register on the Login/Register page (18+).

## 5. Useful commands
- Remove all demo data: `cd backend && python seed.py --remove-demo`
- Turn demo data off: set `SEED_DEMO_DATA=false` in `.env`.
- Admin-only features: New Survey, Export Report (CSV), add projects, edit social stats, Meta sync.

## Decisions worth knowing
- **Survey Responses chart**: responses to the main questionnaire (first survey with questions), Jan 1 -> now split into 6 equal periods labelled Q1..Q6. Y axis is 0-80 and only grows if the data needs it.
- **Registration growth**: new users per month of the current year; "YTD" is the sum.
- **KPI deltas**: current month vs previous month (registrations, completed responses, entries from projects created that month). "N new" = surveys activated in the last 30 days.
- **Instagram card** follows the screenshot: header "Likes (+1.2k)", heart = Shares, bubble = Comments, people = Followers. Facebook shows likes and "Likes (+980)".
- **Registration is 18+** so the age groups (18-24, 25-34, 35-44, 45+) cover everyone.
- Only active surveys with questions can be taken; one submission per user per survey.
- The "View/Edit" links in the dashboard tables are display only (normal HTML links would reload Streamlit and log you out); use the top navigation.
- Meta sync needs `META_ACCESS_TOKEN` plus `META_FACEBOOK_PAGE_ID` / `META_INSTAGRAM_USER_ID`; without them the stored values are used.
- `render.yaml` defines a Render Blueprint for the API, Streamlit frontend, and PostgreSQL database. The database and web services are paid Render plans; connect this folder from a Git repository, then set the prompted admin password before deploying.
- Demo seeding moves the PDF survey's created date 60 days back so the four named demo surveys are the latest rows in the dashboard table.

## Folder structure
See the tree in the project brief: `backend/` (main, database, model, schemas, auth, seed, route/*) and
`frontend/` (app.py, pages/*, api_client, components, utils, styles.css).
