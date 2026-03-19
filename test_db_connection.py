#!/usr/bin/env python3
"""
Script para verificar conectividad a la BD en Railway
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar variables de .env
load_dotenv()

# Obtener DATABASE_URL
db_url = os.getenv("DATABASE_URL")

if not db_url:
    print("❌ ERROR: DATABASE_URL no está definida en .env")
    sys.exit(1)

print(f"📡 Probando conexión a: {db_url.split('@')[1] if '@' in db_url else 'OCULTO'}")
print(f"🔐 (URL completa oculta por seguridad)")

try:
    # Intentar crear el engine
    engine = create_engine(db_url, echo=False)
    
    # Intentar conectar
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        
        print(f"\n✅ CONEXIÓN EXITOSA")
        print(f"\nDetalles PostgreSQL:")
        print(f"  {version}")
        
        # Información adicional
        result = connection.execute(text("SELECT current_database(), current_user;"))
        db_name, user = result.fetchone()
        print(f"\nBD actual: {db_name}")
        print(f"Usuario: {user}")
        
        print("\n✨ La BD está accesible desde tu máquina y lista para usar en Docker.")
        
except Exception as e:
    print(f"\n❌ ERROR DE CONEXIÓN:")
    print(f"  {type(e).__name__}: {str(e)}")
    print(f"\n🔍 Posibles causas:")
    print(f"  1. DATABASE_URL mal formada")
    print(f"  2. Sin acceso a internet o bloqueado por firewall")
    print(f"  3. Credenciales incorrectas u expiradas")
    print(f"  4. Railway está down o la BD fue eliminada")
    sys.exit(1)
