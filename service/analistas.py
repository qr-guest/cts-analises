import pandas as pd
import plotly.express as px
import streamlit as st


MISSING_VALUE = "(Não informado)"


def _clean_text(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _clean_series(series, uppercase=False):
    cleaned = (
        series.astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .replace(
            {
                "": pd.NA,
                "NULL": pd.NA,
                "null": pd.NA,
                "None": pd.NA,
                "nan": pd.NA,
            }
        )
    )
    return cleaned.str.upper() if uppercase else cleaned


def _find_column(df, candidates):
    normalized = {
        _clean_text(column).lower().replace(" ", "").replace("_", ""): column
        for column in df.columns
    }
    for candidate in candidates:
        key = _clean_text(candidate).lower().replace(" ", "").replace("_", "")
        if key in normalized:
            return normalized[key]
    return None


def _fmt_int(value):
    return f"{value:,.0f}".replace(",", ".")


def _fmt_pct(value):
    return (
        f"{value:,.2f}%"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _prepare_noc_data(df_noc):
    df = df_noc.copy() if isinstance(df_noc, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return df, {}

    columns = {
        "noc": _find_column(df, ["Numero NOC", "Número NOC", "NOC"]),
        "date": _find_column(
            df, ["DataRecebimentoSAC", "Data Recebimento SAC", "DataCriacao"]
        ),
        "client": _find_column(df, ["Clientes", "Cliente"]),
        "status": _find_column(df, ["Status"]),
        "type": _find_column(df, ["Tipo de NOC", "Tipo NOC"]),
        "approval": _find_column(
            df, ["AprovacaoInvestigacao", "Aprovação Investigação"]
        ),
        "defect": _find_column(df, ["Defeito"]),
        "parecer": _find_column(df, ["Parecer"]),
        "plant": _find_column(df, ["Planta"]),
        "product": _find_column(df, ["Tipo do Produto", "Tipo Produto"]),
        "analyst": _find_column(
            df,
            [
                "Analistas",
                "Analista",
                "ResponsavelBall",
                "Responsável Ball",
                "Responsavel",
            ],
        ),
        "term": _find_column(df, ["Termo_pesquisa", "Termo Pesquisa"]),
    }

    required = [columns["noc"], columns["date"], columns["client"]]
    if any(column is None for column in required):
        return pd.DataFrame(), columns

    prepared = pd.DataFrame()
    prepared["NUMERO_NOC"] = df[columns["noc"]]
    prepared["DATA_RECEBIMENTO"] = pd.to_datetime(
        df[columns["date"]], errors="coerce", dayfirst=True
    )
    prepared["CLIENTE"] = _clean_series(df[columns["client"]], uppercase=True).fillna(
        MISSING_VALUE
    )

    optional_map = {
        "STATUS": ("status", True),
        "TIPO_NOC": ("type", True),
        "APROVACAO": ("approval", True),
        "DEFEITO": ("defect", True),
        "PARECER": ("parecer", True),
        "PLANTA": ("plant", True),
        "TIPO_PRODUTO": ("product", True),
        "ANALISTA": ("analyst", False),
        "TERMO_PESQUISA": ("term", False),
    }
    for output, (source_key, uppercase) in optional_map.items():
        source_column = columns.get(source_key)
        if source_column:
            prepared[output] = _clean_series(
                df[source_column], uppercase=uppercase
            ).fillna(MISSING_VALUE)
        else:
            prepared[output] = MISSING_VALUE

    prepared["ANO_MES"] = prepared["DATA_RECEBIMENTO"].dt.to_period("M").astype("string")
    prepared["ANO_MES"] = prepared["ANO_MES"].fillna("SEM DATA")
    prepared = prepared.drop_duplicates("NUMERO_NOC", keep="first")
    return prepared, columns


def _filter_period(df, month, year, ytd):
    if df.empty:
        return df
    dates = df["DATA_RECEBIMENTO"]
    if ytd:
        mask = (dates.dt.year == int(year)) & (dates.dt.month <= int(month))
    else:
        mask = (dates.dt.year == int(year)) & (dates.dt.month == int(month))
    return df.loc[mask].copy()


def _apply_multiselect(df, column, label, key):
    options = sorted(
        value for value in df[column].dropna().astype(str).unique() if value
    )
    selected = st.multiselect(label, options=options, key=key, placeholder="Todos")
    if selected:
        return df[df[column].isin(selected)].copy()
    return df


def _filter_valid_nocs(df, include_internal=False, include_unapproved=False):
    filtered = df.copy()
    if "STATUS" in filtered.columns:
        filtered = filtered[
            ~filtered["STATUS"].isin(["CANCELADA", "PREENCHIMENTO DE DADOS DA NOC"])
        ].copy()
    if (
        not include_internal
        and "TIPO_NOC" in filtered.columns
        and filtered["TIPO_NOC"].eq("EXTERNA").any()
    ):
        filtered = filtered[filtered["TIPO_NOC"].eq("EXTERNA")].copy()
    if (
        not include_unapproved
        and "APROVACAO" in filtered.columns
        and filtered["APROVACAO"].eq("APROVADA").any()
    ):
        filtered = filtered[filtered["APROVACAO"].eq("APROVADA")].copy()
    return filtered


def _aggregate_clients(df):
    if df.empty:
        return pd.DataFrame()

    total_nocs = df["NUMERO_NOC"].nunique()
    result = (
        df.groupby("CLIENTE", as_index=False)
        .agg(
            NOCS=("NUMERO_NOC", "nunique"),
            DEFEITOS_DISTINTOS=("DEFEITO", "nunique"),
            PLANTAS_ENVOLVIDAS=("PLANTA", "nunique"),
            PRIMEIRA_NOC=("DATA_RECEBIMENTO", "min"),
            ULTIMA_NOC=("DATA_RECEBIMENTO", "max"),
        )
        .sort_values("NOCS", ascending=False)
    )
    result["INDICE_OCORRENCIA"] = (
        result["NOCS"].div(total_nocs).fillna(0) * 100
    )
    result["INDICE_ACUMULADO"] = result["INDICE_OCORRENCIA"].cumsum()
    result["RANKING"] = range(1, len(result) + 1)
    return result


def _aggregate_dimension(df, dimension):
    if df.empty or dimension not in df.columns:
        return pd.DataFrame()

    total_nocs = df["NUMERO_NOC"].nunique()
    result = (
        df.groupby(dimension, dropna=False, as_index=False)
        .agg(NOCS=("NUMERO_NOC", "nunique"))
        .sort_values("NOCS", ascending=False)
    )
    result["INDICE_OCORRENCIA"] = (
        result["NOCS"].div(total_nocs).fillna(0) * 100
    )
    result["INDICE_ACUMULADO"] = result["INDICE_OCORRENCIA"].cumsum()
    return result


def _horizontal_occurrence_chart(df, dimension, title, color, top_n=15):
    source = _aggregate_dimension(df, dimension)
    if source.empty:
        return None

    ranking = source.head(top_n).sort_values("NOCS")
    fig = px.bar(
        ranking,
        x="NOCS",
        y=dimension,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=["INDICE_OCORRENCIA", "INDICE_ACUMULADO"],
    )
    fig.update_traces(
        text=ranking.apply(
            lambda row: f"<b>{row['NOCS']:,.0f} | {row['INDICE_OCORRENCIA']:.1f}%</b>",
            axis=1,
        ),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "NOCs: %{x:,.0f}<br>"
            "Índice: %{customdata[0]:.2f}%<br>"
            "Índice acumulado: %{customdata[1]:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(
        height=max(430, len(ranking) * 34),
        xaxis_title="NOCs válidas",
        yaxis_title=None,
        margin={"l": 20, "r": 90, "t": 75, "b": 30},
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return fig


def _monthly_noc_chart(df):
    source = (
        df[df["ANO_MES"].ne("SEM DATA")]
        .groupby("ANO_MES", as_index=False)
        .agg(NOCS=("NUMERO_NOC", "nunique"))
        .sort_values("ANO_MES")
    )
    if source.empty:
        return None

    fig = px.bar(
        source,
        x="ANO_MES",
        y="NOCS",
        title="3.3 Gráfico: Quantidade por Mês NOC",
        color_discrete_sequence=["#00838F"],
    )
    fig.update_traces(
        text=source["NOCS"].map(lambda value: f"<b>{value:,.0f}</b>"),
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>NOCs: %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        height=430,
        xaxis_title="Mês",
        yaxis_title="NOCs válidas",
        margin={"l": 20, "r": 40, "t": 75, "b": 35},
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return fig


def _render_chart(fig, description, key):
    st.caption(f"Este gráfico responde: {description}")
    if fig is None:
        st.info("Não existem dados suficientes para montar este gráfico nos filtros atuais.")
    else:
        st.plotly_chart(fig, width="stretch", key=key)


def _prepare_rvt_data(df_rvt):
    df = df_rvt.copy() if isinstance(df_rvt, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return df, {}

    columns = {
        "rvt": _find_column(
            df,
            [
                "Numero RVT",
                "Número RVT",
                "RVT",
                "RVT: Número RVT",
                "RVT: Numero RVT",
            ],
        ),
        "date": _find_column(
            df,
            [
                "DataInicio",
                "Data Início",
                "Data Reclamação",
                "DataCriacao",
                "Data Criação",
                "RVT: Created Date",
            ],
        ),
        "responsible": _find_column(
            df,
            ["ResponsavelBall", "Responsável Ball", "Responsavel", "Responsável"],
        ),
        "unit": _find_column(
            df,
            ["UnidadesBall", "Unidade(s) Ball", "Unidade Ball", "Unidade"],
        ),
        "type": _find_column(df, ["Tipo", "Tipo RVT", "Tipo Atendimento"]),
        "status": _find_column(df, ["Status"]),
        "motive": _find_column(df, ["Motivo", "Assunto", "Descrição", "Descricao"]),
        "client": _find_column(df, ["Cliente", "Clientes"]),
        "city": _find_column(df, ["Cidade do Cliente", "Cidade Cliente", "Cidade"]),
    }

    prepared = pd.DataFrame()
    if columns["rvt"]:
        prepared["NUMERO_RVT"] = df[columns["rvt"]].astype("string")
    else:
        prepared["NUMERO_RVT"] = pd.Series(
            range(1, len(df) + 1), index=df.index, dtype="int64"
        ).astype("string")

    if columns["date"]:
        prepared["DATA_REFERENCIA"] = pd.to_datetime(
            df[columns["date"]], errors="coerce", dayfirst=True
        )
    else:
        prepared["DATA_REFERENCIA"] = pd.NaT

    field_map = {
        "RESPONSAVEL_BALL": ("responsible", False),
        "UNIDADE_BALL": ("unit", True),
        "TIPO": ("type", True),
        "STATUS_RVT": ("status", True),
        "MOTIVO": ("motive", True),
        "CLIENTE_RVT": ("client", True),
        "CIDADE_CLIENTE": ("city", True),
    }
    for output, (source_key, uppercase) in field_map.items():
        source_column = columns.get(source_key)
        if source_column:
            prepared[output] = _clean_series(
                df[source_column], uppercase=uppercase
            ).fillna(MISSING_VALUE)
        else:
            prepared[output] = MISSING_VALUE

    prepared["ANO_MES"] = (
        prepared["DATA_REFERENCIA"].dt.to_period("M").astype("string")
    )
    prepared["ANO_MES"] = prepared["ANO_MES"].fillna("SEM DATA")
    prepared = prepared.drop_duplicates("NUMERO_RVT", keep="first")
    return prepared, columns


def _filter_rvt_period(df, month, year, ytd):
    if df.empty or df["DATA_REFERENCIA"].isna().all():
        return df.copy()
    dates = df["DATA_REFERENCIA"]
    if ytd:
        mask = (dates.dt.year == int(year)) & (dates.dt.month <= int(month))
    else:
        mask = (dates.dt.year == int(year)) & (dates.dt.month == int(month))
    return df.loc[mask].copy()


def _aggregate_rvt_dimension(df, dimension):
    if df.empty or dimension not in df.columns:
        return pd.DataFrame()

    total = df["NUMERO_RVT"].nunique()
    result = (
        df.groupby(dimension, dropna=False, as_index=False)
        .agg(QTD_RVT=("NUMERO_RVT", "nunique"))
        .sort_values("QTD_RVT", ascending=False)
    )
    result["PERCENTUAL"] = result["QTD_RVT"].div(total).fillna(0) * 100
    return result


def _rvt_vertical_bar(df, dimension, title, color, top_n=18):
    source = _aggregate_rvt_dimension(df, dimension).head(top_n)
    if source.empty:
        return None
    fig = px.bar(
        source,
        x=dimension,
        y="QTD_RVT",
        title=title,
        color_discrete_sequence=[color],
        custom_data=["PERCENTUAL"],
    )
    fig.update_traces(
        text=source["QTD_RVT"].map(lambda value: f"<b>{value:,.0f}</b>"),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>RVTs: %{y:,.0f}<br>"
            "Participação: %{customdata[0]:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(
        height=520,
        xaxis_title=None,
        yaxis_title="RVTs",
        xaxis={"tickangle": -35, "automargin": True},
        margin={"l": 20, "r": 45, "t": 75, "b": 145},
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return fig


def _rvt_horizontal_bar(df, dimension, title, color, top_n=15):
    source = _aggregate_rvt_dimension(df, dimension).head(top_n)
    if source.empty:
        return None
    ranking = source.sort_values("QTD_RVT")
    fig = px.bar(
        ranking,
        x="QTD_RVT",
        y=dimension,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=["PERCENTUAL"],
    )
    fig.update_traces(
        text=ranking["QTD_RVT"].map(lambda value: f"<b>{value:,.0f}</b>"),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>RVTs: %{x:,.0f}<br>"
            "Participação: %{customdata[0]:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(
        height=max(430, len(ranking) * 36),
        xaxis_title="RVTs",
        yaxis_title=None,
        margin={"l": 20, "r": 70, "t": 75, "b": 30},
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return fig


def _rvt_donut(df, dimension, title, hole=0.5):
    source = _aggregate_rvt_dimension(df, dimension)
    if source.empty:
        return None
    fig = px.pie(
        source,
        names=dimension,
        values="QTD_RVT",
        title=title,
        hole=hole,
        custom_data=["PERCENTUAL"],
    )
    fig.update_traces(
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>RVTs: %{value:,.0f}<br>"
            "Participação: %{customdata[0]:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(height=480, margin={"l": 20, "r": 20, "t": 75, "b": 25})
    return fig


def _rvt_monthly_chart(df):
    source = (
        df[df["ANO_MES"].ne("SEM DATA")]
        .groupby("ANO_MES", as_index=False)
        .agg(QTD_RVT=("NUMERO_RVT", "nunique"))
        .sort_values("ANO_MES")
    )
    if source.empty:
        return None

    fig = px.line(
        source,
        x="ANO_MES",
        y="QTD_RVT",
        markers=True,
        title="6.6 Gráfico: Visita Mensal",
    )
    fig.update_traces(
        text=source["QTD_RVT"].map(lambda value: f"<b>{value:,.0f}</b>"),
        mode="lines+markers+text",
        textposition="top center",
        line={"color": "#1565C0", "width": 3},
        hovertemplate="<b>%{x}</b><br>RVTs: %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        height=430,
        xaxis_title="Mês",
        yaxis_title="RVTs",
        margin={"l": 20, "r": 40, "t": 75, "b": 35},
    )
    return fig


def _bar_clients(client_index, top_n):
    ranking = client_index.head(top_n).sort_values("NOCS")
    fig = px.bar(
        ranking,
        x="NOCS",
        y="CLIENTE",
        orientation="h",
        title="3.2 Gráfico: Clientes",
        color_discrete_sequence=["#1565C0"],
        custom_data=[
            "INDICE_OCORRENCIA",
            "INDICE_ACUMULADO",
            "DEFEITOS_DISTINTOS",
            "PLANTAS_ENVOLVIDAS",
        ],
    )
    fig.update_traces(
        text=ranking.apply(
            lambda row: f"<b>{row['NOCS']:,.0f} | {row['INDICE_OCORRENCIA']:.1f}%</b>",
            axis=1,
        ),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "NOCs: %{x:,.0f}<br>"
            "Índice: %{customdata[0]:.2f}%<br>"
            "Índice acumulado: %{customdata[1]:.2f}%<br>"
            "Defeitos distintos: %{customdata[2]:,.0f}<br>"
            "Plantas envolvidas: %{customdata[3]:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        height=max(430, len(ranking) * 34),
        xaxis_title="NOCs válidas",
        yaxis_title=None,
        margin={"l": 20, "r": 80, "t": 70, "b": 30},
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return fig


def _pareto_clients(client_index, top_n):
    ranking = client_index.head(top_n).copy()
    fig = px.line(
        ranking,
        x="RANKING",
        y="INDICE_ACUMULADO",
        markers=True,
        title="Pareto acumulado das ocorrências por cliente",
        hover_data=["CLIENTE", "NOCS", "INDICE_OCORRENCIA"],
    )
    fig.update_traces(
        line={"color": "#E87722", "width": 3},
        text=ranking["INDICE_ACUMULADO"].map(lambda value: f"<b>{value:.1f}%</b>"),
        mode="lines+markers+text",
        textposition="top center",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Ranking: %{x}<br>"
            "NOCs: %{customdata[1]:,.0f}<br>"
            "Índice do cliente: %{customdata[2]:.2f}%<br>"
            "Índice acumulado: %{y:.2f}%<extra></extra>"
        ),
    )
    fig.update_yaxes(title_text="Índice acumulado", ticksuffix="%", range=[0, 105])
    fig.update_xaxes(title_text="Ranking do cliente")
    fig.update_layout(height=420, margin={"l": 20, "r": 40, "t": 70, "b": 40})
    return fig


def _monthly_client_chart(df, client):
    monthly = (
        df[df["CLIENTE"].eq(client)]
        .groupby("ANO_MES", as_index=False)
        .agg(NOCS=("NUMERO_NOC", "nunique"))
        .sort_values("ANO_MES")
    )
    if monthly.empty:
        return None
    fig = px.line(
        monthly,
        x="ANO_MES",
        y="NOCS",
        markers=True,
        title=f"Evolução mensal de ocorrências - {client}",
    )
    fig.update_traces(
        text=monthly["NOCS"].map(lambda value: f"<b>{value:,.0f}</b>"),
        mode="lines+markers+text",
        textposition="top center",
        line={"color": "#1565C0", "width": 3},
    )
    fig.update_layout(
        height=420,
        xaxis_title="Mês",
        yaxis_title="NOCs",
        margin={"l": 20, "r": 40, "t": 75, "b": 35},
    )
    return fig


def _defect_chart(df, client):
    defects = (
        df[df["CLIENTE"].eq(client)]
        .groupby("DEFEITO", as_index=False)
        .agg(NOCS=("NUMERO_NOC", "nunique"))
        .sort_values("NOCS", ascending=False)
        .head(10)
        .sort_values("NOCS")
    )
    if defects.empty:
        return None
    fig = px.bar(
        defects,
        x="NOCS",
        y="DEFEITO",
        orientation="h",
        title=f"Top defeitos - {client}",
        color_discrete_sequence=["#6A1B9A"],
    )
    fig.update_traces(
        text=defects["NOCS"].map(lambda value: f"<b>{value:,.0f}</b>"),
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_layout(
        height=max(380, len(defects) * 38),
        xaxis_title="NOCs",
        yaxis_title=None,
        margin={"l": 20, "r": 60, "t": 70, "b": 30},
    )
    return fig


def _render_rvt_section(df_rvt):
    st.subheader("Segunda Parte da aba Analistas — RVT")
    st.caption(
        "Painel controle RVT South America: acompanha o total de RVTs, "
        "responsáveis, unidades Ball, tipo de atendimento, status, motivo e "
        "evolução mensal."
    )

    rvt, columns = _prepare_rvt_data(df_rvt)
    if rvt.empty:
        st.warning(
            "Não foi possível montar a segunda parte com RVT. A base RVT precisa "
            "estar carregada e conter ao menos os campos de RVT/atendimento."
        )
        if columns:
            st.caption("Colunas detectadas: " + str(columns))
        return

    max_date = rvt["DATA_REFERENCIA"].max()
    default_month = int(max_date.month) if pd.notna(max_date) else 12
    default_year = int(max_date.year) if pd.notna(max_date) else 2026

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        month = st.number_input(
            "Mês RVT",
            min_value=1,
            max_value=12,
            value=default_month,
            key="analistas_rvt_mes",
        )
    with filter_col2:
        year = st.number_input(
            "Ano RVT",
            min_value=2023,
            value=default_year,
            key="analistas_rvt_ano",
        )
    with filter_col3:
        period = st.selectbox(
            "Período RVT",
            ["Mensal", "YTD", "Base completa"],
            index=2,
            key="analistas_rvt_periodo",
        )
    with filter_col4:
        top_n = st.selectbox(
            "Itens nos rankings RVT",
            [10, 15, 20, 30, 50],
            index=1,
            key="analistas_rvt_top_n",
        )

    if period == "Base completa":
        filtered = rvt.copy()
    else:
        filtered = _filter_rvt_period(
            rvt, int(month), int(year), ytd=period == "YTD"
        )

    with st.expander("Filtros RVT adicionais", expanded=False):
        filtered = _apply_multiselect(
            filtered,
            "RESPONSAVEL_BALL",
            "Responsável atendimento",
            "analistas_rvt_responsavel",
        )
        filtered = _apply_multiselect(
            filtered,
            "UNIDADE_BALL",
            "Unidade(s) Ball",
            "analistas_rvt_unidade",
        )
        filtered = _apply_multiselect(
            filtered, "TIPO", "Tipo atendimento", "analistas_rvt_tipo"
        )
        filtered = _apply_multiselect(
            filtered, "STATUS_RVT", "Status RVT", "analistas_rvt_status"
        )
        filtered = _apply_multiselect(
            filtered, "MOTIVO", "Motivo", "analistas_rvt_motivo"
        )

    if filtered.empty:
        st.info("Nenhum RVT encontrado para os filtros selecionados.")
        return

    total_rvt = int(filtered["NUMERO_RVT"].nunique())
    responsible_count = int(filtered["RESPONSAVEL_BALL"].nunique())
    unit_count = int(filtered["UNIDADE_BALL"].nunique())
    top_motive = _aggregate_rvt_dimension(filtered, "MOTIVO").iloc[0]

    cards = st.columns(4)
    cards[0].metric("QTD. TOTAL RVT", _fmt_int(total_rvt))
    cards[1].metric("Responsáveis", _fmt_int(responsible_count))
    cards[2].metric("Unidades Ball", _fmt_int(unit_count))
    cards[3].metric(
        "Motivo principal",
        str(top_motive["MOTIVO"]),
        _fmt_int(top_motive["QTD_RVT"]) + " RVTs",
        delta_color="off",
    )

    date_source = columns.get("date") or "sem coluna de data identificada"
    st.caption(
        "Data usada na série mensal/filtros RVT: "
        f"`{date_source}`. O documento cita Data Início, Data Reclamação ou "
        "RVT Created Date como possíveis bases; aqui usamos a primeira coluna "
        "disponível nessa ordem."
    )

    (
        resp_tab,
        unit_tab,
        type_tab,
        status_tab,
        motive_tab,
        monthly_tab,
    ) = st.tabs(
        [
            "6.1 Responsável",
            "6.2 Unidade Ball",
            "6.3 Tipo Atendimento",
            "6.4 Status",
            "6.5 Motivo",
            "6.6 Visita Mensal",
        ]
    )

    with resp_tab:
        _render_chart(
            _rvt_vertical_bar(
                filtered,
                "RESPONSAVEL_BALL",
                "6.1 Gráfico: Responsável Atendimento",
                "#1565C0",
                top_n,
            ),
            "quais responsáveis concentram maior volume de atendimentos/RVTs!",
            "analistas_rvt_61_responsavel",
        )
    with unit_tab:
        _render_chart(
            _rvt_horizontal_bar(
                filtered,
                "UNIDADE_BALL",
                "6.2 Gráfico: Unidade(s) Ball",
                "#2E7D32",
                top_n,
            ),
            "quais unidades Ball concentram maior volume de RVTs!",
            "analistas_rvt_62_unidade",
        )
    with type_tab:
        _render_chart(
            _rvt_donut(filtered, "TIPO", "6.3 Gráfico: Tipo Atendimento"),
            "qual é a proporção dos RVTs por tipo de atendimento!",
            "analistas_rvt_63_tipo",
        )
    with status_tab:
        _render_chart(
            _rvt_donut(filtered, "STATUS_RVT", "6.4 Gráfico: Status", hole=0),
            "como os RVTs estão distribuídos por status!",
            "analistas_rvt_64_status",
        )
    with motive_tab:
        _render_chart(
            _rvt_horizontal_bar(
                filtered,
                "MOTIVO",
                "6.5 Gráfico: Motivo",
                "#6A1B9A",
                top_n,
            ),
            "quais motivos explicam o maior volume de RVTs!",
            "analistas_rvt_65_motivo",
        )
    with monthly_tab:
        _render_chart(
            _rvt_monthly_chart(filtered),
            "como o volume de RVTs/visitas evolui mês a mês!",
            "analistas_rvt_66_visita_mensal",
        )

    st.subheader("Detalhamento RVT")
    st.dataframe(
        filtered.sort_values("DATA_REFERENCIA", ascending=False, na_position="last"),
        hide_index=True,
        width="stretch",
        column_config={
            "DATA_REFERENCIA": st.column_config.DatetimeColumn(
                "Data referência", format="DD/MM/YYYY"
            )
        },
    )
    st.download_button(
        "Baixar RVTs filtrados",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"analistas_rvt_{int(year)}_{int(month):02d}.csv",
        mime="text/csv",
        key="analistas_rvt_download",
    )


def render_analistas_dashboard(df_noc, df_rvt=None):
    st.header("Analistas")
    st.caption(
        "Painel para analisar o índice de ocorrência por cliente. O índice "
        "mostra a participação de cada cliente no total de NOCs válidas do "
        "período filtrado."
    )

    df, columns = _prepare_noc_data(df_noc)
    if df.empty:
        st.warning(
            "Não foi possível montar a aba Analistas. A base NOC precisa conter "
            "`Numero NOC`, `DataRecebimentoSAC` e `Clientes`."
        )
        if columns:
            st.caption("Colunas detectadas: " + str(columns))
        return

    min_date = df["DATA_RECEBIMENTO"].min()
    max_date = df["DATA_RECEBIMENTO"].max()
    default_month = int(max_date.month) if pd.notna(max_date) else 1
    default_year = int(max_date.year) if pd.notna(max_date) else 2026

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        month = st.number_input(
            "Mês", min_value=1, max_value=12, value=default_month, key="analistas_mes"
        )
    with filter_col2:
        year = st.number_input(
            "Ano", min_value=2023, value=default_year, key="analistas_ano"
        )
    with filter_col3:
        period = st.selectbox(
            "Período", ["Mensal", "YTD"], key="analistas_periodo"
        )

    ytd = period == "YTD"
    filtered = _filter_period(df, int(month), int(year), ytd)

    with st.expander("Filtros adicionais", expanded=False):
        options_col1, options_col2 = st.columns(2)
        with options_col1:
            include_internal = st.toggle(
                "Incluir NOCs internas",
                value=False,
                key="analistas_include_internal",
                help="Desligado mantém somente NOCs EXTERNAS.",
            )
        with options_col2:
            include_unapproved = st.toggle(
                "Incluir não aprovadas",
                value=False,
                key="analistas_include_unapproved",
                help="Desligado mantém somente NOCs com investigação APROVADA.",
            )

        filtered = _filter_valid_nocs(
            filtered,
            include_internal=include_internal,
            include_unapproved=include_unapproved,
        )
        filtered = _apply_multiselect(
            filtered, "PLANTA", "Planta", "analistas_filter_planta"
        )
        filtered = _apply_multiselect(
            filtered, "DEFEITO", "Defeito", "analistas_filter_defeito"
        )
        filtered = _apply_multiselect(
            filtered, "PARECER", "Parecer", "analistas_filter_parecer"
        )
        filtered = _apply_multiselect(
            filtered, "TIPO_PRODUTO", "Tipo do produto", "analistas_filter_produto"
        )
        filtered = _apply_multiselect(
            filtered, "ANALISTA", "Analista/responsável", "analistas_filter_responsavel"
        )

    if filtered.empty:
        st.info("Nenhuma NOC encontrada para os filtros selecionados.")
        return

    client_index = _aggregate_clients(filtered)
    total_nocs = int(filtered["NUMERO_NOC"].nunique())
    total_clients = int(client_index["CLIENTE"].nunique())
    top_client = client_index.iloc[0]
    top5_share = float(client_index.head(5)["INDICE_OCORRENCIA"].sum())

    cards = st.columns(4)
    cards[0].metric("NOCs válidas", _fmt_int(total_nocs))
    cards[1].metric("Clientes com ocorrência", _fmt_int(total_clients))
    cards[2].metric(
        "Maior índice",
        str(top_client["CLIENTE"]),
        _fmt_pct(top_client["INDICE_OCORRENCIA"]),
        delta_color="off",
    )
    cards[3].metric("Concentração Top 5", _fmt_pct(top5_share))

    st.caption(
        f"Período analisado: {'YTD até' if ytd else 'mês'} {int(month):02d}/{int(year)}. "
        "Por padrão, são consideradas NOCs externas, não canceladas, fora de "
        "preenchimento e aprovadas."
    )

    top_n = st.selectbox(
        "Quantidade de itens nos gráficos",
        [10, 15, 20, 30, 50],
        index=1,
        key="analistas_top_n",
    )

    tab_overview, tab_client, tab_rvt, tab_detail = st.tabs(
        [
            "Visão geral NOC",
            "Análise do cliente",
            "Segunda Parte - RVT",
            "Detalhamento NOC",
        ]
    )

    with tab_overview:
        st.markdown("### Gráficos 3.1 a 3.6")
        st.caption(
            "Todos os gráficos abaixo usam as mesmas NOCs válidas dos filtros "
            "atuais e exibem quantidade de NOCs mais participação no total."
        )

        (
            defect_tab,
            client_tab,
            month_tab,
            plant_tab,
            parecer_tab,
            status_tab,
        ) = st.tabs(
            [
                "3.1 Defeito",
                "3.2 Clientes",
                "3.3 Mês NOC",
                "3.4 Planta",
                "3.5 Parecer",
                "3.6 Status",
            ]
        )
        with defect_tab:
            _render_chart(
                _horizontal_occurrence_chart(
                    filtered,
                    "DEFEITO",
                    "3.1 Gráfico: Defeito",
                    "#6A1B9A",
                    top_n,
                ),
                "quais defeitos concentram mais ocorrências no período!",
                "analistas_noc_31_defeito",
            )
        with client_tab:
            _render_chart(
                _bar_clients(client_index, top_n),
                "quais clientes concentram mais ocorrências no período!",
                "analistas_noc_32_clientes",
            )
        with month_tab:
            _render_chart(
                _monthly_noc_chart(filtered),
                "como a quantidade de NOCs evolui mês a mês no período filtrado!",
                "analistas_noc_33_mes",
            )
        with plant_tab:
            _render_chart(
                _horizontal_occurrence_chart(
                    filtered,
                    "PLANTA",
                    "3.4 Gráfico: Planta",
                    "#2E7D32",
                    top_n,
                ),
                "quais plantas concentram mais ocorrências no período!",
                "analistas_noc_34_planta",
            )
        with parecer_tab:
            _render_chart(
                _horizontal_occurrence_chart(
                    filtered,
                    "PARECER",
                    "3.5 Gráfico: Parecer",
                    "#E87722",
                    top_n,
                ),
                "como as ocorrências se distribuem por parecer!",
                "analistas_noc_35_parecer",
            )
        with status_tab:
            _render_chart(
                _horizontal_occurrence_chart(
                    filtered,
                    "STATUS",
                    "3.6 Gráfico: Status",
                    "#C62828",
                    top_n,
                ),
                "como as ocorrências se distribuem por status!",
                "analistas_noc_36_status",
            )

        st.markdown("### Análise complementar")
        left, right = st.columns([1.35, 1])
        with left:
            _render_chart(
                _bar_clients(client_index, top_n),
                "quais clientes concentram mais ocorrências no período!",
                "analistas_noc_complementar_clientes",
            )
        with right:
            _render_chart(
                _pareto_clients(client_index, top_n),
                "quantos clientes explicam a maior parte das ocorrências!",
                "analistas_noc_complementar_pareto",
            )

        st.dataframe(
            client_index,
            hide_index=True,
            width="stretch",
            column_config={
                "NOCS": st.column_config.NumberColumn("NOCs", format="%d"),
                "INDICE_OCORRENCIA": st.column_config.NumberColumn(
                    "Índice de ocorrência", format="%.2f%%"
                ),
                "INDICE_ACUMULADO": st.column_config.NumberColumn(
                    "Índice acumulado", format="%.2f%%"
                ),
                "PRIMEIRA_NOC": st.column_config.DatetimeColumn(
                    "Primeira NOC", format="DD/MM/YYYY"
                ),
                "ULTIMA_NOC": st.column_config.DatetimeColumn(
                    "Última NOC", format="DD/MM/YYYY"
                ),
            },
        )

    with tab_client:
        selected_client = st.selectbox(
            "Cliente",
            options=client_index["CLIENTE"].tolist(),
            key="analistas_cliente",
        )
        client_rows = filtered[filtered["CLIENTE"].eq(selected_client)].copy()
        selected_summary = client_index[
            client_index["CLIENTE"].eq(selected_client)
        ].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("NOCs do cliente", _fmt_int(selected_summary["NOCS"]))
        c2.metric(
            "Índice do cliente",
            _fmt_pct(selected_summary["INDICE_OCORRENCIA"]),
        )
        c3.metric(
            "Defeitos distintos",
            _fmt_int(selected_summary["DEFEITOS_DISTINTOS"]),
        )

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            monthly_chart = _monthly_client_chart(filtered, selected_client)
            if monthly_chart is not None:
                st.caption(
                    "Este gráfico responde: a ocorrência deste cliente está "
                    "aumentando, reduzindo ou se mantendo estável!"
                )
                st.plotly_chart(
                    monthly_chart,
                    width="stretch",
                    key="analistas_cliente_evolucao_mensal",
                )
        with chart_col2:
            defect_chart = _defect_chart(filtered, selected_client)
            if defect_chart is not None:
                st.caption(
                    "Este gráfico responde: quais defeitos mais explicam as "
                    "ocorrências deste cliente!"
                )
                st.plotly_chart(
                    defect_chart,
                    width="stretch",
                    key="analistas_cliente_defeitos",
                )

        st.dataframe(
            client_rows.sort_values("DATA_RECEBIMENTO", ascending=False),
            hide_index=True,
            width="stretch",
            column_config={
                "DATA_RECEBIMENTO": st.column_config.DatetimeColumn(
                    "Data recebimento", format="DD/MM/YYYY"
                )
            },
        )

    with tab_rvt:
        _render_rvt_section(df_rvt)

    with tab_detail:
        st.dataframe(
            filtered.sort_values(["CLIENTE", "DATA_RECEBIMENTO"]),
            hide_index=True,
            width="stretch",
            column_config={
                "DATA_RECEBIMENTO": st.column_config.DatetimeColumn(
                    "Data recebimento", format="DD/MM/YYYY"
                )
            },
        )
        st.download_button(
            "Baixar base filtrada",
            data=filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"analistas_indice_ocorrencia_{int(year)}_{int(month):02d}.csv",
            mime="text/csv",
            key="analistas_download",
        )
