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
    """
    Accept an advanced query with AND/OR/NOT logic and return matching jobs.
    Uses CTEs to prefilter tech/org/function IDs to avoid repeated ILIKE scans.
    """
    MAX_DEPTH = 10
    cte_counter = [0]
    
    def get_cte_name():
        cte_counter[0] += 1
        return f"cte_{cte_counter[0]}"
    
    def build_condition(q):
        parts = []
        params = []
        ctes = []
        
        if q.get("tech"):
            cte_name = get_cte_name()
            params.extend([f"%{q['tech']}%", f"%{q['tech']}%"])
            ctes.append(f"{cte_name} AS (SELECT id FROM tech WHERE name ILIKE %s OR slug ILIKE %s)")
            parts.append(f"EXISTS (SELECT 1 FROM job_posts_tech jpt JOIN {cte_name} ct ON jpt.tech_id = ct.id WHERE jpt.job_post_id = jp.id)")
        
        if q.get("organization"):
            cte_name = get_cte_name()
            params.extend([f"%{q['organization']}%", f"%{q['organization']}%"])
            ctes.append(f"{cte_name} AS (SELECT id FROM organizations WHERE name ILIKE %s OR slug ILIKE %s)")
            parts.append(f"jp.organization_id IN (SELECT id FROM {cte_name})")
        
        if q.get("job_function"):
            cte_name = get_cte_name()
            params.extend([f"%{q['job_function']}%", f"%{q['job_function']}%"])
            ctes.append(f"{cte_name} AS (SELECT id FROM job_functions WHERE name ILIKE %s OR slug ILIKE %s)")
            parts.append(f"EXISTS (SELECT 1 FROM job_posts_job_functions jpjf JOIN {cte_name} cjf ON jpjf.job_function_id = cjf.id WHERE jpjf.job_post_id = jp.id)")
        
        condition = " AND ".join(parts) if parts else None
        return condition, params, ctes

    def build_where(q, depth=0):
        if depth > MAX_DEPTH:
            raise HTTPException(status_code=400, detail="Query too deeply nested")
        
        if isinstance(q, dict):
            if "and_" in q and q["and_"]:
                if not isinstance(q["and_"], list):
                    raise HTTPException(status_code=400, detail="and_ must be a list")
                subs = [build_where(sub, depth + 1) for sub in q["and_"]]
                conditions = [s[0] for s in subs if s[0]]
                params = [p for s in subs for p in s[1]]
                ctes = [c for s in subs for c in s[2]]
                condition = "(" + " AND ".join(conditions) + ")" if conditions else None
                return condition, params, ctes
            if "or_" in q and q["or_"]:
                if not isinstance(q["or_"], list):
                    raise HTTPException(status_code=400, detail="or_ must be a list")
                subs = [build_where(sub, depth + 1) for sub in q["or_"]]
                conditions = [s[0] for s in subs if s[0]]
                params = [p for s in subs for p in s[1]]
                ctes = [c for s in subs for c in s[2]]
                condition = "(" + " OR ".join(conditions) + ")" if conditions else None
                return condition, params, ctes
            if "not_" in q and q["not_"]:
                if not isinstance(q["not_"], dict):
                    raise HTTPException(status_code=400, detail="not_ must be an object")
                inner, params, ctes = build_where(q["not_"], depth + 1)
                condition = f"NOT ({inner})" if inner else None
                return condition, params, ctes
            return build_condition(q)
        return None, [], []

    try:
        query_dict = query.model_dump()
        where_clause, params, ctes = build_where(query_dict)
        where_clause = where_clause or "1=1"
        
        cte_clause = "WITH " + ", ".join(ctes) if ctes else ""

        sql = f"""
            {cte_clause}
            SELECT DISTINCT jp.id, jpd.job_title, o.name as organization, jpd.location
            FROM (
                SELECT id, organization_id
                FROM job_posts
                ORDER BY id
                LIMIT 5000
            ) jp
            JOIN job_posts_details jpd ON jp.id = jpd.id
            JOIN organizations o ON jp.organization_id = o.id
            WHERE {where_clause}
            ORDER BY jp.id
            LIMIT 10
        """

        return fetch_all(sql, tuple(params))
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))