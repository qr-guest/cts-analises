import io
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from service.onsite_damage import (
    SEVERITY_ORDER,
    enrich_with_damage,
    find_default_damage_path,
    render_damage_analysis,
)


DEFAULT_ONSITE_PATH = Path(
    "dados-onsite/Dados-snowflake_2026-06-23-0808.csv"
)
LOCAL_DATA_ENV = "ALLOW_LOCAL_DATA"
ONSITE_UPLOAD_STATE_KEY = "onsite_uploaded_csv"
ONSITE_DAMAGE_UPLOAD_STATE_KEY = "onsite_uploaded_damage_csv"

EXPECTED_COLUMNS = [
    "INSPECTION_ID",
    "INSPECTION_NAME",
    "ANO_MES",
    "DATA_INSPECAO",
    "DESTINO_CLIENTE",
    "CLIENTE_GRUPO",
    "TRANSPORTADORA",
    "CAMINHAO_OU_PLACA",
    "ROTA",
    "TOTAL_LATAS_FALTANTES",
    "ENTREGA_COM_PERDA",
    "TEMPLATE_NAME",
    "FIRSTNAME",
    "LASTNAME",
    "EMAIL",
    "WEBLINK",
]

CRITICAL_COLUMNS = {
    "INSPECTION_ID",
    "DATA_INSPECAO",
    "TOTAL_LATAS_FALTANTES",
}

FILTER_COLUMNS = [
    ("CLIENTE_GRUPO", "Grupo do cliente"),
    ("DESTINO_CLIENTE", "Destino/cliente"),
    ("TRANSPORTADORA", "Transportadora"),
    ("CAMINHAO_OU_PLACA", "Caminhão/placa"),
    ("ROTA", "Rota"),
    ("USUARIO", "Usuário"),
    ("TEMPLATE_NAME", "Template"),
    ("SEVERIDADE_AMASSADAS", "Severidade das amassadas"),
]

MISSING_VALUE = "(Não informado)"
INVALID_ROUTE_VALUES = {
    "0",
    "1",
    "2",
    "SIM",
    "NAO",
    "NÃO",
    "YES",
    "NO",
    "C: CONFORME",
    "NC: NO CONFORME",
}


def find_default_onsite_path():
    if not _allow_local_data():
        return None

    candidates = []
    for path in DEFAULT_ONSITE_PATH.parent.glob("*.csv"):
        try:
            columns = set(
                pd.read_csv(
                    path,
                    encoding="utf-8-sig",
                    nrows=0,
                ).columns
            )
        except Exception:
            continue
        if CRITICAL_COLUMNS.issubset(columns):
            candidates.append(
                (
                    "TOTAL_LATAS_AMASSADAS" in columns,
                    path.stat().st_mtime_ns,
                    path.name,
                    path,
                )
            )
    if not candidates:
        return DEFAULT_ONSITE_PATH
    return max(candidates)[-1]


def _allow_local_data():
    return os.getenv(LOCAL_DATA_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
    }


def _read_csv(source):
    try:
        return pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, encoding="latin1", low_memory=False)


@st.cache_data(show_spinner=False)
def load_onsite_csv(path, modified_at):
    del modified_at
    return _read_csv(path)


@st.cache_data(show_spinner=False)
def load_onsite_upload(contents):
    return _read_csv(io.BytesIO(contents))


def validate_onsite_schema(df):
    columns = {str(column).strip() for column in df.columns}
    return [column for column in EXPECTED_COLUMNS if column not in columns]


def _clean_text(series, uppercase=False):
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


def _derive_route_from_inspection_name(inspection_name):
    if pd.isna(inspection_name):
        return pd.NA
    parts = [
        part.strip()
        for part in str(inspection_name).split("/")
        if part.strip()
    ]
    if len(parts) < 4:
        return pd.NA
    origin = parts[2]
    destination = parts[3]
    if not origin or not destination:
        return pd.NA
    return f"{origin} -> {destination}".upper()


@st.cache_data(show_spinner=False)
def prepare_onsite_data(source_df):
    df = source_df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    missing_columns = [
        column for column in EXPECTED_COLUMNS if column not in df.columns
    ]
    for column in missing_columns:
        df[column] = pd.NA

    source_rows = len(df)
    duplicate_rows = int(
        df["INSPECTION_ID"].duplicated(keep="first").sum()
    )

    raw_dates = _clean_text(df["DATA_INSPECAO"])
    dates_without_offset = raw_dates.str.replace(
        r"\s[+-]\d{4}$", "", regex=True
    )
    df["DATA_INSPECAO"] = pd.to_datetime(
        dates_without_offset, errors="coerce"
    )
    invalid_dates = int(
        (raw_dates.notna() & df["DATA_INSPECAO"].isna()).sum()
    )

    raw_loss = _clean_text(df["TOTAL_LATAS_FALTANTES"])
    numeric_loss = pd.to_numeric(raw_loss, errors="coerce")
    invalid_loss = int((raw_loss.notna() & numeric_loss.isna()).sum())
    negative_loss = int(numeric_loss.lt(0).fillna(False).sum())
    df["_INVALID_LOSS"] = raw_loss.notna() & numeric_loss.isna()
    df["_NEGATIVE_LOSS"] = numeric_loss.lt(0).fillna(False)
    df["TOTAL_LATAS_FALTANTES"] = numeric_loss.fillna(0).clip(lower=0)
    df["ENTREGA_COM_PERDA"] = (
        df["TOTAL_LATAS_FALTANTES"].gt(0).astype("int8")
    )

    text_columns = [
        "INSPECTION_ID",
        "INSPECTION_NAME",
        "TEMPLATE_NAME",
        "FIRSTNAME",
        "LASTNAME",
        "EMAIL",
        "WEBLINK",
    ]
    for column in text_columns:
        df[column] = _clean_text(df[column])

    analysis_columns = [
        "DESTINO_CLIENTE",
        "CLIENTE_GRUPO",
        "TRANSPORTADORA",
        "CAMINHAO_OU_PLACA",
        "ROTA",
    ]
    for column in analysis_columns:
        df[f"_MISSING_{column}"] = df[column].isna() | (
            df[column].astype("string").str.strip() == ""
        )
        df[column] = _clean_text(df[column], uppercase=True).fillna(
            MISSING_VALUE
        )

    route_invalid = df["ROTA"].isin(INVALID_ROUTE_VALUES) | df["ROTA"].eq(
        MISSING_VALUE
    )
    derived_routes = df["INSPECTION_NAME"].apply(
        _derive_route_from_inspection_name
    )
    df["_ROTA_ORIGINAL"] = df["ROTA"]
    df["_ROTA_DERIVADA"] = route_invalid & derived_routes.notna()
    df["ROTA"] = df["ROTA"].mask(df["_ROTA_DERIVADA"], derived_routes)

    first_name = df["FIRSTNAME"].fillna("")
    last_name = df["LASTNAME"].fillna("")
    df["USUARIO"] = (
        (first_name + " " + last_name)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    df["USUARIO"] = df["USUARIO"].mask(
        df["USUARIO"].eq(""), df["EMAIL"]
    )
    df["USUARIO"] = df["USUARIO"].fillna(MISSING_VALUE)
    df["TEMPLATE_NAME"] = df["TEMPLATE_NAME"].fillna(MISSING_VALUE)

    df["ANO_MES"] = df["DATA_INSPECAO"].dt.to_period("M").astype("string")
    df["ANO_MES"] = df["ANO_MES"].fillna("SEM DATA")

    positive_loss = df.loc[
        df["TOTAL_LATAS_FALTANTES"].gt(0), "TOTAL_LATAS_FALTANTES"
    ]
    outlier_threshold = (
        float(df["TOTAL_LATAS_FALTANTES"].quantile(0.99))
        if not df.empty
        else 0.0
    )
    df["_OUTLIER"] = (
        df["TOTAL_LATAS_FALTANTES"].gt(outlier_threshold)
        if outlier_threshold > 0
        else False
    )

    df = (
        df.sort_values("DATA_INSPECAO", ascending=False, na_position="last")
        .drop_duplicates("INSPECTION_ID", keep="first")
        .reset_index(drop=True)
    )

    quality = {
        "source_rows": source_rows,
        "analysis_rows": len(df),
        "duplicate_rows": duplicate_rows,
        "invalid_dates": invalid_dates,
        "invalid_loss": invalid_loss,
        "negative_loss": negative_loss,
        "outlier_threshold": outlier_threshold,
        "outlier_rows": int(df["_OUTLIER"].sum()),
        "positive_loss_rows": int(positive_loss.size),
        "missing_columns": missing_columns,
    }
    return df, quality


def calculate_onsite_kpis(df):
    total_deliveries = int(df["INSPECTION_ID"].nunique())
    loss_deliveries = int(
        df.loc[
            df["TOTAL_LATAS_FALTANTES"].gt(0), "INSPECTION_ID"
        ].nunique()
    )
    total_loss = float(df["TOTAL_LATAS_FALTANTES"].sum())
    return {
        "total_deliveries": total_deliveries,
        "loss_deliveries": loss_deliveries,
        "loss_rate": (
            loss_deliveries / total_deliveries * 100
            if total_deliveries
            else 0.0
        ),
        "total_loss": total_loss,
        "average_per_delivery": (
            total_loss / total_deliveries if total_deliveries else 0.0
        ),
        "average_per_loss": (
            total_loss / loss_deliveries if loss_deliveries else 0.0
        ),
    }


def aggregate_onsite_dimension(df, dimension):
    if df.empty or dimension not in df.columns:
        return pd.DataFrame()
    result = (
        df.groupby(dimension, dropna=False, as_index=False)
        .agg(
            ENTREGAS=("INSPECTION_ID", "nunique"),
            ENTREGAS_COM_PERDA=("ENTREGA_COM_PERDA", "sum"),
            LATAS_FALTANTES=("TOTAL_LATAS_FALTANTES", "sum"),
            ULTIMA_INSPECAO=("DATA_INSPECAO", "max"),
        )
    )
    result["TAXA_PERDA"] = (
        result["ENTREGAS_COM_PERDA"]
        .div(result["ENTREGAS"].where(result["ENTREGAS"].ne(0)))
        .fillna(0)
        * 100
    )
    result["MEDIA_POR_PERDA"] = (
        result["LATAS_FALTANTES"]
        .div(
            result["ENTREGAS_COM_PERDA"].where(
                result["ENTREGAS_COM_PERDA"].ne(0)
            )
        )
        .fillna(0)
    )
    return result


def aggregate_onsite_month(df):
    result = aggregate_onsite_dimension(df, "ANO_MES")
    if result.empty:
        return result
    return result[result["ANO_MES"] != "SEM DATA"].sort_values("ANO_MES")


def aggregate_platform_usage(df, dimensions):
    if isinstance(dimensions, str):
        dimensions = [dimensions]
    dimensions = list(dimensions)
    if df.empty or any(column not in df.columns for column in dimensions):
        return pd.DataFrame()

    usage = (
        df.groupby(dimensions, dropna=False, as_index=False)
        .agg(
            INSPECOES=("INSPECTION_ID", "nunique"),
            USUARIOS=("USUARIO", "nunique"),
            DESTINOS=("DESTINO_CLIENTE", "nunique"),
            TEMPLATES=("TEMPLATE_NAME", "nunique"),
            MESES_ATIVOS=("ANO_MES", "nunique"),
            PRIMEIRA_INSPECAO=("DATA_INSPECAO", "min"),
            ULTIMA_INSPECAO=("DATA_INSPECAO", "max"),
        )
        .sort_values("INSPECOES", ascending=False)
    )

    reference_date = df["DATA_INSPECAO"].max()
    if pd.notna(reference_date):
        usage["DIAS_SEM_INSPECAO"] = (
            reference_date.normalize()
            - usage["ULTIMA_INSPECAO"].dt.normalize()
        ).dt.days
    else:
        usage["DIAS_SEM_INSPECAO"] = pd.NA

    usage["STATUS_USO"] = pd.cut(
        usage["DIAS_SEM_INSPECAO"],
        bins=[-1, 7, 30, float("inf")],
        labels=["Até 7 dias", "8 a 30 dias", "Mais de 30 dias"],
    ).astype("string")
    usage["STATUS_USO"] = usage["STATUS_USO"].fillna("Sem data válida")
    return usage


def _fmt_int(value):
    return f"{value:,.0f}".replace(",", ".")


def _fmt_decimal(value):
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _chart_description(text):
    st.caption(f"Este gráfico responde: {text}")


def _padded_axis_range(values, padding=0.18, floor_zero=True):
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None

    minimum = float(numeric.min())
    maximum = float(numeric.max())
    if floor_zero:
        return [0, maximum * (1 + padding) if maximum > 0 else 1]

    span = max(maximum - minimum, abs(maximum) * 0.05, 1)
    return [
        max(0, minimum - span * padding),
        maximum + span * padding * 1.8,
    ]


def _add_line_value_annotations(figure, x_values, y_values, formatter, color):
    numeric = pd.to_numeric(y_values, errors="coerce")
    valid_values = numeric.dropna()
    span = (
        float(valid_values.max() - valid_values.min())
        if not valid_values.empty
        else 0
    )

    for index, (x_value, y_value) in enumerate(zip(x_values, numeric)):
        if pd.isna(y_value):
            continue

        previous_value = (
            numeric.iloc[index - 1] if index > 0 else pd.NA
        )
        next_value = (
            numeric.iloc[index + 1] if index + 1 < len(numeric) else pd.NA
        )
        close_to_neighbor = any(
            pd.notna(value) and span and abs(float(y_value) - float(value)) < span * 0.04
            for value in (previous_value, next_value)
        )
        yshift = 26 if close_to_neighbor and index % 2 == 0 else 18

        figure.add_annotation(
            x=x_value,
            y=float(y_value),
            xref="x",
            yref="y2",
            text=f"<b>{formatter(float(y_value))}</b>",
            showarrow=False,
            yshift=yshift,
            font={"color": color, "size": 12},
            bgcolor="rgba(255,255,255,0.82)",
            borderpad=1,
        )


def _render_filters(df, quality):
    st.subheader("Filtros globais")
    min_date = df["DATA_INSPECAO"].min()
    max_date = df["DATA_INSPECAO"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        selected_dates = None
        st.warning("A base não possui datas válidas para o filtro de período.")
    else:
        selected_dates = st.date_input(
            "Período da inspeção",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date(),
            key="onsite_period",
        )

    selections = {}
    first_row = st.columns(3)
    for index, (column, label) in enumerate(FILTER_COLUMNS[:3]):
        with first_row[index]:
            selections[column] = st.multiselect(
                label,
                options=sorted(df[column].dropna().astype(str).unique()),
                key=f"onsite_filter_{column}",
                placeholder="Todos",
            )

    with st.expander(
        "Mais filtros: caminhão, rota, usuário, template e severidade",
        expanded=False,
    ):
        second_row = st.columns(2)
        for index, (column, label) in enumerate(FILTER_COLUMNS[3:]):
            with second_row[index % 2]:
                options = df[column].dropna().astype(str).unique()
                if column == "SEVERIDADE_AMASSADAS":
                    options = [
                        value for value in SEVERITY_ORDER if value in options
                    ]
                else:
                    options = sorted(options)
                selections[column] = st.multiselect(
                    label,
                    options=options,
                    key=f"onsite_filter_{column}",
                    placeholder="Todos",
                )

    exclude_outliers = st.toggle(
        (
            "Excluir outliers das análises "
            f"(acima do P99: {_fmt_int(quality['outlier_threshold'])} latas)"
        ),
        value=False,
        key="onsite_exclude_outliers",
        disabled=quality["outlier_rows"] == 0,
        help=(
            "O padrão mantém todos os registros. Ative somente para analisar "
            "a tendência operacional sem os eventos extremos."
        ),
    )

    filtered = df.copy()
    if selected_dates:
        if isinstance(selected_dates, (tuple, list)):
            start_date = selected_dates[0]
            end_date = (
                selected_dates[1]
                if len(selected_dates) > 1
                else selected_dates[0]
            )
        else:
            start_date = end_date = selected_dates
        dates = filtered["DATA_INSPECAO"].dt.date
        filtered = filtered[
            dates.between(start_date, end_date, inclusive="both")
        ]

    for column, selected_values in selections.items():
        if selected_values:
            filtered = filtered[filtered[column].isin(selected_values)]

    if exclude_outliers:
        filtered = filtered[~filtered["_OUTLIER"]]

    st.caption(
        f"{_fmt_int(len(filtered))} de {_fmt_int(len(df))} inspeções "
        "permanecem após os filtros."
    )
    return filtered


def _render_kpis(df):
    kpis = calculate_onsite_kpis(df)
    row_one = st.columns(3)
    row_two = st.columns(3)
    row_one[0].metric(
        "Total de entregas",
        _fmt_int(kpis["total_deliveries"]),
        help="Contagem distinta de INSPECTION_ID.",
    )
    row_one[1].metric(
        "Entregas com perda",
        _fmt_int(kpis["loss_deliveries"]),
        help="Entregas com pelo menos uma lata faltante.",
    )
    row_one[2].metric(
        "% de entregas com perda",
        f"{_fmt_decimal(kpis['loss_rate'])}%",
        help="Entregas com perda divididas pelo total de entregas.",
    )
    row_two[0].metric(
        "Total de latas faltantes",
        _fmt_int(kpis["total_loss"]),
    )
    row_two[1].metric(
        "Média por entrega",
        _fmt_decimal(kpis["average_per_delivery"]),
        help="Total de latas faltantes dividido por todas as entregas.",
    )
    row_two[2].metric(
        "Média por entrega com perda",
        _fmt_decimal(kpis["average_per_loss"]),
        help="Total de latas faltantes dividido apenas pelas entregas com perda.",
    )


def _monthly_impact_chart(monthly):
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=monthly["ANO_MES"],
            y=monthly["LATAS_FALTANTES"],
            name="Latas faltantes",
            marker_color="#0B5CAD",
            text=monthly["LATAS_FALTANTES"],
            texttemplate="<b>%{text:,.0f}</b>",
            textposition="inside",
            insidetextanchor="end",
            textfont={"color": "white", "size": 12},
            cliponaxis=False,
            customdata=monthly[["ENTREGAS", "ENTREGAS_COM_PERDA"]],
            hovertemplate=(
                "<b>%{x}</b><br>Latas faltantes: %{y:,.0f}<br>"
                "Total de entregas: %{customdata[0]:,.0f}<br>"
                "Entregas com perda: %{customdata[1]:,.0f}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=monthly["ANO_MES"],
            y=monthly["MEDIA_POR_PERDA"],
            name="Média por entrega com perda",
            mode="lines+markers",
            line={"color": "#E87722", "width": 3},
            hovertemplate=(
                "<b>%{x}</b><br>Média por ocorrência: "
                "%{y:,.2f} latas<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    figure.update_yaxes(title_text="Latas faltantes", secondary_y=False)
    figure.update_yaxes(
        title_text="Média por entrega com perda",
        range=_padded_axis_range(monthly["MEDIA_POR_PERDA"]),
        secondary_y=True,
    )
    _add_line_value_annotations(
        figure,
        monthly["ANO_MES"],
        monthly["MEDIA_POR_PERDA"],
        lambda value: f"{value:,.1f}",
        "#E87722",
    )
    figure.update_layout(
        title="Impacto das perdas por mês",
        legend={"orientation": "h", "y": 1.12},
        margin={"l": 20, "r": 20, "t": 105, "b": 20},
        hovermode="x unified",
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return figure


def _monthly_incidence_chart(monthly):
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=monthly["ANO_MES"],
            y=monthly["ENTREGAS_COM_PERDA"],
            name="Entregas com perda",
            marker_color="#2E7D32",
            text=monthly["ENTREGAS_COM_PERDA"],
            texttemplate="<b>%{text:,.0f}</b>",
            textposition="inside",
            insidetextanchor="end",
            textfont={"color": "white", "size": 12},
            cliponaxis=False,
            customdata=monthly[["ENTREGAS"]],
            hovertemplate=(
                "<b>%{x}</b><br>Entregas com perda: %{y:,.0f}<br>"
                "Total de entregas: %{customdata[0]:,.0f}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=monthly["ANO_MES"],
            y=monthly["TAXA_PERDA"],
            name="% de entregas com perda",
            mode="lines+markers",
            line={"color": "#C62828", "width": 3},
            hovertemplate=(
                "<b>%{x}</b><br>Incidência: %{y:.2f}%<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    figure.update_yaxes(title_text="Entregas com perda", secondary_y=False)
    figure.update_yaxes(
        title_text="% das entregas", ticksuffix="%", secondary_y=True
    )
    figure.update_yaxes(
        range=_padded_axis_range(
            monthly["TAXA_PERDA"],
            padding=0.16,
            floor_zero=False,
        ),
        secondary_y=True,
    )
    _add_line_value_annotations(
        figure,
        monthly["ANO_MES"],
        monthly["TAXA_PERDA"],
        lambda value: f"{value:.1f}%",
        "#C62828",
    )
    figure.update_layout(
        title="Incidência de perdas nas entregas",
        legend={"orientation": "h", "y": 1.12},
        margin={"l": 20, "r": 20, "t": 105, "b": 20},
        hovermode="x unified",
        uniformtext={"minsize": 10, "mode": "show"},
    )
    return figure


def _ranking_chart(data, dimension, metric, title, color):
    ranking = data.sort_values(metric, ascending=False).head(15)
    ranking = ranking.sort_values(metric)
    figure = px.bar(
        ranking,
        x=metric,
        y=dimension,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=[
            "ENTREGAS",
            "ENTREGAS_COM_PERDA",
            "TAXA_PERDA",
            "MEDIA_POR_PERDA",
        ],
    )
    if metric == "TAXA_PERDA":
        figure.update_xaxes(ticksuffix="%")
        value_label = "Taxa de perda"
        value_format = ".2f"
        suffix = "%"
        visible_labels = ranking[metric].map(
            lambda value: f"{value:.1f}%"
        )
    else:
        value_label = "Latas faltantes"
        value_format = ",.0f"
        suffix = ""
        visible_labels = ranking[metric].map(
            lambda value: f"{value:,.0f}"
        )
    figure.update_traces(
        text=visible_labels,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            f"<b>%{{y}}</b><br>{value_label}: "
            f"%{{x:{value_format}}}{suffix}<br>"
            "Total de entregas: %{customdata[0]:,.0f}<br>"
            "Entregas com perda: %{customdata[1]:,.0f}<br>"
            "Taxa: %{customdata[2]:.2f}%<br>"
            "Média por perda: %{customdata[3]:,.2f}<extra></extra>"
        )
    )
    figure.update_layout(
        height=max(420, len(ranking) * 30),
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        yaxis_title=None,
        xaxis_title=value_label,
        uniformtext={"minsize": 10, "mode": "hide"},
    )
    return figure


def _render_overview(df):
    monthly = aggregate_onsite_month(df)
    if monthly.empty:
        st.info("Não existem dados mensais para os filtros selecionados.")
        return
    st.caption(
        "Este gráfico mostra: o volume caiu por melhoria real ou apenas por "
        "menor quantidade de entregas!"
    )
    st.plotly_chart(_monthly_impact_chart(monthly), width="stretch")
    st.caption(
        "Este gráfico mostra: quantas entregas tiveram perda e qual foi a "
        "incidência sobre o total!"
    )
    st.plotly_chart(_monthly_incidence_chart(monthly), width="stretch")
    st.dataframe(
        monthly[
            [
                "ANO_MES",
                "ENTREGAS",
                "ENTREGAS_COM_PERDA",
                "TAXA_PERDA",
                "LATAS_FALTANTES",
                "MEDIA_POR_PERDA",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "ANO_MES": "Mês",
            "ENTREGAS": "Entregas",
            "ENTREGAS_COM_PERDA": "Entregas com perda",
            "TAXA_PERDA": st.column_config.NumberColumn(
                "Taxa de perda", format="%.2f%%"
            ),
            "LATAS_FALTANTES": st.column_config.NumberColumn(
                "Latas faltantes", format="%.0f"
            ),
            "MEDIA_POR_PERDA": st.column_config.NumberColumn(
                "Média por perda", format="%.2f"
            ),
        },
    )


def _render_clients(df):
    clients = aggregate_onsite_dimension(df, "DESTINO_CLIENTE")
    if clients.empty:
        st.info("Não existem clientes para os filtros selecionados.")
        return
    min_deliveries = st.number_input(
        "Mínimo de entregas para o ranking proporcional",
        min_value=1,
        value=10,
        step=1,
        key="onsite_client_min_deliveries",
    )
    left, right = st.columns(2)
    with left:
        st.caption(
            "Quais destinos puxam o volume total e de quantas entregas ele veio!"
        )
        st.plotly_chart(
            _ranking_chart(
                clients,
                "DESTINO_CLIENTE",
                "LATAS_FALTANTES",
                "Top destinos por latas faltantes",
                "#0B5CAD",
            ),
            width="stretch",
        )
    with right:
        proportional = clients[clients["ENTREGAS"] >= min_deliveries]
        st.caption(
            "Quais destinos têm maior incidência, evitando comparar amostras "
            "muito pequenas!"
        )
        st.plotly_chart(
            _ranking_chart(
                proportional,
                "DESTINO_CLIENTE",
                "TAXA_PERDA",
                "Top destinos por incidência",
                "#C62828",
            ),
            width="stretch",
        )
    st.dataframe(
        clients.sort_values("LATAS_FALTANTES", ascending=False),
        hide_index=True,
        width="stretch",
        column_config={
            "TAXA_PERDA": st.column_config.NumberColumn(format="%.2f%%"),
            "LATAS_FALTANTES": st.column_config.NumberColumn(format="%.0f"),
            "MEDIA_POR_PERDA": st.column_config.NumberColumn(format="%.2f"),
            "ULTIMA_INSPECAO": st.column_config.DatetimeColumn(
                format="DD/MM/YYYY HH:mm"
            ),
        },
    )


def _render_carriers(df):
    carriers = aggregate_onsite_dimension(df, "TRANSPORTADORA")
    if carriers.empty:
        st.info("Não existem transportadoras para os filtros selecionados.")
        return
    st.caption(
        "Este gráfico mostra: a transportadora concentra perda por volume "
        "operado ou por incidência proporcional!"
    )
    st.plotly_chart(
        _ranking_chart(
            carriers,
            "TRANSPORTADORA",
            "LATAS_FALTANTES",
            "Transportadoras por latas faltantes",
            "#6A1B9A",
        ),
        width="stretch",
    )

    top_carriers = (
        carriers.sort_values("LATAS_FALTANTES", ascending=False)
        .head(12)["TRANSPORTADORA"]
        .tolist()
    )
    heatmap_source = df[df["TRANSPORTADORA"].isin(top_carriers)]
    matrix = heatmap_source.pivot_table(
        index="CLIENTE_GRUPO",
        columns="TRANSPORTADORA",
        values="TOTAL_LATAS_FALTANTES",
        aggfunc="sum",
        fill_value=0,
    )
    if not matrix.empty:
        heatmap_labels = matrix.map(
            lambda value: f"{value:,.0f}" if value > 0 else ""
        )
        heatmap = go.Figure(
            go.Heatmap(
                z=matrix.values,
                x=matrix.columns,
                y=matrix.index,
                text=heatmap_labels.values,
                texttemplate="%{text}",
                textfont={"size": 11},
                colorscale="Blues",
                colorbar={"title": "Latas"},
                hovertemplate=(
                    "Grupo: %{y}<br>Transportadora: %{x}<br>"
                    "Latas: %{z:,.0f}<extra></extra>"
                ),
            )
        )
        heatmap.update_layout(
            title="Cliente × transportadora",
            height=430,
            margin={"l": 20, "r": 20, "t": 60, "b": 100},
        )
        _chart_description(
            "quais combinações de grupo de cliente e transportadora concentram "
            "mais latas faltantes!"
        )
        st.plotly_chart(heatmap, width="stretch")
    st.dataframe(
        carriers.sort_values("LATAS_FALTANTES", ascending=False),
        hide_index=True,
        width="stretch",
        column_config={
            "TAXA_PERDA": st.column_config.NumberColumn(format="%.2f%%"),
            "LATAS_FALTANTES": st.column_config.NumberColumn(format="%.0f"),
            "MEDIA_POR_PERDA": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def _render_trucks_routes(df):
    trucks = aggregate_onsite_dimension(df, "CAMINHAO_OU_PLACA")
    routes = aggregate_onsite_dimension(df, "ROTA")
    critical_routes = routes[
        (routes["LATAS_FALTANTES"] > 0) & (routes["ROTA"] != MISSING_VALUE)
    ].copy()
    left, right = st.columns(2)
    with left:
        st.caption(
            "Qual caminhão/placa concentra perdas e isso ocorreu em quantas "
            "entregas!"
        )
        st.plotly_chart(
            _ranking_chart(
                trucks,
                "CAMINHAO_OU_PLACA",
                "LATAS_FALTANTES",
                "Top caminhões/placas",
                "#E87722",
            ),
            width="stretch",
        )
    with right:
        st.caption(
            "Qual rota concentra perdas e qual é a taxa sobre o total da rota!"
        )
        if critical_routes.empty:
            st.info(
                "Não há rotas válidas com latas faltantes para os filtros "
                "selecionados. Verifique se a base contém rota ou se ela pode "
                "ser inferida pelo nome da inspeção."
            )
        else:
            st.plotly_chart(
                _ranking_chart(
                    critical_routes,
                    "ROTA",
                    "LATAS_FALTANTES",
                    "Rotas críticas",
                    "#00838F",
                ),
                width="stretch",
            )

    recurrence = trucks[
        (trucks["LATAS_FALTANTES"] > 0)
        & (trucks["CAMINHAO_OU_PLACA"] != MISSING_VALUE)
    ].copy()
    if not recurrence.empty:
        recurrence["VALOR_VISIVEL"] = ""
        critical_indices = recurrence.nlargest(
            5, "LATAS_FALTANTES"
        ).index
        recurrence.loc[critical_indices, "VALOR_VISIVEL"] = recurrence.loc[
            critical_indices, "LATAS_FALTANTES"
        ].map(lambda value: f"{value:,.0f} latas")
        scatter = px.scatter(
            recurrence,
            x="ENTREGAS",
            y="LATAS_FALTANTES",
            size="ENTREGAS_COM_PERDA",
            color="TAXA_PERDA",
            text="VALOR_VISIVEL",
            hover_name="CAMINHAO_OU_PLACA",
            color_continuous_scale="RdYlBu_r",
            labels={
                "ENTREGAS": "Total de entregas",
                "LATAS_FALTANTES": "Latas faltantes",
                "TAXA_PERDA": "Taxa de perda (%)",
            },
            title="Recorrência versus impacto por caminhão/placa",
        )
        scatter.update_traces(
            textposition="top center",
            textfont={"size": 11},
        )
        scatter.update_layout(height=500)
        _chart_description(
            "quais caminhões/placas unem recorrência de entregas com alto "
            "impacto de latas faltantes!"
        )
        st.plotly_chart(scatter, width="stretch")


def _usage_chart(data, label_column, title, color, top_n=None):
    ranking = data.sort_values("INSPECOES", ascending=False)
    if top_n:
        ranking = ranking.head(top_n)
    ranking = ranking.sort_values("INSPECOES")
    figure = px.bar(
        ranking,
        x="INSPECOES",
        y=label_column,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=[
            "USUARIOS",
            "DESTINOS",
            "TEMPLATES",
            "MESES_ATIVOS",
            "ULTIMA_INSPECAO",
            "DIAS_SEM_INSPECAO",
        ],
    )
    figure.update_traces(
        text=ranking["INSPECOES"].map(lambda value: f"{value:,.0f}"),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>Inspeções: %{x:,.0f}<br>"
            "Usuários ativos: %{customdata[0]:,.0f}<br>"
            "Destinos atendidos: %{customdata[1]:,.0f}<br>"
            "Templates usados: %{customdata[2]:,.0f}<br>"
            "Meses com registro: %{customdata[3]:,.0f}<br>"
            "Última inspeção: %{customdata[4]|%d/%m/%Y}<br>"
            "Dias sem inspeção: %{customdata[5]:,.0f}<extra></extra>"
        ),
    )
    figure.update_layout(
        height=max(430, len(ranking) * 31),
        yaxis_title=None,
        xaxis_title="Inspeções",
        uniformtext={"minsize": 10, "mode": "hide"},
        margin={"l": 20, "r": 55, "t": 60, "b": 20},
    )
    return figure


def _usage_table(data, columns):
    st.dataframe(
        data[columns],
        hide_index=True,
        width="stretch",
        column_config={
            "PRIMEIRA_INSPECAO": st.column_config.DatetimeColumn(
                "Primeira inspeção", format="DD/MM/YYYY HH:mm"
            ),
            "ULTIMA_INSPECAO": st.column_config.DatetimeColumn(
                "Última inspeção", format="DD/MM/YYYY HH:mm"
            ),
            "DIAS_SEM_INSPECAO": st.column_config.NumberColumn(
                "Dias sem inspeção", format="%d"
            ),
            "STATUS_USO": st.column_config.TextColumn("Recência do uso"),
        },
    )


def _render_usage(df):
    if df.empty:
        st.info("Não existem registros para analisar o uso da plataforma.")
        return

    total_inspections = int(df["INSPECTION_ID"].nunique())
    active_users = int(df["USUARIO"].nunique())
    client_groups = int(
        df.loc[
            df["CLIENTE_GRUPO"].ne(MISSING_VALUE), "CLIENTE_GRUPO"
        ].nunique()
    )
    destinations = int(
        df.loc[
            df["DESTINO_CLIENTE"].ne(MISSING_VALUE), "DESTINO_CLIENTE"
        ].nunique()
    )
    cards = st.columns(4)
    cards[0].metric("Inspeções no período", _fmt_int(total_inspections))
    cards[1].metric("Usuários ativos", _fmt_int(active_users))
    cards[2].metric("Grupos atendidos", _fmt_int(client_groups))
    cards[3].metric("Destinos atendidos", _fmt_int(destinations))

    st.caption(
        "A recência usa como referência a data mais recente dentro do período "
        "filtrado, permitindo analisar períodos históricos sem comparar com hoje."
    )

    user_tab, group_tab, destination_tab = st.tabs(
        ["Por usuário", "Por grupo do cliente", "Por destino/cliente"]
    )

    with user_tab:
        usage = aggregate_platform_usage(df, "USUARIO")
        emails = df.groupby("USUARIO", as_index=False)["EMAIL"].first()
        usage = usage.merge(emails, on="USUARIO", how="left")
        st.caption(
            "Quem está registrando, quantos destinos atende e há quanto tempo "
            "não cria uma inspeção!"
        )
        st.plotly_chart(
            _usage_chart(
                usage,
                "USUARIO",
                "Uso da plataforma por usuário",
                "#1565C0",
                top_n=20,
            ),
            width="stretch",
        )
        _usage_table(
            usage,
            [
                "USUARIO",
                "EMAIL",
                "INSPECOES",
                "DESTINOS",
                "TEMPLATES",
                "MESES_ATIVOS",
                "ULTIMA_INSPECAO",
                "DIAS_SEM_INSPECAO",
                "STATUS_USO",
            ],
        )

    with group_tab:
        group_usage = aggregate_platform_usage(df, "CLIENTE_GRUPO")
        st.caption(
            "Quais grupos recebem mais inspeções, quantos usuários registram "
            "neles e quais estão há mais tempo sem cobertura!"
        )
        st.plotly_chart(
            _usage_chart(
                group_usage,
                "CLIENTE_GRUPO",
                "Uso da plataforma por grupo do cliente",
                "#00838F",
            ),
            width="stretch",
        )
        _usage_table(
            group_usage,
            [
                "CLIENTE_GRUPO",
                "INSPECOES",
                "USUARIOS",
                "DESTINOS",
                "TEMPLATES",
                "MESES_ATIVOS",
                "PRIMEIRA_INSPECAO",
                "ULTIMA_INSPECAO",
                "DIAS_SEM_INSPECAO",
                "STATUS_USO",
            ],
        )

    with destination_tab:
        destination_usage = aggregate_platform_usage(
            df, ["CLIENTE_GRUPO", "DESTINO_CLIENTE"]
        )
        destination_usage["DESTINO_VISUAL"] = (
            destination_usage["CLIENTE_GRUPO"].astype(str)
            + " · "
            + destination_usage["DESTINO_CLIENTE"].astype(str)
        )
        top_n = st.selectbox(
            "Quantidade de destinos no gráfico",
            options=[10, 20, 30, 50],
            index=1,
            key="onsite_usage_destination_top_n",
        )
        st.caption(
            "Quais destinos concentram o uso e quais clientes precisam de "
            "atenção por falta de inspeções recentes!"
        )
        st.plotly_chart(
            _usage_chart(
                destination_usage,
                "DESTINO_VISUAL",
                "Uso da plataforma por destino/cliente",
                "#6A1B9A",
                top_n=top_n,
            ),
            width="stretch",
        )

        stale_destinations = destination_usage[
            destination_usage["DESTINO_CLIENTE"].ne(MISSING_VALUE)
        ].sort_values(
            ["DIAS_SEM_INSPECAO", "INSPECOES"],
            ascending=[False, False],
            na_position="last",
        )
        st.subheader("Destinos há mais tempo sem inspeção")
        _usage_table(
            stale_destinations,
            [
                "CLIENTE_GRUPO",
                "DESTINO_CLIENTE",
                "INSPECOES",
                "USUARIOS",
                "TEMPLATES",
                "MESES_ATIVOS",
                "PRIMEIRA_INSPECAO",
                "ULTIMA_INSPECAO",
                "DIAS_SEM_INSPECAO",
                "STATUS_USO",
            ],
        )


def _render_details(df):
    columns = [
        "DATA_INSPECAO",
        "INSPECTION_ID",
        "INSPECTION_NAME",
        "CLIENTE_GRUPO",
        "DESTINO_CLIENTE",
        "TRANSPORTADORA",
        "CAMINHAO_OU_PLACA",
        "ROTA",
        "TOTAL_LATAS_FALTANTES",
        "ENTREGA_COM_PERDA",
        "USUARIO",
        "EMAIL",
        "TEMPLATE_NAME",
        "WEBLINK",
    ]
    detail = df[columns].sort_values(
        ["TOTAL_LATAS_FALTANTES", "DATA_INSPECAO"],
        ascending=[False, False],
    )
    st.dataframe(
        detail,
        hide_index=True,
        width="stretch",
        column_config={
            "DATA_INSPECAO": st.column_config.DatetimeColumn(
                "Data", format="DD/MM/YYYY HH:mm"
            ),
            "TOTAL_LATAS_FALTANTES": st.column_config.NumberColumn(
                "Latas faltantes", format="%.0f"
            ),
            "ENTREGA_COM_PERDA": st.column_config.CheckboxColumn(
                "Entrega com perda"
            ),
            "WEBLINK": st.column_config.LinkColumn(
                "Abrir inspeção", display_text="Abrir"
            ),
        },
    )
    st.download_button(
        "Baixar dados filtrados em CSV",
        data=detail.to_csv(index=False).encode("utf-8-sig"),
        file_name="onsite_perdas_filtrado.csv",
        mime="text/csv",
        key="onsite_download_details",
    )


def _render_quality(df, quality):
    cards = st.columns(4)
    cards[0].metric("Linhas na origem", _fmt_int(quality["source_rows"]))
    cards[1].metric(
        "Inspeções únicas", _fmt_int(quality["analysis_rows"])
    )
    cards[2].metric(
        "Duplicidades removidas", _fmt_int(quality["duplicate_rows"])
    )
    cards[3].metric(
        "Outliers acima do P99", _fmt_int(quality["outlier_rows"])
    )

    fields = [
        ("DESTINO_CLIENTE", "Destino/cliente"),
        ("TRANSPORTADORA", "Transportadora"),
        ("CAMINHAO_OU_PLACA", "Caminhão/placa"),
        ("ROTA", "Rota"),
    ]
    completeness_rows = []
    for column, label in fields:
        missing_column = f"_MISSING_{column}"
        missing_count = (
            int(df[missing_column].sum())
            if missing_column in df.columns
            else len(df)
        )
        completeness_rows.append(
            {
                "Campo": label,
                "Preenchimento": (
                    (len(df) - missing_count) / len(df) * 100
                    if len(df)
                    else 0
                ),
                "Ausentes": missing_count,
                "Total": len(df),
            }
        )
    completeness = pd.DataFrame(completeness_rows)
    figure = px.bar(
        completeness,
        x="Preenchimento",
        y="Campo",
        orientation="h",
        range_x=[0, 100],
        text="Preenchimento",
        title="Completude dos campos-chave",
        color="Preenchimento",
        color_continuous_scale="RdYlGn",
        custom_data=["Ausentes", "Total"],
    )
    figure.update_traces(
        texttemplate="%{x:.1f}%",
        hovertemplate=(
            "<b>%{y}</b><br>Preenchimento: %{x:.2f}%<br>"
            "Ausentes: %{customdata[0]:,.0f}<br>"
            "Total: %{customdata[1]:,.0f}<extra></extra>"
        ),
    )
    figure.update_layout(height=390, coloraxis_showscale=False)
    _chart_description(
        "quais campos-chave estão mais completos ou mais frágeis para análise "
        "de perdas!"
    )
    st.plotly_chart(figure, width="stretch")

    issue_col1, issue_col2, issue_col3, issue_col4 = st.columns(4)
    issue_col1.metric("Datas inválidas", quality["invalid_dates"])
    issue_col2.metric("Latas inválidas", quality["invalid_loss"])
    issue_col3.metric("Latas negativas", quality["negative_loss"])
    outros = (
        int(df["CLIENTE_GRUPO"].eq("OUTROS").sum()) if not df.empty else 0
    )
    issue_col4.metric("Grupo OUTROS", _fmt_int(outros))

    if quality["missing_columns"]:
        st.warning(
            "Colunas ausentes no arquivo: "
            + ", ".join(quality["missing_columns"])
        )
    else:
        st.success("Todas as colunas esperadas estão presentes na base.")

    outliers = df[df["_OUTLIER"]].sort_values(
        "TOTAL_LATAS_FALTANTES", ascending=False
    )
    st.subheader("Inspeções para auditoria")
    st.caption(
        "Registros acima do percentil 99. Eles permanecem nos indicadores, "
        "a menos que o filtro de exclusão de outliers seja ativado."
    )
    if outliers.empty:
        st.info("Nenhum outlier nos filtros atuais.")
    else:
        st.dataframe(
            outliers[
                [
                    "DATA_INSPECAO",
                    "DESTINO_CLIENTE",
                    "TRANSPORTADORA",
                    "CAMINHAO_OU_PLACA",
                    "TOTAL_LATAS_FALTANTES",
                    "WEBLINK",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "DATA_INSPECAO": st.column_config.DatetimeColumn(
                    "Data", format="DD/MM/YYYY"
                ),
                "TOTAL_LATAS_FALTANTES": st.column_config.NumberColumn(
                    "Latas faltantes", format="%.0f"
                ),
                "WEBLINK": st.column_config.LinkColumn(
                    "Auditar", display_text="Abrir"
                ),
            },
        )


def render_onsite_dashboard():
    st.header("On-Site | Perdas Logísticas")
    st.caption(
        "Dashboard executivo das inspeções SafetyCulture exportadas do "
        "Snowflake. Todos os indicadores de perda exibem o universo de "
        "entregas usado como denominador."
    )

    default_path = find_default_onsite_path()
    default_damage_path = (
        find_default_damage_path() if _allow_local_data() else None
    )
    with st.expander("Fonte de dados", expanded=False):
        uploaded_file = st.file_uploader(
            "Carregar CSV consolidado gerado pelo SQL",
            type=["csv"],
            key="onsite_csv_upload",
            help=(
                "O aplicativo não carrega dados locais por padrão. Gere o CSV "
                "atualizado com o SQL consolidado e envie aqui para montar o "
                "painel On-Site."
            ),
        )
        uploaded_damage_file = st.file_uploader(
            "Fonte complementar legada de latas amassadas (opcional)",
            type=["csv"],
            key="onsite_damage_csv_upload",
            help=(
                "Use apenas se o CSV principal ainda não trouxer "
                "TOTAL_LATAS_AMASSADAS. Para a exportação consolidada nova, "
                "este upload não é necessário."
            ),
        )
        if _allow_local_data() and default_path is not None:
            st.caption(
                "Modo local de desenvolvimento ativo por ALLOW_LOCAL_DATA=true. "
                f"Fallback detectado: {default_path}"
            )
        if st.button("Limpar base On-Site carregada", key="onsite_clear_uploads"):
            st.session_state.pop(ONSITE_UPLOAD_STATE_KEY, None)
            st.session_state.pop(ONSITE_DAMAGE_UPLOAD_STATE_KEY, None)
            st.rerun()

    if uploaded_file is not None:
        st.session_state[ONSITE_UPLOAD_STATE_KEY] = {
            "name": uploaded_file.name,
            "contents": uploaded_file.getvalue(),
        }
    if uploaded_damage_file is not None:
        st.session_state[ONSITE_DAMAGE_UPLOAD_STATE_KEY] = {
            "name": uploaded_damage_file.name,
            "contents": uploaded_damage_file.getvalue(),
        }

    stored_upload = st.session_state.get(ONSITE_UPLOAD_STATE_KEY)
    stored_damage_upload = st.session_state.get(
        ONSITE_DAMAGE_UPLOAD_STATE_KEY
    )

    try:
        if stored_upload is not None:
            source_df = load_onsite_upload(stored_upload["contents"])
            source_name = stored_upload["name"]
        elif default_path is not None and default_path.exists():
            source_df = load_onsite_csv(
                str(default_path),
                default_path.stat().st_mtime_ns,
            )
            source_name = default_path.name
        else:
            st.info(
                "Carregue o CSV consolidado do On-Site para visualizar este "
                "painel. O app não procura arquivos locais de dados por padrão "
                "para evitar exposição de informações sensíveis."
            )
            st.caption(
                "O arquivo esperado é a exportação gerada pelo SQL consolidado, "
                "contendo INSPECTION_ID, DATA_INSPECAO, DESTINO_CLIENTE, "
                "TOTAL_LATAS_FALTANTES e, idealmente, TOTAL_LATAS_AMASSADAS."
            )
            return
    except Exception as error:
        st.error(f"Não foi possível ler o CSV: {error}")
        return

    missing_columns = validate_onsite_schema(source_df)
    missing_critical = sorted(CRITICAL_COLUMNS.intersection(missing_columns))
    if missing_critical:
        st.error(
            "A análise não pode ser calculada porque faltam as colunas: "
            + ", ".join(missing_critical)
        )
        st.info(
            "Colunas esperadas: " + ", ".join(EXPECTED_COLUMNS)
        )
        return
    if missing_columns:
        st.warning(
            "O arquivo será carregado com análise parcial. Colunas ausentes: "
            + ", ".join(missing_columns)
        )

    try:
        data, quality = prepare_onsite_data(source_df)
    except Exception as error:
        st.error(f"Não foi possível preparar a base On-Site: {error}")
        return

    damage_source = None
    damage_source_name = None
    try:
        if stored_damage_upload is not None:
            damage_source = load_onsite_upload(
                stored_damage_upload["contents"]
            )
            damage_source_name = stored_damage_upload["name"]
        elif default_damage_path is not None and default_damage_path.exists():
            damage_source = load_onsite_csv(
                str(default_damage_path),
                default_damage_path.stat().st_mtime_ns,
            )
            damage_source_name = default_damage_path.name
    except Exception as error:
        st.warning(
            f"A fonte de latas amassadas não pôde ser lida: {error}"
        )

    data, damage_context = enrich_with_damage(
        data,
        source_df=damage_source,
        source_name=damage_source_name,
    )

    st.caption(
        f"Fonte ativa: {source_name} · "
        f"{_fmt_int(quality['analysis_rows'])} inspeções únicas"
    )
    filtered = _render_filters(data, quality)
    if filtered.empty:
        st.warning("Nenhuma inspeção corresponde aos filtros selecionados.")
        return

    _render_kpis(filtered)
    (
        overview_tab,
        clients_tab,
        carriers_tab,
        trucks_tab,
        usage_tab,
        damage_tab,
        details_tab,
        quality_tab,
    ) = st.tabs(
        [
            "Visão Geral Executiva",
            "Cliente/Destino",
            "Transportadora",
            "Caminhão e Rota",
            "Uso da Plataforma",
            "Análise de Latas Amassadas",
            "Detalhamento",
            "Qualidade de Dados",
        ]
    )
    with overview_tab:
        _render_overview(filtered)
    with clients_tab:
        _render_clients(filtered)
    with carriers_tab:
        _render_carriers(filtered)
    with trucks_tab:
        _render_trucks_routes(filtered)
    with usage_tab:
        _render_usage(filtered)
    with damage_tab:
        render_damage_analysis(filtered, damage_context)
    with details_tab:
        _render_details(filtered)
    with quality_tab:
        _render_quality(filtered, quality)
