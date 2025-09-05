# API Sentinel

API Sentinel is a backend service for managing API usage, authentication, and project-level access control. Built with FastAPI and SQLAlchemy, it provides secure endpoints for user, project, and API key management, as well as usage tracking and budgeting.

## Features
- User registration and authentication (OAuth2/JWT)
- Project and API key (Sentinel Key) management
- Usage logging and cost tracking
- PostgreSQL database integration
- Environment-based configuration

## Tech Stack
- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- python-jose
- passlib
- python-dotenv


## API Endpoints

### Authentication
- `POST /auth/signup`  
   Create a new user account.
- `POST /auth/token`  
   Obtain a JWT access token (login).

### SDK Usage Reporting
- `POST /v1/usage`  
   Report API usage and cost (requires `x-sentinel-key` header).

### Projects
- `POST /projects`  
   Create a new project (requires authentication).
- `DELETE /projects/{project_id}`  
   Delete a project by ID (requires authentication).
- `GET /projects`  
   List all projects for the current user (requires authentication).

### Users
- `DELETE /users/me`  
   Delete the current user and all associated data (requires authentication).

### Dashboard
- `GET /v1/projects/{project_id}/stats`  
   Get monthly usage stats for a project (requires authentication).

## Project Structure
```
api-sentinel/
    main.py         # FastAPI app and endpoints
    database.py     # SQLAlchemy setup
    models.py       # ORM models
    setupdb.py      # DB table creation script
    requirements.txt
    .env            # Environment variables (not committed)
```

## Author
[aimrrs](https://github.com/aimrrs)
