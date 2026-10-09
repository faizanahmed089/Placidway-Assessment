# Deploying to Streamlit Community Cloud

Streamlit Community Cloud runs `streamlit_app.py` straight from the GitHub
repository. It is free, needs no payment card, and visitors need no login.

## 1. Push the code to GitHub

The repository must contain `streamlit_app.py` and `requirements.txt` on the
`main` branch.

## 2. Create the app

1. Open https://share.streamlit.io and sign in with GitHub.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `faizanahmed089/Placidway-Assessment`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`
   - **App URL:** pick a name, for example `placidway-chatbot`
4. Open **Advanced settings**:
   - **Python version:** 3.12 or newer
   - **Secrets:** paste the two lines below with your real values

```toml
GROQ_API_KEY = "your-groq-key"
ADMIN_TOKEN = "your-admin-token"
```

5. Click **Deploy**.

## 3. Check it

1. The first start takes a few minutes: it installs the packages, downloads the
   embedding model and re-checks the 7 pages.
2. Your public URL is `https://YOUR-APP-NAME.streamlit.app`.
3. Open it in a private window (not signed in) and ask a question.
4. Ask the test questions from `test_results.md` and compare the answers.
5. In the sidebar, open **Admin**, enter the admin token and try
   **Refresh content now**.

## Updating later

Push to `main` on GitHub. Streamlit redeploys automatically.

## Keeping it up for 7 days

A free app goes to sleep after a period without visitors. The next visitor
sees a "wake up" page and has to wait while it restarts. Open the URL at least
once a day during the review week so reviewers find it awake.

## If the deployment fails

Open **Manage app** (bottom right of the app page) to see the log, and copy
the error.

## Alternative: Docker

The `Dockerfile` runs the FastAPI version (`app/main.py`) on any Docker host,
on port 7860. It has not been built or tested.
