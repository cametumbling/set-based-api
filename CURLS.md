# Required Curl Commands

## a. organization: apple AND tech: .net

```bash
curl -X POST http://localhost:8000/jobs -H "Content-Type: application/json" -d '{"and_": [{"organization": "apple"}, {"tech": ".net"}]}'
```

## b. NOT organization: apple AND (job_function: statistician OR tech: psql)

```bash
curl -X POST http://localhost:8000/jobs -H "Content-Type: application/json" -d '{"and_": [{"not_": {"organization": "apple"}}, {"or_": [{"job_function": "statistician"}, {"tech": "psql"}]}]}'
```
