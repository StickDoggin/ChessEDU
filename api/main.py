"""
Chess Study Engine — FastAPI application.

Routes:
  GET  /health
  GET  /players/{id}/profile
  GET  /players/{id}/weakness-graph
  GET  /players/{id}/prescription
  GET  /players/{id}/opening-gaps
  GET  /players/{id}/drill-session
  POST /players/{id}/drill-attempt
  GET  /players/{id}/games
  GET  /players/{id}/games/{game_id}/moves
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import players, weaknesses, drills, games

app = FastAPI(
    title="Chess Study Engine",
    description="Personalized chess weakness diagnosis and study prescription API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173",
                   "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(weaknesses.router)
app.include_router(drills.router)
app.include_router(games.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
