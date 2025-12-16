# Sumble Advanced Query API

## Overview

API that accepts advanced queries with AND/OR/NOT logic to search job posts by technology, organization, and job function.

## Design Decisions

### Query Structure

Chose a nested JSON structure for queries rather than parsing a string. This is faster to implement and less error-prone.

### SQL Approach

-   **CTEs (Common Table Expressions)**: Pre-filter tech/org/job_function IDs once, rather than running ILIKE per row. If a CTE returns zero rows, the query short-circuits fast.
-   **Parameterized queries**: Prevent SQL injection by using %s placeholders with psycopg2. Params are built alongside SQL in each function to guarantee correct ordering.
-   **EXISTS subqueries**: Avoid row multiplication from many-to-many joins.
-   **DISTINCT**: Prevent duplicate results from joins.
-   **Slug OR name matching**: Searches match against both slug and name fields for flexibility (e.g., ".net" matches "C .NET" by name or "c-net" by slug).
-   **Deterministic ordering**: Results ordered by job ID for consistent pagination.

### Performance

-   ILIKE runs once per filter in CTEs, not per job row
-   EXISTS short-circuits once a match is found
-   Result set limited to 10 for responsiveness

## Running

```bash
docker compose up --build
```

Requires Docker and Docker Compose.

API available at http://localhost:8000

Health check: GET /health

## Query JSON Format

### Simple filter

```json
{ "tech": "python" }
```

### AND

```json
{ "and_": [{ "organization": "apple" }, { "tech": ".net" }] }
```

### OR

```json
{ "or_": [{ "tech": "python" }, { "tech": "java" }] }
```

### NOT

```json
{ "not_": { "organization": "apple" } }
```

### Combined

```json
{
	"and_": [
		{ "not_": { "organization": "apple" } },
		{ "or_": [{ "job_function": "statistician" }, { "tech": "psql" }] }
	]
}
```

## Example Queries

```bash
# Apple jobs with .NET
curl -X POST http://localhost:8000/jobs -H "Content-Type: application/json" -d '{"and_": [{"organization": "apple"}, {"tech": ".net"}]}'

# NOT Apple AND (statistician OR psql)
curl -X POST http://localhost:8000/jobs -H "Content-Type: application/json" -d '{"and_": [{"not_": {"organization": "apple"}}, {"or_": [{"job_function": "statistician"}, {"tech": "psql"}]}]}'
```
