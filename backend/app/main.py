from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import vendas, vendedores, cambistas, auth

app = FastAPI(title="ERP Eleven API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(vendas.router, prefix="/api/vendas", tags=["vendas"])
app.include_router(vendedores.router, prefix="/api/vendedores", tags=["vendedores"])
app.include_router(cambistas.router, prefix="/api/cambistas", tags=["cambistas"])

@app.get("/")
async def root():
    return {"message": "ERP Eleven API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}