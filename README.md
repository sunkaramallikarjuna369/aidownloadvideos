# Course Content Downloader

A FastAPI backend with a rich React UI that allows you to login to online course platforms and download all modules with videos and PDFs.

## Features

- Login to course platforms with username/password
- Automatically detect and parse course modules
- Select specific modules to download
- Download videos and PDFs organized by module
- Real-time download progress tracking
- Download all content as a ZIP file
- Beautiful dark-themed UI with purple accents

## Project Structure

```
aidownloadvideos/
├── course-downloader-backend/    # FastAPI backend
│   ├── app/
│   │   └── main.py              # Main API endpoints
│   └── pyproject.toml           # Python dependencies
├── course-downloader-frontend/   # React frontend
│   ├── src/
│   │   └── App.tsx              # Main React component
│   └── package.json             # Node dependencies
└── downloads/                    # Downloaded content directory
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- Google Chrome (for Selenium web scraping)
- pip (Python package manager)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/sunkaramallikarjuna369/aidownloadvideos.git
cd aidownloadvideos
```

### 2. Backend Setup (Using Virtual Environment)

```bash
# Navigate to backend directory
cd course-downloader-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Start the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### Alternative: Backend Setup (Using Poetry)

If you prefer using Poetry:

```bash
cd course-downloader-backend
poetry install
poetry run fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

Open a new terminal:

```bash
# Navigate to frontend directory
cd course-downloader-frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

### 4. Configure Environment (Optional)

Frontend environment variables (`.env` file in frontend directory):

```env
VITE_API_URL=http://localhost:8000
```

## Quick Start (All Commands)

```bash
# Terminal 1 - Backend
cd aidownloadvideos/course-downloader-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd aidownloadvideos/course-downloader-frontend
npm install
npm run dev
```

Then open http://localhost:5173 in your browser.

## Usage

1. Open the frontend in your browser at `http://localhost:5173`

2. Enter your course URL in the "Course URL" field

3. Enter your username/email and password

4. Click "Login & Scan" to authenticate and scan for modules
   - Or click "Scan Only" to scan without full authentication

5. Select the modules you want to download using the checkboxes

6. Click "Download X Modules" to start downloading

7. Monitor the download progress in real-time

8. Once complete, click "Download as ZIP" to get all files

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/api/login` | POST | Login and scan course |
| `/api/scan-page` | POST | Scan page for content |
| `/api/download` | POST | Start download |
| `/api/download/progress/{id}` | GET | Get download progress |
| `/api/download/zip/{id}` | GET | Download as ZIP |
| `/api/sessions` | GET | List active sessions |
| `/api/downloads` | GET | List all downloads |

## Technical Details

### Backend Stack
- FastAPI - Modern Python web framework
- Selenium - Web browser automation
- BeautifulSoup4 - HTML parsing
- WebDriver Manager - Automatic ChromeDriver management

### Frontend Stack
- React 18 with TypeScript
- Vite - Build tool
- Tailwind CSS - Styling
- shadcn/ui - UI components
- Lucide React - Icons

## Troubleshooting

### Chrome/ChromeDriver Issues

If you encounter ChromeDriver errors:

```bash
# Install Chrome on Ubuntu
sudo apt update
sudo apt install -y google-chrome-stable

# Or install Chromium
sudo apt install -y chromium-browser
```

### Port Already in Use

If port 8000 or 5173 is already in use:

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173
lsof -ti:5173 | xargs kill -9
```

### Poetry Not Found

Install Poetry:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

## Notes

- Downloaded files are stored in the `downloads/` directory
- The backend uses in-memory storage for sessions (data is lost on restart)
- Some course platforms may have anti-scraping measures
- Ensure you have permission to download course content

## License

MIT License
