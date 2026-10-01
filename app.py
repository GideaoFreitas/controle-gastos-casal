from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Controle de Gastos - Casal", layout="wide")

st.title("💰 Controle Financeiro Inteligente do Casal")

try:
   db_url = st.secrets["DB_URL"]

# Se a URL começar com postgres://, mudamos para postgresql+psycopg2://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(db_url)
# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_gastos():
  try:
    df = pd.read_sql("SELECT * FROM gastos", engine)
    if not df.empty:
      # Converte o DataFrame do banco para o formato de lista de dicionários que o app usa
      return df.to_dict(orient="records")
    return []
  except Exception:
    # Se a tabela não existir ainda, retorna lista vazia
    return []


def carregar_rendas():
  try:
    df = pd.read_sql("SELECT * FROM rendas", engine)
    if not df.empty:
      return df.to_dict(orient="records")
    return []
  except Exception:
    return []


# Criar tabelas automaticamente se não existirem
with engine.begin() as conn:
  conn.execute(
      __import__("sqlalchemy").text("""
        CREATE TABLE IF NOT EXISTS gastos (
            id TEXT PRIMARY KEY,
            mes TEXT,
            responsavel TEXT,
            categoria TEXT,
            valor NUMERIC,
            descricao TEXT,
            data TEXT
        );
    """)
  )
  conn.execute(
      __import__("sqlalchemy").text("""
        CREATE TABLE IF NOT EXISTS rendas (
            mes TEXT PRIMARY KEY,
            marido NUMERIC,
            esposa NUMERIC
        );
    """)
  )


# Inicializar dados do banco na sessão
if "historico" not in st.session_state:
  st.session_state.historico = carregar_gastos()

if "rendas" not in st.session_state:
  st.session_state.rendas = carregar_rendas()

mes_atual = datetime.now().strftime("%Y-%m")

# --- SIDEBAR: CONFIGURAÇÕES E LANÇAMENTOS ---
st.sidebar.header("⚙️ Configurações e Lançamentos")

# 1. Gerenciar Categorias
if "categorias" not in st.session_state:
  st.session_state.categorias = [
      "Alimentação",
      "Moradia",
      "Transporte",
      "Lazer",
      "Saúde",
      "Investimentos",
      "Outros",
  ]

nova_categoria = st.sidebar.text_input("Adicionar Nova Categoria de Gasto")
if st.sidebar.button("Cadastrar Categoria"):
  if nova_categoria and nova_categoria not in st.session_state.categorias:
    st.session_state.categorias.append(nova_categoria)
    st.sidebar.success(f"Categoria '{nova_categoria}' adicionada!")
    st.rerun()

st.sidebar.divider()

# 2. Registrar Rendas Mensais
st.sidebar.subheader("💵 Registrar Entradas (Salários)")
mes_renda = st.sidebar.selectbox(
    "Mês de Referência (Renda)", [mes_atual, "2026-08", "2026-07", "2026-06"]
)
renda_marido = st.sidebar.number_input(
    "Quanto o Marido recebe (R$)", min_value=0.0, format="%.2f", key="r_marido"
)
renda_esposa = st.sidebar.number_input(
    "Quanto a Esposa recebe (R$)", min_value=0.0, format="%.2f", key="r_esposa"
)

if st.sidebar.button("Salvar Rendas do Mês"):
  df_renda_novo = pd.DataFrame(
      [{"mes": mes_renda, "marido": renda_marido, "esposa": renda_esposa}]
  )

  # Salva no Supabase (atualiza se já existir o mês)
  with engine.begin() as conn:
    conn.execute(
        __import__("sqlalchemy").text(
            "DELETE FROM rendas WHERE mes = :mes_val"
        ),
        {"mes_val": mes_renda},
    )
  df_renda_novo.to_sql(
      "rendas", engine, if_exists="append", index=False, method="multi"
  )

  st.session_state.rendas = carregar_rendas()
  st.sidebar.success("Rendas salvas com sucesso no banco!")
  st.rerun()

st.sidebar.divider()

# 3. Adicionar Gastos em Tempo Real
st.sidebar.subheader("🛒 Novo Gasto")
mes_gasto = st.sidebar.selectbox(
    "Mês de Referência (Gasto)", [mes_atual, "2026-08", "2026-07", "2026-06"]
)
responsavel = st.sidebar.selectbox("Quem gastou?", ["Marido", "Esposa", "Ambos"])
categoria_escolhida = st.sidebar.selectbox(
    "Categoria", st.session_state.categorias
)
valor_gasto = st.sidebar.number_input(
    "Valor do Gasto (R$)", min_value=0.0, format="%.2f", key="v_gasto"
)
descricao = st.sidebar.text_input("Descrição (opcional)")

if st.sidebar.button("Adicionar Gasto"):
  if valor_gasto > 0:
    novo_registro = {
        "id": str(datetime.now().timestamp()),
        "mes": mes_gasto,
        "responsavel": responsavel,
        "categoria": categoria_escolhida,
        "valor": valor_gasto,
        "descricao": descricao,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    df_novo_gasto = pd.DataFrame([novo_registro])
    df_novo_gasto.to_sql(
        "gastos", engine, if_exists="append", index=False, method="multi"
    )

    st.session_state.historico = carregar_gastos()
    st.sidebar.success("Gasto adicionado ao banco!")
    st.rerun()
  else:
    st.sidebar.error("O valor deve ser maior que zero.")

# --- ÁREA PRINCIPAL ---
meses_com_dados = list(set([h["mes"] for h in st.session_state.historico]))
if mes_atual not in meses_com_dados:
  meses_com_dados.append(mes_atual)
meses_com_dados = sorted(meses_com_dados, reverse=True)

filtro_mes = st.selectbox("📅 Selecione o Mês para Análise", meses_com_dados)

# Filtrar dados e rendas do mês
dados_filtrados = [
    h for h in st.session_state.historico if h["mes"] == filtro_mes
]
renda_mes = next(
    (r for r in st.session_state.rendas if r["mes"] == filtro_mes),
    {"marido": 0.0, "esposa": 0.0},
)

total_renda = renda_mes["marido"] + renda_mes["esposa"]
total_gasto = (
    sum([d["valor"] for d in dados_filtrados]) if dados_filtrados else 0.0
)
saldo = total_renda - total_gasto

# Exibir Métricas de Resumo
col1, col2, col3 = st.columns(3)
col1.metric("💵 Renda Total do Mês", f"R$ {total_renda:.2f}")
col2.metric("🛒 Gastos Totais", f"R$ {total_gasto:.2f}")

delta_color = "normal" if saldo >= 0 else "inverse"
col3.metric(
    "📊 Saldo do Mês",
    f"R$ {saldo:.2f}",
    delta=(
        "Equilibrado/Positivo" if saldo >= 0 else "No Vermelho (Déficit)"
    ),
    delta_color=delta_color,
)

st.divider()

if dados_filtrados or total_renda > 0:
  col_grafico, col_tabela = st.columns([1, 1])

  with col_grafico:
    st.subheader("🥧 Divisão dos Gastos por Categoria")
    if dados_filtrados:
      df = pd.DataFrame(dados_filtrados)
      df_cat = df.groupby("categoria")["valor"].sum().reset_index()
      fig = px.pie(
          df_cat,
          values="valor",
          names="categoria",
          hole=0.4,
          title=f"Gastos em {filtro_mes}",
      )
      st.plotly_chart(fig, use_container_width=True)
    else:
      st.info("Nenhum gasto registrado neste mês.")

  with col_tabela:
    st.subheader("📋 Detalhes dos Lançamentos")
    if dados_filtrados:
      df = pd.DataFrame(dados_filtrados)
      st.dataframe(
          df[
              ["data", "responsavel", "categoria", "descricao", "valor"]
          ].sort_values(by="data", ascending=False),
          use_container_width=True,
      )

      gasto_para_excluir = st.selectbox(
          "Remover lançamento:",
          options=df["id"].tolist(),
          format_func=lambda x: f"{df[df['id'] == x]['data'].values[0]} - {df[df['id'] == x]['categoria'].values[0]} - R$ {df[df['id'] == x]['valor'].values[0]:.2f}",
      )
      if st.button("Excluir Gasto"):
        with engine.begin() as conn:
          conn.execute(
              __import__("sqlalchemy").text(
                  "DELETE FROM gastos WHERE id = :id_val"
              ),
              {"id_val": str(gasto_para_excluir)},
          )
        st.session_state.historico = carregar_gastos()
        st.success("Gasto removido com sucesso!")
        st.rerun()
    else:
      st.write("Sem lançamentos para exibir.")

  # --- DICAS FINANCEIRAS AUTOMATIZADAS NO FINAL ---
  st.subheader("💡 Dicas para Melhorar a Vida Financeira do Casal")
  if total_renda == 0:
    st.warning(
        "⚠️ Vocês ainda não informaram as rendas deste mês na barra lateral."
        " Preencha para receber análises completas!"
    )
  else:
    percentual_gasto = (
        (total_gasto / total_renda) * 100 if total_renda > 0 else 0
    )

    if saldo < 0:
      st.error(
          f"🚨 **Alerta Vermelho:** Vocês gastaram {percentual_gasto:.1f}% da"
          f" renda total e estão com um déficit de **R$ {abs(saldo):.2f}**."
          " Recomenda-se cortar urgentemente gastos supérfluos (como lazer e"
          " delivery) até reequilibrar as contas."
      )
    elif percentual_gasto > 80:
      st.warning(
          f"⚠️ **Atenção:** Vocês comprometeram {percentual_gasto:.1f}% da"
          " renda. O ideal é manter os gastos abaixo de 70% para conseguir"
          " construir uma reserva de emergência ou investir para o futuro do"
          " casal."
      )
    elif percentual_gasto > 50:
      st.success(
          f"✅ **Bom Trabalho!** Vocês gastaram {percentual_gasto:.1f}% da"
          " renda e terminaram o mês no azul. Continuem mantendo o controle das"
          " categorias principais."
      )
    else:
      st.balloons()
      st.success(
          "🌟 **Excelente!** Vocês pouparam mais da metade da renda do casal este"
          " mês. Excelente momento para direcionar o excedente para"
          " investimentos conjuntos ou sonhos futuros!"
      )

    if dados_filtrados:
      df_cat = df.groupby("categoria")["valor"].sum().reset_index()
      maior_gasto = df_cat.loc[df_cat["valor"].idxmax()]
      st.info(
          f"🔍 **Curiosidade do mês:** A categoria que mais pesou no orçamento"
          f" foi **{maior_gasto['categoria']}**, totalizando R$"
          f" {maior_gasto['valor']:.2f} ({(maior_gasto['valor']/total_renda)*100:.1f}%"
          " da renda)."
      )

else:
  st.info(
      "👈 Comece preenchendo as rendas e adicionando os gastos na barra lateral."
  )

# 4. Histórico Completo
with st.expander("📁 Visualizar Histórico de Rendas e Gastos"):
  st.write("### Histórico de Rendas")
  if st.session_state.rendas:
    st.dataframe(pd.DataFrame(st.session_state.rendas), use_container_width=True)
  else:
    st.write("Nenhuma renda registrada.")

  st.write("### Histórico de Gastos")
  if st.session_state.historico:
    st.dataframe(
        pd.DataFrame(st.session_state.historico), use_container_width=True
    )
  else:
    st.write("Nenhum gasto registrado.")
