import streamlit as st
import pandas as pd
import fdb
import os

# =======================================
# 1. CARREGAR CONFIG DO SECRETS.TOML
# =======================================
FB_HOST = st.secrets["FB_HOST"]
FB_PORT = st.secrets["FB_PORT"]
FB_DATABASE = st.secrets["FB_DATABASE"]
FB_USER = st.secrets["FB_USER"]
FB_PASSWORD = st.secrets["FB_PASSWORD"]

# =======================================
# 2. DETECTAR AMBIENTE (LOCAL vs CLOUD)
# =======================================
RODANDO_NO_CLOUD = os.name != "nt"  # Windows = local

if not RODANDO_NO_CLOUD:
    # Windows → Carrega DLL do Firebird
    try:
        fdb.load_api(r"C:\Drivers\Firebird\GDS32.DLL")
        print("✔ DLL Firebird carregada.")
    except Exception as e:
        print(f"⚠ Não foi possível carregar a DLL Firebird: {e}")
else:
    print("✔ Rodando no Streamlit Cloud (DLL ignorada).")

# =======================================
# 3. FUNÇÃO DE CONEXÃO FIREBIRD
# =======================================
def conectar_firebird():
    return fdb.connect(
        host=FB_HOST,
        port=int(FB_PORT),
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASSWORD,
        charset="UTF8"
    )

# =======================================
# 4. CONSULTA SQL
# =======================================
SQL_BASE = """
WITH
PARAMETROS AS (
    SELECT
        COD_PRODUTO AS COD_PROD,
        'PR' AS UF,
        CASE 
            WHEN TIPOCALCST_PRODUTO = '-1' THEN 'SEM ST'
            WHEN TIPOCALCST_PRODUTO = '0' THEN 'PMC'
            WHEN TIPOCALCST_PRODUTO = '1' THEN 'MVA'
            WHEN TIPOCALCST_PRODUTO = '4' THEN 'PMPF'
        END AS TIPOCALCST,
        FPOPULAR_PRODUTO AS FLG_FPOPULAR,
        PRFPOPULAR_PRODUTO AS PMC,
        NULL AS REDUTOR_CRED,
        NULL AS REDUTOR_DEB,
        MVA_PRODUTO/100.0000 AS MVA,
        ICMSST_PRODUTO/100.0000 AS ALIQ_ICMS_DEB,
        ICMS_PRODUTO/100.0000 AS ALIQ_ICMS_CRED,
        VLRPMPF_PRODUTO AS PMPF
    FROM PRODUTOS p
    WHERE STATUS_PRODUTO = 1
    
    UNION ALL

    SELECT
        CODPROD_ICMS_FORA AS COD_PROD,
        UF_ICMS_FORA AS UF,
        CASE 
            WHEN TIPOCALCST_IMCS_FORA = -1 THEN 'SEM ST'
            WHEN TIPOCALCST_IMCS_FORA = 0 THEN 'PMC'
            WHEN TIPOCALCST_IMCS_FORA = 1 THEN 'MVA'
            WHEN TIPOCALCST_IMCS_FORA = 4 THEN 'PMPF'
        END AS TIPOCALCST,
        P.FPOPULAR_PRODUTO AS FLG_FPOPULAR,
        PMC_ICMS_FORA AS PMC,
        BASECALC_ICMS_FORA/100.0000 AS REDUTOR_CRED,
        BASECALCPMC_ICMS_FORA/100.0000 AS REDUTOR_DEB,
        MVAPAUTA_ICMS_FORA/100.0000 AS MVA,
        ALIQ_ICMS_EXTERNA_ICMS_FORA/100.0000 AS ALIQ_ICMS_DEB,
        ALIQ_ICMS_FORA/100.0000 AS ALIQ_ICMS_CRED,
        VLRPMPF_PRODUTO AS PMPF
    FROM ICMS_FORA ICMS_F
    LEFT JOIN PRODUTOS P ON CODPROD_ICMS_FORA = COD_PRODUTO
    WHERE UF_ICMS_FORA <> 'PR'
)

SELECT
    CODCLI_CLIV AS COD_CLIENTE,
    UF_CIDADE,
    COD_PRODUTO,
    LISTA.PRVENDA_COM_DESC,
    CASE
        WHEN FLG_FPOPULAR = 'S' AND CLIENTES.HEFPOPULAR_CLIENTE = 'S' AND UF_CIDADE = 'PR' 
        THEN 'PMC' 
        ELSE PAR.TIPOCALCST 
    END AS TIPOCALCST, 
    ROUND(
        CASE
            WHEN FLG_FPOPULAR = 'S' AND CLIENTES.HEFPOPULAR_CLIENTE = 'S' AND UF_CIDADE = 'PR' 
                THEN ((PAR.PMC) * ALIQ_ICMS_DEB) - (LISTA.PRVENDA_COM_DESC * ALIQ_ICMS_CRED)
            ELSE
                CASE 
                    WHEN TIPOCALCST = 'PMPF' THEN (PMPF * ALIQ_ICMS_DEB) - (LISTA.PRVENDA_COM_DESC * ALIQ_ICMS_CRED)
                    WHEN TIPOCALCST = 'MVA'  THEN ((LISTA.PRVENDA_COM_DESC * MVA + LISTA.PRVENDA_COM_DESC) * ALIQ_ICMS_DEB)
                                           - ((LISTA.PRVENDA_COM_DESC * COALESCE(REDUTOR_CRED,0)) * ALIQ_ICMS_CRED)
                    WHEN TIPOCALCST = 'PMC'  THEN ((LISTA.PMC * REDUTOR_DEB) * ALIQ_ICMS_DEB)
                                           - (LISTA.PRVENDA_COM_DESC * ALIQ_ICMS_CRED)
                    WHEN TIPOCALCST = 'SEM ST' THEN 0
                END 
        END, 2
    ) AS ST

FROM CLI_VENDEDORES CLI
LEFT JOIN LISTA_PRECOS_ATUAL LISTA ON LISTA.ID = CLI.CODLISTAPR_CLIV
LEFT JOIN CLIENTES ON CLI.CODCLI_CLIV = COD_CLIENTE
LEFT JOIN PRODUTOS P ON LISTA.CODPROD = COD_PRODUTO
LEFT JOIN CIDADES c ON CODCIDADE_CLIENTE = c.COD_CIDADE 
LEFT JOIN PARAMETROS PAR ON UF_CIDADE = PAR.UF AND LISTA.CODPROD = PAR.COD_PROD

WHERE POSICAO_CLIV = 1
  AND STATUS_PRODUTO = 1
  AND STATUS_CLIENTE = 'A'
"""

# =======================================
# 5. INTERFACE STREAMLIT
# =======================================
st.title("🔎 Calculadora ST")
st.subheader("Filtros opcionais")

cod_clientes_str = st.text_input("Filtrar por COD_CLIENTE (separar por vírgula):")
cod_produtos_str = st.text_input("Filtrar por COD_PRODUTO (separar por vírgula):")

# =======================================
# 6. EXECUTAR CONSULTA
# =======================================
if st.button("Executar Consulta"):
    try:
        conn = conectar_firebird()
        query = SQL_BASE

        # --- FILTRO CLIENTES ---
        if cod_clientes_str:
            lista = [c.strip() for c in cod_clientes_str.split(',') if c.strip().isdigit()]
            if lista:
                query += f" AND CLI.CODCLI_CLIV IN ({','.join(lista)})"

        # --- FILTRO PRODUTOS ---
        if cod_produtos_str:
            lista = [p.strip() for p in cod_produtos_str.split(',') if p.strip().isdigit()]
            if lista:
                query += f" AND P.COD_PRODUTO IN ({','.join(lista)})"

        df = pd.read_sql(query, conn)
        conn.close()

        st.success(f"{len(df)} registros encontrados.")
        st.dataframe(df, width=1000)

    except Exception as e:
        st.error(f"Erro ao executar consulta: {e}")
