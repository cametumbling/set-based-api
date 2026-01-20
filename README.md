# Set-based Advanced Query API

## Overview

API that accepts advanced queries with AND / OR / NOT logic to search job posts by technology, organization, and job function.

The API is designed to handle complex boolean queries efficiently on large datasets.

## Design Decisions

### Query Structure

Chose a nested JSON structure for queries rather than parsing a query string. This avoids writing a custom parser, keeps the API explicit, and maps cleanly to boolean logic.

### SQL Approach

-   **Set-based boolean logic**: Each filter produces a set of `job_post_id`s. Boolean operators are implemented using SQL set operations:
    -   AND → `INTERSECT`
    -   OR → `UNION`
    -   NOT → `EXCEPT`
-   **CTEs (Common Table Expressions)**: Each leaf filter (tech / organization / job_function) is evaluated once in its own CTE, producing a set of `job_post_id`s.
-   **Deferred joins**: Job details and organization metadata are joined _after_ the final `job_post_id` set is computed. This avoids wide scans and expensive row-wise `EXISTS` checks for OR-heavy queries.
-   **Parameterized queries**: All inputs are passed via `%s` placeholders using psycopg2 to prevent SQL injection.
-   **Slug OR name matching**: Filters match against both `slug` and `name` fields for flexibility (e.g. `.net` matches `C .NET` by name or `c-net` by slug).
-   **Deterministic ordering**: Results are ordered by job ID and limited to 10.

## Performance Characteristics

-   Boolean logic is executed via SQL set algebra (`UNION / INTERSECT / EXCEPT`)
-   Each filter runs once, independent of dataset size
-   Avoids row-wise predicate evaluation on large tables
-   Result set is limited to 10 for responsiveness

This approach ensures predictable performance even for broad OR / NOT queries.

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
