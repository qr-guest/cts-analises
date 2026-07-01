from pathlib import Path
import re

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import unidecode


ROLE_SHEETS = {
    "Analista": "Analista",
    "Supervisor": "Supervisor",
    "Especialista On Site": "Espe. On site",
    "Especialista Performance": "Espe. Performance",
    "Key Account": "Key Account",
}

STATUS_COLORS = {
    "Atingido": "#2E7D32",
    "Em atenção": "#F9A825",
    "Fora da meta": "#C62828",
    "Com atividade": "#1565C0",
    "Sem atividade": "#90A4AE",
    "Parcial": "#7E57C2",
    "Sem dados": "#D7DCE2",
}

STATUS_SCORES = {
    "Atingido": 100,
    "Em atenção": 65,
    "Fora da meta": 25,
    "Com atividade": 100,
    "Sem atividade": 20,
    "Parcial": 50,
    "Sem dados": 0,
}

MONTH_LABELS = {
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
    12: "Dez",
}


def _clean_text(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _normalized(value):
    return unidecode.unidecode(_clean_text(value)).upper()


def _safe_dataframe(value):
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _chart_description(text):
    st.caption(f"Este gráfico responde: {text}")


def _find_column(df, exact=(), contains=()):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None

    normalized_columns = {_normalized(column): column for column in df.columns}
    for candidate in exact:
        found = normalized_columns.get(_normalized(candidate))
        if found is not None:
            return found

    contains_normalized = [_normalized(candidate) for candidate in contains]
    if not contains_normalized:
        return None
    for column in df.columns:
        normalized_column = _normalized(column)
        if all(term in normalized_column for term in contains_normalized):
            return column
    return None


def _read_role_sheet(workbook_path, sheet_name, role_name):
    raw = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None)
    if raw.empty or raw.shape[1] < 5:
        return pd.DataFrame()

    raw = raw.iloc[3:, : min(raw.shape[1], 7)].copy()
    raw = raw[raw.iloc[:, :6].notna().any(axis=1)].copy()
    if raw.empty:
        return pd.DataFrame()

    while raw.shape[1] < 7:
        raw[raw.shape[1]] = pd.NA

    raw.columns = [
        "KPI",
        "Meta",
        "Descrição",
        "Métrica",
        "Modelo",
        "Exemplo",
        "Lembretes",
    ]
    raw[["KPI", "Meta", "Descrição", "Métrica"]] = raw[
        ["KPI", "Meta", "Descrição", "Métrica"]
    ].ffill()
    raw.insert(0, "Cargo Modelo", role_name)
    raw.insert(1, "Aba Origem", sheet_name)
    raw.insert(2, "Linha Origem", raw.index + 1)

    for column in ["KPI", "Meta", "Descrição", "Métrica", "Modelo", "Lembretes"]:
        raw[column] = raw[column].map(_clean_text)

    raw["Código Meta"] = (
        raw["Cargo Modelo"].map(_normalized)
        + "|"
        + raw["KPI"].map(_normalized)
        + "|"
        + raw["Meta"].map(_normalized)
        + "|"
        + raw["Descrição"].map(_normalized)
        + "|"
        + raw["Métrica"].map(_normalized)
    )
    return raw.reset_index(drop=True)


def load_metas_workbook(workbook_path=None):
    if workbook_path is None:
        workbook_path = (
            Path(__file__).resolve().parents[1]
            / "excel-metas"
            / "Todas-metas-2026.xlsx"
        )
    workbook_path = Path(workbook_path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Planilha de metas não encontrada: {workbook_path}")

    role_frames = []
    for role_name, sheet_name in ROLE_SHEETS.items():
        role_frame = _read_role_sheet(workbook_path, sheet_name, role_name)
        if not role_frame.empty:
            role_frames.append(role_frame)

    detailed = pd.read_excel(workbook_path, sheet_name="Metas 2026")
    detailed.columns = [_clean_text(column) for column in detailed.columns]

    summary_raw = pd.read_excel(
        workbook_path, sheet_name="Resumo 2026", header=None
    )
    summary = _normalize_summary(summary_raw)

    return {
        "df_metas_modelo": (
            pd.concat(role_frames, ignore_index=True)
            if role_frames
            else pd.DataFrame()
        ),
        "df_metas_detalhadas": detailed,
        "df_metas_resumo": summary,
        "metas_workbook_path": str(workbook_path),
    }


def _normalize_summary(raw):
    if not isinstance(raw, pd.DataFrame) or raw.empty or len(raw) < 3:
        return pd.DataFrame()

    header_row = raw.iloc[1]
    records = []
    for column_index, role in header_row.items():
        role = _clean_text(role)
        if not role:
            continue
        for row_index in range(2, len(raw)):
            goal = _clean_text(raw.iloc[row_index, column_index])
            if goal:
                records.append(
                    {
                        "Cargo": role,
                        "Ordem": row_index - 1,
                        "Meta Resumida": goal,
                    }
                )
    return pd.DataFrame(records)


def _filter_period(df, date_column, month, year, ytd):
    if (
        not isinstance(df, pd.DataFrame)
        or df.empty
        or not date_column
        or date_column not in df.columns
    ):
        return _safe_dataframe(df)

    converted = pd.to_datetime(df[date_column], errors="coerce", dayfirst=True)
    if ytd:
        mask = (converted.dt.year == int(year)) & (
            converted.dt.month <= int(month)
        )
    else:
        mask = (converted.dt.year == int(year)) & (
            converted.dt.month == int(month)
        )
    return df.loc[mask].copy()


def _series_normalized(series):
    return series.fillna("").map(_normalized)


def _person_row(df_time, person):
    name_column = _find_column(
        df_time, exact=("NomeSalesforce", "Nome Salesforce", "Nome")
    )
    if not name_column:
        return pd.Series(dtype=object)
    matches = df_time[_series_normalized(df_time[name_column]) == _normalized(person)]
    return matches.iloc[0] if not matches.empty else pd.Series(dtype=object)


def _row_value(row, candidates):
    if row is None or len(row) == 0:
        return ""
    normalized_index = {_normalized(column): column for column in row.index}
    for candidate in candidates:
        column = normalized_index.get(_normalized(candidate))
        if column is not None:
            return _clean_text(row.get(column))
    return ""


def _cargo_templates(cargo, person_row=None):
    normalized_role = _normalized(cargo)
    if normalized_role == "ANALISTA":
        return ["Analista"]
    if normalized_role == "SUPERVISOR":
        return ["Supervisor"]
    if normalized_role == "KEY ACCOUNT":
        return ["Key Account"]
    if "ESPECIALISTA" in normalized_role:
        row_text = _normalized(
            " ".join(str(value) for value in getattr(person_row, "values", []))
        )
        if "ON SITE" in row_text or "ONSITE" in row_text:
            return ["Especialista On Site"]
        if "PERFORMANCE" in row_text:
            return ["Especialista Performance"]
        return ["Especialista On Site", "Especialista Performance"]
    return []


def _team_names(df_time, selected_row, person, cargo):
    names = {_normalized(person)}
    if _normalized(cargo) != "SUPERVISOR":
        return names

    name_column = _find_column(
        df_time, exact=("NomeSalesforce", "Nome Salesforce", "Nome")
    )
    role_column = _find_column(df_time, exact=("Divisão", "Divisao", "Cargo"))
    region_column = _find_column(
        df_time,
        exact=("RegiãoSupervisor", "RegiaoSupervisor", "Região Supervisor"),
    )
    selected_region = (
        _clean_text(selected_row.get(region_column))
        if region_column and region_column in selected_row.index
        else ""
    )
    if not name_column or not region_column or not selected_region:
        return names

    same_region = df_time[
        _series_normalized(df_time[region_column]) == _normalized(selected_region)
    ]
    if role_column:
        allowed_roles = {"ANALISTA", "SUPERVISOR"}
        same_region = same_region[
            _series_normalized(same_region[role_column]).isin(allowed_roles)
        ]
    names.update(_series_normalized(same_region[name_column]).tolist())
    return {name for name in names if name}


def _scope_rvt(df_rvt, team_names, month, year, ytd):
    df_rvt = _safe_dataframe(df_rvt)
    responsible_column = _find_column(
        df_rvt,
        exact=(
            "ResponsavelBall",
            "Responsável Ball",
            "Responsavel",
            "Responsável",
        ),
    )
    if responsible_column and team_names:
        df_rvt = df_rvt[
            _series_normalized(df_rvt[responsible_column]).isin(team_names)
        ].copy()
    else:
        df_rvt = df_rvt.iloc[0:0].copy()

    date_column = _find_column(
        df_rvt, exact=("DataInicio", "Data Início", "DataCriacao", "Data Criação")
    )
    return _filter_period(df_rvt, date_column, month, year, ytd)


def _scope_noc(df_noc, selected_row, person, cargo, divisoes, month, year, ytd):
    df_noc = _safe_dataframe(df_noc)
    normalized_role = _normalized(cargo)

    if normalized_role == "SUPERVISOR":
        target_column = _find_column(
            df_noc, exact=("Supervisores", "Supervisor")
        )
        target = _row_value(
            selected_row,
            ("FiltroSalesforce", "Filtro Salesforce", "NomeSalesforce"),
        )
    elif "ESPECIALISTA" in normalized_role:
        target_column = _find_column(
            df_noc, exact=("Especialistas", "Especialista")
        )
        target = _row_value(
            selected_row,
            ("FiltroSalesforce", "Filtro Salesforce", "NomeSalesforce"),
        )
    elif normalized_role == "ANALISTA":
        target_column = _find_column(
            df_noc,
            exact=(
                "Analistas",
                "Analista",
                "ResponsavelBall",
                "Responsável Ball",
                "Responsavel",
            ),
        )
        target = person
        if not target_column:
            target_column = _find_column(
                df_noc, exact=("Planta", "UnidadeBall", "Unidade Ball", "Unidade")
            )
            target = _row_value(
                selected_row,
                (
                    "PlantaBase",
                    "Planta Base",
                    "Planta",
                    "UnidadeBall",
                    "Unidade Ball",
                    "Unidade",
                ),
            )
    elif normalized_role == "KEY ACCOUNT":
        target_column = None
        target = ""
        client_column = _find_column(df_noc, exact=("Clientes", "Cliente"))
        key_account = _row_value(selected_row, ("KA", "Key Account"))
        allowed_clients = []
        for key in [item.strip() for item in key_account.split(",") if item.strip()]:
            for division_key, clients in (divisoes or {}).items():
                if _normalized(division_key) == _normalized(key):
                    allowed_clients.extend(clients)
        if client_column and allowed_clients:
            normalized_clients = {_normalized(client) for client in allowed_clients}
            df_noc = df_noc[
                _series_normalized(df_noc[client_column]).isin(normalized_clients)
            ].copy()
        else:
            df_noc = df_noc.iloc[0:0].copy()
    else:
        target_column = None
        target = ""
        df_noc = df_noc.iloc[0:0].copy()

    if target_column and target:
        df_noc = df_noc[
            _series_normalized(df_noc[target_column]) == _normalized(target)
        ].copy()
    elif normalized_role != "KEY ACCOUNT":
        df_noc = df_noc.iloc[0:0].copy()

    date_column = _find_column(
        df_noc,
        exact=("DataRecebimentoSAC", "Data Recebimento SAC", "DataCriacao"),
    )
    df_noc = _filter_period(df_noc, date_column, month, year, ytd)

    status_column = _find_column(df_noc, exact=("Status",))
    if status_column:
        df_noc = df_noc[
            _series_normalized(df_noc[status_column]) != "CANCELADA"
        ].copy()
    return df_noc


def _scope_auxiliary(
    df, selected_row, person, cargo, month, year, ytd, team_names=None
):
    df = _safe_dataframe(df)
    if df.empty:
        return df

    normalized_role = _normalized(cargo)
    if normalized_role == "SUPERVISOR":
        person_column = _find_column(
            df, exact=("Supervisores", "Supervisor")
        )
        if person_column:
            target = _row_value(
                selected_row,
                ("FiltroSalesforce", "Filtro Salesforce", "NomeSalesforce"),
            )
            allowed_people = {_normalized(target)} if target else set()
        else:
            person_column = _find_column(
                df,
                exact=(
                    "NomeSalesforce",
                    "ResponsavelBall",
                    "Responsavel",
                    "Responsável",
                    "Analista",
                    "Nome",
                ),
            )
            allowed_people = set(team_names or [])
    else:
        person_column = _find_column(
            df,
            exact=(
                "NomeSalesforce",
                "ResponsavelBall",
                "Responsavel",
                "Responsável",
                "Analista",
                "Nome",
            ),
        )
        target = person
        allowed_people = {_normalized(target)} if target else set()

    if not person_column or not allowed_people:
        return df.iloc[0:0].copy()
    df = df[
        _series_normalized(df[person_column]).isin(allowed_people)
    ].copy()
    date_column = _find_column(
        df, exact=("DataCriacao", "Data Criação", "Data", "DataInicio")
    )
    return _filter_period(df, date_column, month, year, ytd)


def _distinct_ids(df, candidates):
    id_column = _find_column(df, exact=candidates)
    if not id_column or df.empty:
        return []
    values = []
    for value in df[id_column].dropna():
        cleaned = _clean_text(value)
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _contains_mask(df, columns, terms):
    if df.empty:
        return pd.Series(False, index=df.index)
    available_columns = [column for column in columns if column in df.columns]
    if not available_columns:
        return pd.Series(False, index=df.index)

    combined = pd.Series("", index=df.index, dtype="object")
    for column in available_columns:
        combined = combined + " " + _series_normalized(df[column])
    return combined.map(lambda value: any(term in value for term in terms))


def _rvt_categories(df_rvt, divisoes):
    df_rvt = _safe_dataframe(df_rvt)
    if df_rvt.empty:
        return {
            "training": df_rvt,
            "training_onsite": df_rvt,
            "training_client": df_rvt,
            "quality_review": df_rvt,
            "quality_factory": df_rvt,
            "quality_client": df_rvt,
            "smartskin": df_rvt,
            "maintenance": df_rvt,
        }

    motive_column = _find_column(
        df_rvt, exact=("Motivo", "Assunto", "Descrição", "Descricao")
    )
    type_column = _find_column(df_rvt, exact=("Tipo", "Tipo RVT"))
    client_column = _find_column(df_rvt, exact=("Clientes", "Cliente"))
    text_columns = [
        column for column in [motive_column, type_column] if column is not None
    ]

    training_mask = _contains_mask(
        df_rvt, text_columns, ("TREINAMENTO", "CAPACITACAO")
    )
    quality_mask = _contains_mask(
        df_rvt, text_columns, ("QUALITY REVIEW", "QUALITY", " QR ")
    )
    smartskin_mask = _contains_mask(df_rvt, text_columns, ("SMARTSKIN",))
    maintenance_mask = _contains_mask(
        df_rvt, text_columns, ("MANUTENCAO", "MAINTENANCE")
    )

    plant_clients = {
        _normalized(client)
        for client in (divisoes or {}).get("planta_ball", [])
        if _clean_text(client)
    }
    if client_column:
        plant_mask = _series_normalized(df_rvt[client_column]).isin(plant_clients)
    else:
        plant_mask = pd.Series(False, index=df_rvt.index)
    onsite_text_mask = _contains_mask(
        df_rvt, text_columns, ("ON SITE", "ONSITE", "FABRICA")
    )
    onsite_mask = plant_mask | onsite_text_mask

    return {
        "training": df_rvt[training_mask].copy(),
        "training_onsite": df_rvt[training_mask & onsite_mask].copy(),
        "training_client": df_rvt[training_mask & ~onsite_mask].copy(),
        "quality_review": df_rvt[quality_mask].copy(),
        "quality_factory": df_rvt[quality_mask & plant_mask].copy(),
        "quality_client": df_rvt[quality_mask & ~plant_mask].copy(),
        "smartskin": df_rvt[smartskin_mask].copy(),
        "maintenance": df_rvt[maintenance_mask].copy(),
    }


def _corrective_rvts(df_rvt):
    df_rvt = _safe_dataframe(df_rvt)
    type_column = _find_column(df_rvt, exact=("Tipo", "Tipo RVT"))
    if df_rvt.empty or not type_column:
        return df_rvt
    corrective_mask = _series_normalized(df_rvt[type_column]).str.contains(
        "CORRETIVA", regex=False
    )
    return df_rvt[corrective_mask].copy()


def _business_days_between(start, end):
    start = pd.to_datetime(start, errors="coerce", dayfirst=True)
    end = pd.to_datetime(end, errors="coerce", dayfirst=True)
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    first, last = sorted((start.normalize(), end.normalize()))
    return max(len(pd.bdate_range(first, last)) - 1, 0)


def _average_duration(df, start_candidates, end_candidates, business_days=False):
    start_column = _find_column(df, exact=start_candidates)
    end_column = _find_column(df, exact=end_candidates)
    if not start_column or not end_column or df.empty:
        return None

    values = []
    for start, end in zip(df[start_column], df[end_column]):
        if business_days:
            value = _business_days_between(start, end)
        else:
            start_date = pd.to_datetime(start, errors="coerce", dayfirst=True)
            end_date = pd.to_datetime(end, errors="coerce", dayfirst=True)
            value = (
                abs((end_date - start_date).days)
                if pd.notna(start_date) and pd.notna(end_date)
                else pd.NA
            )
        if pd.notna(value):
            values.append(float(value))
    return round(sum(values) / len(values), 1) if values else None


def _average_noc_closure(df_noc, ressarce_frames, investigation_only=False):
    if df_noc.empty:
        return None, []

    noc_column = _find_column(df_noc, exact=("Numero NOC", "Número NOC"))
    received_column = _find_column(
        df_noc, exact=("DataRecebimentoSAC", "Data Recebimento SAC")
    )
    approval_column = _find_column(
        df_noc, exact=("DataAprovacao", "Data Aprovação")
    )
    if not noc_column or not received_column:
        return None, []

    final_dates = {}
    if not investigation_only:
        for frame in ressarce_frames:
            frame = _safe_dataframe(frame)
            frame_noc_column = _find_column(
                frame, exact=("Numero NOC", "Número NOC")
            )
            final_column = _find_column(
                frame,
                exact=(
                    "StatusFinal",
                    "Data Conclusão",
                    "DataConclusao",
                    "DataModificacao",
                ),
            )
            if not frame_noc_column or not final_column:
                continue
            for _, row in frame.iterrows():
                noc_key = _normalized(row.get(frame_noc_column))
                final_date = pd.to_datetime(
                    row.get(final_column), errors="coerce", dayfirst=True
                )
                if noc_key and pd.notna(final_date):
                    current = final_dates.get(noc_key)
                    if current is None or final_date > current:
                        final_dates[noc_key] = final_date

    durations = []
    evidence = []
    for _, row in df_noc.iterrows():
        noc_value = row.get(noc_column)
        noc_key = _normalized(noc_value)
        start = pd.to_datetime(
            row.get(received_column), errors="coerce", dayfirst=True
        )
        if investigation_only:
            end = pd.to_datetime(
                row.get(approval_column), errors="coerce", dayfirst=True
            ) if approval_column else pd.NaT
        else:
            end = final_dates.get(noc_key)
            if end is None and approval_column:
                end = pd.to_datetime(
                    row.get(approval_column), errors="coerce", dayfirst=True
                )
        if pd.notna(start) and end is not None and pd.notna(end):
            durations.append(abs((end - start).days))
            evidence.append(_clean_text(noc_value))

    average = round(sum(durations) / len(durations), 1) if durations else None
    return average, evidence


def _metric_result(
    template,
    result=None,
    unit="",
    source="Manual",
    evidence=None,
    fill_type="Manual",
    note="Não há coluna-fonte suficiente nas quatro bases.",
):
    evidence = evidence or []
    return {
        "Código Meta": template.get("Código Meta"),
        "Cargo Modelo": template.get("Cargo Modelo"),
        "KPI": template.get("KPI"),
        "Meta": template.get("Meta"),
        "Indicador": template.get("Descrição"),
        "Métrica": template.get("Métrica"),
        "Resultado": result,
        "Unidade": unit,
        "Fonte": source,
        "Evidências": ", ".join(str(item) for item in evidence[:100]),
        "Preenchimento": fill_type,
        "Observação": note,
        "Regra da planilha": template.get("Modelo"),
        "Lembretes": template.get("Lembretes"),
    }


def build_metas_results(
    df_metas,
    df_time,
    df_noc,
    df_rvt,
    df_riscos,
    ressarce_frames,
    divisoes,
    person,
    cargo,
    month,
    year,
    ytd=False,
):
    df_time = _safe_dataframe(df_time)
    selected_row = _person_row(df_time, person)
    team_names = _team_names(df_time, selected_row, person, cargo)
    model_roles = _cargo_templates(cargo, selected_row)
    templates = _safe_dataframe(df_metas)
    templates = templates[templates["Cargo Modelo"].isin(model_roles)].copy()

    scoped_rvt = _scope_rvt(df_rvt, team_names, month, year, ytd)
    scoped_noc = _scope_noc(
        df_noc, selected_row, person, cargo, divisoes, month, year, ytd
    )
    scoped_risks = _scope_auxiliary(
        df_riscos,
        selected_row,
        person,
        cargo,
        month,
        year,
        ytd,
        team_names=team_names,
    )
    categories = _rvt_categories(scoped_rvt, divisoes)
    corrective_rvt = _corrective_rvts(scoped_rvt)
    rvt_ids = {
        key: _distinct_ids(value, ("Numero RVT", "Número RVT", "RVT"))
        for key, value in categories.items()
    }

    closure_average, closure_evidence = _average_noc_closure(
        scoped_noc, ressarce_frames, investigation_only=False
    )
    investigation_average, investigation_evidence = _average_noc_closure(
        scoped_noc, ressarce_frames, investigation_only=True
    )
    issue_average = _average_duration(
        corrective_rvt,
        ("DataCriacao", "Data Criação"),
        ("DataFim", "Data Fim"),
        business_days=True,
    )
    contact_average = _average_duration(
        corrective_rvt,
        ("DataReclamacao", "Data Reclamação"),
        ("Data1ContatoCliente", "Data 1 Contato Cliente"),
        business_days=True,
    )

    records = []
    for _, template in templates.iterrows():
        text = _normalized(
            " ".join(
                [
                    template.get("KPI", ""),
                    template.get("Meta", ""),
                    template.get("Descrição", ""),
                    template.get("Métrica", ""),
                ]
            )
        )
        description = _normalized(template.get("Descrição"))
        metric = _normalized(template.get("Métrica"))
        meta = _normalized(template.get("Meta"))

        if "PONTOS DE RISCO" in text:
            if "APRESENTADO" in description or metric in {"SIM", "NAO"}:
                records.append(
                    _metric_result(
                        template,
                        result=len(scoped_risks) if not scoped_risks.empty else None,
                        unit="riscos identificados" if not scoped_risks.empty else "",
                        source=(
                            "Clientes.xlsx / Risco de Segurança"
                            if not scoped_risks.empty
                            else "Manual"
                        ),
                        fill_type="Parcial" if not scoped_risks.empty else "Manual",
                        note=(
                            "Os riscos foram localizados, mas as bases não registram "
                            "se cada ponto foi apresentado no DDS."
                            if not scoped_risks.empty
                            else "Não há vínculo entre riscos e apresentações de DDS."
                        ),
                    )
                )
                continue
            if not scoped_risks.empty:
                risk_ids = _distinct_ids(
                    scoped_risks, ("Numero RVT", "Número RVT", "RVT")
                )
                records.append(
                    _metric_result(
                        template,
                        result=len(scoped_risks),
                        unit="registros",
                        source="Clientes.xlsx / Risco de Segurança",
                        evidence=risk_ids,
                        fill_type="Automático",
                        note="Quantidade de registros de risco atribuídos à pessoa no período.",
                    )
                )
            else:
                records.append(
                    _metric_result(
                        template,
                        note="A aba de riscos não possui vínculo reconhecível com esta pessoa ou não teve registros no período.",
                    )
                )
            continue

        if "ZERO ACIDENT" in text or "DDS" in text:
            records.append(
                _metric_result(
                    template,
                    note="DDS e acidentes não possuem registro individual nas bases carregadas.",
                )
            )
            continue

        if "TREINAMENTO" in text:
            if "PLANEJ" in metric or metric == "DATA":
                records.append(
                    _metric_result(
                        template,
                        note="O realizado vem da RVT, mas o planejamento/agenda precisa ser informado em uma fonte própria.",
                    )
                )
                continue
            if "%" in metric or "PARTICIPACAO" in description:
                records.append(
                    _metric_result(
                        template,
                        result=len(categories["training"]),
                        unit="treinamentos identificados",
                        source="RVT",
                        evidence=rvt_ids["training"],
                        fill_type="Parcial",
                        note="As RVTs comprovam os treinamentos, mas não informam a lista de presença necessária para calcular a participação.",
                    )
                )
                continue

            category = "training"
            if "ON SITE" in meta and "CLIENT" not in meta:
                category = "training_onsite"
            elif "CLIENT" in meta and "ON SITE" not in meta:
                category = "training_client"

            records.append(
                _metric_result(
                    template,
                    result=len(categories[category]),
                    unit="RVTs",
                    source="RVT",
                    evidence=rvt_ids[category],
                    fill_type="Automático",
                    note="Calculado por RVTs com motivo de treinamento no período.",
                )
            )
            continue

        if "QUALITY REVIEW" in text or re.search(r"\bQR\b", text):
            if "PLANEJ" in metric:
                records.append(
                    _metric_result(
                        template,
                        note="O realizado vem da RVT, mas o cronograma planejado não está nas quatro bases.",
                    )
                )
                continue
            category = "quality_review"
            if "FABRICA" in meta or " BALL" in meta:
                category = "quality_factory"
            elif "CLIENT" in meta:
                category = "quality_client"
            records.append(
                _metric_result(
                    template,
                    result=len(categories[category]),
                    unit="RVTs",
                    source="RVT",
                    evidence=rvt_ids[category],
                    fill_type="Automático",
                    note="Calculado por RVTs classificadas como Quality Review.",
                )
            )
            continue

        if "PRIMEIRO ATENDIMENTO" in text or "1 CONTATO" in text:
            records.append(
                _metric_result(
                    template,
                    result=contact_average,
                    unit="dias úteis",
                    source="RVT",
                    evidence=_distinct_ids(
                        corrective_rvt, ("Numero RVT", "Número RVT", "RVT")
                    ),
                    fill_type="Automático" if contact_average is not None else "Manual",
                    note=(
                        "Média entre DataReclamacao e Data1ContatoCliente."
                        if contact_average is not None
                        else "As RVTs do período não possuem as duas datas necessárias."
                    ),
                )
            )
            continue

        if "EMISSAO RVT" in text:
            records.append(
                _metric_result(
                    template,
                    result=issue_average,
                    unit="dias úteis",
                    source="RVT",
                    evidence=_distinct_ids(
                        corrective_rvt, ("Numero RVT", "Número RVT", "RVT")
                    ),
                    fill_type="Automático" if issue_average is not None else "Manual",
                    note=(
                        "Média entre DataCriacao e DataFim das RVTs do período."
                        if issue_average is not None
                        else "As RVTs do período não possuem as duas datas necessárias."
                    ),
                )
            )
            continue

        if "8D LEAD TIME" in text:
            records.append(
                _metric_result(
                    template,
                    result=investigation_average,
                    unit="dias corridos",
                    source="NOC",
                    evidence=investigation_evidence,
                    fill_type=(
                        "Automático"
                        if investigation_average is not None
                        else "Manual"
                    ),
                    note="Média entre DataRecebimentoSAC e DataAprovacao.",
                )
            )
            continue

        if "FECHAMENTO" in text or "PLANILHA DE GESTAO" in text:
            records.append(
                _metric_result(
                    template,
                    result=closure_average,
                    unit="dias corridos",
                    source="NOC + RessarceBall",
                    evidence=closure_evidence,
                    fill_type=(
                        "Automático" if closure_average is not None else "Manual"
                    ),
                    note="Usa StatusFinal do RessarceBall; quando não existe, usa DataAprovacao da NOC.",
                )
            )
            continue

        if "SMARTSKIN" in text:
            records.append(
                _metric_result(
                    template,
                    result=len(categories["smartskin"]),
                    unit="RVTs",
                    source="RVT",
                    evidence=rvt_ids["smartskin"],
                    fill_type="Automático",
                    note="RVTs cujo motivo ou tipo menciona Smartskin.",
                )
            )
            continue

        if "MANUTENCAO" in text:
            records.append(
                _metric_result(
                    template,
                    result=len(categories["maintenance"]),
                    unit="RVTs",
                    source="RVT",
                    evidence=rvt_ids["maintenance"],
                    fill_type="Automático",
                    note="RVTs cujo motivo ou tipo menciona manutenção.",
                )
            )
            continue

        records.append(_metric_result(template))

    results = pd.DataFrame(records)
    if not results.empty:
        results.insert(0, "Pessoa", person)
        results.insert(1, "Cargo CTS", cargo)
        results.insert(2, "Período", f"YTD até {month}/{year}" if ytd else f"{month}/{year}")

    context = {
        "rvt": scoped_rvt,
        "noc": scoped_noc,
        "riscos": scoped_risks,
        "team_names": sorted(team_names),
        "model_roles": model_roles,
    }
    return results, context


def _goal_threshold(row):
    text = _normalized(
        " ".join(
            [
                row.get("KPI", ""),
                row.get("Meta", ""),
                row.get("Indicador", ""),
                row.get("Métrica", ""),
            ]
        )
    )
    if "PRIMEIRO ATENDIMENTO" in text or "1 CONTATO" in text:
        return 1.0, "max", "≤ 1 dia útil"
    if "EMISSAO RVT" in text:
        return 4.0, "max", "≤ 4 dias úteis"
    if "8D LEAD TIME" in text:
        return 20.0, "max", "≤ 20 dias"
    if "FECHAMENTO" in text or "PLANILHA DE GESTAO" in text:
        return 45.0, "max", "≤ 45 dias"
    return None, None, ""


def enrich_metas_status(results):
    enriched = _safe_dataframe(results)
    if enriched.empty:
        return enriched

    status_values = []
    target_values = []
    target_labels = []
    evaluation_types = []
    progress_values = []
    score_values = []

    for _, row in enriched.iterrows():
        result = pd.to_numeric(
            pd.Series([row.get("Resultado")]), errors="coerce"
        ).iloc[0]
        fill_type = _normalized(row.get("Preenchimento"))
        target, direction, target_label = _goal_threshold(row)

        if fill_type == "MANUAL" or pd.isna(result):
            status = "Sem dados"
            evaluation_type = "Sem regra automática"
            progress = 0.0
        elif target is not None:
            evaluation_type = "Meta objetiva"
            if direction == "max":
                attention_limit = (
                    target + 1 if target <= 4 else target * 1.2
                )
                if result <= target:
                    status = "Atingido"
                elif result <= attention_limit:
                    status = "Em atenção"
                else:
                    status = "Fora da meta"
                progress = (
                    100.0
                    if result <= target
                    else max(0.0, min(100.0, target / result * 100))
                )
            else:
                status = "Atingido"
                progress = 100.0
        elif fill_type == "PARCIAL":
            status = "Parcial"
            evaluation_type = "Atividade parcial"
            progress = 50.0 if result > 0 else 25.0
        else:
            status = "Com atividade" if result > 0 else "Sem atividade"
            evaluation_type = "Atividade monitorada"
            progress = 100.0 if result > 0 else 0.0

        status_values.append(status)
        target_values.append(target)
        target_labels.append(target_label)
        evaluation_types.append(evaluation_type)
        progress_values.append(round(progress, 1))
        score_values.append(STATUS_SCORES[status])

    enriched["Status da meta"] = status_values
    enriched["Meta numérica"] = target_values
    enriched["Referência"] = target_labels
    enriched["Tipo de avaliação"] = evaluation_types
    enriched["Progresso (%)"] = progress_values
    enriched["Índice"] = score_values
    enriched["Indicador visual"] = (
        enriched["KPI"].map(_clean_text)
        + " · "
        + enriched["Meta"].map(_clean_text)
        + " · "
        + enriched["Indicador"].map(_clean_text)
    )
    return enriched


def _status_summary(group):
    group = _safe_dataframe(group)
    if group.empty:
        return "Sem dados"

    objective = group[group["Tipo de avaliação"] == "Meta objetiva"]
    if not objective.empty:
        for status in ["Fora da meta", "Em atenção", "Atingido"]:
            if status in objective["Status da meta"].values:
                return status

    measurable = group[group["Status da meta"] != "Sem dados"]
    if measurable.empty:
        return "Sem dados"
    if "Fora da meta" in measurable["Status da meta"].values:
        return "Fora da meta"
    if "Em atenção" in measurable["Status da meta"].values:
        return "Em atenção"
    if "Com atividade" in measurable["Status da meta"].values:
        return "Com atividade"
    if "Atingido" in measurable["Status da meta"].values:
        return "Atingido"
    if "Parcial" in measurable["Status da meta"].values:
        return "Parcial"
    if "Sem atividade" in measurable["Status da meta"].values:
        return "Sem atividade"
    return "Sem dados"


def _build_history(
    dados_carregados,
    df_metas,
    df_time,
    person,
    cargo,
    final_month,
    year,
):
    ressarce_frames = [
        dados_carregados.get("df_argentina"),
        dados_carregados.get("df_paraguai"),
        dados_carregados.get("df_chile"),
        dados_carregados.get("df_r_brasil"),
        dados_carregados.get("df_d_brasil"),
    ]
    frames = []
    for history_month in range(1, int(final_month) + 1):
        month_results, _ = build_metas_results(
            df_metas=df_metas,
            df_time=df_time,
            df_noc=dados_carregados.get("df_noc"),
            df_rvt=dados_carregados.get("df_rvt"),
            df_riscos=dados_carregados.get("riscos"),
            ressarce_frames=ressarce_frames,
            divisoes=dados_carregados.get("divisoes") or {},
            person=person,
            cargo=cargo,
            month=history_month,
            year=int(year),
            ytd=False,
        )
        month_results = enrich_metas_status(month_results)
        if month_results.empty:
            continue
        month_results["Mês número"] = history_month
        month_results["Mês"] = MONTH_LABELS[history_month]
        frames.append(month_results)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _build_team_status(
    dados_carregados,
    df_metas,
    df_time,
    people,
    cargo,
    month,
    year,
    ytd,
):
    ressarce_frames = [
        dados_carregados.get("df_argentina"),
        dados_carregados.get("df_paraguai"),
        dados_carregados.get("df_chile"),
        dados_carregados.get("df_r_brasil"),
        dados_carregados.get("df_d_brasil"),
    ]
    records = []
    for team_person in people:
        person_results, _ = build_metas_results(
            df_metas=df_metas,
            df_time=df_time,
            df_noc=dados_carregados.get("df_noc"),
            df_rvt=dados_carregados.get("df_rvt"),
            df_riscos=dados_carregados.get("riscos"),
            ressarce_frames=ressarce_frames,
            divisoes=dados_carregados.get("divisoes") or {},
            person=team_person,
            cargo=cargo,
            month=int(month),
            year=int(year),
            ytd=ytd,
        )
        person_results = enrich_metas_status(person_results)
        if person_results.empty:
            continue
        for kpi, group in person_results.groupby("KPI", dropna=False):
            status = _status_summary(group)
            records.append(
                {
                    "Pessoa": team_person,
                    "KPI": _clean_text(kpi),
                    "Status": status,
                    "Índice": STATUS_SCORES[status],
                }
            )
    return pd.DataFrame(records)


def _render_status_cards(results, evidence_count):
    objective = results[results["Tipo de avaliação"] == "Meta objetiva"]
    achieved = int((objective["Status da meta"] == "Atingido").sum())
    attention = int((objective["Status da meta"] == "Em atenção").sum())
    outside = int((objective["Status da meta"] == "Fora da meta").sum())
    no_data = int((results["Status da meta"] == "Sem dados").sum())
    measurable = int((results["Status da meta"] != "Sem dados").sum())
    coverage = round(measurable / len(results) * 100, 1) if len(results) else 0

    columns = st.columns(6)
    columns[0].metric("Atingidas", achieved)
    columns[1].metric("Em atenção", attention)
    columns[2].metric("Fora da meta", outside)
    columns[3].metric("Sem dados", no_data)
    columns[4].metric("Cobertura", f"{coverage}%")
    columns[5].metric("Evidências", evidence_count)


def _render_dashboard_charts(results):
    status_counts = (
        results["Status da meta"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Quantidade")
    )
    status_domain = list(STATUS_COLORS.keys())
    status_range = [STATUS_COLORS[status] for status in status_domain]

    donut = (
        alt.Chart(status_counts)
        .mark_arc(innerRadius=55, outerRadius=105)
        .encode(
            theta=alt.Theta("Quantidade:Q"),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=status_domain, range=status_range),
                legend=alt.Legend(title=None),
            ),
            tooltip=["Status:N", "Quantidade:Q"],
        )
        .properties(title="Distribuição dos indicadores", height=320)
    )

    progress = results[
        (results["Status da meta"] != "Sem dados")
        & results["Resultado"].notna()
    ].copy()
    progress = progress.sort_values(
        ["Progresso (%)", "KPI"], ascending=[False, True]
    ).head(15)
    progress["Rótulo"] = progress["Indicador visual"].map(
        lambda value: (
            value if len(_clean_text(value)) <= 58
            else _clean_text(value)[:55] + "..."
        )
    )
    progress = progress.sort_values(
        ["Progresso (%)", "KPI"], ascending=[True, False]
    )
    progress_colors = [
        STATUS_COLORS.get(status, STATUS_COLORS["Sem dados"])
        for status in progress["Status da meta"]
    ]
    progress_customdata = progress[
        [
            "Indicador visual",
            "Resultado",
            "Unidade",
            "Status da meta",
            "Referência",
        ]
    ].astype(object).values
    progress_chart = go.Figure()
    progress_chart.add_trace(
        go.Bar(
            x=[100] * len(progress),
            y=progress["Rótulo"],
            orientation="h",
            marker={
                "color": "#EEF1F5",
                "line": {"color": "#D5DAE1", "width": 1},
            },
            hoverinfo="skip",
            showlegend=False,
            name="Faixa",
        )
    )
    progress_chart.add_trace(
        go.Bar(
            x=progress["Progresso (%)"],
            y=progress["Rótulo"],
            orientation="h",
            marker={
                "color": progress_colors,
                "line": {"color": progress_colors, "width": 1},
            },
            customdata=progress_customdata,
            text=progress["Progresso (%)"].map(lambda value: f"{value:.0f}%"),
            textposition="auto",
            textfont={"color": "#263238"},
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Resultado: %{customdata[1]} %{customdata[2]}<br>"
                "Situação: %{customdata[3]}<br>"
                "Referência: %{customdata[4]}<br>"
                "Índice: %{x:.1f}%<extra></extra>"
            ),
            showlegend=False,
            name="Progresso",
        )
    )
    progress_chart.update_layout(
        title="Progresso e atividade por indicador",
        barmode="overlay",
        height=max(420, len(progress) * 48),
        xaxis={
            "title": "Índice de acompanhamento (%)",
            "range": [0, 105],
            "ticksuffix": "%",
            "gridcolor": "#E8EBEF",
        },
        yaxis={"title": None, "automargin": True},
        margin={"l": 20, "r": 30, "t": 55, "b": 55},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
    )

    chart_col1, chart_col2 = st.columns([1, 2])
    with chart_col1:
        _chart_description(
            "como os indicadores da pessoa estão distribuídos por situação "
            "no período selecionado!"
        )
        st.altair_chart(donut, width="stretch")
    with chart_col2:
        if progress.empty:
            st.info("Ainda não existem resultados mensuráveis para o período.")
        else:
            _chart_description(
                "quais indicadores estão mais próximos ou mais distantes da "
                "referência/meta acompanhada!"
            )
            st.plotly_chart(
                progress_chart,
                width="stretch",
                config={"displayModeBar": False},
            )

    radar_source = (
        results[results["Status da meta"] != "Sem dados"]
        .groupby("KPI", as_index=False)["Índice"]
        .mean()
    )
    if not radar_source.empty:
        radar_source["Índice"] = radar_source["Índice"].round(1)
        radar = go.Figure()
        radar.add_trace(
            go.Scatterpolar(
                r=radar_source["Índice"].tolist()
                + [radar_source["Índice"].iloc[0]],
                theta=radar_source["KPI"].tolist()
                + [radar_source["KPI"].iloc[0]],
                fill="toself",
                name="Índice",
                line_color="#1565C0",
                fillcolor="rgba(21, 101, 192, 0.25)",
            )
        )
        radar.update_layout(
            title="Índice de acompanhamento por KPI",
            polar={"radialaxis": {"visible": True, "range": [0, 100]}},
            showlegend=False,
            height=420,
            margin={"l": 40, "r": 40, "t": 70, "b": 30},
        )
        _chart_description(
            "em quais KPIs a pessoa está mais forte ou mais frágil na média "
            "dos indicadores mensuráveis!"
        )
        st.plotly_chart(radar, width="stretch")
        st.caption(
            "O radar combina metas objetivas, atividades registradas e itens "
            "parciais. Ele representa visibilidade/acompanhamento, não uma nota formal."
        )


def _render_history(history):
    numeric_history = history[
        history["Resultado"].notna()
        & history["Preenchimento"].map(_normalized).isin(
            {"AUTOMATICO", "PARCIAL"}
        )
    ].copy()
    if numeric_history.empty:
        st.info("Não existem resultados históricos mensuráveis para essa pessoa.")
        return

    numeric_history["Série"] = (
        numeric_history["KPI"].map(_clean_text)
        + " · "
        + numeric_history["Meta"].map(_clean_text)
        + " · "
        + numeric_history["Indicador"].map(_clean_text)
        + " · "
        + numeric_history["Métrica"].map(_clean_text)
    )
    options = sorted(numeric_history["Série"].unique())
    selected_series = st.selectbox(
        "Indicador para evolução", options, key="metas_history_series"
    )
    selected = numeric_history[
        numeric_history["Série"] == selected_series
    ].sort_values("Mês número")
    unit = _clean_text(selected["Unidade"].iloc[0])
    selected = selected.copy()
    selected["Valor exibido"] = selected["Resultado"].map(
        lambda value: f"{value:,.1f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
    target = selected["Meta numérica"].dropna()

    line = (
        alt.Chart(selected)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "Mês:N",
                sort=list(MONTH_LABELS.values()),
                title="Mês",
            ),
            y=alt.Y("Resultado:Q", title=unit or "Resultado"),
            color=alt.value("#1565C0"),
            tooltip=[
                "Mês:N",
                "Resultado:Q",
                "Unidade:N",
                "Status da meta:N",
                "Referência:N",
            ],
        )
        .properties(title="Evolução mensal do indicador", height=380)
    )
    labels = (
        alt.Chart(selected)
        .mark_text(align="center", baseline="bottom", dy=-10, fontSize=12)
        .encode(
            x=alt.X(
                "Mês:N",
                sort=list(MONTH_LABELS.values()),
                title="Mês",
            ),
            y=alt.Y("Resultado:Q", title=unit or "Resultado"),
            text="Valor exibido:N",
            color=alt.value("#263238"),
        )
    )
    line = line + labels
    if not target.empty:
        target_value = float(target.iloc[0])
        target_line = (
            alt.Chart(pd.DataFrame({"Meta": [target_value]}))
            .mark_rule(color="#C62828", strokeDash=[6, 4])
            .encode(y="Meta:Q")
        )
        line = line + target_line
    _chart_description(
        "como o resultado do indicador escolhido evoluiu mês a mês e se ele "
        "está acima ou abaixo da meta de referência!"
    )
    st.altair_chart(line, width="stretch")

    monthly_summary = (
        history[history["Status da meta"] != "Sem dados"]
        .groupby(["Mês número", "Mês"], as_index=False)
        .agg(
            Indicadores=("Status da meta", "size"),
            Índice=("Índice", "mean"),
        )
        .sort_values("Mês número")
    )
    monthly_summary["Índice"] = monthly_summary["Índice"].round(1)
    st.dataframe(
        monthly_summary[["Mês", "Indicadores", "Índice"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Índice": st.column_config.ProgressColumn(
                "Índice de acompanhamento",
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
        },
    )


def _render_team_heatmap(team_status):
    if team_status.empty:
        st.info("Não foi possível montar a comparação do cargo selecionado.")
        return

    status_domain = list(STATUS_COLORS.keys())
    status_range = [STATUS_COLORS[status] for status in status_domain]
    heatmap = (
        alt.Chart(team_status)
        .mark_rect(cornerRadius=3)
        .encode(
            x=alt.X("KPI:N", title=None, axis=alt.Axis(labelAngle=-25)),
            y=alt.Y("Pessoa:N", title=None),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=status_domain, range=status_range),
                legend=alt.Legend(title="Situação"),
            ),
            tooltip=["Pessoa:N", "KPI:N", "Status:N", "Índice:Q"],
        )
        .properties(title="Heatmap pessoa × KPI", height=max(260, len(team_status["Pessoa"].unique()) * 34))
    )
    labels = (
        alt.Chart(team_status)
        .mark_text(fontSize=11)
        .encode(
            x="KPI:N",
            y="Pessoa:N",
            text="Status:N",
            color=alt.condition(
                alt.datum.Status == "Sem dados",
                alt.value("#263238"),
                alt.value("white"),
            ),
        )
    )
    _chart_description(
        "quais pessoas do cargo selecionado estão melhor ou pior posicionadas "
        "em cada KPI!"
    )
    st.altair_chart(heatmap + labels, width="stretch")
    st.caption(
        "A célula consolida os indicadores mensuráveis de cada KPI. Itens "
        "exclusivamente manuais aparecem como “Sem dados”."
    )


def render_metas_dashboard(dados_carregados):
    df_time = _safe_dataframe(dados_carregados.get("df_time"))
    df_metas = _safe_dataframe(dados_carregados.get("df_metas_modelo"))
    if df_time.empty:
        st.warning("CTS.xlsx não foi carregado ou a aba `cts` está vazia.")
        return
    if df_metas.empty:
        message = dados_carregados.get(
            "metas_error",
            "A planilha excel-metas/Todas-metas-2026.xlsx não foi carregada.",
        )
        st.warning(message)
        return

    st.header("Metas 2026")
    st.caption(
        "Resultados calculados a partir de CTS, NOC, RVT, Riscos e RessarceBall. "
        "Campos sem fonte estruturada permanecem identificados como manuais."
    )

    role_column = _find_column(df_time, exact=("Divisão", "Divisao", "Cargo"))
    name_column = _find_column(
        df_time, exact=("NomeSalesforce", "Nome Salesforce", "Nome")
    )
    if not role_column or not name_column:
        st.error("CTS.xlsx precisa conter as colunas `Divisão` e `NomeSalesforce`.")
        return

    supported_roles = []
    for role in df_time[role_column].dropna().map(_clean_text).unique():
        row = df_time[
            _series_normalized(df_time[role_column]) == _normalized(role)
        ].iloc[0]
        if _cargo_templates(role, row):
            supported_roles.append(role)
    supported_roles = sorted(set(supported_roles))
    if not supported_roles:
        st.warning("Nenhum cargo do CTS corresponde aos modelos da planilha de metas.")
        return

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        month = st.number_input(
            "Mês", min_value=1, max_value=12, value=1, step=1, key="metas_month"
        )
    with filter_col2:
        year = st.number_input(
            "Ano", min_value=2023, value=2026, step=1, key="metas_year"
        )
    with filter_col3:
        period_type = st.selectbox(
            "Período", ["Mensal", "YTD"], key="metas_period_type"
        )
    with filter_col4:
        selected_role = st.selectbox(
            "Cargo", supported_roles, key="metas_role"
        )

    people = sorted(
        df_time.loc[
            _series_normalized(df_time[role_column])
            == _normalized(selected_role),
            name_column,
        ]
        .dropna()
        .map(_clean_text)
        .unique()
    )
    if not people:
        st.info("Não há pessoas cadastradas para o cargo selecionado.")
        return
    person = st.selectbox("Pessoa", people, key="metas_person")

    ressarce_frames = [
        dados_carregados.get("df_argentina"),
        dados_carregados.get("df_paraguai"),
        dados_carregados.get("df_chile"),
        dados_carregados.get("df_r_brasil"),
        dados_carregados.get("df_d_brasil"),
    ]
    results, context = build_metas_results(
        df_metas=df_metas,
        df_time=df_time,
        df_noc=dados_carregados.get("df_noc"),
        df_rvt=dados_carregados.get("df_rvt"),
        df_riscos=dados_carregados.get("riscos"),
        ressarce_frames=ressarce_frames,
        divisoes=dados_carregados.get("divisoes") or {},
        person=person,
        cargo=selected_role,
        month=int(month),
        year=int(year),
        ytd=period_type == "YTD",
    )

    if results.empty:
        st.info("Não há modelo de metas compatível com essa pessoa.")
        return

    results = enrich_metas_status(results)
    automatic_count = int((results["Preenchimento"] == "Automático").sum())
    partial_count = int((results["Preenchimento"] == "Parcial").sum())
    manual_count = int((results["Preenchimento"] == "Manual").sum())
    evidence_count = (
        len(context["rvt"]) + len(context["noc"]) + len(context["riscos"])
    )
    _render_status_cards(results, evidence_count)
    st.caption(
        f"Origem do preenchimento: {automatic_count} automático(s), "
        f"{partial_count} parcial(is) e {manual_count} manual(is)."
    )

    if len(context["model_roles"]) > 1:
        st.info(
            "O CTS não diferencia o subtipo do especialista. Foram exibidos os "
            "modelos: " + ", ".join(context["model_roles"])
        )
    if _normalized(selected_role) == "SUPERVISOR":
        visible_team = [
            name
            for name in context["team_names"]
            if name != _normalized(person)
        ]
        if visible_team:
            st.caption(
                f"RVTs regionais agregadas para {len(visible_team)} integrante(s) "
                "encontrado(s) no CTS."
            )

    (
        tab_dashboard,
        tab_results,
        tab_history,
        tab_team,
        tab_evidence,
        tab_rules,
    ) = st.tabs(
        [
            "Dashboard",
            "Acompanhamento",
            "Evolução mensal",
            "Equipe",
            "Evidências",
            "Critérios da planilha",
        ]
    )
    with tab_dashboard:
        _render_dashboard_charts(results)

    with tab_results:
        fill_filter = st.multiselect(
            "Exibir preenchimentos",
            ["Automático", "Parcial", "Manual"],
            default=["Automático", "Parcial", "Manual"],
            key="metas_fill_filter",
        )
        display = results[results["Preenchimento"].isin(fill_filter)].copy()
        st.dataframe(
            display,
            hide_index=True,
            width="stretch",
            column_order=[
                "KPI",
                "Meta",
                "Indicador",
                "Métrica",
                "Resultado",
                "Unidade",
                "Status da meta",
                "Referência",
                "Progresso (%)",
                "Preenchimento",
                "Fonte",
                "Evidências",
                "Observação",
            ],
            column_config={
                "Resultado": st.column_config.NumberColumn(format="%.1f"),
                "Progresso (%)": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "Observação": st.column_config.TextColumn(width="large"),
                "Evidências": st.column_config.TextColumn(width="large"),
            },
        )
        st.download_button(
            "Baixar acompanhamento em CSV",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"metas_{_normalized(person).replace(' ', '_')}_{year}_{month}.csv",
            mime="text/csv",
        )

    with tab_history:
        with st.spinner("Calculando a evolução mensal das metas..."):
            history = _build_history(
                dados_carregados=dados_carregados,
                df_metas=df_metas,
                df_time=df_time,
                person=person,
                cargo=selected_role,
                final_month=int(month),
                year=int(year),
            )
        _render_history(history)

    with tab_team:
        st.caption(
            f"Comparação entre pessoas cadastradas no CTS com o cargo "
            f"`{selected_role}`."
        )
        with st.spinner("Consolidando o heatmap da equipe..."):
            team_status = _build_team_status(
                dados_carregados=dados_carregados,
                df_metas=df_metas,
                df_time=df_time,
                people=people,
                cargo=selected_role,
                month=int(month),
                year=int(year),
                ytd=period_type == "YTD",
            )
        _render_team_heatmap(team_status)

    with tab_evidence:
        evidence_rvt, evidence_noc, evidence_risk = st.tabs(
            ["RVT", "NOC", "Riscos"]
        )
        with evidence_rvt:
            st.caption(
                "RVTs consideradas para a pessoa ou equipe no período selecionado."
            )
            st.dataframe(context["rvt"], hide_index=True, width="stretch")
        with evidence_noc:
            st.caption(
                "NOCs atribuídas à pessoa, supervisor, especialista ou conta."
            )
            st.dataframe(context["noc"], hide_index=True, width="stretch")
        with evidence_risk:
            st.caption("Registros de risco vinculados à pessoa no período.")
            st.dataframe(
                context["riscos"], hide_index=True, width="stretch"
            )

    with tab_rules:
        detailed = _safe_dataframe(dados_carregados.get("df_metas_detalhadas"))
        summary = _safe_dataframe(dados_carregados.get("df_metas_resumo"))
        detailed_role_column = _find_column(
            detailed, exact=("Responsável", "Responsavel", "Cargo")
        )
        if detailed_role_column:
            detailed_filtered = detailed[
                _series_normalized(detailed[detailed_role_column])
                == _normalized(selected_role)
            ]
        else:
            detailed_filtered = pd.DataFrame()

        if not detailed_filtered.empty:
            st.subheader("Critérios detalhados")
            st.dataframe(
                detailed_filtered, hide_index=True, width="stretch"
            )
        else:
            st.info(
                "A aba `Metas 2026` possui critérios detalhados apenas para os "
                "cargos cadastrados nela. Abaixo está o resumo disponível."
            )

        if not summary.empty:
            summary_filtered = summary[
                summary["Cargo"].map(_normalized).str.contains(
                    _normalized(selected_role), regex=False
                )
            ]
            if not summary_filtered.empty:
                st.subheader("Resumo por cargo")
                st.dataframe(
                    summary_filtered, hide_index=True, width="stretch"
                )
