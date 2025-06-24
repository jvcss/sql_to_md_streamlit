import streamlit as st
import asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
import pandas as pd

DATABASE_URL = "sqlite+aiosqlite:///meu_banco_teste.db"

# SQL padrão como template inicial
DEFAULT_SQL = """DROP TABLE IF EXISTS cliente;
DROP TABLE IF EXISTS empresa;

CREATE TABLE empresa (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE cliente (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    email TEXT,
    empresa_id INTEGER,
    FOREIGN KEY (empresa_id) REFERENCES empresa(id)
);

INSERT INTO empresa (id, nome) VALUES
(1, 'OpenAI'),
(2, 'Growth Inc.');

INSERT INTO cliente (id, nome, email, empresa_id) VALUES
(1, 'João Victor', 'joao@example.com', 1),
(2, 'Maria Silva', NULL, 2),
(3, NULL, 'maria@example.com', NULL);"""

async def execute_sql(engine, raw_sql: str):
    async with engine.begin() as conn:
        for statement in raw_sql.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(text(stmt))

async def fetch_schema_markdown(db_url: str) -> str:
    engine = create_async_engine(db_url)
    output = ["## Banco de Dados: exemplo_sqlite\n"]

    async with engine.begin() as conn:
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    async with engine.connect() as conn:
        for tbl in table_names:
            output.append(f"### Tabela: `{tbl}`\n")
            try:
                cols = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns(tbl))
                output.append("| Coluna | Tipo |\n|--------|------|")
                for c in cols:
                    output.append(f"| {c['name']} | {c['type']} |")

                pk_info = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_pk_constraint(tbl))
                pks = pk_info.get("constrained_columns", []) if pk_info else []
                if pks:
                    output.append(f"\n**Chave Primária:** `{', '.join(pks)}`\n")

                fks = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_foreign_keys(tbl))
                if fks:
                    output.append("\n**Relacionamentos (chaves estrangeiras):**")
                    for fk in fks:
                        col = ", ".join(fk["constrained_columns"])
                        ref_table = fk["referred_table"]
                        ref_cols = ", ".join(fk["referred_columns"])
                        output.append(f"- `{col}` → `{ref_table}({ref_cols})`")

                if cols:
                    query = f"""
                        SELECT * FROM `{tbl}`
                        ORDER BY (
                            { " + ".join([f"CASE WHEN `{c['name']}` IS NOT NULL THEN 1 ELSE 0 END" for c in cols]) }
                        ) DESC
                        LIMIT 1
                    """
                    result = await conn.execute(text(query))
                    row = result.fetchone()

                    if row:
                        df = pd.DataFrame([row], columns=result.keys())
                        output.append("\n**Exemplo de dados:**\n")
                        output.append(df.to_markdown(index=False))
                    else:
                        output.append("\n*Sem dados disponíveis*")
            except Exception as e:
                output.append(f"*Erro ao processar tabela `{tbl}`: {e}*")
            output.append("")

    await engine.dispose()
    return "\n".join(output)

# --- Streamlit App ---
st.set_page_config(page_title="Documentação SQL Automática", layout="wide")
st.title("📄 Gerador de Documentação Markdown para Esquema SQL")

tab_md, tab_sql = st.tabs(["📜 Markdown", "🧱 SQL Schema"])

with tab_sql:
    st.subheader("🔧 Definição do Esquema SQL")
    user_sql = st.text_area("SQL para criação do esquema:", value=DEFAULT_SQL, height=300)

    if st.button("🧱 Executar Script SQL e Resetar Banco"):
        engine = create_async_engine(DATABASE_URL)
        try:
            asyncio.run(execute_sql(engine, user_sql))
            st.success("Script executado com sucesso. Banco reinicializado.")
        except Exception as e:
            st.error(f"Erro ao executar o script SQL:\n{e}")
        finally:
            asyncio.run(engine.dispose())

with tab_md:
    st.subheader("📄 Visualização da Documentação Markdown")
    if st.button("📄 Gerar Markdown"):
        with st.spinner("Analisando estrutura do banco..."):
            markdown = asyncio.run(fetch_schema_markdown(DATABASE_URL))
            st.download_button(
                label="💾 Baixar Markdown",
                data=markdown,
                file_name="documentacao_banco.md",
                mime="text/markdown",
                use_container_width=True
            )
            st.markdown(markdown)
# Streamlit app to generate SQL schema documentation in Markdown format
