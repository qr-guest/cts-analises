import pandas as pd
import streamlit as st
import altair as alt
from streamlit_option_menu import option_menu
from dotenv import load_dotenv
import os
import json
from textwrap import wrap

load_dotenv()

from service.functions import menu_mensal, filtrar_por_mes, filtrar_por_ytd, get_incidentes_por_divisao, get_qtd_quality, get_qtd_treinamentos, get_rvt_by_person, get_tempo_resposta, get_time_for_each_level, get_tipos_visitas_rvt, get_visitas_por_divisao, nocs_nao_cadastradas, load_translation, get_text, get_flow, get_tempo_rvt, get_incidentes_nps, get_qtd_latas_tampas, get_qtd_parecer, get_qtd_tratativa, get_qtd_defeitos, get_qtd_incidentes_planta, get_qtd_clientes, get_qtd_ressarce
from service.connections import processar_arquivos_carregados


def check_password():
    with st.form("password_form"):
        password = st.text_input(get_text("password_label"), type="password")
        submitted = st.form_submit_button(get_text("enter_button"))

        if submitted and password == os.getenv("APP_PASSWORD_G"):
            st.session_state["password_correct_g"] = True
            st.rerun()
        elif submitted and password == os.getenv("APP_PASSWORD_C"):
            st.session_state["password_correct_c"] = True
            st.rerun()
        elif submitted:
            st.session_state["password_correct_g"] = False
            st.session_state["password_correct_c"] = False
            st.error(get_text("wrong_password_error"))

if st.session_state.get("password_correct_g", False):
    login_inicio_g = 1
    login_inicio_c = 0

elif st.session_state.get("password_correct_c", False):
    login_inicio_c = 1
    login_inicio_g = 0

else:
    login_inicio_g = 0
    login_inicio_c = 0
    st.set_page_config(
        page_title="CTS Review",
        page_icon="🤝", 
        layout='centered'
    )
    st.title(get_text("login_title"))
    st.warning(get_text("login_warning"))
    check_password()

if(login_inicio_c or login_inicio_g):
    st.set_page_config(
        page_title="Quality Review",
        page_icon="📚",
        layout="wide" 
    )

    if 'dados_carregados' not in st.session_state:
        st.header("1. Carregar Arquivos")
        
        uploaded_files = st.file_uploader(
            "Navegue até a pasta \\16 - SERVIÇO AO CLIENTE\\32. Conexoes, e selecione todos os arquivos",
            type=['xlsx'],
            accept_multiple_files=True
        )
        
        if uploaded_files and len(uploaded_files) == 4:
            dados = processar_arquivos_carregados(uploaded_files)
            
            if dados:
                st.session_state.dados_carregados = dados
                st.success("Arquivos carregados e processados com sucesso!")
                st.rerun() 

    if 'dados_carregados' in st.session_state:
        
        df_noc = st.session_state.dados_carregados.get('df_noc')
        df_rvt = st.session_state.dados_carregados.get('df_rvt')
        df_consulta = st.session_state.dados_carregados.get('df_consulta')
        df_d_brasil = st.session_state.dados_carregados.get('df_d_brasil')
        df_r_brasil = st.session_state.dados_carregados.get('df_r_brasil')
        df_argentina = st.session_state.dados_carregados.get('df_argentina')
        df_chile = st.session_state.dados_carregados.get('df_chile')
        df_paraguai = st.session_state.dados_carregados.get('df_paraguai')
        df_time = st.session_state.dados_carregados.get('df_time')
        divisoes = st.session_state.dados_carregados.get('divisoes')
        df_cop = st.session_state.dados_carregados.get('df_cop')
        df_riscos = st.session_state.dados_carregados.get('riscos')
        df_melhorias = st.session_state.dados_carregados.get('melhorias') 
       
        divisoes_pesquisa = {}
        
        dfs_ressarceball = {
            "Ressarceball Argentina": st.session_state.dados_carregados.get('df_argentina'),
            "Ressarceball Paraguai": st.session_state.dados_carregados.get('df_paraguai'),
            "Ressarceball Chile": st.session_state.dados_carregados.get('df_chile'),
            "Ressarceball Ressarcimento Brasil": st.session_state.dados_carregados.get('df_r_brasil'),
            "Ressarceball Devolução Brasil": st.session_state.dados_carregados.get('df_d_brasil')
        }

        dfs_salesforce = {
            "NOCs Salesforce": st.session_state.dados_carregados.get('df_noc'),
            "RVTs Salesforce": st.session_state.dados_carregados.get('df_rvt')
        }

        with st.sidebar:
            st.header("Configurações")
            
            is_spanish = st.toggle(
                "Idioma: 🇧🇷 / 🇪🇸", 
                help="Alterne para mudar o idioma. Desligado = Português, Ligado = Español"
            )
            
            if is_spanish:
                st.session_state.language = "es"
            else:
                st.session_state.language = "pt"

        st.title(get_text("main_title"))
        st.write(get_text("app_intro"))

        logo = str(os.getenv("logo"))
        ##st.logo(logo)

        if(login_inicio_g):
            with st.sidebar:
                menu_options_g = [
                    get_text("salesforce_section_title"), 
                    get_text("ressarceball_section_title"), 
                    get_text("noc_rvt_relation_section_title"), 
                    get_text("search_noc_section_title"),
                    get_text("search_rvt_section_title"), 
                    get_text("rvt_time"),
                    get_text("response_time"),
                    get_text("riscos_melhorias"),
                    get_text("NPS"),  
                    get_text("cts_managers_section_title")
                ]
                selecao_side_bar = option_menu(get_text("sidebar_menu_title"), menu_options_g, 
                    icons=['cloud', 'coin', 'search', 'search', 'search', 'clock', 'clock', 'hammer', 'person', 'person', 'eye'], menu_icon="cast", default_index=0,
                    styles={"nav-link-selected": {"background-color": "#093DC1"}})
        
        elif (login_inicio_c):
            with st.sidebar:
                menu_options_c = [
                    get_text("response_time"),
                    get_text("rvt_time"),
                ]
                selecao_side_bar = option_menu(get_text("sidebar_menu_title"), menu_options_c, 
                    icons=['cloud', 'coin', 'search', 'search', 'search', 'clock', 'clock', 'hammer', 'person', 'person'], menu_icon="cast", default_index=0,
                    styles={"nav-link-selected": {"background-color": "#093DC1"}})
                
        if selecao_side_bar == get_text("salesforce_section_title"):
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            option_ytd = periodo[2]
            if(option_ytd == "YTD"):
                ytd = 1
            else:
                ytd = 0

            with st.container(border=True):
                st.subheader(get_text("rvt_classification_subheader", mes=mes, ano=ano))
                get_visitas_por_divisao(df_rvt, mes, ano, ytd)

            with st.container(border=True):
                st.subheader(get_text("preventive_corrective_subheader", mes=mes, ano=ano))
                get_tipos_visitas_rvt(df_rvt, mes, ano, ytd)
            
            with st.container(border=True):
                st.subheader(get_text("training_subheader", mes=mes, ano=ano))
                get_qtd_treinamentos(df_rvt, mes, ano, ytd)

            with st.container(border=True):
                st.subheader(get_text("quality_reviews_subheader", mes=mes, ano=ano))
                get_qtd_quality(df_rvt, mes, ano, ytd)

            with st.container(border=True):
                st.subheader(get_text("incidents_subheader", mes=mes, ano=ano))
                get_incidentes_por_divisao(df_noc, mes, ano)

        elif selecao_side_bar == get_text("ressarceball_section_title"):
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            
            # investigação, devolução, bonificação, carta de crédito
            st.subheader(get_text("ressarceball_title"))
            if(nocs_nao_cadastradas): st.info(get_text("nocs_not_registered_info", nocs_nao_cadastradas=nocs_nao_cadastradas))
            tempo_resposta_niveis_br = {'Investigação':{'acumulado':0, 'qtd':0}, 'Devolução': {'acumulado':0, 'qtd':0}, 'Bonificação': {'acumulado':0, 'qtd':0}, 'Carta de Crédito': {'acumulado':0, 'qtd':0}}

            get_time_for_each_level(mes, ano, df_r_brasil, df_noc, 'Data da Ultima Modificação - Ressarcimento - Tipo de Ressarcimento', 'Investigação', tempo_resposta_niveis_br)
            get_time_for_each_level(mes, ano, df_r_brasil, df_noc, 'Data da Ultima Modificação - Bonificações Alocadas', 'Bonificação', tempo_resposta_niveis_br)
            get_time_for_each_level(mes, ano, df_r_brasil, df_noc, 'Emissão Gerente CTS em', 'Carta de Crédito', tempo_resposta_niveis_br)

            get_time_for_each_level(mes, ano, df_d_brasil, df_noc, 'Data de Ultima Modificação - Solicitação de Devolução', 'Investigação', tempo_resposta_niveis_br)
            get_time_for_each_level(mes, ano, df_d_brasil, df_noc, 'Data de Ultima Modificação - Aprovação dos Registros', 'Devolução', tempo_resposta_niveis_br)

            # st.write("RessarceBall Brasil")

            tempo_resposta_niveis_arg = {'Investigação':{'acumulado':0, 'qtd':0}, 'Devolução': {'acumulado':0, 'qtd':0}, 'Bonificação': {'acumulado':0, 'qtd':0}, 'Carta de Crédito': {'acumulado':0, 'qtd':0}}

            get_time_for_each_level(mes, ano, df_argentina, df_noc, 'DataCriacao', 'Investigação', tempo_resposta_niveis_arg)
            get_time_for_each_level(mes, ano, df_argentina, df_noc, 'DataFinal - Devolução', 'Devolução', tempo_resposta_niveis_arg) 
            get_time_for_each_level(mes, ano, df_argentina, df_noc, 'DataFinal - Ressarcimento', 'Carta de Crédito', tempo_resposta_niveis_arg)

            tempo_resposta_niveis_chi = {'Investigação':{'acumulado':0, 'qtd':0}, 'Devolução': {'acumulado':0, 'qtd':0}, 'Bonificação': {'acumulado':0, 'qtd':0}, 'Carta de Crédito': {'acumulado':0, 'qtd':0}}

            get_time_for_each_level(mes, ano, df_chile, df_noc, 'DataCriacao', 'Investigação', tempo_resposta_niveis_chi)
            get_time_for_each_level(mes, ano, df_chile, df_noc, 'DataFinal - Devolução', 'Devolução', tempo_resposta_niveis_chi) 
            get_time_for_each_level(mes, ano, df_chile, df_noc, 'DataFinal - Ressarcimento', 'Carta de Crédito', tempo_resposta_niveis_chi) 

            tempo_resposta_niveis_py = {'Investigação':{'acumulado':0, 'qtd':0}, 'Devolução': {'acumulado':0, 'qtd':0}, 'Bonificação': {'acumulado':0, 'qtd':0}, 'Carta de Crédito': {'acumulado':0, 'qtd':0}}

            get_time_for_each_level(mes, ano, df_paraguai, df_noc, 'Solicitación criada en', 'Investigação', tempo_resposta_niveis_py)
            get_time_for_each_level(mes, ano, df_paraguai, df_noc, 'DataFinal - Devolução', 'Devolução', tempo_resposta_niveis_py)
            get_time_for_each_level(mes, ano, df_paraguai, df_noc, 'DataFinal - Ressarcimento', 'Carta de Crédito', tempo_resposta_niveis_py)

            options = ["Brasil", "Paraguai", "Chile", "Argentina"]
            select_rb = st.segmented_control(
                "País RessarceBall", options, selection_mode="multi"
            )

            resultados = {'Investigação':{'acumulado':0, 'qtd':0}, 'Devolução': {'acumulado':0, 'qtd':0}, 'Bonificação': {'acumulado':0, 'qtd':0}, 'Carta de Crédito': {'acumulado':0, 'qtd':0}}
            retorno = ['Investigação', 'Devolução', 'Bonificação', 'Carta de Crédito']

            for pais in select_rb:
                if(pais == "Brasil"): 
                    tempo_resposta = tempo_resposta_niveis_br
                elif(pais == "Argentina"): 
                    tempo_resposta = tempo_resposta_niveis_arg
                elif(pais == "Chile"): 
                    tempo_resposta = tempo_resposta_niveis_chi
                elif(pais == "Paraguai"): 
                    tempo_resposta = tempo_resposta_niveis_py
                
                for chave, item in tempo_resposta.items():
                    resultados[chave]['acumulado'] += tempo_resposta[chave]['acumulado']
                    resultados[chave]['qtd'] += tempo_resposta[chave]['qtd']  

            valores = []
            for chave in resultados.keys():
                if(resultados[chave]['qtd'] == 0): 
                    valores.append(0)
                else:
                    valores.append(round(resultados[chave]['acumulado']/resultados[chave]['qtd']))
        
            df_dados_grafico = pd.DataFrame({
                'tipo': retorno,
                'média de dias': valores
            })

            MAX_WIDTH = 12
            SEPARATOR = '@'
            def wrap_label_for_altair(label, width=MAX_WIDTH, sep=SEPARATOR):
                """Quebra o texto e junta as linhas com o separador."""
                # O wrap quebra o texto em uma lista de strings
                wrapped_lines = wrap(label, width=width)
                # Juntamos as strings com o nosso separador
                return sep.join(wrapped_lines)

            df_dados_grafico['tipo_'] = df_dados_grafico['tipo'].apply(wrap_label_for_altair)

            tipos = alt.Chart(df_dados_grafico).encode(
                x=alt.X('tipo_', axis=alt.Axis(
                            labelFontSize=18,      
                            titleFontSize=14,  
                            labelColor="#000000" ,
                            labelExpr=f"split(datum.label, '{SEPARATOR}')"   
                        )),
                y=alt.Y('média de dias')
            )

            chart = tipos.mark_bar() + tipos.mark_text(align='center', baseline='bottom', dy=-5, color="#000000", fontSize=16, fontWeight='bold').encode(text=alt.Text('média de dias'))

            st.altair_chart(chart.properties(height=450, width=700), use_container_width=False)

            source = pd.DataFrame({
                "Categoria": retorno,
                "Quantidade": valores
            })

            total_media = sum(valores)/len(valores) if valores else 0

            base = alt.Chart(source).encode(
                theta=alt.Theta("Quantidade", stack=True)
            )

            donut = base.mark_arc(innerRadius=55, outerRadius=120).encode(
                color=alt.Color("Categoria:N", scale=alt.Scale(scheme='set1')), 
                order=alt.Order("Quantidade", sort="descending"), 
                tooltip=["Categoria", "Quantidade"] 
            )

            text = base.mark_text(radius=130, fontSize=16, fontWeight='bold').encode(
                text=alt.Text("Quantidade"),
                order=alt.Order("Quantidade", sort="descending"),
                color=alt.value("black")
            )

            center_text_data = pd.DataFrame([{"text": f"Média: {round(total_media,1)}"}])

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
                title="Média de Conclusão por Etapa em Dias" 
            )

            st.altair_chart(chart.configure(background='#ffffff00').properties(width=600, height=330), use_container_width=False)

        elif selecao_side_bar == get_text("noc_rvt_relation_section_title"):
            st.subheader(get_text("noc_rvt_relation_subheader"))
            st.write(get_text("noc_rvt_relation_write"))

            st.dataframe(df_consulta)
            
            #buscar noc ou rvt na tabela de relação
            with st.container(border=True):
                options = ["NOC", "RVT"]
                select_rn = st.segmented_control(
                    get_text("search_relation_label"), options, selection_mode="single"
                )
                if(select_rn):
                    if select_rn == "NOC": 
                        buscaNOC = st.text_input(get_text("type_noc_number_label"), placeholder=get_text("noc_placeholder"))
                        if(buscaNOC):
                            linhas_noc = df_consulta.loc[df_consulta["Numero NOC"] == int(buscaNOC)]
                            if(linhas_noc.empty):
                                st.write(get_text("noc_has_no_rvt_write"))
                                #buscar na tabela de noc
                                linhas_noc = df_noc.loc[df_noc["Numero NOC"] == int(buscaNOC)]
                                if(linhas_noc.empty):
                                    st.write(get_text("noc_not_registered_write"))
                                else:
                                    st.dataframe(linhas_noc)
                            else:
                                st.write(get_text("noc_found_write"))
                                manter_col = ["NR (Relação NOC e RVT)", "Data Criação NR", "Numero NOC", "NOC.DataRecebimentoSAC", "NOC.DataCriacao", "Numero RVT", "Data Criação RVT"]
                                st.dataframe(linhas_noc.drop(columns=[col for col in df_consulta if col not in manter_col]))

                    else: 
                        buscaRVT = st.text_input(get_text("type_rvt_number_label"), placeholder=get_text("rvt_placeholder"))
                        if(buscaRVT):
                            linhas_rvt = df_consulta.loc[df_consulta["Numero RVT"] == buscaRVT]
                            if(linhas_rvt.empty):
                                st.write(get_text("rvt_has_no_noc_write"))
                                #buscar na tabela de noc
                                linhas_rvt = df_rvt.loc[df_rvt["Numero RVT"] == buscaRVT]
                                if(linhas_rvt.empty):
                                    st.write(get_text("rvt_not_registered_write"))
                                else:
                                    st.dataframe(linhas_rvt)
                            else:
                                st.write(get_text("rvt_found_write"))
                                manter_col = ["NR (Relação NOC e RVT)", "Data Criação NR", "Numero NOC", "NOC.DataRecebimentoSAC", "NOC.DataCriacao", "Numero RVT", "Data Criação RVT"]
                                st.dataframe(linhas_rvt.drop(columns=[col for col in df_consulta if col not in manter_col]))

        elif selecao_side_bar == get_text("search_noc_section_title"):
            with st.container(border=True):
                    st.subheader(get_text("search_noc_subheader"))
                    noc_pesquisada = st.text_input(get_text("noc_search_input_label"), placeholder=get_text("noc_search_input_placeholder"))
                    if(noc_pesquisada):
                        for local, df_local in dfs_ressarceball.items():
                            df_filtro_noc = df_local[df_local['Numero NOC'].astype(int) == int(noc_pesquisada)]

                            if not df_filtro_noc.empty:
                                st.write(local)
                                df_sorted = df_filtro_noc.sort_values(by='ID', ascending=False)
                                st.dataframe(df_sorted)
                                get_flow(local, int(noc_pesquisada), df_sorted.iloc[0])

                        for local, df_local in dfs_salesforce.items():
                            if local == 'NOCs Salesforce':
                                df_filtro_noc = df_local[df_local['Numero NOC'].astype(int) == int(noc_pesquisada)]
                            
                                if not df_filtro_noc.empty:
                                    st.write(local)
                                    st.dataframe(df_filtro_noc)

        elif selecao_side_bar == get_text("search_rvt_section_title"):
            buscaRVT = st.text_input(get_text("type_rvt_number_label"), placeholder=get_text("rvt_placeholder"))
            if(buscaRVT):
                linhas_rvt = df_rvt.loc[df_rvt["Numero RVT"] == buscaRVT]
                if(linhas_rvt.empty):
                    st.write(get_text("rvt_not_registered_write"))
                else:
                    st.dataframe(linhas_rvt)

        elif selecao_side_bar == get_text("rvt_time"):
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            df_time_filtrado = df_time[df_time['Divisão'] == 'Analista']
            df_time_filtrado_2 = df_time[df_time['Divisão'] == 'Supervisor']
            df_time_filtrado_3 =  pd.concat([df_time_filtrado, df_time_filtrado_2], axis=0)   

            nomes = list(set(df_time_filtrado_3['NomeSalesforce']))
            analista = st.selectbox("Selecione o Supervisor ou Analista:", options=nomes)
            df_rvt_filtrado_mes = filtrar_por_mes(df_rvt, "DataInicio", mes, ano)
            df_rvt_filtrado_tipo = df_rvt_filtrado_mes[df_rvt_filtrado_mes["Tipo"].astype(str).str.contains("CORRETIVA")]
            df_rvt_nome_analista = df_rvt_filtrado_tipo[df_rvt_filtrado_tipo['ResponsavelBall'] == analista]
            
            st.dataframe(df_rvt_nome_analista, hide_index=True)

            get_tempo_rvt(df_rvt_nome_analista)
            
        elif selecao_side_bar == get_text("response_time"):
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            tab1, tab2, tab3 = st.tabs(["📗Supervisores", "📘 Especialistas", "📙 Key Accounts"])
            with tab1:
                df_time_filtrado = df_time[df_time['Divisão'] == 'Supervisor']
                options = list(set(df_time_filtrado['RegiãoSupervisor']))
                
                selection = st.segmented_control(
                    "Supervisores", options, selection_mode='single'
                )
            
                df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes, ano)
                df_filtrado_status = df_filtrado[df_filtrado['Status']!= 'CANCELADA']
                df_filtrado_status2 = df_filtrado_status[df_filtrado_status['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                df_filtrado_tipo = df_filtrado_status2[df_filtrado_status2['Tipo de NOC'] == 'EXTERNA']
                df_filtrado_aprovacao = df_filtrado_tipo[df_filtrado_tipo["AprovacaoInvestigacao"] == "APROVADA"]
                

                if(selection):
                    df_selecao = df_time_filtrado[df_time_filtrado['RegiãoSupervisor'] == selection]
                    filtro_sup = str(df_selecao['FiltroSalesforce'].iloc[0])
                    nome = str(df_selecao['NomeSalesforce'].iloc[0])
                    imagem1 = str(df_selecao['ImagemPessoaDB'].iloc[0])
                    imagem2 = str(df_selecao['ImagemRegiaoDB'].iloc[0])
                    

                    with st.container(border=True):
                        col1, col2 = st.columns([0.2, 0.8], vertical_alignment="center")
                        with col1:
                            
                            cl1,cl2,cl3 = st.columns([1,3,1])
                            with cl2:
                                st.image(imagem1, nome)
                            
                            st.image(imagem2)
                        df_filtro_sup = df_filtrado_aprovacao[df_filtrado_aprovacao['Supervisores'] == filtro_sup] 
                        with col2:
                            st.info(get_text("month_info_text", mes=mes, ano=ano, nome=nome, role="supervisor"))
                            st.dataframe(df_filtro_sup)

                    with st.container(border=True):
                        st.subheader(get_text("response_time_subheader", mes=mes, ano=ano))
                        get_tempo_resposta(df_filtro_sup)

                    with st.container(border=True):
                        st.subheader(get_text("ytd_response_time_subheader"))
                        df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                        df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                        df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                        df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                        df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                        df_filtro_sup_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Supervisores'] == filtro_sup]
                        st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome, role="supervisor"))
                        st.dataframe(df_filtro_sup_ytd)
                        get_tempo_resposta(df_filtro_sup_ytd)                       
            with tab2:
                df_time_filtrado = df_time[df_time['Divisão'] == 'Especialista']
                options = list(set(df_time_filtrado['RegiãoEspecialista']))
                selection = st.segmented_control(
                    "Especialistas", options, selection_mode='single'
                )
            
                df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes, ano)
                df_filtrado_status = df_filtrado[df_filtrado['Status']!= 'CANCELADA']
                df_filtrado_status2 = df_filtrado_status[df_filtrado_status['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                df_filtrado_tipo = df_filtrado_status2[df_filtrado_status2['Tipo de NOC'] == 'EXTERNA']
                df_filtrado_aprovacao = df_filtrado_tipo[df_filtrado_tipo["AprovacaoInvestigacao"] == "APROVADA"]
                
                if selection:
                    if(selection == 'ConeSul'):
                        df_selecao = df_time_filtrado[df_time_filtrado['RegiãoEspecialista'] == selection]
                        filtro_sup = str(df_selecao['FiltroSalesforce'].iloc[0])
                        nome = str(df_selecao['NomeSalesforce'].iloc[0])
                        imagem1 = str(df_selecao['ImagemPessoaDB'].iloc[0])
                        imagem2 = str(df_selecao['ImagemRegiaoDB'].iloc[0])

                        with st.container(border=True):
                            col1, col2 = st.columns([0.2, 0.8], vertical_alignment="center")
                            with col1:
                                
                                cl1,cl2,cl3 = st.columns([1,3,1])
                                with cl2:
                                    st.image(imagem1, nome)
                                
                                st.image(imagem2)
                            with col2:
                                st.info(get_text("month_info_text", mes=mes, ano=ano, nome=nome, role="especialista"))
                                df_filtro_sup = df_filtrado_aprovacao[df_filtrado_aprovacao['Supervisores'] == filtro_sup] 
                                st.dataframe(df_filtro_sup)

                        with st.container(border=True):
                            st.subheader(get_text("response_time_subheader", mes=mes, ano=ano))
                            get_tempo_resposta(df_filtro_sup)

                        with st.container(border=True):
                            st.subheader(get_text("ytd_response_time_subheader"))
                            df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                            df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                            df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                            df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                            df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                            df_filtro_sup_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Supervisores'] == filtro_sup]
                            st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome, role="especialista"))
                            st.dataframe(df_filtro_sup_ytd)
                            get_tempo_resposta(df_filtro_sup_ytd)


                    else:
                        df_selecao = df_time_filtrado[df_time_filtrado['RegiãoEspecialista'] == selection]
                        filtro_sup = str(df_selecao['FiltroSalesforce'].iloc[0])
                        nome = str(df_selecao['NomeSalesforce'].iloc[0])
                        imagem1 = str(df_selecao['ImagemPessoaDB'].iloc[0])
                        imagem2 = str(df_selecao['ImagemRegiaoDB'].iloc[0])

                        with st.container(border=True):
                            col1, col2 = st.columns([0.2, 0.8], vertical_alignment="center")
                            with col1:
                                
                                cl1,cl2,cl3 = st.columns([1,3,1])
                                with cl2:
                                    st.image(imagem1, nome)
                                
                                st.image(imagem2)
                            with col2:
                                st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome, role="especialista"))
                                                      

                        with st.container(border=True):
                            st.subheader(get_text("ytd_response_time_subheader"))
                            df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                            df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                            df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                            df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                            df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                            df_filtro_sup_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Especialistas'] == filtro_sup]
                            st.dataframe(df_filtro_sup_ytd, hide_index=True, column_order=['Numero NOC', 'DataRecebimentoSAC', 'Status', 'Parecer', 'CodigoCLiente', 'Clientes', 'Termo_pesquisa', 'Planta','AprovacaoInvestigacao', 'DataAprovacao', 'Defeito', 'Codigo do Produto', 'Rotulo do Produto', 'Lote'])
                            get_tempo_resposta(df_filtro_sup_ytd)

                        with st.container(border=True):
                            st.header("NOCS AGUARDANDO APROVAÇÃO")
                            df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                            df_filtrado_tipo_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Tipo de NOC'] == 'EXTERNA']
                            df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "NÃO INICIADA"]
                            df_filtro_sup_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Especialistas'] == filtro_sup]
                            st.dataframe(df_filtro_sup_ytd,  hide_index=True, column_order=['Numero NOC', 'DataRecebimentoSAC', 'Status', 'Parecer', 'CodigoCLiente', 'Clientes', 'Termo_pesquisa', 'Planta','AprovacaoInvestigacao', 'DataAprovacao', 'Defeito', 'Codigo do Produto', 'Rotulo do Produto', 'Lote'])
                        
                        with st.container(border=True):
                            st.header("NOCS CANCELADAS")
                            df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']== 'CANCELADA']
                            df_filtro_sup_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Especialistas'] == filtro_sup]
                            st.dataframe(df_filtro_sup_ytd,  hide_index=True, column_order=['Numero NOC', 'DataRecebimentoSAC', 'Status', 'Parecer', 'CodigoCLiente', 'Clientes', 'Termo_pesquisa', 'Planta','AprovacaoInvestigacao', 'DataAprovacao', 'Defeito', 'Codigo do Produto', 'Rotulo do Produto', 'Lote'])
                        

            with tab3:  
                options = [div for div in divisoes.keys() if div not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']]
                df_time_filtrado = df_time[df_time['Divisão'] == 'Key Account']
                selection = st.segmented_control(
                    "Key Accounts", options, selection_mode="single"
                )
                
                st.write(get_text("key_accounts_clients_write"))
                df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes, ano)
                df_filtrado_status = df_filtrado[df_filtrado['Status']!= 'CANCELADA']
                df_filtrado_status2 = df_filtrado_status[df_filtrado_status['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                df_filtrado_tipo = df_filtrado_status2[df_filtrado_status2['Tipo de NOC'] == 'EXTERNA']
                df_filtrado_aprovacao = df_filtrado_tipo[df_filtrado_tipo["AprovacaoInvestigacao"] == "APROVADA"]
                
                
                if(selection):
                    df_selecao = df_time_filtrado[df_time_filtrado['KA'] == selection]
                    # filtro_sup = str(df_selecao['FiltroSalesforce'].iloc[0])
                    nome = str(df_selecao['NomeSalesforce'].iloc[0])
                    imagem1 = str(df_selecao['ImagemPessoaDB'].iloc[0])
                    imagem2 = str(df_selecao['ImagemRegiaoDB'].iloc[0])
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([0.2, 0.8], vertical_alignment="center")

                        with col1:
                            cl1,cl2,cl3 = st.columns([1,3,1])
                            with cl2:
                                st.image(imagem1, nome)
                            
                            st.image(imagem2)
                        #por cliente
                        lista_em_maiusculo = [cliente.upper() for cliente in divisoes[selection]]
                        df_filtro_ka = df_filtrado_aprovacao[df_filtrado_aprovacao['Clientes'].isin(lista_em_maiusculo)]
                        # df_filtro_kaa = df_filtrado[df_filtrado['Clientes'].isin(lista_em_maiusculo)]
                        # st.dataframe(df_filtro_kaa)
                        st.dataframe(df_filtro_ka.drop_duplicates(subset=['CodigoCliente']), column_order=["CodigoCliente", "Clientes", "Termo_pesquisa"])
                        with col2:
                            st.info(get_text("month_info_text", mes=mes, ano=ano, nome=nome, role="ka"))
                            st.dataframe(df_filtro_ka)
                    
                    with st.container(border=True):
                        st.subheader(f"Tempo de resposta - {mes}/{ano}")
                        get_tempo_resposta(df_filtro_ka)

                    with st.container(border=True):
                        st.subheader("Tempo de resposta - YTD")
                        df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                        df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                        df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                        df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                        df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                        df_filtro_ka_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Clientes'].isin(lista_em_maiusculo)]
                        st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome, role="ka"))
                        st.dataframe(df_filtro_ka_ytd)
                        st.dataframe(df_filtro_ka_ytd.drop_duplicates(subset=['CodigoCliente']), column_order=["CodigoCliente", "Clientes", "Termo_pesquisa"])    
                        get_tempo_resposta(df_filtro_ka_ytd)

        elif selecao_side_bar == get_text("riscos_melhorias"):
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            
            option_ytd = periodo[2]  # Novo parâmetro vindo do menu

            # Define flag YTD
            ytd = 1 if option_ytd == "YTD" else 0

            tab1, tab2 = st.tabs(["⛑️Riscos de Segurança", "🔨Oportunidades de Melhoria"])
            with tab1:
                if option_ytd == "YTD":
                    df_filtrado_riscos = filtrar_por_ytd(df_riscos, "DataCriacao", mes, ano)
                else:
                    df_filtrado_riscos = filtrar_por_mes(df_riscos, "DataCriacao", mes, ano)
                st.dataframe(df_filtrado_riscos, hide_index=True)
            with tab2:
                if option_ytd == "YTD":
                    df_filtrado_melhorias = filtrar_por_ytd(df_melhorias, "DataCriacao", mes, ano)
                else:    
                    df_filtrado_melhorias = filtrar_por_mes(df_melhorias, "DataCriacao", mes, ano)
                st.dataframe(df_filtrado_melhorias, hide_index=True)

        elif selecao_side_bar == get_text("NPS"):
            
            st.info("Esta página permite avaliar o NPS, dados sobre a quantidade de reclamações de latas e tampas, parecer, tratativa e a relação entre clientes e defeitos/plantas")
            
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]

            options_ka = [coluna for coluna in divisoes.keys() if coluna not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']]
            options_ka.append("todos")
           
            plantas = set(list(df_noc['Planta'].fillna("-")))
            plantas.remove("-")
            plantas.remove('COMEX CORP EC')
            # plantas.remove('LOGÍSTICA CORP EC')
            plantas.remove('SANTA CRUZ')
            
            on = st.toggle("KA ou Planta")
            if on:
                planta = st.multiselect("selecione uma planta ou mais", options=plantas, placeholder="plantas")
                ka = "todos"
            else: 
                ka = st.selectbox("selecione um key account", options=options_ka)
                planta = ""

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                with st.container(border=True,height=340):
                    st.write("Latas x Tampas")
                    get_incidentes_nps(df_noc, mes, ano, ka, planta)
        
            with col2:
                with st.container(border=True):
                    st.write("Latas e Tampas")
                    get_qtd_latas_tampas(df_noc, mes, ano, ka, planta)
            with col3:
                with st.container(border=True):
                    st.write("Parecer")
                    get_qtd_parecer(df_noc, mes, ano, ka, planta)
            with col4:
                with st.container(border=True):
                    st.write("Tratativa Final")
                    get_qtd_tratativa(df_noc, mes, ano, ka, planta)
            
            #devolucao ressarcimento e cartas de credito para latas e tampas
            c1, c2 = st.columns(2)
            vet_ressarce = get_qtd_ressarce(df_r_brasil, df_d_brasil, mes, ano, ka)
            with c1:
                with st.container(border=True, height=270):
                    st.subheader("LATAS")
                    colu1, colu2 = st.columns([1,2])
                    with colu1:
                        st.image("data/Picture1.png",width=230)
                    with colu2:
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("<h1 style='text-align: center; color: black;'> 🚚 </h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> {vet_ressarce[0]} </h2>", unsafe_allow_html=True)
                        with col2:
                            st.markdown("<h1 style='text-align: center; color: black;'> 💵 </h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> {vet_ressarce[1]} </h2>", unsafe_allow_html=True)
                        with col3:
                            st.markdown("<h1 style='text-align: center; color: black;'>💲</h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> ${vet_ressarce[2]:,.2f} </h2>", unsafe_allow_html=True)
            with c2:
                with st.container(border=True, height=270):
                    st.subheader("TAMPAS")
                    colu1, colu2 = st.columns([1,2])
                    with colu1:
                        st.image("data/image.png",width=80)
                        st.image("data/Picture2.png",width=255)
                    with colu2:
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown("<h1 style='text-align: center; color: black;'> 🚚 </h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> {vet_ressarce[3]} </h2>", unsafe_allow_html=True)
                        with col2:
                            st.markdown("<h1 style='text-align: center; color: black;'> 💵 </h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> {vet_ressarce[4]} </h2>", unsafe_allow_html=True)
                        with col3:
                            st.markdown("<h1 style='text-align: center; color: black;'>💲</h1>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: black;'> ${vet_ressarce[5]:,.2f} </h2>", unsafe_allow_html=True)

            parecer = st.selectbox("Parecer", options=["em análise, procedente, não procedente e procedente alerta", "em análise", "procedente", "não procedente", "procedente alerta"])
            cl1, cl2, cl3 = st.columns([1,1,1])
            with cl1:
                with st.container(border=True, height=435):
                    st.write(f"TOP 5 Defeitos")
                    get_qtd_defeitos(df_noc, mes, ano, ka, parecer, planta)
            with cl2:
                with st.container(border=True, height=435):
                    st.write("Incidentes por Planta")
                    get_qtd_incidentes_planta(df_noc, mes, ano, ka, planta)
            with cl3:
                with st.container(border=True, height=435):
                        st.write("Incidentes por Cliente")
                        get_qtd_clientes(df_noc, mes, ano, ka, planta)
            

            with st.container(border=True, height=520):
                    st.write("Incidentes por Envasador")
            
            with st.container(border=True, height=520):
                    st.write("Procedentes x RVT (tudo ou corretiva?)")

        elif selecao_side_bar == get_text("cts_managers_section_title"):
            
            periodo = menu_mensal()
            mes = periodo[0]
            ano = periodo[1]
            
            with st.container(border=True):
                get_rvt_by_person(df_rvt, mes, ano, 0)
            
            with st.container(border=True):
                st.subheader("YTD")
                get_rvt_by_person(df_rvt, mes, ano, 1)


            options = [div for div in divisoes.keys() if div not in ['planta_ball','outros', 'argentina', 'chile', 'paraguai', 'bolivia', 'peru', 'copacker']]
            df_time_filtrado = df_time[df_time['Divisão'] == 'Gerente']
            options1 = df_time_filtrado["KA"].iloc[0]
            options_1s = options1.split(", ")
            options2 = df_time_filtrado["KA"].iloc[1]
            options_2s = options2.split(", ")

            df_filtrado = filtrar_por_mes(df_noc, 'DataRecebimentoSAC', mes, ano)
            df_filtrado_status = df_filtrado[df_filtrado['Status']!= 'CANCELADA']
            df_filtrado_status2 = df_filtrado_status[df_filtrado_status['Status']!='PREENCHIMENTO DE DADOS DA NOC']
            df_filtrado_tipo = df_filtrado_status2[df_filtrado_status2['Tipo de NOC'] == 'EXTERNA']
            df_filtrado_aprovacao = df_filtrado_tipo[df_filtrado_tipo["AprovacaoInvestigacao"] == "APROVADA"]
            
            nome1 = str(df_time_filtrado['NomeSalesforce'].iloc[0])
            nome2 = str(df_time_filtrado['NomeSalesforce'].iloc[1])
            
            st.subheader(nome1)
            with st.container(border=True):
                st.info(get_text("month_info_text", mes=mes, ano=ano, nome=nome1, role="gerente"))
                lista_final = []
                for opcao in options_1s:
                    lista_em_maiusculo = [cliente.upper() for cliente in divisoes[opcao]]
                    lista_final += lista_em_maiusculo
                df_filtro_ka = df_filtrado_aprovacao[df_filtrado_aprovacao['Clientes'].isin(lista_final)]
                # st.dataframe(df_filtro_ka) 

            with st.container(border=True):
                st.subheader(f"Tempo de resposta - {mes}/{ano}")
                get_tempo_resposta(df_filtro_ka)
    
            with st.container(border=True):
                st.subheader("Tempo de resposta - YTD")
                df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                
                df_filtro_ka_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Clientes'].isin(lista_final)]
                st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome1, role="ka"))
                get_tempo_resposta(df_filtro_ka_ytd)


            st.subheader(nome2)
            with st.container(border=True):
                st.info(get_text("month_info_text", mes=mes, ano=ano, nome=nome2, role="gerente"))
                lista_final = []
                for opcao in options_2s:
                    lista_em_maiusculo = [cliente.upper() for cliente in divisoes[opcao]]
                    lista_final += lista_em_maiusculo
                df_filtro_ka = df_filtrado_aprovacao[df_filtrado_aprovacao['Clientes'].isin(lista_final)]
                st.dataframe(df_filtro_ka) 
            
            with st.container(border=True):
                st.subheader(f"Tempo de resposta - {mes}/{ano}")
                get_tempo_resposta(df_filtro_ka)

            with st.container(border=True):
                st.subheader("Tempo de resposta - YTD")
                df_filtrado_ytd = filtrar_por_ytd(df_noc, 'DataRecebimentoSAC', mes, ano)
                df_filtrado_status_ytd = df_filtrado_ytd[df_filtrado_ytd['Status']!= 'CANCELADA']
                df_filtrado_status2_ytd = df_filtrado_status_ytd[df_filtrado_status_ytd['Status']!='PREENCHIMENTO DE DADOS DA NOC']
                df_filtrado_tipo_ytd = df_filtrado_status2_ytd[df_filtrado_status2_ytd['Tipo de NOC'] == 'EXTERNA']
                df_filtrado_aprovacao_ytd = df_filtrado_tipo_ytd[df_filtrado_tipo_ytd["AprovacaoInvestigacao"] == "APROVADA"]
                
                df_filtro_ka_ytd = df_filtrado_aprovacao_ytd[df_filtrado_aprovacao_ytd['Clientes'].isin(lista_final)]
                st.info(get_text("ytd_info_text", mes=mes, ano=ano, nome=nome1, role="ka"))
                get_tempo_resposta(df_filtro_ka_ytd)

    else:
        st.warning(get_text("upload_warning"))

