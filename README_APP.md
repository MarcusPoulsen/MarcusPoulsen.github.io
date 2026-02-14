# Power Usage & Cost Monitor

A simple web app to monitor your household electricity usage and costs using data from Eloverblik API and electricity prices from Elprisenligenu.

## Features

- 📊 Input your Eloverblik refresh token
- 📈 View hourly power usage for the last 30 days
- 💰 See electricity costs with real-time price data
- 📋 Download data as CSV
- 📅 Daily and hourly summaries
- 🔒 Token is never stored - only used for this session

## Local Setup

1. **Clone the repo and navigate to the directory:**
```bash
cd /Users/marcuspoulsen/MarcusPoulsen.github.io
```

2. **Install dependencies:**
```bash
conda install -c conda-forge streamlit plotly pandas requests
# OR
pip install -r requirements.txt
```

3. **Run the app:**
```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## How to Use

1. Get your Eloverblik refresh token from https://eloverblik.dk
2. Paste it into the app (it won't be stored)
3. Click "Fetch Data"
4. View your power usage and costs for the last 30 days
5. Download the data as CSV if needed

## Deploy to the Web (Free Options)

### Option 1: Streamlit Cloud (Easiest)

1. Push your code to GitHub
2. Go to https://streamlit.io/cloud
3. Click "New app" and select your repository
4. Set `app.py` as the main file
5. Deploy! (It's free and takes 2 minutes)

Your app will be at: `https://[your-username]-[repo-name].streamlit.app/`

### Option 2: Railway.app

1. Create account at https://railway.app
2. Connect your GitHub repo
3. Create a new project and select your repo
4. Railway will auto-detect Streamlit and deploy it

### Option 3: Heroku

1. Create a `Procfile`:
```
web: streamlit run app.py --server.port=$PORT --server.headless true
```

2. Deploy:
```bash
heroku create your-app-name
git push heroku main
```

## Architecture

- **Frontend:** Streamlit (Python web framework)
- **APIs Used:**
  - Eloverblik API: Fetch power usage data
  - Elprisenligenu API: Fetch electricity prices
- **Data Processing:** Pandas DataFrames

## Files

- `app.py` - Main Streamlit web application
- `fetch_power_data.py` - Standalone script to fetch power data
- `get_prices.py` - Standalone script to fetch price data
- `requirements.txt` - Python dependencies

## Security Notes

- Your token is **never stored** in the app
- It's only used to fetch data for your current session
- You can revoke tokens anytime from the Eloverblik portal
- The token field uses `type='password'` to hide input

## License

Free to use and modify
