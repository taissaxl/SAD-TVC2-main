import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import matplotlib.pyplot as plt

# configuração da página do dashboard para ocupar a tela toda
st.set_page_config(page_title="SAD - Precificação Amazon", layout="wide")

st.title("📊 Sistema de Apoio à Decisão (SAD) - Precificação Tática")
st.markdown("Interface interativa baseada no processamento de dados do e-commerce.")

print("A carregar os dados do amazon.csv...")
try:
    df = pd.read_csv('amazon.csv')
    print("Ficheiro da Amazon carregado com sucesso!")
except FileNotFoundError:
    print("ERRO: O ficheiro 'amazon.csv' não foi encontrado na pasta.")
    st.error("ERRO: O ficheiro 'amazon.csv' não foi encontrado na pasta.")
    st.stop()

# limpeza dos dados: remover o símbolo '₹' (rupia) e converter preços para float
def limpar_preco(valor):
    if pd.isna(valor): return 0.0
    return float(str(valor).replace('₹', '').replace(',', '').strip())

df['Preco_Original'] = df['actual_price'].apply(limpar_preco)

# como a coluna category tem subcategorias longas separadas por '|',
# vamos extrair apenas o primeiro nome para termos categorias limpas.
df['Categoria_Principal'] = df['category'].apply(lambda x: str(x).split('|')[0] if pd.notna(x) else 'Outros')

# filtrar o volume de demanda (remover vírgulas do rating_count)
df['Demanda_Base'] = df['rating_count'].astype(str).str.replace(',', '').str.strip()
df['Demanda_Base'] = pd.to_numeric(df['Demanda_Base'], errors='coerce').fillna(100)

# agrupamos por categoria principal para extrair a média de preço real e volume real
df_base = df.groupby('Categoria_Principal').agg(
    Preco_Original=('Preco_Original', 'mean'),
    Quantidade_Base=('Demanda_Base', 'sum')
).reset_index()

# selecionamos as 3 categorias com maior volume
df_base = df_base.sort_values(by='Quantidade_Base', ascending=False).head(3).copy()

st.sidebar.header("⚙️ Parâmetros das Regras de Negócio")
st.sidebar.markdown("Arraste os controles abaixo para reconfigurar as variáveis do SAD ao vivo:")

# injetando as variáveis do sad (margens e elasticidades)
# como a base não traz margem nem elasticidade, o sad injeta estas premissas por sliders:
premissas_dinamicas = {}
for idx, row in df_base.iterrows():
    cat = row['Categoria_Principal']
    st.sidebar.subheader(f"📁 {cat}")
    
    # valores padrão originais do script para servir de início
    margem_padrao = 0.40 if "Electronics" in cat else (0.45 if "Computers" in cat else 0.35)
    eps_padrao = -2.5 if "Electronics" in cat else (-1.4 if "Computers" in cat else -0.8)
    
    # sliders interativos para o gestor brincar com os números
    margem = st.sidebar.slider(f"Margem de Lucro Base ({cat})", 0.10, 0.80, margem_padrao, 0.05)
    elasticidade = st.sidebar.slider(f"Elasticidade-Preço ({cat})", -5.0, -0.1, eps_padrao, 0.1)
    
    premissas_dinamicas[cat] = {'margem': margem, 'eps': elasticidade}

# motor analítico what-if (simulação de cenários)
politicas_desconto = [0.00, 0.05, 0.10, 0.15, 0.20] # políticas a testar: 0% a 20%
resultados_simulacao = []

for dct in politicas_desconto:
    for idx, row in df_base.iterrows():
        cat = row['Categoria_Principal']
        p0 = row['Preco_Original']
        q0 = row['Quantidade_Base']
        
        # puxa os dados ajustados dinamicamente nos controles laterais da tela
        margem_atual = premissas_dinamicas[cat]['margem']
        eps_atual = premissas_dinamicas[cat]['eps']
        
        # calcula o custo unitário fixo com base nos preços reais extraídos da amazon
        custo = p0 * (1 - margem_atual)
        
        # projeções do que aconteceria (what-if)
        p_novo = p0 * (1 - dct)
        q_nova = int(q0 * (1 - (eps_atual * dct))) # modelo matemático da elasticidade-preço
        receita_nova = p_novo * q_nova
        lucro_novo = (p_novo - custo) * q_nova
        
        resultados_simulacao.append({
            'Cenário Desconto': f"{int(dct*100)}%",
            'Categoria': cat,
            'Preço Médio ($)': round(p_novo, 2),
            'Demanda Projetada (Uds)': q_nova,
            'Lucro Estimado ($)': round(lucro_novo, 2)
        })

df_what_if = pd.DataFrame(resultados_simulacao)

# geração automática do arquivo png para o latex em segundo plano
plt.figure(figsize=(10, 5))
for cat in df_base['Categoria_Principal']:
    dados_cat = df_what_if[df_what_if['Categoria'] == cat]
    plt.plot(dados_cat['Cenário Desconto'], dados_cat['Lucro Estimado ($)'], marker='o', linewidth=2, label=cat)

plt.title('Análise What-If: Impacto dos Descontos no Lucro (Base Amazon)', fontsize=12, fontweight='bold', color='black')
plt.xlabel('Cenários de Desconto Concedido', color='black')
plt.ylabel('Lucro Líquido Projetado ($)', color='black')
plt.xticks(color='black')
plt.yticks(color='black')
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()
plt.savefig('grafico_what_if_amazon.png', dpi=300)
plt.close()

# tomada de decisão automatizada
lucro_por_cenario = df_what_if.groupby('Cenário Desconto')['Lucro Estimado ($)'].sum()
melhor_cenario = lucro_por_cenario.idxmax()
maior_lucro = lucro_por_cenario.max()

# bloco de cartões com os outputs de recomendação e lucro máximo
col1, col2 = st.columns(2)
with col1:
    st.metric(label="💡 RECOMENDAÇÃO AUTOMÁTICA DO SAD", value=f"Política de {melhor_cenario} de desconto.")
with col2:
    st.metric(label="💰 Lucro Consolidado Projetado", value=f"$ {maior_lucro:,.2f}")

st.markdown("---")

# visualização dos dados 
fig = px.line(
    df_what_if, 
    x='Cenário Desconto', 
    y='Lucro Estimado ($)', 
    color='Categoria',
    markers=True,
    labels={'Lucro Estimado ($)': 'Lucro Líquido Projetado ($)', 'Cenário Desconto': 'Cenários de Desconto Concedido'},
    title="Análise What-If: Impacto dos Descontos no Lucro (Base Amazon)"
)

fig.update_layout(
    hovermode="x unified", 
    template="plotly_white",
    title={
        'font': {'size': 16, 'family': 'sans-serif', 'color': 'white'},
        'y': 0.95,
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top'
    },
    font=dict(
        family="sans-serif", 
        size=12, 
        color="white"
    ),
    xaxis=dict(
        title_font=dict(color='white'),
        tickfont=dict(color='white'),
        gridcolor='lightgray'
    ),
    yaxis=dict(
        title_font=dict(color='white'),
        tickfont=dict(color='white'),
        gridcolor='lightgray'
    ),
    legend=dict(
        font=dict(color='white'),
        bordercolor='white',
        borderwidth=1
    )
)

# mostra o gráfico interativo na interface web configurado com a largura elástica stretch
st.plotly_chart(fig, width='stretch')

# comparação direta: uma política escolhida x cenário sem desconto (0%)
import plotly.graph_objects as go

def formatar_valor(v, sinal=False):
    """formata valores grandes de forma curta (mil / mi / bi) no padrão brasileiro"""
    s = '-' if v < 0 else ('+' if sinal and v > 0 else '')
    a = abs(v)
    for limite, sufixo in [(1e9, ' bi'), (1e6, ' mi'), (1e3, ' mil')]:
        if a >= limite:
            num = f"{a / limite:,.1f}"
            break
    else:
        num, sufixo = f"{a:,.0f}", ''
    num = num.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{s}$ {num}{sufixo}"

def formatar_pct(v):
    return f"{v:+.1f}%".replace('.', ',')

st.markdown("---")
st.subheader("🔍 Comparar uma política com o cenário sem desconto")
st.markdown(
    "Escolha uma política de desconto e veja, para cada categoria, se o lucro **sobe ou cai** "
    "em relação a **não dar desconto nenhum**. Dar desconto baixa o preço, mas atrai mais clientes: "
    "a política só compensa quando o aumento nas vendas cobre o lucro que se perde por unidade."
)

opcoes_politica = [f"{int(d*100)}%" for d in politicas_desconto if d > 0]
indice_padrao = opcoes_politica.index(melhor_cenario) if melhor_cenario in opcoes_politica else 0
politica = st.radio("Política de desconto a comparar:", opcoes_politica, index=indice_padrao, horizontal=True)

base = df_what_if[df_what_if['Cenário Desconto'] == '0%'].set_index('Categoria')
sel = df_what_if[df_what_if['Cenário Desconto'] == politica].set_index('Categoria')

df_comp = pd.DataFrame({
    'Demanda sem desconto (Uds)': base['Demanda Projetada (Uds)'],
    f'Demanda com {politica} (Uds)': sel['Demanda Projetada (Uds)'],
    'Lucro sem desconto ($)': base['Lucro Estimado ($)'],
    f'Lucro com {politica} ($)': sel['Lucro Estimado ($)'],
})
df_comp['Diferença ($)'] = df_comp[f'Lucro com {politica} ($)'] - df_comp['Lucro sem desconto ($)']
df_comp['Variação do Lucro (%)'] = df_comp['Diferença ($)'] / df_comp['Lucro sem desconto ($)'].abs() * 100
df_comp['Variação da Demanda (%)'] = (
    (df_comp[f'Demanda com {politica} (Uds)'] / df_comp['Demanda sem desconto (Uds)'] - 1) * 100
)

total_base = df_comp['Lucro sem desconto ($)'].sum()
total_sel = df_comp[f'Lucro com {politica} ($)'].sum()
dif_total = total_sel - total_base
var_total = dif_total / abs(total_base) * 100

ganham = [c for c, d in df_comp['Diferença ($)'].items() if d > 0]
perdem = [c for c, d in df_comp['Diferença ($)'].items() if d < 0]
if dif_total > 0:
    veredito = f"✅ **Vale a pena.** Com {politica} de desconto, o lucro total **sobe {formatar_valor(dif_total)} ({formatar_pct(var_total)})** em relação a não dar desconto."
elif dif_total < 0:
    veredito = f"❌ **Não vale a pena.** Com {politica} de desconto, o lucro total **cai {formatar_valor(abs(dif_total))} ({formatar_pct(var_total)})** em relação a não dar desconto."
else:
    veredito = f"➖ Com {politica} de desconto, o lucro total fica **igual** ao cenário sem desconto."
detalhes = []
if ganham:
    detalhes.append("Categorias que **ganham**: " + ", ".join(ganham) + ".")
if perdem:
    detalhes.append("Categorias que **perdem**: " + ", ".join(perdem) + ".")
st.markdown(veredito + "  \n" + " ".join(detalhes))

# cartões: total + um por categoria, sempre "com desconto" e a diferença para o sem desconto
colunas = st.columns(len(df_comp) + 1)
with colunas[0]:
    st.metric(
        label="Lucro TOTAL",
        value=formatar_valor(total_sel),
        delta=f"{formatar_valor(dif_total, sinal=True)} ({formatar_pct(var_total)})",
        help=f"Sem desconto: {formatar_valor(total_base)}",
    )
    st.caption(f"Sem desconto: {formatar_valor(total_base)}")
for col, (cat, linha) in zip(colunas[1:], df_comp.iterrows()):
    with col:
        st.metric(
            label=cat,
            value=formatar_valor(linha[f'Lucro com {politica} ($)']),
            delta=f"{formatar_valor(linha['Diferença ($)'], sinal=True)} ({formatar_pct(linha['Variação do Lucro (%)'])})",
        )
        st.caption(
            f"Sem desconto: {formatar_valor(linha['Lucro sem desconto ($)'])} · "
            f"Vendas: {formatar_pct(linha['Variação da Demanda (%)'])}"
        )

# gráfico de barras divergente: variação % do lucro em relação ao sem desconto
nomes = list(df_comp.index) + ['TOTAL']
variacoes = list(df_comp['Variação do Lucro (%)']) + [var_total]
cores = ['#2e9e5b' if v >= 0 else '#d64545' for v in variacoes]

fig_comp = go.Figure(go.Bar(
    x=variacoes,
    y=nomes,
    orientation='h',
    marker_color=cores,
    text=[formatar_pct(v) for v in variacoes],
    textposition='outside',
    cliponaxis=False,
    hovertemplate='%{y}: %{text} de lucro vs. sem desconto<extra></extra>',
))
limite_x = max(abs(v) for v in variacoes) * 1.35 or 1
fig_comp.add_vline(x=0, line_width=2, line_color='gray')
fig_comp.update_layout(
    title=f"Quanto o lucro muda com {politica} de desconto (em relação a 0%)",
    xaxis=dict(title='Variação do lucro (%)', range=[-limite_x, limite_x], ticksuffix='%', zeroline=False),
    yaxis=dict(autorange='reversed'),
    height=120 + 60 * len(nomes),
    margin=dict(l=10, r=10, t=60, b=40),
    showlegend=False,
)
st.plotly_chart(fig_comp, width='stretch')
st.caption("🟩 barra verde = lucro maior que sem desconto · 🟥 barra vermelha = lucro menor que sem desconto")

with st.expander(f"📄 Tabela da comparação: {politica} x sem desconto"):
    st.dataframe(
        df_comp.style.format({
            'Demanda sem desconto (Uds)': '{:,.0f}',
            f'Demanda com {politica} (Uds)': '{:,.0f}',
            'Lucro sem desconto ($)': '{:,.2f}',
            f'Lucro com {politica} ($)': '{:,.2f}',
            'Diferença ($)': '{:+,.2f}',
            'Variação do Lucro (%)': '{:+.1f}%',
            'Variação da Demanda (%)': '{:+.1f}%',
        }),
        width='stretch',
    )

st.markdown("---")

# expansor opcional para exibir a tabela de projeções na interface
with st.expander("📄 Visualizar Tabela Completa de Projeções What-If (Dados Amazon)"):
    st.dataframe(df_what_if[['Cenário Desconto', 'Categoria', 'Demanda Projetada (Uds)', 'Lucro Estimado ($)']], width='stretch')