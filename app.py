import streamlit as st
import pandas as pd
import fdb
from dotenv import load_dotenv
import os

# =======================================
# 1. CARREGAR VARIÁVEIS DO ARQUIVO .ENV
# =======================================
load_dotenv()

FB_HOST = os.getenv("FB_HOST")          # ex: 127.0.0.1
FB_PORT = os.getenv("FB_PORT")
FB_DATABASE = os.getenv("FB_DATABASE")  # caminho do .fdb
FB_USER = os.getenv("FB_USER")
FB_PASSWORD = os.getenv("FB_PASSWORD")

# =======================================
# 2. FORÇAR CARREGAMENTO DO CLIENT FIREBIRD
# =======================================
try:
    fdb.load_api(r'C:\Drivers\Firebird\GDS32.DLL')
except Exception as e:
    print("Erro ao carregar biblioteca Firebird:", e)

# =======================================
# 3. FUNÇÃO DE CONEXÃO
# =======================================
def conectar_firebird():
    return fdb.connect(
        host=FB_HOST,               # já inclui host:porta
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASSWORD,
        charset="UTF8"
    )


# =======================================
# 4. CONSULTA SQL COMPLETA
# =======================================
SQL = """
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
st.title("🔎 Calculadora ST (Em Testes)")

st.subheader("Filtros opcionais")

# Instrução para múltiplos valores separados por vírgula
cod_clientes_str = st.text_input("Filtrar por COD_CLIENTE (separar múltiplos por vírgula):")
cod_produtos_str = st.text_input("Filtrar por COD_PRODUTO (separar múltiplos por vírgula):")

if st.button("Executar Consulta"):
    try:
        conn = conectar_firebird()
        query = SQL

        # --- Lógica de Filtragem por Múltiplos Valores ---

        # 1. Processar códigos de cliente
        if cod_clientes_str:
            # Divide a string por vírgula, remove espaços e filtros vazios
            # O resultado é uma string de códigos separados por vírgula: "100,201,350"
            lista_clientes = ','.join([c.strip() for c in cod_clientes_str.split(',') if c.strip().isdigit()])
            if lista_clientes:
                # Adiciona o filtro usando o operador IN
                # Importante: A cláusula WHERE deve ser adicionada à sua SQL completa
                query += f" AND CLI.CODCLI_CLIV IN ({lista_clientes})"

        # 2. Processar códigos de produto
        if cod_produtos_str:
            # Divide a string por vírgula, remove espaços e filtros vazios
            # Assumindo que COD_PRODUTO é numérico. Se for STRING, precisa de aspas: "'PROD1','PROD2'"
            lista_produtos = ','.join([p.strip() for p in cod_produtos_str.split(',') if p.strip().isdigit()])
            if lista_produtos:
                # Adiciona o filtro usando o operador IN
                query += f" AND P.COD_PRODUTO IN ({lista_produtos})"
        
        # ------------------------------------------------

        df = pd.read_sql(query, conn)

        st.success(f"{len(df)} registros encontrados.")
        st.dataframe(df, use_container_width=True)

        conn.close()

    except Exception as e:
        st.error(f"Erro ao executar consulta: {e}")
