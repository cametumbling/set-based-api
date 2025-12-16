from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from db import fetch_all

app = FastAPI()

class Query(BaseModel):
    and_: Optional[List[dict]] = None
    or_: Optional[List[dict]] = None
    not_: Optional[dict] = None
    tech: Optional[str] = None
    organization: Optional[str] = None
    job_function: Optional[str] = None

    class Config:
        populate_by_name = True
        extra = "allow"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs")
def search_jobs(query: Query):
    cte_counter = 0
    ctes = []
    params = []

    def next_cte():
        nonlocal cte_counter
        cte_counter += 1
        return f"s{cte_counter}"

    def leaf(q):
        sets = []

        if q.get("tech"):
            c = next_cte()
            params.extend([f"%{q['tech']}%", f"%{q['tech']}%"])
            ctes.append(f"""
            {c} AS (
              SELECT jpt.job_post_id AS id
              FROM job_posts_tech jpt
              JOIN tech t ON t.id = jpt.tech_id
              WHERE t.name ILIKE %s OR t.slug ILIKE %s
            )
            """)
            sets.append(f"SELECT id FROM {c}")

        if q.get("job_function"):
            c = next_cte()
            params.extend([f"%{q['job_function']}%", f"%{q['job_function']}%"])
            ctes.append(f"""
            {c} AS (
              SELECT jpjf.job_post_id AS id
              FROM job_posts_job_functions jpjf
              JOIN job_functions jf ON jf.id = jpjf.job_function_id
              WHERE jf.name ILIKE %s OR jf.slug ILIKE %s
            )
            """)
            sets.append(f"SELECT id FROM {c}")

        if q.get("organization"):
            c = next_cte()
            params.extend([f"%{q['organization']}%", f"%{q['organization']}%"])
            ctes.append(f"""
            {c} AS (
              SELECT jp.id
              FROM job_posts jp
              JOIN organizations o ON o.id = jp.organization_id
              WHERE o.name ILIKE %s OR o.slug ILIKE %s
            )
            """)
            sets.append(f"SELECT id FROM {c}")

        if not sets:
            return "SELECT id FROM job_posts"

        return " INTERSECT ".join(sets)

    def build(q):
        if "and_" in q and q["and_"]:
            return " INTERSECT ".join(f"({build(s)})" for s in q["and_"])
        if "or_" in q and q["or_"]:
            return " UNION ".join(f"({build(s)})" for s in q["or_"])
        if "not_" in q and q["not_"]:
            return f"""
            (SELECT id FROM job_posts)
            EXCEPT
            ({build(q["not_"])})
            """
        return leaf(q)

    id_set_sql = build(query.model_dump())

    sql = f"""
    WITH
    {",".join(ctes)}
    SELECT jp.id, jpd.job_title, o.name AS organization, jpd.location
    FROM ({id_set_sql}) ids
    JOIN job_posts jp ON jp.id = ids.id
    JOIN job_posts_details jpd ON jpd.id = jp.id
    JOIN organizations o ON o.id = jp.organization_id
    ORDER BY jp.id
    LIMIT 10
    """

    return fetch_all(sql, tuple(params))
