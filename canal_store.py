import sqlite3
import time
import json
from typing import Optional, List

DB_FILE = "samba_canals.db"

def init_db():
    """Run this once when your FastAPI server starts up"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canals (
            canal_id TEXT PRIMARY KEY,
            phone_bif TEXT,
            bif_amount INTEGER,
            sats_amount INTEGER,
            btc_side_json TEXT,
            status TEXT,
            created_at REAL
        )
    """)
    conn.commit()
    conn.close()

# Automatically initialize the database table when the file is imported
init_db()

def create_bif_canal(phone: str, bif_amount: int, sats_amount: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Generate an incremental ID safely using DB rowcount
    cursor.execute("SELECT COUNT(*) FROM canals")
    count = cursor.fetchone()[0] + 1
    canal_id = f"CANAL{count:04d}"
    
    cursor.execute("""
        INSERT INTO canals (canal_id, phone_bif, bif_amount, sats_amount, btc_side_json, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (canal_id, phone, bif_amount, sats_amount, None, "WAITING_BTC", time.time()))
    
    conn.commit()
    conn.close()
    return canal_id

def match_btc_canal(phone: str, canal_id: str, invoice: str) -> Optional[dict]:
    canal = get_canal(canal_id)
    if not canal or canal["status"] != "WAITING_BTC":
        return None
    if canal["bif_side"]["phone"] == phone:
        return None  # Prevent buying own offer
        
    btc_side = {
        "phone": phone,
        "invoice": invoice,
        "committed": True
    }
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE canals 
        SET btc_side_json = ?, status = 'MATCHED'
        WHERE canal_id = ?
    """, (json.dumps(btc_side), canal_id))
    conn.commit()
    conn.close()
    
    return get_canal(canal_id)

def get_canal(canal_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM canals WHERE canal_id = ?", (canal_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "canal_id": row[0],
        "bif_side": {"phone": row[1], "bif_amount": row[2], "committed": True},
        "sats_amount": row[3],
        "btc_side": json.loads(row[4]) if row[4] else None,
        "status": row[5],
        "created_at": row[6]
    }

def get_open_canals() -> List[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT canal_id FROM canals WHERE status = 'WAITING_BTC'")
    rows = cursor.fetchall()
    conn.close()
    return [get_canal(r[0]) for r in rows if r[0]]

def complete_canal(canal_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE canals SET status = 'COMPLETED' WHERE canal_id = ?", (canal_id,))
    conn.commit()
    conn.close()

def get_user_canal(phone: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Pull entries descending to mimic reversed() behavior
    cursor.execute("""
        SELECT canal_id, btc_side_json FROM canals 
        WHERE status IN ('WAITING_BTC', 'MATCHED', 'COMPLETED') 
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        canal = get_canal(row[0])
        if not canal:
            continue
        btc_side = canal.get("btc_side")
        btc_phone = btc_side["phone"] if btc_side else None
        
        if phone == canal["bif_side"]["phone"] or phone == btc_phone:
            return canal
    return None