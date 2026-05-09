# CollabDocs API

CollabDocs is an API-first backend for collaborative document editing and review. It provides document versioning, threaded comments, tagging, role-based access control (RBAC), and audit-friendly request logging so teams can integrate document collaboration into other services or UIs.

**Key features:**
- Document creation, editing, and deletion with automatic `DocumentVersion` snapshots for every save.
- Threaded comments on documents and document versions.
- Tagging and simple search/filtering by tags and metadata.
- Role-based access control (roles and permissions managed per workspace/user).
- Audit-friendly request logging (method, path, status, timing) and support for the `X-User-ID` header for simulated user context in Postman.
- API-only design so any frontend or service can consume it (Postman collection included: `CollabDocs.postman_collection.json`).

## Getting started (quick)

Prerequisites:
- Python 3.10+ (virtual environment recommended)
- A database supported via `DATABASE_URL` (Postgres recommended)

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create environment configuration:
- Copy or create your `.env` (if this repo includes `.env.example`, use it as a template).
- At minimum set `DATABASE_URL` to point to your Postgres instance.

4. Apply database migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

5. (Optional) Load the provided Postman collection `CollabDocs.postman_collection.json` into Postman to exercise example requests.

6. Run the development server:

```bash
python manage.py runserver
```

## Configuration / Environment variables
- `DATABASE_URL` — DB connection string (Postgres recommended).
- Other Django settings may be driven by `config/settings.py` and environment variables; inspect that file for more options.

## Project layout (important files)
- `manage.py` — Django CLI entry point.
- `config/` — Django project settings and ASGI/WSGI entry points.
- `core/` — Main app containing models, serializers, views, permissions, and middleware.
- `CollabDocs.postman_collection.json` — Postman collection with example requests.

## How to use the API (high-level)
- Authenticate or provide `X-User-ID` header when using Postman to simulate an acting user for RBAC and audit logging.
- Create a `Document` via the documents endpoint. Each save will create a `DocumentVersion` snapshot.
- Add comments to documents or document versions to start threaded discussions.
- Use tags to categorize documents and filter queries.

## API Endpoints Reference

### Users

**Create user:**
- POST `http://127.0.0.1:8000/api/users/`

![Create User](docs/images/image_0.png)

**Get user:**
- GET `http://127.0.0.1:8000/api/users/{user_id}/`

![Get User](docs/images/image_1.png)

### Workspaces

**Create workspace + auto-add owner as admin member:**
- POST `http://127.0.0.1:8000/api/workspaces/`
- Headers: `X-User-ID` (required)

![Create Workspace](docs/images/image_2.png)

**Get workspace with member count:**
- GET `http://127.0.0.1:8000/api/workspaces/{workspace_id}/`

![Get Workspace](docs/images/image_3.png)

**Add a member to a workspace with a role:**
- POST `http://127.0.0.1:8000/api/workspaces/{workspace_id}/members/`
- Headers: `X-User-ID` (required)
- Body: `{ "user_id": "...", "role": "admin|editor|viewer" }`

![Add Workspace Member](docs/images/image_4.png)

**List all members with their roles:**
- GET `http://127.0.0.1:8000/api/workspaces/{workspace_id}/members/`

![List Members](docs/images/image_5.png)

**Get workspace summary (doc count, member count, total comments):**
- GET `http://127.0.0.1:8000/api/workspaces/{workspace_id}/summary/`

![Workspace Summary](docs/images/image_6.png)

### Documents

**Create a document + first version (atomic transaction):**
- POST `http://127.0.0.1:8000/api/documents/`
- Headers: `X-User-ID` (required)
- Body: `{ "title": "...", "content": "...", "workspace_id": "..." }`

![Create Document](docs/images/image_7.png)

**Update document content (saves a new version):**
- PUT `http://127.0.0.1:8000/api/documents/{document_id}/`
- Headers: `X-User-ID` (required)
- Body: `{ "title": "...", "content": "...", "status": "draft|published|archived" }`

![Update Document](docs/images/image_8.png)

**List documents - filter by workspace, status, tag name, search:**
- GET `http://127.0.0.1:8000/api/documents/`

Query parameters:
- `?workspace_ids={workspace_id}` — Filter by workspace
- `?status_in=draft,published` — Filter by status
- `?search=query` — Search in title and content
- `?title_icontains=text` — Filter by title substring
- `?tag_name=tagname` — Filter by tag name
- `?tag_ids=tag1-id,tag2-id` — Filter by tag IDs

**Examples:**
- Filter by workspace: `GET http://127.0.0.1:8000/api/documents/?workspace_ids=f462cdeb-1336-4096-b936-e01abcf4f0d2`

![List Documents](docs/images/image_9.png)

- Filter by status: `GET http://127.0.0.1:8000/api/documents/?status_in=draft`

![Filter by Status](docs/images/image_10.png)

- Search title/content: `GET http://127.0.0.1:8000/api/documents/?search=brief`

![Search Documents](docs/images/image_11.png)

- Search title only: `GET http://127.0.0.1:8000/api/documents/?title_icontains=project`

![Search Title](docs/images/image_12.png)

**Get all versions of a document (in order):**
- GET `http://127.0.0.1:8000/api/documents/{document_id}/versions/`

![Document Versions](docs/images/image_13.png)

**Get document statistics (version count, comment count, contributor count):**
- GET `http://127.0.0.1:8000/api/documents/{document_id}/stats/`

![Document Stats](docs/images/image_14.png)

**Add one or more tags to a document:**
- POST `http://127.0.0.1:8000/api/documents/{document_id}/tags/`
- Headers: `X-User-ID` (required)
- Body: `{ "tag_ids": ["8ec9caa1-36ea-4153-b729-148c299fef1e"] }`

![Add Tags to Document](docs/images/image_15.png)

### Comments

**Add a top-level comment to a document:**
- POST `http://127.0.0.1:8000/api/comments/`
- Headers: `X-User-ID` (required)
- Body:
  ```json
  {
    "document": "6d3732d2-ed47-42db-ab9b-d341f79c1043",
    "content": "This is the first comment"
  }
  ```

![Create Comment](docs/images/image_16.png)

**Reply to a comment:**
- POST `http://127.0.0.1:8000/api/comments/`
- Headers: `X-User-ID` (required)
- Body:
  ```json
  {
    "document": "6d3732d2-ed47-42db-ab9b-d341f79c1043",
    "content": "This is a reply",
    "parent": "{parent_comment_id}"
  }
  ```

![Reply to Comment](docs/images/image_17.png)

**List all comments for a document:**
- GET `http://127.0.0.1:8000/api/comments/?document={document_id}`

![List Comments](docs/images/image_18.png)

### Tags

**Create a tag:**
- POST `http://127.0.0.1:8000/api/tags/`
- Body: `{ "name": "tag-name" }`

![Create Tag](docs/images/image_19.png)

**Add tags to existing document:**
- POST `http://127.0.0.1:8000/api/documents/{document_id}/tags/`
- Headers: `X-User-ID` (required)
- Body: `{ "tag_ids": ["tag-uuid-1", "tag-uuid-2"] }`

![Add Tags](docs/images/image_20.png)

### Audit Logs

**List audit logs (filtered by actor, action, model, timestamp):**
- GET `http://127.0.0.1:8000/api/audit-logs/`

Query parameters:
- `?actor={actor_id}` — Filter by actor (user ID)
- `?action={action}` — Filter by action (e.g., "created", "updated", "tag_added")
- `?model_name={model}` — Filter by model name (e.g., "Document")
- `?timestamp_after={iso_timestamp}` — Filter by timestamp (on or after)
- `?timestamp_before={iso_timestamp}` — Filter by timestamp (on or before)

![Audit Logs](docs/images/image_21.png)

![Filter Audit Logs](docs/images/image_22.png)

## Developer notes / implementation details
- The API reads `DATABASE_URL` from the environment when configuring Django's database settings.
- On every `Document` save the code creates a corresponding `DocumentVersion` inside the same database transaction to ensure consistency.
- Request logging middleware prints request method, path, response status, and timing for every request; this can be found in `core/middleware.py`.
- Role checks and permission logic live in `core/permissions.py` and are referenced by views in `core/views.py`.

## Running tests
If there are tests included in this repository, run them with:

```bash
python manage.py test
```

## Postman
Import `CollabDocs.postman_collection.json` into Postman. When testing endpoints that depend on an acting user, add the header `X-User-ID` with a valid user id.

---

Current quick notes from this repository:

- The API reads `DATABASE_URL` from `.env`.
- Every `Document` save creates a `DocumentVersion` snapshot inside the same transaction.
- Request logging middleware prints method, path, status, and timing for every request.
- Use the `X-User-ID` header in Postman to identify the acting user for role checks and audit logging.
