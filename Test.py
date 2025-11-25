import fdb
from dotenv import load_dotenv
import os

print("🔄 Carregando variáveis do .env...")
load_dotenv()

FB_HOST = os.getenv("FB_HOST")
FB_PORT = os.getenv("FB_PORT")
FB_DATABASE = os.getenv("FB_DATABASE")
FB_USER = os.getenv("FB_USER")
FB_PASSWORD = os.getenv("FB_PASSWORD")

print("HOST:", FB_HOST)
print("PORT:", FB_PORT)
print("DATABASE:", FB_DATABASE)
print("USER:", FB_USER)

# Carregar a DLL como no seu app
try:
    fdb.load_api(r'C:\Drivers\Firebird\GDS32.DLL')
    print("DLL carregada com sucesso.")
except Exception as e:
    print("Erro ao carregar DLL:", e)

print("\n🔌 Testando conexão...")

try:
    con = fdb.connect(
        host=FB_HOST,
        port=int(FB_PORT),       # <<<<<< agora estamos usando a porta correta
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASSWORD,
        charset="UTF8"
    )

    print("✅ Conexão realizada com sucesso!")
    con.close()

except Exception as e:
    print("❌ Erro ao conectar:")
    print(e)
