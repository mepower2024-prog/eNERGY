from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime
import sqlite3
import uvicorn

# Use SQLite - Render has ephemeral storage, so database resets on redeploy
DATABASE_URL = "energy_monitoring.db"

# Data model for meter data
class MeterData(BaseModel):
    meter_id: str
    timestamp: str
    location: str
    voltages: Dict[str, Optional[float]]
    currents: Dict[str, Optional[float]]
    power: Dict[str, Optional[float]]
    power_factors: Dict[str, Optional[float]]
    frequency: Optional[float]
    reactive_power: Optional[Dict[str, Optional[float]]] = None
    apparent_power: Optional[Dict[str, Optional[float]]] = None

# Initialize SQLite database
def init_database():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Create tables with more columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meters (
            id TEXT PRIMARY KEY,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    #location TEXT NOT NULL,
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meter_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meter_id TEXT NOT NULL,
            location TEXT NOT_NULL,
            timestamp TIMESTAMP NOT NULL,
            -- Voltages
            voltage_r REAL, voltage_y REAL, voltage_b REAL, voltage_avg REAL,
            voltage_ry REAL, voltage_yb REAL, voltage_br REAL,
            -- Currents
            current_r REAL, current_y REAL, current_b REAL, current_n REAL,
            -- Power
            power_r REAL, power_y REAL, power_b REAL, power_total REAL,
            -- Reactive Power
            reactive_power_r REAL, reactive_power_y REAL, reactive_power_b REAL, reactive_power_total REAL,
            -- Apparent Power
            apparent_power_r REAL, apparent_power_y REAL, apparent_power_b REAL, apparent_power_total REAL,
            -- Power Factor
            power_factor_r REAL, power_factor_y REAL, power_factor_b REAL, power_factor_avg REAL,
            -- Other
            frequency REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meter_status (
            meter_id TEXT PRIMARY KEY,
            online BOOLEAN DEFAULT FALSE,
            last_update TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert sample meters if they don't exist
    # cursor.execute("""
    #     INSERT OR IGNORE INTO meters (id, location, description) VALUES
    #     ('meter_001', 'Main Panel', 'Primary energy meter'),
    #     ('meter_002', 'Sub Panel A', 'Secondary meter A'),
    #     ('meter_003', 'Sub Panel B', 'Secondary meter B')
    # """)
    cursor.execute("""
        INSERT OR IGNORE INTO meters (id, description) VALUES
        ('meter_001', 'Primary energy meter'),
        ('meter_002', 'Secondary meter A'),
        ('meter_003', 'Secondary meter B'),
        ('meter_004', 'Secondary meter C')
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")
#ugytyt
# Create FastAPI app
app = FastAPI(title="Energy Monitoring API")

@app.on_event("startup")
async def startup_event():
    init_database()

# Allow frontend and Arduino to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://energy-monitoring-frontend.onrender.com",  # Your frontend URL
        "*"  # For Arduino testing - restrict this in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (keep all your existing routes the same)
@app.get("/")
async def root():
    return {"message": "Energy Monitoring API is running!"}

@app.post("/api/meter-data")
async def receive_meter_data(data: MeterData):
    try:
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        dt = datetime.fromisoformat(data.timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
        # Debug: Print what we're receiving
        print(f"📨 Received data for {data.meter_id}:")
        print(f"  Voltages: {data.voltages}")
        print(f"  Currents: {data.currents}")
        print(f"  Power: {data.power}")
        print(f"  Power Factors: {data.power_factors}")
        print(f"  Frequency: {data.frequency}")
        
        # Insert into meter_readings table with all fields
        cursor.execute("""
            INSERT INTO meter_readings 
            (meter_id, location, timestamp, 
             voltage_r, voltage_y, voltage_b, voltage_avg, voltage_ry, voltage_yb, voltage_br,
             current_r, current_y, current_b, current_n,
             power_r, power_y, power_b, power_total,
             reactive_power_r, reactive_power_y, reactive_power_b, reactive_power_total,
             apparent_power_r, apparent_power_y, apparent_power_b, apparent_power_total,
             power_factor_r, power_factor_y, power_factor_b, power_factor_avg,
             frequency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.meter_id,
            data.location,
            #datetime.fromisoformat(data.timestamp.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M:%S"),
            # data.timestamp.replace("Z", ""),
            dt,
            # Voltages (7 values)
            data.voltages.get('V_RN'), data.voltages.get('V_YN'), data.voltages.get('V_BN'),
            data.voltages.get('V_Avg'), data.voltages.get('V_RY'), data.voltages.get('V_YB'), data.voltages.get('V_BR'),
            # Currents (4 values)
            data.currents.get('I_R'), data.currents.get('I_Y'), data.currents.get('I_B'), data.currents.get('I_N'),
            # Power (4 values)
            data.power.get('P_R'), data.power.get('P_Y'), data.power.get('P_B'), data.power.get('P_Total'),
            # Reactive Power (4 values)
            data.reactive_power.get('Q_R') if data.reactive_power else None,
            data.reactive_power.get('Q_Y') if data.reactive_power else None,
            data.reactive_power.get('Q_B') if data.reactive_power else None,
            data.reactive_power.get('Q_Total') if data.reactive_power else None,
            # Apparent Power (4 values)
            data.apparent_power.get('S_R') if data.apparent_power else None,
            data.apparent_power.get('S_Y') if data.apparent_power else None,
            data.apparent_power.get('S_B') if data.apparent_power else None,
            data.apparent_power.get('S_Total') if data.apparent_power else None,
            # Power Factor (4 values)
            data.power_factors.get('PF_R'), data.power_factors.get('PF_Y'), data.power_factors.get('PF_B'),
            data.power_factors.get('PF_Avg'),
            # Frequency (1 value)
            data.frequency
        ))
        
        # Update meter status
        utc_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO meter_status (meter_id, online, last_update)
            VALUES (?, ?, ?)
            ON CONFLICT(meter_id) 
            DO UPDATE SET online = ?, last_update = ?
        """, (data.meter_id, True, utc_now, True, utc_now))
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Data saved successfully")
        return {"status": "success", "message": "Data saved successfully"}
        
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return {"status": "error", "message": str(e)}
    pass

@app.get("/api/meters")
async def get_meters():
    try:
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, ms.online, ms.last_update
            FROM meters m
            LEFT JOIN meter_status ms ON m.id = ms.meter_id
            WHERE m.is_active = 1
        """)
        
        meters = []
        for row in cursor.fetchall():
            meters.append({
                "meter_id": row[0],
                "online": bool(row[1]) if row[1] is not None else False,
                "last_update": row[2]
            })
        
        cursor.close()
        conn.close()
        
        return {"meters": meters}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    pass

@app.get("/api/meter/{meter_id}/readings")
async def get_meter_readings(meter_id: str, hours: int = 24):
    try:
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, 
                   voltage_r, voltage_y, voltage_b, voltage_avg, voltage_ry, voltage_yb, voltage_br,
                   current_r, current_y, current_b, current_n,
                   power_r, power_y, power_b, power_total,
                   reactive_power_r, reactive_power_y, reactive_power_b, reactive_power_total,
                   apparent_power_r, apparent_power_y, apparent_power_b, apparent_power_total,
                   power_factor_r, power_factor_y, power_factor_b, power_factor_avg,
                   frequency
            FROM meter_readings 
            WHERE meter_id = ? AND timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
            LIMIT 100
        """, (meter_id, f'-{hours} hours'))
        readings = []
        for row in cursor.fetchall():
            readings.append({
                "timestamp": row[0],
                "voltages": {
                    "V_RN": row[1], "V_YN": row[2], "V_BN": row[3], "V_Avg": row[4], "V_RY": row[5], "V_YB": row[6], "V_BR": row[7]
                },
                "currents": {
                    "I_R": row[8], "I_Y": row[9], "I_B": row[10], "I_N": row[11]
                },
                "power": {
                    "P_R": row[12], "P_Y": row[13], "P_B": row[14], "P_Total": row[15]
                },
                "reactive_power": {
                    "Q_R": row[16], "Q_Y": row[17], "Q_B": row[18], "Q_Total": row[19]
                },
                "apparent_power": {
                    "S_R": row[20], "S_Y": row[21], "S_B": row[22], "S_Total": row[23]
                },
                "power_factors": {
                    "PF_R": row[24], "PF_Y": row[25], "PF_B": row[26], "PF_Avg": row[27]
                },
                "frequency": row[28]
            })
        
        cursor.close()
        conn.close()
        
        return {"meter_id": meter_id, "readings": readings}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    pass

# Remove the __main__ block since Render uses startCommand