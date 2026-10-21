# Phase 1 architecture

The application is an intentionally simple monorepo with two independently runnable processes.

```text
React / TypeScript HMI (Vite, port 5173)
                    |
                    | HTTP JSON /api/*
                    v
FastAPI application (Uvicorn, port 8000)
                    |
                    v
SQLAlchemy database adapter
        |                         |
SQLite development default   PostgreSQL production option
```

Phase 1 establishes the user interface shell, routing, API boundary, configuration, logging,
database connectivity, and service health visibility. Product models, inspection recipes,
captured images, checkpoint results, and mock AI workflow belong to Phase 2.

## Extension boundaries

- `backend/app/api/routes`: versionable REST route modules.
- `backend/app/core`: configuration, logging, and database infrastructure.
- `backend/app/models`: SQLAlchemy entities (Phase 2).
- `backend/app/schemas`: API request and response contracts (Phase 2).
- `backend/app/services`: workflow, camera, measurement, colour, and reporting services (Phase 2).
- `backend/app/vision`: replaceable OpenCV/YOLO adapters (future phase).
- `frontend/src/services`: typed HTTP client boundary.
- `frontend/src/pages`: route-level operator and management screens.
- `frontend/src/components`: reusable industrial HMI components.
