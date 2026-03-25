import httpx, json
r = httpx.get("http://localhost:8071/api/health")
print(json.dumps(r.json(), indent=2))
