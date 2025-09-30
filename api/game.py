from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import asyncio
import json

app = FastAPI()

# Aby frontend mógł się łączyć
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Przechowuje oczekujących graczy
waiting_players = []

# Przechowuje aktywne gry: game_id -> {player1, player2, board, turn}
active_games = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    player_id = str(uuid.uuid4())

    # Odbierz dane gracza (nazwa)
    data = await websocket.receive_text()
    player_data = json.loads(data)
    player_name = player_data.get("name", "Anon")

    # Dodaj do oczekujących
    waiting_players.append({"id": player_id, "ws": websocket, "name": player_name})

    # Czekamy aż znajdzie się przeciwnik
    while True:
        if len(waiting_players) >= 2:
            p1 = waiting_players.pop(0)
            p2 = waiting_players.pop(0)

            # Utwórz grę
            game_id = str(uuid.uuid4())
            active_games[game_id] = {
                "player1": p1,
                "player2": p2,
                "board": [""] * 9,
                "turn": p1["id"]
            }

            # Powiadom graczy
            start_msg_p1 = json.dumps({"type": "start", "symbol": "X", "opponent": p2["name"], "game_id": game_id})
            start_msg_p2 = json.dumps({"type": "start", "symbol": "O", "opponent": p1["name"], "game_id": game_id})
            await p1["ws"].send_text(start_msg_p1)
            await p2["ws"].send_text(start_msg_p2)

            # Obsługa ruchów
            asyncio.create_task(handle_game(game_id))
        await asyncio.sleep(1)

async def handle_game(game_id):
    game = active_games[game_id]
    p1_ws = game["player1"]["ws"]
    p2_ws = game["player2"]["ws"]

    while True:
        for player in [game["player1"], game["player2"]]:
            try:
                data = await player["ws"].receive_text()
                move = json.loads(data)
                idx = move.get("idx")
                symbol = "X" if player["id"] == game["player1"]["id"] else "O"

                if game["turn"] != player["id"] or game["board"][idx]:
                    continue

                game["board"][idx] = symbol
                game["turn"] = game["player2"]["id"] if player["id"] == game["player1"]["id"] else game["player1"]["id"]

                msg = json.dumps({"type": "update", "board": game["board"], "turn": game["turn"]})
                await p1_ws.send_text(msg)
                await p2_ws.send_text(msg)

                winner = check_winner(game["board"])
                if winner:
                    win_msg = json.dumps({"type": "winner", "winner": winner})
                    await p1_ws.send_text(win_msg)
                    await p2_ws.send_text(win_msg)
                    del active_games[game_id]
                    return
            except:
                # Jeśli gracz rozłączył się
                del active_games[game_id]
                return
        await asyncio.sleep(0.1)

def check_winner(board):
    wins = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for a,b,c in wins:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "Draw"
    return None
