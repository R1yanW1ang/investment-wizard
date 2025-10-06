# Investment Wizard

A full-stack web application that scrapes technology news from BBC and CNN, processes them with AI to generate summaries and investment suggestions, and presents them in a modern React dashboard.

## Features

- **Web Scraping**: Automated scraping of BBC and CNN technology sections
- **AI Processing**: LLM-powered article summarization and investment suggestions
- **Background Jobs**: Celery-based task scheduling for daily scraping
- **REST API**: Django REST Framework API for data access
- **Modern Frontend**: React with Vite, React Query, and responsive design
- **Docker Support**: Complete containerization with Docker Compose

## Tech Stack

### Backend
- Django 4.2.7
- Django REST Framework
- MySQL 8.0
- Celery + Redis
- BeautifulSoup4 + Newspaper3k for scraping

### Frontend
- React 18
- Vite
- React Router
- React Query (TanStack Query)
- Lucide React icons
- Axios for API calls

### Infrastructure
- Docker & Docker Compose
- MySQL database
- Redis for Celery broker
- Nginx (optional)

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd investment-wizard
   ```

2. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your configuration
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin

### Manual Setup

1. **Backend Setup**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Set up database
   # Create MySQL database 'investment_wizard'
   # Update settings.py with your database credentials

   # Run migrations
   python manage.py migrate

   # Create superuser
   python manage.py createsuperuser

   # Start Django server
   python manage.py runserver
   ```

2. **Start Celery Worker**
   ```bash
   celery -A investment_wizard worker --loglevel=info --concurrency=4
   ```

3. **Start Celery Beat (Scheduler) - Runs every 5 minutes**
   ```bash
   celery -A investment_wizard beat --loglevel=info
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Email Notifications Setup

### Gmail Setup (Recommended)
1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Update .env file** with your credentials:
   ```env
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-16-character-app-password
   EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
   ```

### Other Email Providers
- **Outlook**: `smtp-mail.outlook.com:587`
- **Yahoo**: `smtp.mail.yahoo.com:587`
- **Custom SMTP**: Update `EMAIL_HOST` and `EMAIL_PORT`

### Testing Email Configuration
```bash
# Check email configuration status
curl http://localhost:8000/api/email/status/

# Send test email
curl -X POST http://localhost:8000/api/email/test/
```

## Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

```env
# Database Configuration
DB_NAME=investment_wizard
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306

# Django Configuration
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=4

# Email Configuration (for high-confidence alerts)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com
EMAIL_NOTIFICATION_ENABLED=True
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
CONFIDENCE_THRESHOLD=0.8

# LLM API Configuration
OPENAI_API_KEY=your-openai-api-key
LLM_API_URL=https://api.openai.com/v1/chat/completions

# Scraping Configuration
SCRAPING_INTERVAL_HOURS=24
MAX_ARTICLES_PER_SOURCE=50
# Note: Scraping runs every 5 minutes via Celery Beat scheduler
```

## API Endpoints

### Articles
- `GET /api/articles/` - List all articles (paginated)
- `GET /api/articles/{id}/` - Get single article details
- `POST /api/scrape/` - Manually trigger scraping job
- `GET /api/health/` - Health check

### Email Notifications
- `GET /api/email/status/` - Get email configuration status
- `POST /api/email/test/` - Send test email to verify configuration

### Example API Response
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/articles/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Tech Company Announces Major Breakthrough",
      "url": "https://example.com/article",
      "content": "Full article content...",
      "published_at": "2024-01-15T10:30:00Z",
      "summary": "AI-generated summary...",
      "suggestion": "Investment suggestion...",
      "source": "BBC",
      "is_processed": true
    }
  ]
}
```

## Project Structure

```
investment-wizard/
├── investment_wizard/          # Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py
├── news/                       # Django app
│   ├── models.py              # Article model
│   ├── views.py               # API views
│   ├── serializers.py         # DRF serializers
│   ├── scrapers.py            # Web scraping logic
│   ├── llm_service.py         # LLM integration
│   ├── tasks.py               # Celery tasks
│   └── admin.py               # Admin interface
├── frontend/                   # React application
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/            # Page components
│   │   ├── api/              # API client
│   │   └── App.jsx           # Main app component
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml         # Docker configuration
├── Dockerfile.backend         # Backend Dockerfile
├── Dockerfile.frontend        # Frontend Dockerfile
├── requirements.txt           # Python dependencies
└── README.md
```

## Features in Detail

### Web Scraping
- Scrapes BBC and CNN technology sections
- Extracts title, content, URL, and publication date
- Prevents duplicate articles by URL checking
- Rate limiting to respect website policies

### AI Processing
- Generates article summaries using LLM
- Creates investment suggestions based on content
- Placeholder system for when API keys are not available
- Configurable LLM provider (OpenAI by default)

### Background Jobs
- Daily scraping schedule using Celery Beat
- Asynchronous article processing
- Automatic cleanup of old articles
- Error handling and retry logic

### Frontend Dashboard
- Responsive design with modern UI
- Real-time article updates
- Search and filtering capabilities
- Article detail views with full content
- Manual scraping trigger

## Development

### Running Tests
```bash
python manage.py test
```

### Code Quality
```bash
# Backend
flake8 .
black .

# Frontend
cd frontend
npm run lint
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Deployment

### Production Considerations
1. Set `DEBUG=False` in production
2. Use strong `SECRET_KEY`
3. Configure proper database credentials
4. Set up SSL certificates
5. Use environment variables for sensitive data
6. Configure proper logging
7. Set up monitoring and alerting

### Scaling
- Use multiple Celery workers
- Implement Redis clustering
- Use load balancer for multiple backend instances
- Consider CDN for static files

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check MySQL service is running
   - Verify database credentials in `.env`
   - Ensure database exists

2. **Celery Worker Not Processing Tasks**
   - Check Redis is running
   - Verify Celery broker URL
   - Check worker logs

3. **Scraping Not Working**
   - Check internet connection
   - Verify website accessibility
   - Check rate limiting settings

4. **Frontend Not Loading**
   - Check if backend is running
   - Verify CORS settings
   - Check browser console for errors

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
