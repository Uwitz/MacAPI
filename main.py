import os
import sys
import uvicorn
import Quartz

from dotenv import load_dotenv, find_dotenv, set_key
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return "MacAPI is online"

@app.get("/lock")
async def lock(request: Request):
    if request.headers.get("Authorization") != owner_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    os.system("osascript -e 'tell application \"System Events\" to keystroke \"q\" using {command down, control down}'")
    return "Locked the mac"

@app.post("/unlock")
async def unlock(request: Request):
    data = await request.json()
    if request.headers.get("Authorization") != owner_token or str(hash(data.get("password"))) != os.getenv("HASHED_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_dictionary = Quartz.CGSessionCopyCurrentDictionary()
    if not (session_dictionary and session_dictionary.get("CGSSessionScreenIsLocked", 0) == 0 and session_dictionary.get("kCGSSessionOnConsoleKey", 0) == 1):
        os.system(f"osascript -e 'tell application \"System Events\" to keystroke \"{data.get("password")}\"'")
        os.system(f"osascript -e 'tell application \"System Events\" to keystroke return'")
    return "Unlocked the mac"

if __name__ == "__main__":
    owner_token = os.getenv("OWNER_TOKEN")
    if not os.getenv("HASHED_PASSWORD"):
        set_key(find_dotenv(), "HASHED_PASSWORD", str(hash(input("Enter Mac Password: "))))
    uvicorn.run(app, host="0.0.0.0", port=2201)