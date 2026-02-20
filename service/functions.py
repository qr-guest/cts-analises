import pandas as pd
from datetime import datetime
from datetime import date, timedelta
from collections import defaultdict
import streamlit as st
import unidecode
import altair as alt
import io
import plotly.express as px
import plotly.graph_objects as go
import os
import time
import string
import json
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from copy import deepcopy

@st.cache_data
def load_translation(language):
    """Carrega o arquivo JSON de tradução para o idioma selecionado."""
    filepath = os.path.join("locale", f"{language}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Função para obter o texto traduzido
def get_text(key, **kwargs):
    """
    Obtém o texto traduzido para uma chave específica.
    Usa o idioma armazenado no session_state.
    Permite a formatação de strings com .format().
    """
    lang = st.session_state.get("language", "pt") 
    translations = load_translation(lang)
    text = translations.get(key, f"Texto não encontrado para a chave: {key}")
    if kwargs:
        return text.format(**kwargs)
    return text

nocs_nao_cadastradas = []

dict_meses = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez"
}

def clientes_clean(cliente):
    cliente = str(cliente)
    cliente = cliente.lower()
    cliente = unidecode.unidecode(cliente)
    cliente = cliente.replace('\xa0', "").strip()
    return cliente
  
def categorizar_divisao(cliente):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    if pd.isna(cliente):
        return 'outros'
    cliente = clientes_clean(cliente)
    if 'ball' in cliente:
        return 'planta_ball'
    for chave, lista_de_strings in divisoes.items():
        for s in lista_de_strings:
            if cliente in s:  # ignora maiúsculas/minúsculas
                return chave
    st.info(get_text("unclassified_client_info", cliente=cliente))
    return 'outros'

def filtrar_por_mes(df, campo_data, mes, ano):
    df_aux_copy = df.copy()
    if mes == '' or df.empty:
        return df
    df_aux_copy[campo_data] = pd.to_datetime(df_aux_copy[campo_data], format="%d/%m/%Y")
    return df[(df_aux_copy[campo_data].dt.month == int(mes)) & (df_aux_copy[campo_data].dt.year == int(ano))]

def filtrar_por_ytd(df, campo_data, mes, ano):
    df_aux_copy = df.copy()
    if mes == '' or df.empty:
        return df
    df_aux_copy[campo_data] = pd.to_datetime(df_aux_copy[campo_data], format="%d/%m/%Y", dayfirst=False)
    return df[(df_aux_copy[campo_data].dt.month <= int(mes)) & (df_aux_copy[campo_data].dt.year == int(ano))]

def get_visitas_por_divisao(df_rvt, mes, ano, ytd):
    if(ytd):
        df_filtrado = filtrar_por_ytd(df_rvt, 'DataInicio', mes, ano)
    else:
        df_filtrado = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano)
    
    visitas = defaultdict(lambda: defaultdict(int))
          
    for index, row in df_filtrado.iterrows():
        cliente = row['Clientes']
        motivo = row['Motivo']
        
        div = categorizar_divisao(cliente)
        visitas[div]['total'] += 1
        
        visitas[div][motivo] += 1
    # st.dataframe(dict(visitas))
    ka = st.selectbox("selecione um key account", options=[coluna for coluna in visitas.keys() if coluna not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: 
        display_gauge(visitas[ka]["QUALITY REVIEW"], "QUALITY REVIEW", "blue")
    with col2: 
        treinamentos = visitas[ka]["TREINAMENTO CLIENTE"] + visitas[ka]["TREINAMENTO"] + visitas[ka]["TREINAMENTO ON-SITE"] + visitas[ka]["TREINAMENTO FÁBRICA"] + visitas[ka]["TREINAMENTO CTS"] 
        display_gauge(treinamentos, "TREINAMENTOS", "blue")
    with col3: 
        display_gauge(visitas[ka]["SUPORTE TÉCNICO"], "SUPORTE TÉCNICO", "blue")
    with col4: 
        display_gauge(visitas[ka]["total"], "TOTAL DE RVTs", "blue")

def get_tipos_visitas_rvt(df_rvt, mes, ano, ytd):
    if(ytd):
        df_filtrado = filtrar_por_ytd(df_rvt, 'DataInicio', mes, ano)
    else:
        df_filtrado = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano)
    
    dados_atuais = {'preventiva':0, 'corretiva':0}
    for tipo in df_filtrado['Tipo']:
        if tipo == 'PREVENTIVA' or tipo == 'ATENDIMENTO REMOTO - PREVENTIVO':
            dados_atuais['preventiva'] += 1
        else: dados_atuais['corretiva'] += 1

    if mes == 1: 
        mes = 12
        ano = ano-1
    else: mes = mes-1
    
    # Dados do período anterior
    if(ytd):
        df_filtrado = filtrar_por_ytd(df_rvt, 'DataInicio', 12, ano)
    else:
        df_filtrado = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano)
    
    dados_anteriores = {'preventiva':0, 'corretiva':0}
    for tipo in df_filtrado['Tipo']:
        if tipo == 'PREVENTIVA' or tipo == 'ATENDIMENTO REMOTO - PREVENTIVO':
            dados_anteriores['preventiva'] += 1
        else: dados_anteriores['corretiva'] += 1


    col1, col2 = st.columns(2)
    # with col1:
    #     st.write("atual")
    #     st.dataframe(dados_atuais)
    # with col2:
    #     if(ytd):
    #         st.write("ano passado")
    #     else:
    #         st.write("mês passado")
    #     st.dataframe(dados_anteriores)

    col1, col2 = st.columns(2)
    col1.metric("Preventiva", dados_atuais['preventiva'], f"{round((dados_atuais['preventiva']*100/dados_anteriores['preventiva'])-100,2) if dados_anteriores['preventiva'] !=0 else 0}% (anterior: {dados_anteriores['preventiva']})")
    col2.metric("Corretiva", dados_atuais['corretiva'], f"{round((dados_atuais['corretiva']*100/dados_anteriores['corretiva'])-100,2) if dados_anteriores['corretiva'] !=0 else 0}% (anterior: {dados_anteriores['corretiva']})", "inverse")

    source = pd.DataFrame({
        "Categoria": dados_atuais.keys(),
        "Quantidade": dados_atuais.values()
    })

    total = dados_atuais['preventiva'] + dados_atuais['corretiva']

    base = alt.Chart(source).encode(
        theta=alt.Theta("Quantidade", stack=True)
    )

    donut = base.mark_arc(innerRadius=55, outerRadius=110).encode(
        color=alt.Color("Categoria:N", scale=alt.Scale(scheme='blues')), # Aplica as cores personalizadas
        order=alt.Order("Quantidade", sort="descending"), # Opcional: ordena as fatias
        tooltip=["Categoria", "Quantidade"] # Adiciona tooltip
    )

    text = base.mark_text(radius=130, fontSize=16, fontWeight='bold').encode(
        text=alt.Text("Quantidade"),
        order=alt.Order("Quantidade", sort="descending"),
        color=alt.value("black")
    )

    center_text_data = pd.DataFrame([{"text": f"Total: {total}"}])

    center_text = alt.Chart(center_text_data).mark_text(
        align='center',
        baseline='middle',
        fontSize=20, 
        fontWeight='bold',
        color='black' 
    ).encode(
        text=alt.Text("text")
    )

    chart = (donut + text + center_text).properties(
        title="Visitas Preventivas e Corretivas" 
    )
    col1, col2 = st.columns([3,1])
    with col1:
        st.altair_chart(chart.configure(background='#ffffff00').properties(width=650, height=330), use_container_width=False)
    with col2:
        st.info(get_text("qr_afternoon_chart_info"))

def get_qtd_treinamentos(df_rvt, mes, ano, ytd):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    if(ytd):
        df_filtrado = filtrar_por_ytd(df_rvt, 'DataInicio', mes, ano)
    else:
        df_filtrado = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano)
    
    treinamentos = 0
    tipo_treinamento = {'treinamento', 'treinamento cts','treinamento cliente', 'treinamento on-site', 'treinamento fabrica', 'treinamento outros'}
    tipo_treinamentos = defaultdict(int)
    indice = 0
    for motivo in df_filtrado['Motivo']:
        if(str(motivo).lower() == 'treinamento'):
            if(str(df_filtrado['Clientes'].iloc[indice]).lower() in divisoes['planta_ball']):
                tipo_treinamentos['treinamento fabrica'] +=1
            else:
                tipo_treinamentos['treinamento cliente'] +=1
            treinamentos +=1
        elif any(str(motivo).lower() in tipo.lower() for tipo in tipo_treinamento):
            tipo_treinamentos[motivo.lower()] += 1
            treinamentos += 1
        indice +=1
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        display_gauge(treinamentos, "TOTAL", "blue")
    with col2:
        display_gauge(tipo_treinamentos['treinamento cliente'], "Treinamento Cliente", "blue")
    with col3:
        display_gauge(tipo_treinamentos['treinamento cts'], "Treinamento CTS", "blue")
    with col4:
        display_gauge(tipo_treinamentos['treinamento fabrica'], "Treinamento Fábrica", "blue")
    with col5:
        display_gauge(tipo_treinamentos['treinamento on-site'], "Treinamento On-Site", "blue")
        # st.dataframe(tipo_treinamentos)

def get_qtd_quality(df_rvt, mes, ano, ytd):
    if(ytd):
        df_filtrado = filtrar_por_ytd(df_rvt, 'DataInicio', mes, ano)
    else:
        df_filtrado = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano)

    quality = defaultdict(int)
    cidades = {}
    indice = 0
    for motivo in df_filtrado['Motivo']:
        if str(motivo).lower() == "quality review":
            div = categorizar_divisao(df_filtrado['Clientes'].iloc[indice]) #linha desse cliente
            if div == "planta_ball":
                if(df_filtrado['UnidadesBall'].iloc[indice] not in cidades):
                    cidades[df_filtrado['UnidadesBall'].iloc[indice]] = []
                quality[div] +=1
                cidades[df_filtrado['UnidadesBall'].iloc[indice]].append(df_filtrado['DataInicio'].iloc[indice])
                #     cidades[df_filtrado['UnidadesBall'].iloc[indice]] = 0
                # quality[div] +=1
                # cidades[df_filtrado['UnidadesBall'].iloc[indice]] += 1
            
            else: quality[div] +=1
        indice +=1
    
    df_cidades_lista_datas = pd.DataFrame(list(cidades.items()), columns=['Plantas', 'Datas'])
    st.write(get_text("qr_plants_write"))
    st.dataframe(df_cidades_lista_datas, hide_index=True)
    
    source = pd.DataFrame({
        "Categoria": quality.keys(),
        "Quantidade": quality.values()
    })

    total = source["Quantidade"].sum()

    base = alt.Chart(source).encode(
        theta=alt.Theta("Quantidade", stack=True)
    )

    donut = base.mark_arc(innerRadius=55, outerRadius=110).encode(
        color=alt.Color("Categoria:N", scale=alt.Scale(scheme='set1')), # Aplica as cores personalizadas
        order=alt.Order("Quantidade", sort="descending"), # Opcional: ordena as fatias
        tooltip=["Categoria", "Quantidade"] # Adiciona tooltip
    )

    text = base.mark_text(radius=130, fontSize=16, fontWeight='bold').encode(
        text=alt.Text("Quantidade"),
        order=alt.Order("Quantidade", sort="descending"),
        color=alt.value("black")
    )

    center_text_data = pd.DataFrame([{"text": f"Total: {total}"}])

    center_text = alt.Chart(center_text_data).mark_text(
        align='center',
        baseline='middle',
        fontSize=20, 
        fontWeight='bold',
        color='black' 
    ).encode(
        text=alt.Text("text")
    )

    chart = (donut + text + center_text).properties(
        title="Quality Reviews Cliente e Planta" 
    )

    col1, col2 = st.columns([3,1])
    with col1:
        st.altair_chart(chart.configure(background='#ffffff00').properties(width=650, height=330), use_container_width=False)
    with col2:
        st.info(get_text("qr_afternoon_chart_info"))

def get_incidentes_por_divisao(df_noc, mes, ano):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    incidentes_anteriores = {}
    popnoc = {}
    allnocs = []
    for mes_anteriores in range(1, mes+1):
        df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes_anteriores, ano)
        indice = 0
        ignorar = []
        for div in divisoes.keys():
            if(div not in incidentes_anteriores):
                incidentes_anteriores[div] = {}
                popnoc[div] = []
            if(dict_meses[mes_anteriores] not in incidentes_anteriores[div]):
                incidentes_anteriores[div][dict_meses[mes_anteriores]] = 0
        for cliente in df_filtrado['Clientes']:
            
            if str(cliente).lower() in df_cop['copacker']:
                for divisao in df_cop.keys():
                    
                    for rotulo in df_cop[divisao]:
                        if rotulo.upper() in df_filtrado["Rotulo do Produto"].iloc[indice]:
                            # st.write(df_filtrado["Rotulo do Produto"].iloc[indice])
                            div = divisao
                            ignorar.append(cliente)
                            popnoc[div].append(df_filtrado["Numero NOC"].iloc[indice].astype(int))
                            allnocs.append(df_filtrado["Numero NOC"].iloc[indice].astype(int))
                            break
                
            if(cliente not in ignorar):
                div = categorizar_divisao(cliente)
            if(df_filtrado['Status'].iloc[indice] != 'CANCELADA' and (pd.isna(cliente) == 0) and div != "outros"):
                incidentes_anteriores[div][dict_meses[mes_anteriores]] += 1
            indice += 1

    # st.dataframe(incidentes_anteriores, column_order=[coluna for coluna in incidentes_anteriores.keys() if coluna not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']]) #incidentes do mes atual
    col1, col2, col3 = st.columns(3)
    colu1, colu2, colu3 = st.columns(3)
    with col1:
        ka = st.selectbox("selecione um key account", options=[coluna for coluna in incidentes_anteriores.keys() if coluna not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']])
          
    st.write(get_text("evaluate_incidents_write"))
    st.subheader("Clientes Regulares")
    for mes_anteriores in range(1, mes+1):
        df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes_anteriores, ano)
        clientes_permitidos = [str(cliente).lower() for cliente in divisoes[ka]]
    
        mascara_filtragem = df_filtrado['Clientes'].str.lower().isin(clientes_permitidos)
        
        st.write(f"Incidentes - {ka} - {mes_anteriores}/{ano}")
        df_filtrado_2 = df_filtrado[mascara_filtragem]
        df_filtrado_1 = df_filtrado_2[~df_filtrado["Numero NOC"].astype(int).isin(allnocs)]
        df_filtrado_3 = df_filtrado_1[df_filtrado_1["Status"] != "CANCELADA"]
        
        st.dataframe(df_filtrado_3, column_order=["Numero NOC", "DataRecebimentoSAC", "Clientes", "Defeito", "Planta"], hide_index=True)
    if(popnoc[ka]):
        st.subheader("Co-packers")
        
        df_cop = df_noc[df_noc["Numero NOC"].astype(int).isin(popnoc[ka])]
        st.dataframe(df_cop, column_order=["Numero NOC", "DataRecebimentoSAC", "Clientes", "Defeito", "Planta"], hide_index=True)
        tem_cop = 1
    else:
        tem_cop = 0


 
    source = incidentes_anteriores[ka]
    df_source = pd.DataFrame(list(source.items()), columns=['Mês', 'Incidentes'])

    month_order_map = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12
    }
    df_source['MonthOrder'] = df_source['Mês'].map(month_order_map)
    df_source['Incidentes'] = df_source['Incidentes'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Incidentes', title='Nº de Incidentes'),
        y=alt.Y('Mês', sort=alt.EncodingSortField(field="MonthOrder", op="min", order='ascending'), axis=alt.Axis(
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000"  
        )),
        text='Incidentes'
    ).properties(
        width=290,
        height=260
    )
    
    chart_display = base_display.mark_bar(color="#1f77b4") + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)

    base_download = alt.Chart(df_source).encode(
        x=alt.X('Incidentes'),
        y=alt.Y('Mês', sort=alt.EncodingSortField(field="MonthOrder", op="min", order='ascending'), axis=alt.Axis(
            labelFontSize=16,  
            titleFontSize=16,  
            labelColor="#ffffff",
            labelFontWeight='bold'    
        )), 
        text='Incidentes'
    ).properties(
        width=290, 
        height=260       
    )

    chart_for_download = base_download.mark_bar(color="#fefefe") + base_download.mark_text(align='left', dx=2, color='#ffffff', fontSize=16, fontWeight='bold')
    chart_for_download = chart_for_download.configure(background='#ffffff00')
    png_buffer = io.BytesIO()
    # chart_for_download.save(png_buffer, format='png', engine='vl-convert')

    import vl_convert as vlc
    png_data = vlc.vegalite_to_png(chart_for_download.to_dict())
    png_buffer.write(png_data)

    with col1:
        st.download_button(
            label="⬇️ Baixar Gráfico (PNG)",
            data=png_buffer.getvalue(),
            file_name=f"grafico_incidentes_{ka}.png",
            mime="image/png"
        )
    
    with col2:
        cl1, cl2, cl3 = st.columns([0.5,3,1])
        with cl2:
            st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=False)
    with col3:
        st.info(get_text("qr_slide_chart_info"))
        st.info(get_text("filter_info"))
    

    
    with colu1:
        display_gauge(sum(incidentes_anteriores[ka].values()), f"NOCs YTD - {ano}", "blue")
    with colu2:
        display_gauge((incidentes_anteriores[ka][dict_meses[mes]]), f"NOCs - {mes}/{ano}", "blue")
    with colu3:
        if(tem_cop):
            display_gauge(len(df_cop), "NOCs Copackers YTD", "blue")
    
    # st.subheader("Baixar relatório de NOCs")

def get_time_for_each_level(mes, ano, db, df_noc, coluna_data, tipo_retorno, tempo_resposta_niveis):
    
    df_filtrado = filtrar_por_mes(db, coluna_data, mes, ano)
    df_filtrado_can = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    indice = 0
    for data in df_filtrado[coluna_data]:
        if(df_filtrado['Status'].iloc[indice] != 'CANCELADA'):
            noc_na_data = df_filtrado['Numero NOC'].iloc[indice]
            if(noc_na_data):
                df_noc['Numero NOC'] = pd.to_numeric(df_noc['Numero NOC'], errors='coerce')
                noc_a_buscar = pd.to_numeric(noc_na_data, errors='coerce')
                df_filtro_noc = df_noc[df_noc['Numero NOC'] == noc_a_buscar]
                if not df_filtro_noc.empty:
                    data_sac = df_filtro_noc['DataRecebimentoSAC'].iloc[0]
                    data_sac = datetime.strptime(str(data_sac), '%d/%m/%Y').date()
                    formatos = ['%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', "%d/%m/%Y %H:%M:%S"]
                    for fmt in formatos:
                        try:
                            data = datetime.strptime(str(data), fmt).date()
                            break
                        except ValueError:
                            pass
                    
                    diferenca = data - data_sac
                    diferenca = diferenca.days
                    tempo_resposta_niveis[tipo_retorno]['acumulado'] += diferenca
                    tempo_resposta_niveis[tipo_retorno]['qtd'] += 1
                
                else:
                    if(str(noc_na_data) not in nocs_nao_cadastradas):
                        nocs_nao_cadastradas.append(str(noc_na_data))
                    
            indice += 1
               
def get_rvt_by_person(df_rvt, mes, ano, ytd):
    df_time = st.session_state.dados_carregados.get('df_time')
    mes_data = ["Jan", "Fev", "Mar", "Abr", "Maio", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    dados_atuais = defaultdict(int)
    if(ytd): df_filtrado_mes = filtrar_por_ytd(df_rvt, 'DataInicio', mes, ano) #por que data início e não data de criação do RVT?
    else: df_filtrado_mes = filtrar_por_mes(df_rvt, 'DataInicio', mes, ano) #por que data início e não data de criação do RVT?
    indice = 0
    for responsavel in df_filtrado_mes['ResponsavelBall']:
        if responsavel != os.getenv("nome_ignorado1") and responsavel != os.getenv("nome_ignorado2"):
            dados_atuais[responsavel] += 1
        indice +=1

    source = dados_atuais
    df_source = pd.DataFrame(list(source.items()), columns=['Nome', 'QTD RVT'])

    df_anonimo = df_source.copy()
    role_mapping = {}
    for index, linha in df_time.iterrows():
        chave = linha['NomeSalesforce']
        role_mapping[chave] = linha['Divisão']
    

    # 2. Contadores para cada tipo de cargo
    counters = {
        'Supervisor': 1,
        'Especialista': 1,
        'Key Account': 1,
        'Analista': 1
    }
    
    new_names = []

    for name in df_anonimo['Nome']:
        role_type = role_mapping.get(name)

        if role_type:
            new_name = f"{role_type} {counters[role_type]}"
            new_names.append(new_name)
            counters[role_type] += 1
        else:
            new_names.append(name)

    df_anonimo['Nome'] = new_names

    col1, col2 = st.columns(2)
    base = alt.Chart(df_anonimo).encode(
        x=alt.X('QTD RVT:Q'),
        y=alt.Y('Nome', sort='-x',
        axis=alt.Axis(
            labelFontSize=14,  
            titleFontSize=16,   
            labelLimit=500   
        )), 
        text='QTD RVT'
    ).properties(
        width=800, 
        height=900,
        title=f"RVTs por pessoa em {int(mes)}/{ano} - anônimo"
    )

    chart_anonimo = base.mark_bar(color="#26a72c") + base.mark_text(align='left', dx=2, color="#090909", fontSize=14)

    base = alt.Chart(df_source).encode(
        x=alt.X('QTD RVT:Q'),
        y=alt.Y('Nome', sort='-x',
        axis=alt.Axis(
            labelFontSize=14,  
            titleFontSize=16,   
            labelLimit=500   
        )), 
        text='QTD RVT'
    ).properties(
        width=800, 
        height=900,
        title=f"RVTs por pessoa em {int(mes)}/{ano}"
    )

    chart_source = base.mark_bar(color="#26a72c") + base.mark_text(align='left', dx=2, color="#090909", fontSize=14)

    with col1:
        st.altair_chart(chart_anonimo.configure(background="#ffffffff"))
    with col2:
        st.altair_chart(chart_source.configure(background="#ffffffff"))
   
def calcular_tempo(data_inicio, data_fim):
        """Calcula a diferença em dias. Retorna '-' se alguma data for inválida."""
        # pd.to_datetime lida com a conversão e com valores nulos (NaT)
        data_inicio = pd.to_datetime(data_inicio,format="%d/%m/%Y")
        data_fim = pd.to_datetime(data_fim, format="%d/%m/%Y" )
        # st.write(data_inicio)
        # st.write(data_fim)
        if pd.notna(data_inicio) and pd.notna(data_fim):
            return abs((data_fim - data_inicio).days)
        return "-"

def get_tempo_resposta(df_filtro):
    dfs_ressarceball = {
        "Ressarceball Argentina": st.session_state.dados_carregados.get('df_argentina'),
        "Ressarceball Paraguai": st.session_state.dados_carregados.get('df_paraguai'),
        "Ressarceball Chile": st.session_state.dados_carregados.get('df_chile'),
        "Ressarceball Ressarcimento Brasil": st.session_state.dados_carregados.get('df_r_brasil'),
        "Ressarceball Devolução Brasil": st.session_state.dados_carregados.get('df_d_brasil')
    }

    lista_tempo_resposta = []

    # .iterrows() permite acessar o índice e os dados de cada linha.
    for _, linha_sup in df_filtro.iterrows():
        noc = linha_sup['Numero NOC']
        data_recebimento = linha_sup['DataRecebimentoSAC']
        encontrado = False

        # Procura a NOC em cada um dos DataFrames de "ressarceball"
        for local, df_local in dfs_ressarceball.items():
            df_filtro_noc = df_local[df_local['Numero NOC'] == noc]

            if not df_filtro_noc.empty:
                # se houver mais de uma correspondência, pega a linha com o maior 'Id'.
                linha_maior_id = df_filtro_noc.loc[df_filtro_noc['ID'].idxmax()]

                # st.dataframe(df_filtro_noc)

                data_final = linha_maior_id['StatusFinal']
                tempo = calcular_tempo(data_recebimento, data_final)
                if(tempo != "-"):
                    lista_tempo_resposta.append({
                        "Numero NOC": noc,
                        "Local": "Concluída",
                        "Tempo de Resposta (dias)": tempo
                    })
                else:
                    lista_tempo_resposta.append({
                        "Numero NOC": noc,
                        "Local": local,
                        "Tempo de Resposta (dias)": tempo
                    })
                
                encontrado = True
                break  

        # Se, após procurar em todos os DFs, a NOC não foi encontrada
        if not encontrado:
            data_final = linha_sup['DataAprovacao']
            tempo = calcular_tempo(data_recebimento, data_final)
            if(tempo != "-"):
                lista_tempo_resposta.append({
                    "Numero NOC": noc,
                    "Local": "Concluída",
                    "Tempo de Resposta (dias)": tempo
                })
            else:
                lista_tempo_resposta.append({
                    "Numero NOC": noc,
                    "Local": "Salesforce - esperando aprovação",
                    "Tempo de Resposta (dias)": tempo
                })

    # Cria o DataFrame final a partir da lista de dicionários.
    df_nocs_tempo_resposta = pd.DataFrame(
        lista_tempo_resposta,
        columns=["Numero NOC", "Local", "Tempo de Resposta (dias)"]
    )

    # Exibe o DataFrame final e consolidado
    st.info(get_text("ressarceball_time_info"))
    st.dataframe(df_nocs_tempo_resposta, hide_index=True)

    

    tempos = pd.to_numeric(df_nocs_tempo_resposta['Tempo de Resposta (dias)'], errors='coerce')
    media_dias = round(tempos.mean(), 1)

    if(media_dias > 0): st.metric("Média de Dias", media_dias)

def calcular_fim_semana(data_inicio, data_fim):
    dias_de_fim_de_semana = 0
    data_inicio = pd.to_datetime(data_inicio, format="%d/%m/%Y" )
    data_fim = pd.to_datetime(data_fim, format="%d/%m/%Y" )
    while data_inicio <= data_fim:
        # O método weekday() retorna:
        # Segunda-feira = 0, Terça-feira = 1, ..., Sábado = 5, Domingo = 6
        if data_inicio.weekday() >= 5:  # Se for sábado (5) ou domingo (6)
            dias_de_fim_de_semana += 1
        
        # Avança para o próximo dia
        data_inicio += timedelta(days=1)
    return dias_de_fim_de_semana

def get_tempo_rvt(df_filtro):
    lista_tempo_resposta = []

    # .iterrows() permite acessar o índice e os dados de cada linha.
    for _, linha_sup in df_filtro.iterrows():
        rvt = linha_sup['Numero RVT']
        data_1Contato = linha_sup['Data1ContatoCliente']
        data_reclamacao = linha_sup['DataReclamacao']
        data_fim = linha_sup['DataFim']
        data_criacao = linha_sup['DataCriacao']

        tempo_reclamacao = calcular_tempo(data_fim, data_criacao) 
        tempo_contato = calcular_tempo(data_1Contato, data_reclamacao)
        if(tempo_reclamacao != "-"):
            tempo_reclamacao = tempo_reclamacao - calcular_fim_semana(data_fim, data_criacao)
        if(tempo_contato != "-"):
            tempo_contato = tempo_contato - calcular_fim_semana(data_1Contato, data_reclamacao)


        lista_tempo_resposta.append({
                "Numero RVT": rvt,
                "Tempo de Emissão (dias)": tempo_reclamacao,
                "Tempo de 1º Contato (dias)": tempo_contato
        })
        
    # Cria o DataFrame final a partir da lista de dicionários.
    df_rvt_tempo_resposta = pd.DataFrame(
        lista_tempo_resposta,
        columns=["Numero RVT", "Tempo de Emissão (dias)", "Tempo de 1º Contato (dias)"]
    )

    st.dataframe(df_rvt_tempo_resposta, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        tempos = pd.to_numeric(df_rvt_tempo_resposta['Tempo de Emissão (dias)'], errors='coerce')
        media_dias = round(tempos.mean(), 1)
        st.metric("Média de emissão RVT Corretivo", media_dias)
    with col2:
        tempos = pd.to_numeric(df_rvt_tempo_resposta['Tempo de 1º Contato (dias)'], errors='coerce')
        media_dias = round(tempos.mean(), 1)
        st.metric("Média de Tempo de 1º Contato RVT Corretivo", media_dias)

def get_incidentes_nps(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    incidentes_anteriores = {}
    popnoc = {}
    allnocs = []
    if ka != 'todos':
        for mes_anteriores in range(1, mes+1):
            df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes_anteriores, ano)
            indice = 0
            ignorar = []
            for div in divisoes.keys():
                if(div not in incidentes_anteriores):
                    incidentes_anteriores[div] = {}
                    popnoc[div] = []
                if(dict_meses[mes_anteriores] not in incidentes_anteriores[div]):
                    incidentes_anteriores[div][dict_meses[mes_anteriores]] = 0
            for cliente in df_filtrado['Clientes']:
                
                if str(cliente).lower() in df_cop['copacker']:
                    for divisao in df_cop.keys():
                        
                        for rotulo in df_cop[divisao]:
                            if rotulo.upper() in df_filtrado["Rotulo do Produto"].iloc[indice]:

                                div = divisao
                                ignorar.append(cliente)
                                popnoc[div].append(df_filtrado["Numero NOC"].iloc[indice].astype(int))
                                allnocs.append(df_filtrado["Numero NOC"].iloc[indice].astype(int))
                                break
                    
                if(cliente not in ignorar):
                    div = categorizar_divisao(cliente)
                if(df_filtrado['Status'].iloc[indice] != 'CANCELADA' and (pd.isna(cliente) == 0) and div != "outros"):
                    incidentes_anteriores[div][dict_meses[mes_anteriores]] += 1
                indice += 1
        source = incidentes_anteriores[ka]
        df_source = pd.DataFrame(list(source.items()), columns=['Mês', 'Incidentes'])
        display_gauge(df_source["Incidentes"].sum(), "YTD", "blue")
 
    if planta:
        df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
        df_filtro_canc = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
        df_filtrado_planta = df_filtro_canc[df_filtro_canc['Planta'].isin(planta)]
        
        df_filtro_parecer = df_filtrado_planta[df_filtrado_planta['Parecer'].isin(['PROCEDENTE', 'PROCEDENTE ALERTA'])]
        col1, col2, col3 = st.columns([1,1,0.2])
        with col1:
            display_gauge(len(df_filtrado_planta['Planta']), 'YTD', 'blue')
        with col2:
            display_gauge(len(df_filtro_parecer['Planta']), 'YTD\nProcedente', 'blue')

def get_qtd_latas_tampas(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    df_filtrado_n = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    dados_latas = {'latas':0, 'tampas':0}

    if ka != 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Clientes'].str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        for tipo in df_filtrado_cliente['Tipo do Produto']:
            if tipo == 'LATAS':
                dados_latas['latas'] += 1
            else: dados_latas['tampas'] += 1

        df_filtrado_n["Rotulo do Produto"] = df_filtrado_n["Rotulo do Produto"].fillna('-')
        for rotulo in df_cop[ka]:
            df_cop_filtro = df_filtrado_n[df_filtrado_n["Rotulo do Produto"].str.contains(rotulo.upper())]
            df_cop_filtro2 = df_cop_filtro[df_cop_filtro['Clientes'].fillna('').str.lower().isin(df_cop['copacker'])]
        
            for tipo in df_cop_filtro2['Tipo do Produto']:
                if tipo == 'LATAS':
                    dados_latas['latas'] += 1
                else: dados_latas['tampas'] += 1

    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for tipo in df_filtrado_planta['Tipo do Produto']:
            if tipo == 'LATAS':
                dados_latas['latas'] += 1
            else: dados_latas['tampas'] += 1

    source = dados_latas
    df_source = pd.DataFrame(list(source.items()), columns=['Tipo do Produto', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)

    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Tipo do Produto', axis=alt.Axis(
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000"  
        )),
        color=alt.Color('Tipo do Produto',
                  scale=alt.Scale(range=['blue','blue','blueviolet','cadetblue']), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
        text='Quantidade'
    ).properties(
        width=290,
        height=260
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)
    
def get_qtd_parecer(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    df_filtrado_n = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    dados_parecer = {"procedente":0, "procedente alerta":0, "não procedente":0, "em análise":0}
    if ka != 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Clientes'].str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        for tipo in df_filtrado_cliente['Parecer']:
            if tipo == 'PROCEDENTE':
                dados_parecer['procedente'] += 1
            elif tipo == 'NÃO PROCEDENTE':
                dados_parecer['não procedente'] += 1
            elif tipo == "PROCEDENTE ALERTA":
                dados_parecer['procedente alerta'] += 1 
            else: dados_parecer['em análise'] += 1

        df_filtrado_n["Rotulo do Produto"] = df_filtrado_n["Rotulo do Produto"].fillna('-')
        for rotulo in df_cop[ka]:
            df_cop_filtro = df_filtrado_n[df_filtrado_n["Rotulo do Produto"].str.contains(rotulo.upper())]
            df_cop_filtro2 = df_cop_filtro[df_cop_filtro['Clientes'].str.lower().isin(df_cop['copacker'])]
            
            for tipo in df_cop_filtro2['Parecer']:
                if tipo == 'PROCEDENTE':
                    dados_parecer['procedente'] += 1
                elif tipo == 'NÃO PROCEDENTE':
                    dados_parecer['não procedente'] += 1
                elif tipo == "PROCEDENTE ALERTA":
                    dados_parecer['procedente alerta'] += 1 
                else: dados_parecer['em análise'] += 1

    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for tipo in df_filtrado_planta['Parecer']:
                if tipo == 'PROCEDENTE':
                    dados_parecer['procedente'] += 1
                elif tipo == 'NÃO PROCEDENTE':
                    dados_parecer['não procedente'] += 1
                elif tipo == "PROCEDENTE ALERTA":
                    dados_parecer['procedente alerta'] += 1 
                else: dados_parecer['em análise'] += 1

    source = dados_parecer
    df_source = pd.DataFrame(list(source.items()), columns=['Parecer', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Parecer', axis=alt.Axis(
            labelLimit=200,
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000"  
        )),
        color=alt.Color('Parecer',
                  scale=alt.Scale(range=["#949494","blue","#FF0000","#E42108"]), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
                 
    text='Quantidade'
    ).properties(
        width=290,
        height=260
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)

def get_qtd_tratativa(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    df_filtrado_n = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    dados_tratativa = {"concluída":0, "em tratativa":0}
    if ka!= 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Clientes'].str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        
        for tipo in df_filtrado_cliente['Status']:
            if tipo == 'CONCLUÍDA':
                dados_tratativa['concluída'] += 1
            else: dados_tratativa['em tratativa'] += 1

        df_filtrado_n["Rotulo do Produto"] = df_filtrado_n["Rotulo do Produto"].fillna('-')
        for rotulo in df_cop[ka]:
            df_cop_filtro = df_filtrado_n[df_filtrado_n["Rotulo do Produto"].str.contains(rotulo.upper())]
            df_cop_filtro2 = df_cop_filtro[df_cop_filtro['Clientes'].str.lower().isin(df_cop['copacker'])]
            
            for tipo in df_cop_filtro2['Status']:
                if tipo == 'CONCLUÍDA':
                    dados_tratativa['concluída'] += 1
                else: dados_tratativa['em tratativa'] += 1
    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for tipo in df_filtrado_planta['Status']:
                if tipo == 'CONCLUÍDA':
                    dados_tratativa['concluída'] += 1
                else: dados_tratativa['em tratativa'] += 1

    source = dados_tratativa
    df_source = pd.DataFrame(list(source.items()), columns=['Tratativa', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Tratativa', axis=alt.Axis(
            labelLimit=200,
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000"  
        )),
        color=alt.Color('Tratativa',
                  scale=alt.Scale(range=['blue',"#8B8B8B",'blueviolet','cadetblue']), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
                 
    text='Quantidade'
    ).properties(
        width=290,
        height=260
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)

def get_qtd_defeitos(df_noc, mes, ano, ka, parecer, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    dados_defeito = {}
    if(parecer=="em análise, procedente, não procedente e procedente alerta"):
        df_filtrado_parecer = df_filtrado
    elif(parecer=="em análise"):
        df_filtrado_parecer = df_filtrado[~df_filtrado['Parecer'].isin(["NÃO PROCEDENTE", "PROCEDENTE", "PROCEDENTE ALERTA"])]
    else: df_filtrado_parecer = df_filtrado[df_filtrado['Parecer']==parecer.upper()]
    df_filtrado_n = df_filtrado_parecer[df_filtrado_parecer['Status'] != 'CANCELADA']
    if ka!= 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Clientes'].str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        
        for tipo in df_filtrado_cliente['Defeito']:
            if tipo not in dados_defeito:
                dados_defeito[tipo] = 0 
            dados_defeito[tipo] += 1

        df_filtrado_n["Rotulo do Produto"] = df_filtrado_n["Rotulo do Produto"].fillna('-')
        for rotulo in df_cop[ka]:
            df_cop_filtro = df_filtrado_n[df_filtrado_n["Rotulo do Produto"].str.contains(rotulo.upper())]
            df_cop_filtro2 = df_cop_filtro[df_cop_filtro['Clientes'].str.lower().isin(df_cop['copacker'])]
            
            for tipo in df_cop_filtro2['Defeito']:
                if tipo not in dados_defeito:
                    dados_defeito[tipo] = 0 
                dados_defeito[tipo] += 1

    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for tipo in df_filtrado_planta['Defeito']:
                if tipo not in dados_defeito:
                    dados_defeito[tipo] = 0 
                dados_defeito[tipo] += 1

    # dados_defeito[tipo] = {"procedente":0, "procedente alerta":0, "não procedente":0, "em análise":0}
                
    #             if df_filtrado_planta['Parecer'].mesmalinha in ["NÃO PROCEDENTE", "PROCEDENTE", "PROCEDENTE ALERTA"]:
    #                 dados_defeito[tipo][df_filtrado_planta['Parecer'].lower()] += 1
    #             else:
    #                 dados_defeito[tipo]["em análise"] += 1
    itens_ordenados = sorted(dados_defeito.items(), key=lambda item: item[1], reverse=True)
    top_10_itens = itens_ordenados[:5] #10
    source = dict(top_10_itens)
    df_source = pd.DataFrame(list(source.items()), columns=['Defeito', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Defeito:N', axis=alt.Axis(
            labelLimit=600,
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000",    
            titleAngle=0,       # 1. Deixa o título na horizontal
            titleAlign='left',  # 2. Alinha o texto à esquerda
            titleAnchor='start',# 3. Define o ponto de "âncora" do texto no início
            titleY=-20,         # 4. Move o título para CIMA (valores negativos)
            titleX=0            # 5. Ajusta na horizontal (0 geralmente funciona bem)
        )).sort('-x'),
        color=alt.Color('Defeito',
                  scale=alt.Scale(range=['blue']), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
                 
    text='Quantidade'
    ).properties(
        width=290,
        height=350
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)

def get_qtd_incidentes_planta(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    df_filtrado_n = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    dados_planta = {}
    if ka != 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Clientes'].str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        
        for tipo in df_filtrado_cliente['Planta']:
            if tipo not in dados_planta:
                dados_planta[tipo] = 0 
            dados_planta[tipo] += 1

        df_filtrado_n["Rotulo do Produto"] = df_filtrado_n["Rotulo do Produto"].fillna('-')
        for rotulo in df_cop[ka]:
            df_cop_filtro = df_filtrado_n[df_filtrado_n["Rotulo do Produto"].str.contains(rotulo.upper())]
            df_cop_filtro2 = df_cop_filtro[df_cop_filtro['Clientes'].str.lower().isin(df_cop['copacker'])]
            
            for tipo in df_cop_filtro2['Planta']:
                if tipo not in dados_planta:
                    dados_planta[tipo] = 0 
                dados_planta[tipo] += 1

    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for tipo in df_filtrado_planta['Planta']:
                if tipo not in dados_planta:
                    dados_planta[tipo] = 0 
                dados_planta[tipo] += 1

    itens_ordenados = sorted(dados_planta.items(), key=lambda item: item[1], reverse=True)
    top_10_itens = itens_ordenados[:10]
    source = dict(top_10_itens)
    df_source = pd.DataFrame(list(source.items()), columns=['Planta', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Planta:N', axis=alt.Axis(
            labelLimit=600,
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000",
            titleAngle=0,       # 1. Deixa o título na horizontal
            titleAlign='left',  # 2. Alinha o texto à esquerda
            titleAnchor='start',# 3. Define o ponto de "âncora" do texto no início
            titleY=-20,         # 4. Move o título para CIMA (valores negativos)
            titleX=0 
        )).sort('-x'),
        color=alt.Color('Planta',
                  scale=alt.Scale(range=['blue']), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
                 
    text='Quantidade'
    ).properties(
        width=290,
        height=350
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)

    # st.write(f"{len(df_source["Planta"])}/14")
    # display_gauge(len(df_source["Planta"]), "QTD de Plantas", "blue")

def get_qtd_clientes(df_noc, mes, ano, ka, planta):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    
    df_filtrado = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
    dados_clientes = {}
    df_filtrado_n = df_filtrado[df_filtrado['Status'] != 'CANCELADA']
    
    if planta:
        df_filtrado_planta = df_filtrado_n[df_filtrado_n['Planta'].isin(planta)]
        for cliente in df_filtrado_planta['Clientes']:
                if cliente not in dados_clientes:
                    dados_clientes[cliente] = 0 
                dados_clientes[cliente] += 1


    itens_ordenados = sorted(dados_clientes.items(), key=lambda item: item[1], reverse=True)
    top_10_itens = itens_ordenados[:5] #10
    source = dict(top_10_itens)
    df_source = pd.DataFrame(list(source.items()), columns=['Clientes', 'Quantidade'])

    df_source['Quantidade'] = df_source['Quantidade'].fillna(0)
    
    base_display = alt.Chart(df_source).encode(
        x=alt.X('Quantidade', title='Quantidade', scale=alt.Scale(nice=True)),
        y=alt.Y('Clientes:N', axis=alt.Axis(
            labelLimit=600,
            labelFontSize=14,
            titleFontSize=16,
            labelColor="#000000", 
            titleColor="#000000",    
            titleAngle=0,       # 1. Deixa o título na horizontal
            titleAlign='left',  # 2. Alinha o texto à esquerda
            titleAnchor='start',# 3. Define o ponto de "âncora" do texto no início
            titleY=-20,         # 4. Move o título para CIMA (valores negativos)
            titleX=0            # 5. Ajusta na horizontal (0 geralmente funciona bem)
        )).sort('-x'),
        color=alt.Color('Clientes',
                  scale=alt.Scale(range=['blue']), # Define sua paleta de cores aqui
                  legend=None # Opcional: remove a legenda de cores se for redundante
                 ),
                 
    text='Quantidade'
    ).properties(
        width=290,
        height=350
    )
    
    chart_display = base_display.mark_bar() + base_display.mark_text(align='left', dx=3, color='#000000', fontSize=14)
    st.altair_chart(chart_display.configure(background='#ffffff00'), use_container_width=True)

def get_qtd_ressarce(df_r_brasil, df_d_brasil, mes, ano, ka):
    divisoes = st.session_state.dados_carregados.get('divisoes')
    df_cop = st.session_state.dados_carregados.get('df_cop')
    vet_ressarce = [0,0,0,0,0,0]

    df_aux_copy = df_r_brasil.copy()
    df_aux_copy['DataCriacao'] = pd.to_datetime(df_aux_copy['DataCriacao'], format="%d/%m/%Y", dayfirst=True)

    df_filtrado_r = df_r_brasil[(df_aux_copy['DataCriacao'].dt.month <= int(mes)) & (df_aux_copy['DataCriacao'].dt.year == int(ano))]
    df_filtrado_n = df_filtrado_r[df_filtrado_r['Status'] != 'CANCELADA']
    
    if ka != 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
    
        mascara_filtragem = df_filtrado_n['Cliente'].fillna('').str.strip().str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        
        df_filtrado_lata = df_filtrado_cliente[df_filtrado_cliente['Rótulo'].str.contains("LATA|LT", case=False, na=False, regex=True)]
        vet_ressarce[1] = len(df_filtrado_lata['Cliente'])
        vet_ressarce[2] = sum(df_filtrado_lata['Dolar'].fillna(0))

        df_filtrado_tampa = df_filtrado_cliente[df_filtrado_cliente['Rótulo'].str.contains("TAMPA|TP", case=False, na=False, regex=True)]
        vet_ressarce[4] = len(df_filtrado_tampa['Cliente'])
        vet_ressarce[5] = df_filtrado_tampa['Dolar'].sum()

    df_filtrado_d = filtrar_por_ytd(df_d_brasil, 'DataCriacao', mes, ano)
    df_filtrado_n = df_filtrado_d[df_filtrado_d['Status'] != 'CANCELADA']
    
    if ka != 'todos':
        clientes_permitidos1 = [str(cliente).lower() for cliente in divisoes[ka]]
        clientes_permitidos = [str(cliente).lower() for cliente in clientes_permitidos1 if cliente not in df_cop['copacker']]
        mascara_filtragem = df_filtrado_n['Cliente'].str.strip().str.lower().isin(clientes_permitidos)
        df_filtrado_cliente = df_filtrado_n[mascara_filtragem]        
        df_filtrado_lata = df_filtrado_cliente[df_filtrado_cliente['Rótulo'].str.contains("LATA|LT", case=False, na=False, regex=True)]
        vet_ressarce[0] = len(df_filtrado_lata['Cliente'])

        df_filtrado_tampa = df_filtrado_cliente[df_filtrado_cliente['Rótulo'].str.contains("TAMPA|TP", case=False, na=False, regex=True)]
        vet_ressarce[3] = len(df_filtrado_tampa['Cliente'])
    
    return vet_ressarce

# termo pesquisa para envasador

def display_gauge(value, title, color):
    """
    Mostra um medidor (gauge) customizado do Plotly.
    """
    fig = go.Figure(go.Indicator(
        mode = "number",
        value = value,
        title = {'text': title, 'font': {'size': 19}},
        gauge = {
            'axis': {'range': [None, 80], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
        }
    ))

    fig.update_layout(
        paper_bgcolor = "rgba(0,0,0,0)", # Fundo transparente
        font = {'color': "darkblue", 'family': "Arial"},
        height=237
    )

    st.plotly_chart(fig, use_container_width=True)

def get_flow(nome_df, noc, linha_noc):
    if 'flow_state' not in st.session_state:
        st.session_state.flow_state = None
    if 'last_status' not in st.session_state:
        st.session_state.last_status = None
    if 'all_flows' not in st.session_state:
        st.session_state.all_flows = {}

    STYLE_DEFAULT = {'background': '#D3D3D3', 'border': '2px solid #808080', 'borderRadius': '5px', 'padding': '10px', 'color': '#000000'}
    STYLE_CURRENT = {'background': '#FFA500', 'border': '2px solid #A56C00', 'borderRadius': '5px', 'padding': '10px', 'color': '#FFFFFF'}
    STYLE_COMPLETED = {'background': '#2E8B57', 'border': '2px solid #1E5937', 'borderRadius': '5px', 'padding': '10px', 'color': '#FFFFFF'}
    STYLE_CANCELLED = {'background': '#DC143C', 'border': '2px solid #8B0000', 'borderRadius': '5px', 'padding': '20px', 'color': '#FFFFFF'}
    
    if(nome_df == "Ressarceball Ressarcimento Brasil"):

        INITIAL_NODES = [
            StreamlitFlowNode('SOLICITAÇÕES', (50, 250), {'content': 'SOLICITAÇÕES'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', (300, 250), {'content': 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO'}, 'default', 'right', 'left', draggable=False),
            # Ramo Superior: Carta de Crédito
            StreamlitFlowNode('CARTA DE CRÉDITO SOLICITADA', (600, 100), {'content': 'CARTA DE CRÉDITO SOLICITADA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('AGUARDANDO APROVAÇÃO GERENTE CTS', (900, 100), {'content': 'AGUARDANDO APROVAÇÃO GERENTE CTS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('AGUARDANDO EMISSÃO DA CARTA DE CRÉDITO', (1200, 100), {'content': 'AGUARDANDO EMISSÃO DA CARTA DE CRÉDITO'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('CARTA DE CRÉDITO FINALIZADA', (1500, 100), {'content': 'CARTA DE CRÉDITO FINALIZADA'}, 'output', 'right', 'left', draggable=False),
            # Ramo Inferior: Bonificação
            StreamlitFlowNode('AGUARDANDO ALOCAÇÃO BONIFICAÇÃO', (600, 400), {'content': 'AGUARDANDO ALOCAÇÃO BONIFICAÇÃO'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('BONIFICAÇÃO ALOCADA', (900, 400), {'content': 'BONIFICAÇÃO ALOCADA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('BONIFICAÇÃO FINALIZADA', (1200, 400), {'content': 'BONIFICAÇÃO FINALIZADA'}, 'output', 'right', 'left', draggable=False)
        ]

        EDGES = [
            StreamlitFlowEdge('e1', 'SOLICITAÇÕES', 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', animated=False),
            StreamlitFlowEdge('e2', 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', 'CARTA DE CRÉDITO SOLICITADA', animated=False),
            StreamlitFlowEdge('e3', 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', 'AGUARDANDO ALOCAÇÃO BONIFICAÇÃO', animated=False),
            StreamlitFlowEdge('e4', 'CARTA DE CRÉDITO SOLICITADA', 'AGUARDANDO APROVAÇÃO GERENTE CTS', animated=False),
            StreamlitFlowEdge('e5', 'AGUARDANDO APROVAÇÃO GERENTE CTS', 'AGUARDANDO EMISSÃO DA CARTA DE CRÉDITO', animated=False),
            StreamlitFlowEdge('e6', 'AGUARDANDO EMISSÃO DA CARTA DE CRÉDITO', 'CARTA DE CRÉDITO FINALIZADA', animated=False),
            StreamlitFlowEdge('e7', 'AGUARDANDO ALOCAÇÃO BONIFICAÇÃO', 'BONIFICAÇÃO ALOCADA', animated=False),
            StreamlitFlowEdge('e8', 'BONIFICAÇÃO ALOCADA', 'BONIFICAÇÃO FINALIZADA', animated=False)
        ]

        PATH_CREDIT = ['SOLICITAÇÕES', 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', 'CARTA DE CRÉDITO SOLICITADA', 'AGUARDANDO APROVAÇÃO GERENTE CTS', 'AGUARDANDO EMISSÃO DA CARTA DE CRÉDITO', 'CARTA DE CRÉDITO FINALIZADA']
        PATH_BONUS = ['SOLICITAÇÕES', 'AGUARDANDO DEFINIÇÃO DE RESSARCIMENTO', 'AGUARDANDO ALOCAÇÃO BONIFICAÇÃO', 'BONIFICAÇÃO ALOCADA', 'BONIFICAÇÃO FINALIZADA']
        PATHS = {'PATH_CREDIT': PATH_CREDIT, 'PATH_BONUS': PATH_BONUS}

    elif nome_df == "Ressarceball Devolução Brasil":
        INITIAL_NODES = [
            StreamlitFlowNode('AGUARDANDO NF DEVOLUÇÕES', (50, 250), {'content': 'AGUARDANDO NF DEVOLUÇÕES'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('AGENDAMENTO DA COLETA', (300, 250), {'content': 'AGENDAMENTO DA COLETA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('AGUARDANDO RECEBIMENTO DA CARGA', (550, 250), {'content': 'AGUARDANDO RECEBIMENTO DA CARGA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('AGUARDANDO OV E REMESSA', (800, 250), {'content': 'AGUARDANDO OV E REMESSA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('AGUARDANDO LANÇAMENTO DAS OV', (1050, 250), {'content': 'AGUARDANDO LANÇAMENTO DAS OV'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('APROVAÇÃO TAX', (1300, 250), {'content': 'APROVAÇÃO TAX'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DEVOLUÇÃO FINALIZADA', (1550, 250), {'content': 'DEVOLUÇÃO FINALIZADA'}, 'output', 'right', 'left', draggable=False)
        ]
        EDGES = [
            StreamlitFlowEdge('e1', 'AGUARDANDO NF DEVOLUÇÕES', 'AGENDAMENTO DA COLETA', animated=False),
            StreamlitFlowEdge('e2', 'AGENDAMENTO DA COLETA', 'AGUARDANDO RECEBIMENTO DA CARGA', animated=False),
            StreamlitFlowEdge('e3', 'AGUARDANDO RECEBIMENTO DA CARGA', 'AGUARDANDO OV E REMESSA', animated=False),
            StreamlitFlowEdge('e4', 'AGUARDANDO OV E REMESSA', 'AGUARDANDO LANÇAMENTO DAS OV', animated=False),
            StreamlitFlowEdge('e5', 'AGUARDANDO LANÇAMENTO DAS OV', 'APROVAÇÃO TAX', animated=False),
            StreamlitFlowEdge('e6', 'APROVAÇÃO TAX', 'DEVOLUÇÃO FINALIZADA', animated=False),
            # Loops de "Não Aprovada"
        ]
        PATH_MAIN = ['AGUARDANDO NF DEVOLUÇÕES', 'AGENDAMENTO DA COLETA', 'AGUARDANDO RECEBIMENTO DA CARGA', 'AGUARDANDO OV E REMESSA', 'AGUARDANDO LANÇAMENTO DAS OV', 'APROVAÇÃO (TIK)', 'DEVOLUÇÃO FINALIZADA']
        PATHS = {'PATH_MAIN': PATH_MAIN}

    elif nome_df == "RessarceBall Argentina":
        INITIAL_NODES = [
            # Common End
            StreamlitFlowNode('FINALIZADA', (1800, 250), {'content': 'FINALIZADA'}, 'output', 'left', draggable=False),
            # Top Branch
            StreamlitFlowNode('CON DEVOLUCION', (50, 100), {'content': 'CON DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('CREAR SOLICITACION DE DEVOLUCION', (300, 100), {'content': 'CREAR SOLICITACION DE DEVOLUCION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DEL OV - COMERCIAL', (600, 100), {'content': 'PENDIENTE DEL OV - COMERCIAL'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DEL RETIRO - LOGISTICA', (900, 100), {'content': 'DATOS DEL RETIRO - LOGISTICA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('INGRESO DE LA DEVOLUCION - EXPEDICION', (1200, 100), {'content': 'INGRESO DE LA DEVOLUCION - EXPEDICION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('EMISION DE LA FACTURA', (1500, 100), {'content': 'EMISION DE LA FACTURA'}, 'default', 'right', 'left', draggable=False),
            # Bottom Branch
            StreamlitFlowNode('SIN DEVOLUCION', (50, 400), {'content': 'SIN DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('CREAR SOLICITACION DE CARTA DE CREDITO', (300, 400), {'content': 'CREAR SOLICITACION DE CARTA DE CREDITO'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('VALIDACION DE LA CANTIDAD - CTS', (600, 400), {'content': 'VALIDACION DE LA CANTIDAD - CTS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DE LO VALOR - PRICING', (900, 400), {'content': 'DATOS DE LO VALOR - PRICING'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('EMISION NOTA DE CREDITO - C2C', (1200, 400), {'content': 'EMISION NOTA DE CREDITO - C2C'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('ENVIO AL CLIENTE - CTS', (1500, 400), {'content': 'ENVIO AL CLIENTE - CTS'}, 'default', 'right', 'left', draggable=False),
        ]
        EDGES = [
            StreamlitFlowEdge('e_top1', 'CON DEVOLUCION', 'CREAR SOLICITACION DE DEVOLUCION', animated=False),
            StreamlitFlowEdge('e_top2', 'CREAR SOLICITACION DE DEVOLUCION', 'PENDIENTE DEL OV - COMERCIAL', animated=False),
            StreamlitFlowEdge('e_top3', 'PENDIENTE DEL OV - COMERCIAL', 'DATOS DEL RETIRO - LOGISTICA', animated=False),
            StreamlitFlowEdge('e_top4', 'DATOS DEL RETIRO - LOGISTICA', 'INGRESO DE LA DEVOLUCION - EXPEDICION', animated=False),
            StreamlitFlowEdge('e_top5', 'INGRESO DE LA DEVOLUCION - EXPEDICION', 'EMISION DE LA FACTURA', animated=False),
            StreamlitFlowEdge('e_top_final', 'EMISION DE LA FACTURA', 'FINALIZADA', animated=False),
            StreamlitFlowEdge('e_bot1', 'SIN DEVOLUCION', 'CREAR SOLICITACION DE CARTA DE CREDITO', animated=False),
            StreamlitFlowEdge('e_bot2', 'CREAR SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', animated=False),
            StreamlitFlowEdge('e_bot3', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', animated=False),
            StreamlitFlowEdge('e_bot4', 'DATOS DE LO VALOR - PRICING', 'EMISION NOTA DE CREDITO - C2C', animated=False),
            StreamlitFlowEdge('e_bot5', 'EMISION NOTA DE CREDITO - C2C', 'ENVIO AL CLIENTE - CTS', animated=False),
            StreamlitFlowEdge('e_bot_final', 'ENVIO AL CLIENTE - CTS', 'FINALIZADA', animated=False),
        ]
        PATH_TOP = ['CON DEVOLUCION', 'CREAR SOLICITACION DE DEVOLUCION', 'PENDIENTE DEL OV - COMERCIAL', 'DATOS DEL RETIRO - LOGISTICA', 'INGRESO DE LA DEVOLUCION - EXPEDICION', 'EMISION DE LA FACTURA', 'FINALIZADA']
        PATH_BOTTOM = ['SIN DEVOLUCION', 'CREAR SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', 'EMISION NOTA DE CREDITO - C2C', 'ENVIO AL CLIENTE - CTS', 'FINALIZADA']
        PATHS = {'PATH_TOP': PATH_TOP, 'PATH_BOTTOM': PATH_BOTTOM}

    elif nome_df == "RessarceBall Chile":
        INITIAL_NODES = [
            StreamlitFlowNode('FINALIZADA', (2100, 250), {'content': 'FINALIZADA'}, 'output', 'left', draggable=False),
            # Top Branch
            StreamlitFlowNode('CON DEVOLUCION', (50, 100), {'content': 'CON DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('CREAR SOLICITACION CON DEVOLUCION', (300, 100), {'content': 'CREAR SOLICITACION CON DEVOLUCION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DEL RETIRO - BP', (600, 100), {'content': 'DATOS DEL RETIRO - BP'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DE VENTA - EXPEDICION', (900, 100), {'content': 'DATOS DE VENTA - EXPEDICION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DEL OV - GDS', (1200, 100), {'content': 'PENDIENTE DEL OV - GDS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('INGRESO DE LA DEVOLUCION - EXPEDICION', (1500, 100), {'content': 'INGRESO DE LA DEVOLUCION - EXPEDICION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('VALIDACION DEL REMITO DEVOLUCIONES - BP', (1800, 100), {'content': 'VALIDACION DEL REMITO DEVOLUCIONES - BP'}, 'default', 'right', 'left', draggable=False),
            # Bottom Branch
            StreamlitFlowNode('SIN DEVOLUCION', (50, 400), {'content': 'SIN DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('CREAR SOLICITACION DE CARTA DE CREDITO', (300, 400), {'content': 'CREAR SOLICITACION DE CARTA DE CREDITO'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('VALIDACION DE LA CANTIDAD - CTS', (600, 400), {'content': 'VALIDACION DE LA CANTIDAD - CTS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DE LO VALOR - PRICING', (900, 400), {'content': 'DATOS DE LO VALOR - PRICING'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DE FACTURA - COMERCIAL', (1200, 400), {'content': 'PENDIENTE DE FACTURA - COMERCIAL'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('EMISION NOTA DE CREDITO - GDS', (1500, 400), {'content': 'EMISION NOTA DE CREDITO - GDS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('ENVIO AL CLIENTE - COMERCIAL', (1800, 400), {'content': 'ENVIO AL CLIENTE - COMERCIAL'}, 'default', 'right', 'left', draggable=False),
        ]
        EDGES = [
            StreamlitFlowEdge('e_top1', 'CON DEVOLUCION', 'CREAR SOLICITACION CON DEVOLUCION', animated=False),
            StreamlitFlowEdge('e_top2', 'CREAR SOLICITACION CON DEVOLUCION', 'DATOS DEL RETIRO - BP', animated=False),
            StreamlitFlowEdge('e_top3', 'DATOS DEL RETIRO - BP', 'DATOS DE VENTA - EXPEDICION', animated=False),
            StreamlitFlowEdge('e_top4', 'DATOS DE VENTA - EXPEDICION', 'PENDIENTE DEL OV - GDS', animated=False),
            StreamlitFlowEdge('e_top5', 'PENDIENTE DEL OV - GDS', 'INGRESO DE LA DEVOLUCION - EXPEDICION', animated=False),
            StreamlitFlowEdge('e_top6', 'INGRESO DE LA DEVOLUCION - EXPEDICION', 'VALIDACION DEL REMITO DEVOLUCIONES - BP', animated=False),
            StreamlitFlowEdge('e_top_final', 'VALIDACION DEL REMITO DEVOLUCIONES - BP', 'FINALIZADA', animated=False),
            StreamlitFlowEdge('e_bot1', 'SIN DEVOLUCION', 'CREAR SOLICITACION DE CARTA DE CREDITO', animated=False),
            StreamlitFlowEdge('e_bot2', 'CREAR SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', animated=False),
            StreamlitFlowEdge('e_bot3', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', animated=False),
            StreamlitFlowEdge('e_bot4', 'DATOS DE LO VALOR - PRICING', 'PENDIENTE DE FACTURA - COMERCIAL', animated=False),
            StreamlitFlowEdge('e_bot5', 'PENDIENTE DE FACTURA - COMERCIAL', 'EMISION NOTA DE CREDITO - GDS', animated=False),
            StreamlitFlowEdge('e_bot6', 'EMISION NOTA DE CREDITO - GDS', 'ENVIO AL CLIENTE - COMERCIAL', animated=False),
            StreamlitFlowEdge('e_bot_final', 'ENVIO AL CLIENTE - COMERCIAL', 'FINALIZADA', animated=False),
        ]
        PATH_TOP = ['CON DEVOLUCION', 'CREAR SOLICITACION CON DEVOLUCION', 'DATOS DEL RETIRO - BP', 'DATOS DE VENTA - EXPEDICION', 'PENDIENTE DEL OV - GDS', 'INGRESO DE LA DEVOLUCION - EXPEDICION', 'VALIDACION DEL REMITO DEVOLUCIONES - BP', 'FINALIZADA']
        PATH_BOTTOM = ['SIN DEVOLUCION', 'CREAR SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', 'PENDIENTE DE FACTURA - COMERCIAL', 'EMISION NOTA DE CREDITO - GDS', 'ENVIO AL CLIENTE - COMERCIAL', 'FINALIZADA']
        PATHS = {'PATH_TOP': PATH_TOP, 'PATH_BOTTOM': PATH_BOTTOM}

    elif nome_df == "RessarceBall Paraguai":
        INITIAL_NODES = [
            StreamlitFlowNode('FINALIZADA', (1800, 250), {'content': 'FINALIZADA'}, 'output', 'left', draggable=False),
            # Top Branch
            StreamlitFlowNode('CON DEVOLUCION', (50, 100), {'content': 'CON DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('SOLICITAR DEVOLUCION', (300, 100), {'content': 'SOLICITAR DEVOLUCION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE C2C/GBS', (600, 100), {'content': 'PENDIENTE C2C/GBS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DE LOGISTICA', (900, 100), {'content': 'PENDIENTE DE LOGISTICA'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DE EXPEDICION', (1200, 100), {'content': 'PENDIENTE DE EXPEDICION'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('PENDIENTE DEL COMERCIAL', (1500, 100), {'content': 'PENDIENTE DEL COMERCIAL'}, 'default', 'right', 'left', draggable=False),
            # Bottom Branch
            StreamlitFlowNode('SIN DEVOLUCION', (50, 400), {'content': 'SIN DEVOLUCION'}, 'input', 'right', draggable=False),
            StreamlitFlowNode('SOLICITACION DE CARTA DE CREDITO', (300, 400), {'content': 'SOLICITACION DE CARTA DE CREDITO'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('VALIDACION DE LA CANTIDAD - CTS', (600, 400), {'content': 'VALIDACION DE LA CANTIDAD - CTS'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('DATOS DE LO VALOR - PRICING', (900, 400), {'content': 'DATOS DE LO VALOR - PRICING'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('EMISION NOTA DE CREDITO - C2C', (1200, 400), {'content': 'EMISION NOTA DE CREDITO - C2C'}, 'default', 'right', 'left', draggable=False),
            StreamlitFlowNode('ENVIO AL CLIENTE - CTS', (1500, 400), {'content': 'ENVIO AL CLIENTE - CTS'}, 'default', 'right', 'left', draggable=False),
        ]
        EDGES = [
            StreamlitFlowEdge('e_top1', 'CON DEVOLUCION', 'SOLICITAR DEVOLUCION', animated=False),
            StreamlitFlowEdge('e_top2', 'SOLICITAR DEVOLUCION', 'PENDIENTE C2C/GBS', animated=False),
            StreamlitFlowEdge('e_top3', 'PENDIENTE C2C/GBS', 'PENDIENTE DE LOGISTICA', animated=False),
            StreamlitFlowEdge('e_top4', 'PENDIENTE DE LOGISTICA', 'PENDIENTE DE EXPEDICION', animated=False),
            StreamlitFlowEdge('e_top5', 'PENDIENTE DE EXPEDICION', 'PENDIENTE DEL COMERCIAL', animated=False),
            StreamlitFlowEdge('e_top_final', 'PENDIENTE DEL COMERCIAL', 'FINALIZADA', animated=False),
            StreamlitFlowEdge('e_bot1', 'SIN DEVOLUCION', 'SOLICITACION DE CARTA DE CREDITO', animated=False),
            StreamlitFlowEdge('e_bot2', 'SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', animated=False),
            StreamlitFlowEdge('e_bot3', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', animated=False),
            StreamlitFlowEdge('e_bot4', 'DATOS DE LO VALOR - PRICING', 'EMISION NOTA DE CREDITO - C2C', animated=False),
            StreamlitFlowEdge('e_bot5', 'EMISION NOTA DE CREDITO - C2C', 'ENVIO AL CLIENTE - CTS', animated=False),
            StreamlitFlowEdge('e_bot_final', 'ENVIO AL CLIENTE - CTS', 'FINALIZADA', animated=False),
        ]
        PATH_TOP = ['CON DEVOLUCION', 'SOLICITAR DEVOLUCION', 'PENDIENTE C2C/GBS', 'PENDIENTE DE LOGISTICA', 'PENDIENTE DE EXPEDICION', 'PENDIENTE DEL COMERCIAL', 'FINALIZADA']
        PATH_BOTTOM = ['SIN DEVOLUCION', 'SOLICITACION DE CARTA DE CREDITO', 'VALIDACION DE LA CANTIDAD - CTS', 'DATOS DE LO VALOR - PRICING', 'EMISION NOTA DE CREDITO - C2C', 'ENVIO AL CLIENTE - CTS', 'FINALIZADA']
        PATHS = {'PATH_TOP': PATH_TOP, 'PATH_BOTTOM': PATH_BOTTOM}

    current_status_id = linha_noc['Status']
    flow_key = str(noc)
    last_known_status = st.session_state.all_flows.get(flow_key, {}).get('last_status')

    # Só recalcula se o status DESTE FLUXO mudou
    if last_known_status != current_status_id:
        
        nodes_to_render = []
        edges_to_render = []

        if current_status_id == 'CANCELADA':
            cancelled_node = StreamlitFlowNode('CANCELADA', (800, 250), {'content': 'CANCELADA'}, 'output', style=STYLE_CANCELLED)
            nodes_to_render = [cancelled_node]
            edges_to_render = []
        else:
            active_path = []
            for path_name, path_list in PATHS.items():
                if current_status_id in path_list:
                    active_path = path_list
                    break
            
            try:
                current_index = active_path.index(current_status_id)
            except (ValueError, IndexError):
                current_index = -1

            nodes_to_render = deepcopy(INITIAL_NODES)
            edges_to_render = EDGES

            for node in nodes_to_render:
                node.style = STYLE_DEFAULT
                if active_path and node.id in active_path:
                    node_index_in_path = active_path.index(node.id)
                    if node_index_in_path < current_index:
                        node.style = STYLE_COMPLETED
                    elif node_index_in_path == current_index:
                        node.style = STYLE_CURRENT
        
        # Cria o objeto de estado do fluxo
        new_flow_state = StreamlitFlowState(nodes=nodes_to_render, edges=edges_to_render)

        # Guarda o estado e o status na "memória" DESTE FLUXO, usando a chave única
        st.session_state.all_flows[flow_key] = {
            'state_object': new_flow_state,
            'last_status': current_status_id
        }

    # Pega o estado a ser renderizado da memória deste fluxo específico
    state_to_render = st.session_state.all_flows.get(flow_key, {}).get('state_object')

    if state_to_render:
        streamlit_flow(
            key=f'flow_renderer_{flow_key}_{nome_df}', 
            state=state_to_render,
            fit_view=True,
            show_minimap=False,
            show_controls=False
        )

def menu_mensal():
        st.write("Selecione o mês e ano desejado:")
        periodo = []
        col1, col2, col3 = st.columns(3)
        with col1:
            mes = st.number_input("Insira o mês (número)",min_value=1, max_value=12, step=1)
            periodo.append(mes)
        with col2:
            ano = st.number_input("Insira o ano",min_value=2023, step=1)
            periodo.append(ano)
        with col3:
            option_ytd = st.selectbox("Mensal ou YTD: ", ["Mensal", "YTD"])
            periodo.append(option_ytd)
        
        return periodo


