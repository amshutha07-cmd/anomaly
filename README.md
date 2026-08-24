PS C:\Users\amshu\Desktop\live anonalu> Set-Location "C:\Users\amshu\Desktop\live anonalu"
>>
>> Get-Content .\hosted\api\app\main.py |
>>   Select-Object -Skip 60 -First 38 |
>>   ForEach-Object -Begin { $n = 61 } -Process { "{0}: {1}" -f $n++, $_ }
>>
61:
62:
63: _PUBLIC_PATHS = {"/health", "/api/readiness"}
64:
65:
66: @app.middleware("http" )
67: async def require_supabase_auth(request: Request, call_next):
68:     """Protect API routes while keeping health/readiness and CORS preflight public."""
69:     if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS or not request.url.path.startswith("/api/"):
70:         return await call_next(request)
71:
72:     if request.url.path == "/api/internal/alerts/dispatch" and worker_token_matches(request.headers.get("x-alert-worker-token")):
73:         request.state.worker = True
74:         return await call_next(request)
75:
76:     if request.url.path == "/api/internal/alerts/dispatch" and worker_token_matches(request.headers.get("x-alert-worker-token")):
77:         request.state.worker = True
78:         return await call_next(request)
79:
80:     header = request.headers.get("authorization", "")
81:     scheme, _, token = header.partition(" ")
82:     if scheme.lower() != "bearer" or not token:
83:         return JSONResponse(status_code=401, content={"detail": "Bearer access token required"})
84:
85:     try:
86:         request.state.user = validate_access_token(token)
87:     except HTTPException as exc:
88:         return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
89:
90:     return await call_next(request)
91:
92: def database_url() -> str | None:
93:     return os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
94:
95:
96: class PipelineRunCreate(BaseModel):
97:     model_config = ConfigDict(extra="forbid")
98:
PS C:\Users\amshu\Desktop\live anonalu>
