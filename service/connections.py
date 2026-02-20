import pandas as pd
import streamlit as st
import os

def limpar_df(df, colunas_remover=[], colunas_data=[]):
    st.write()
    date_columns = [col for col in df.columns if 'Data' in col]
    if colunas_data:
        date_columns.extend(colunas_data)
    df = pd.DataFrame(df)
    if(colunas_remover):
        df = df.drop(columns=colunas_remover)
    for col in date_columns:
        df[col] = pd.to_datetime(df[col], format='mixed', errors='raise')
        df[col] = df[col].dt.strftime('%d/%m/%Y')
    return df

def processar_arquivos_carregados(uploaded_files):
    """
    Recebe os arquivos carregados e retorna um dicionário de DataFrames.
    Esta função APENAS processa os dados, não mostra o widget de upload.
    """
    dados_carregados = {}
    
    # É uma boa prática verificar se a lista não está vazia
    if not uploaded_files:
        return None

    for upload_file in uploaded_files:
        print(f"Processando o arquivo: {upload_file.name}")
        
        if(upload_file.name == 'CTS.xlsx'):
            # xls = pd.ExcelFile(upload_file)
            # print(f"Available sheets: {xls.sheet_names}")
            # print(upload_file.name)
            df_time = pd.read_excel(upload_file, sheet_name="cts")
            dados_carregados["df_time"] = df_time

        elif(upload_file.name == "Clientes.xlsx"):
                df_clientes = pd.read_excel(upload_file, sheet_name="clientes")
                df_temp = df_clientes.set_index('KA')
                series_de_listas = df_temp.apply(lambda linha: linha.dropna().tolist(), axis=1)
                divisoes = series_de_listas.to_dict()
                divisoes_pesquisa = {}
                dados_carregados["divisoes"] = divisoes
                

                df_cop1 = pd.read_excel(upload_file, sheet_name="copacker")
                df_temp1 = df_cop1.set_index('divisao')
                series_de_listas1 = df_temp1.apply(lambda linha: linha.dropna().tolist(), axis=1)
                df_cop = series_de_listas1.to_dict()
                dados_carregados["df_cop"] = df_cop

                df_riscos1 = pd.read_excel(upload_file, sheet_name="Risco de Segurança")
                df_riscos = limpar_df(df_riscos1)
                dados_carregados["riscos"] = df_riscos
                
                df_melhorias1 = pd.read_excel(upload_file, sheet_name="Oportunidade de Melhoria")
                df_melhorias = limpar_df(df_melhorias1)
                dados_carregados["melhorias"] = df_melhorias
                
        elif(upload_file.name == 'Conexoes_NOC_RVT.xlsx'):
            df_noc1 = pd.read_excel(upload_file, sheet_name="NOC")
            df_noc = limpar_df(df_noc1, ['ClienteId'])
            dados_carregados["df_noc"] = df_noc
            
            df_rvt1 = pd.read_excel(upload_file, sheet_name="RVT")
            df_rvt = limpar_df(df_rvt1, colunas_remover=['Cliente__c', 'ResponsavelBall__c'])
            dados_carregados["df_rvt"] = df_rvt
            
            df_consulta1 = pd.read_excel(upload_file, sheet_name="NOC_e_RVT")
            unnamedcol = [col for col in df_consulta1 if "Unnamed" in col]
            unnamedcol.append("NOC__c")
            unnamedcol.append("RVT__c")
            df_consulta = limpar_df(df_consulta1, unnamedcol)
            dados_carregados["df_consulta"] = df_consulta
            
        elif(upload_file.name == 'Conexoes_RessarceBall.xlsx'):
            df_r_brasil_1 = pd.read_excel(upload_file, sheet_name="RES_Brasil")
            df_r_brasil = limpar_df(df_r_brasil_1, colunas_data=["Data Conclusão","Emissão Gerente CTS em", "StatusFinal"])
            dados_carregados["df_r_brasil"] = df_r_brasil
            
            df_d_brasil_1 = pd.read_excel(upload_file, sheet_name="DEV_Brasil")
            df_d_brasil = limpar_df(df_d_brasil_1, colunas_data=["StatusFinal", "DataModificacao"])
            dados_carregados["df_d_brasil"] = df_d_brasil
            
            df_argentina_1 = pd.read_excel(upload_file, sheet_name="Argentina")
            colunas_data_1 = [col for col in df_argentina_1.columns if 'Preenchido em' in col]
            colunas_data_2 = [col for col in df_argentina_1.columns if 'Preenchida em' in col]
            colunas_data_3 = [col for col in df_argentina_1.columns if 'em:' in col]
            colunas_data_4=["Fecha del Remito", "Devolução Criada em", "Fecha Retiro", "Emision Nota de Credito - Enviado em", "Enviado ao Cliente em", "StatusFinal"]
            colunas_data_4.extend(colunas_data_1)
            colunas_data_4.extend(colunas_data_2)
            colunas_data_4.extend(colunas_data_3)
            df_argentina = limpar_df(df_argentina_1, colunas_data=colunas_data_4)
            dados_carregados["df_argentina"] = df_argentina
            
            df_chile_1 = pd.read_excel(upload_file, sheet_name="Chile")
            colunas_data_1 = [col for col in df_chile_1.columns if 'Preenchido em' in col]
            colunas_data_2 = [col for col in df_chile_1.columns if 'Preenchida em' in col]
            colunas_data_3 = [col for col in df_chile_1.columns if 'em:' in col]
            colunas_data_4=["Fecha Retiro", "StatusFinal", "OV Emitida no SAP em"]
            colunas_data_4.extend(colunas_data_1)
            colunas_data_4.extend(colunas_data_2)
            colunas_data_4.extend(colunas_data_3)
            df_chile = limpar_df(df_chile_1, colunas_data=colunas_data_4) 
            dados_carregados["df_chile"] = df_chile
            
            df_paraguai_1 = pd.read_excel(upload_file, sheet_name="Paraguay")
            colunas_data_1 = [col for col in df_paraguai_1.columns if 'Preenchido em' in col]
            colunas_data_2 = [col for col in df_paraguai_1.columns if 'preenchida em' in col]
            colunas_data_3 = [col for col in df_paraguai_1.columns if 'em:' in col]
            colunas_data_4=["Solicitación criada en", "Fecha retiro", "StatusFinal", "Fecha del Remito", "Transporte solicitado en", "Recusado en", "Recibido en", "Emitida en"]
            colunas_data_4.extend(colunas_data_1)
            colunas_data_4.extend(colunas_data_2)
            colunas_data_4.extend(colunas_data_3)
            df_paraguai = limpar_df(df_paraguai_1, colunas_data=colunas_data_4) 
            dados_carregados["df_paraguai"] = df_paraguai
        
        
    return dados_carregados


