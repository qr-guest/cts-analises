import pandas as pd
import streamlit as st
import os

from service.metas import load_metas_workbook

def limpar_df(df, colunas_remover=[], colunas_data=[]):
    st.write()
    date_columns = [col for col in df.columns if 'Data' in col]
    if colunas_data:
        date_columns.extend(colunas_data)
    df = pd.DataFrame(df)
    if(colunas_remover):
        # Remover apenas colunas que existem
        df = df.drop(columns=[col for col in colunas_remover if col in df.columns])
    for col in date_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                df[col] = df[col].dt.strftime('%d/%m/%Y')
            except Exception as e:
                # Se houver erro na conversão, deixar a coluna como está
                pass
    return df

def carregar_rotulos_monster(upload_file):
    try:
        upload_file.seek(0)
        xls = pd.ExcelFile(upload_file)
        sheet_map = {str(sheet).strip().lower(): sheet for sheet in xls.sheet_names}
        sheet_name = sheet_map.get("rótulos monster") or sheet_map.get("rotulos monster")
        if not sheet_name:
            return []

        df_rotulos = pd.read_excel(upload_file, sheet_name=sheet_name)
        if df_rotulos.empty:
            return []

        primeira_coluna = df_rotulos.columns[0]
        rotulos = [str(rotulo).strip().upper() for rotulo in df_rotulos[primeira_coluna].dropna()]
        return [rotulo for rotulo in rotulos if rotulo]
    except Exception:
        return []
    finally:
        try:
            upload_file.seek(0)
        except Exception:
            pass

def carregar_copackers_monster(upload_file):
    try:
        upload_file.seek(0)
        xls = pd.ExcelFile(upload_file)
        sheet_map = {str(sheet).strip().lower(): sheet for sheet in xls.sheet_names}
        sheet_name = sheet_map.get("copacker")
        if not sheet_name:
            return [], []

        df_copacker = pd.read_excel(upload_file, sheet_name=sheet_name)
        if df_copacker.empty or "divisao" in [str(col).strip().lower() for col in df_copacker.columns]:
            return [], []

        nocs = []
        clientes = []
        if "Numero NOC" in df_copacker.columns:
            nocs = pd.to_numeric(df_copacker["Numero NOC"], errors="coerce").dropna().astype(int).tolist()
        if "Clientes" in df_copacker.columns:
            clientes = [str(cliente).strip().lower() for cliente in df_copacker["Clientes"].dropna()]

        return nocs, [cliente for cliente in clientes if cliente]
    except Exception:
        return [], []
    finally:
        try:
            upload_file.seek(0)
        except Exception:
            pass

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
        rotulos_monster = carregar_rotulos_monster(upload_file)
        if rotulos_monster:
            dados_carregados["monster_rotulos"] = sorted(set(dados_carregados.get("monster_rotulos", []) + rotulos_monster))
        monster_copacker_nocs, monster_copacker_clientes = carregar_copackers_monster(upload_file)
        if monster_copacker_nocs:
            dados_carregados["monster_copacker_nocs"] = sorted(set(dados_carregados.get("monster_copacker_nocs", []) + monster_copacker_nocs))
        if monster_copacker_clientes:
            dados_carregados["monster_copacker_clientes"] = sorted(set(dados_carregados.get("monster_copacker_clientes", []) + monster_copacker_clientes))
        
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
        
        
    try:
        dados_carregados.update(load_metas_workbook())
    except Exception as error:
        dados_carregados["metas_error"] = (
            f"Não foi possível carregar a planilha de metas: {error}"
        )

    return dados_carregados


