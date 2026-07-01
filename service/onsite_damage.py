import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


DAMAGE_FILE_PATTERN = "LT_AMASSADA_*.csv"
DAMAGE_REQUIRED_DETAIL_COLUMNS = {"INSPECTION_ID", "LABEL", "RESPONSE"}
DAMAGE_SUMMARY_COLUMNS = {
    "LABEL",
    "QTD_LINHAS",
    "QTD_INSPECOES",
    "EXEMPLO_MIN",
    "EXEMPLO_MAX",
}
FULL_EXPORT_SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "dados-onsite"
    / "SQL_Export_OnSite_Com_Amassadas.sql"
)

SEVERITY_ORDER = [
    "Não identificado",
    "Sem amassadas",
    "Ocorrência sem quantidade",
    "Baixa: 1 a 10",
    "Média: 11 a 50",
    "Alta: 51 a 200",
    "Crítica: acima de 200",
]

DETAIL_EXPORT_SQL = """SELECT
    ii.INSPECTION_ID,
    ii.LABEL,
    ii.RESPONSE
FROM DW_STAGING.SAFETY_CULTURE.INSPECTION_ITEMS ii
WHERE ii.RESPONSE IS NOT NULL
  AND (
       LOWER(ii.LABEL) LIKE '%lata%amass%'
    OR LOWER(ii.LABEL) LIKE '%latas avariadas%'
    OR LOWER(ii.LABEL) LIKE '%lata%danific%'
  )
ORDER BY ii.INSPECTION_ID, ii.LABEL;"""


def get_damage_export_sql():
    if FULL_EXPORT_SQL_PATH.exists():
        return FULL_EXPORT_SQL_PATH.read_text(encoding="utf-8")
    return DETAIL_EXPORT_SQL


def find_default_damage_path(directory=Path("dados-onsite")):
    candidates = list(Path(directory).glob(DAMAGE_FILE_PATTERN))
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )


def _normalized(value):
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().upper()


def classify_damage_label(label):
    text = _normalized(label)
    has_can = bool(re.search(r"\bLATA(?:S)?\b", text))
    has_damage = any(
        term in text
        for term in (
            "AMASS",
            "AVARI",
            "DANIFIC",
        )
    )
    relevant = has_can and has_damage
    explicit_logistics_units = (
        text.startswith("LATAS AVARIADAS") and "UNIDADE" in text
    )
    explicit_dented_quantity = (
        has_can
        and "AMASS" in text
        and any(term in text for term in ("QUANTA", "QUANTIDADE", "QTD"))
    )
    quantitative = explicit_logistics_units or explicit_dented_quantity

    if "TRANSPORTE" in text and quantitative:
        category = "TRANSPORTE"
    elif "DESCARGA" in text and quantitative:
        category = "DESCARGA"
    elif "MOVIMENTACAO EXTERNA" in text and quantitative:
        category = "MOVIMENTACAO EXTERNA"
    elif quantitative:
        category = "GERAL"
    else:
        category = "CONTEXTO/QUALITATIVO"

    return {
        "LABEL_RELEVANTE": relevant,
        "LABEL_QUANTITATIVO": quantitative,
        "CATEGORIA_LABEL": category,
    }


def profile_damage_labels(source_df):
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        return pd.DataFrame()
    source = source_df.copy()
    source.columns = [str(column).strip().upper() for column in source.columns]
    if "LABEL" not in source.columns:
        return pd.DataFrame()

    classifications = source["LABEL"].map(classify_damage_label)
    profile = pd.concat(
        [
            source.reset_index(drop=True),
            pd.DataFrame(classifications.tolist()),
        ],
        axis=1,
    )
    return profile[
        profile["LABEL_RELEVANTE"]
    ].sort_values(
        ["LABEL_QUANTITATIVO", "QTD_INSPECOES"]
        if "QTD_INSPECOES" in profile.columns
        else ["LABEL_QUANTITATIVO"],
        ascending=False,
    )


def _parse_numeric_response(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(float(value), 0.0)

    text = str(value).strip()
    match = re.search(r"-?\d[\d\s.,]*", text)
    if not match:
        return None
    token = re.sub(r"\s+", "", match.group(0))
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        decimals = len(token.rsplit(",", 1)[1])
        token = (
            token.replace(",", ".")
            if decimals <= 2
            else token.replace(",", "")
        )
    elif "." in token:
        decimals = len(token.rsplit(".", 1)[1])
        if decimals == 3:
            token = token.replace(".", "")
    try:
        return max(float(token), 0.0)
    except ValueError:
        return None


def parse_damage_response(value):
    numeric = _parse_numeric_response(value)
    if numeric is not None:
        return {
            "QUANTIDADE": numeric,
            "OCORRENCIA": numeric > 0,
            "QUANTIDADE_IDENTIFICADA": True,
            "RESPOSTA_NAO_NUMERICA": False,
        }

    text = _normalized(value)
    negative = (
        not text
        or text
        in {
            "NAO",
            "NO",
            "N/D",
            "NAO APLICAVEL",
            "SEM AVARIA",
            "SEM AMASSADAS",
            "OK",
            "APROVADO",
            "CONFORME",
        }
    )
    positive = (
        text in {"SIM", "YES", "REPROVADO", "NOK", "NAO OK", "N/OK"}
        or "NAO CONFORME" in text
    )
    return {
        "QUANTIDADE": 0.0 if negative else None,
        "OCORRENCIA": True if positive else False if negative else None,
        "QUANTIDADE_IDENTIFICADA": negative,
        "RESPOSTA_NAO_NUMERICA": bool(text) and not negative,
    }


def _prepare_detail_items(source_df):
    items = source_df.copy()
    items.columns = [str(column).strip().upper() for column in items.columns]
    items["INSPECTION_ID"] = (
        items["INSPECTION_ID"].astype("string").str.strip()
    )
    items["LABEL"] = items["LABEL"].astype("string").str.strip()
    classifications = items["LABEL"].map(classify_damage_label)
    items = pd.concat(
        [items.reset_index(drop=True), pd.DataFrame(classifications.tolist())],
        axis=1,
    )
    items = items[
        items["LABEL_RELEVANTE"] & items["LABEL_QUANTITATIVO"]
    ].copy()
    if items.empty:
        return items

    parsed = items["RESPONSE"].map(parse_damage_response)
    items = pd.concat(
        [items.reset_index(drop=True), pd.DataFrame(parsed.tolist())],
        axis=1,
    )
    return items


def aggregate_damage_items(source_df):
    items = _prepare_detail_items(source_df)
    if items.empty:
        return pd.DataFrame(), items

    records = []
    for inspection_id, group in items.groupby("INSPECTION_ID", dropna=False):
        specific = group[
            group["CATEGORIA_LABEL"].isin(
                ["TRANSPORTE", "DESCARGA", "MOVIMENTACAO EXTERNA"]
            )
        ]
        specific_numeric = specific[
            specific["QUANTIDADE_IDENTIFICADA"]
        ]["QUANTIDADE"]
        general_numeric = group[
            (group["CATEGORIA_LABEL"] == "GERAL")
            & group["QUANTIDADE_IDENTIFICADA"]
        ]["QUANTIDADE"]

        if not specific_numeric.empty:
            total = float(specific_numeric.fillna(0).sum())
            quantity_known = True
        elif not general_numeric.empty:
            total = float(general_numeric.fillna(0).sum())
            quantity_known = True
        else:
            total = None
            quantity_known = False

        occurrence = bool(group["OCORRENCIA"].fillna(False).any())
        if total is not None and total > 0:
            occurrence = True
        occurrence_without_quantity = occurrence and not quantity_known
        records.append(
            {
                "INSPECTION_ID": inspection_id,
                "TOTAL_LATAS_AMASSADAS": total,
                "AMASSADA_DADO_IDENTIFICADO": quantity_known,
                "AMASSADA_OCORRENCIA_SEM_QUANTIDADE": (
                    occurrence_without_quantity
                ),
                "ENTREGA_COM_AMASSADA": int(occurrence),
                "LABELS_AMASSADAS": " | ".join(
                    sorted(group["LABEL"].dropna().astype(str).unique())
                ),
            }
        )
    return pd.DataFrame(records), items


def _severity(row):
    if not row.get("AMASSADA_DADO_IDENTIFICADO", False):
        if row.get("AMASSADA_OCORRENCIA_SEM_QUANTIDADE", False):
            return "Ocorrência sem quantidade"
        return "Não identificado"
    value = row.get("TOTAL_LATAS_AMASSADAS")
    if pd.isna(value) or value <= 0:
        return "Sem amassadas"
    if value <= 10:
        return "Baixa: 1 a 10"
    if value <= 50:
        return "Média: 11 a 50"
    if value <= 200:
        return "Alta: 51 a 200"
    return "Crítica: acima de 200"


def enrich_with_damage(main_df, source_df=None, source_name=None):
    data = main_df.copy()
    context = {
        "source_name": source_name,
        "source_type": "none",
        "profile": pd.DataFrame(),
        "detail_items": pd.DataFrame(),
        "missing_detail_columns": sorted(DAMAGE_REQUIRED_DETAIL_COLUMNS),
        "non_numeric_samples": pd.DataFrame(),
    }

    if "TOTAL_LATAS_AMASSADAS" in data.columns:
        raw = data["TOTAL_LATAS_AMASSADAS"]
        numeric = pd.to_numeric(raw, errors="coerce")
        existing_identified = (
            pd.to_numeric(
                data["AMASSADA_DADO_IDENTIFICADO"], errors="coerce"
            )
            .fillna(0)
            .gt(0)
            if "AMASSADA_DADO_IDENTIFICADO" in data.columns
            else pd.Series(False, index=data.index)
        )
        existing_without_quantity = (
            pd.to_numeric(
                data["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"],
                errors="coerce",
            )
            .fillna(0)
            .gt(0)
            if "AMASSADA_OCORRENCIA_SEM_QUANTIDADE" in data.columns
            else pd.Series(False, index=data.index)
        )
        existing_occurrence = (
            pd.to_numeric(
                data["ENTREGA_COM_AMASSADA"], errors="coerce"
            )
            .fillna(0)
            .gt(0)
            if "ENTREGA_COM_AMASSADA" in data.columns
            else pd.Series(False, index=data.index)
        )
        data["TOTAL_LATAS_AMASSADAS"] = numeric.clip(lower=0)
        data["AMASSADA_DADO_IDENTIFICADO"] = (
            existing_identified | (raw.notna() & numeric.notna())
        )
        data["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"] = (
            existing_without_quantity
        )
        data["ENTREGA_COM_AMASSADA"] = (
            existing_occurrence
            | existing_without_quantity
            | numeric.gt(0)
        ).astype("int8")
        context["source_type"] = "enriched"

    if isinstance(source_df, pd.DataFrame) and not source_df.empty:
        source = source_df.copy()
        source.columns = [
            str(column).strip().upper() for column in source.columns
        ]
        context["profile"] = profile_damage_labels(source)
        columns = set(source.columns)
        if DAMAGE_REQUIRED_DETAIL_COLUMNS.issubset(columns):
            aggregated, detail_items = aggregate_damage_items(source)
            context["source_type"] = "detail"
            context["detail_items"] = detail_items
            context["missing_detail_columns"] = []
            if not detail_items.empty:
                context["non_numeric_samples"] = detail_items[
                    detail_items["RESPOSTA_NAO_NUMERICA"]
                ][
                    ["LABEL", "RESPONSE", "CATEGORIA_LABEL"]
                ].drop_duplicates().head(100)
            if not aggregated.empty:
                data = data.drop(
                    columns=[
                        "TOTAL_LATAS_AMASSADAS",
                        "AMASSADA_DADO_IDENTIFICADO",
                        "AMASSADA_OCORRENCIA_SEM_QUANTIDADE",
                        "ENTREGA_COM_AMASSADA",
                    ],
                    errors="ignore",
                ).merge(aggregated, on="INSPECTION_ID", how="left")
        elif DAMAGE_SUMMARY_COLUMNS.issubset(columns):
            if context["source_type"] == "none":
                context["source_type"] = "summary"
            context["missing_detail_columns"] = sorted(
                DAMAGE_REQUIRED_DETAIL_COLUMNS - columns
            )

    for column, default in (
        ("TOTAL_LATAS_AMASSADAS", pd.NA),
        ("AMASSADA_DADO_IDENTIFICADO", False),
        ("AMASSADA_OCORRENCIA_SEM_QUANTIDADE", False),
        ("ENTREGA_COM_AMASSADA", 0),
        ("LABELS_AMASSADAS", pd.NA),
    ):
        if column not in data.columns:
            data[column] = default

    data["AMASSADA_DADO_IDENTIFICADO"] = (
        data["AMASSADA_DADO_IDENTIFICADO"].fillna(False).astype(bool)
    )
    data["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"] = (
        data["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"]
        .fillna(False)
        .astype(bool)
    )
    data["ENTREGA_COM_AMASSADA"] = (
        data["ENTREGA_COM_AMASSADA"].fillna(0).astype("int8")
    )
    data["TOTAL_LATAS_AMASSADAS"] = pd.to_numeric(
        data["TOTAL_LATAS_AMASSADAS"], errors="coerce"
    )
    data["ENTREGA_COM_FALTANTE_E_AMASSADA"] = (
        data["TOTAL_LATAS_FALTANTES"].gt(0)
        & data["ENTREGA_COM_AMASSADA"].eq(1)
    ).astype("int8")
    data["SEVERIDADE_AMASSADAS"] = data.apply(_severity, axis=1)

    positive = data.loc[
        data["TOTAL_LATAS_AMASSADAS"].gt(0), "TOTAL_LATAS_AMASSADAS"
    ]
    threshold = float(positive.quantile(0.99)) if not positive.empty else 0.0
    data["_OUTLIER_AMASSADAS"] = (
        data["TOTAL_LATAS_AMASSADAS"].gt(threshold)
        if threshold > 0
        else False
    )
    context["outlier_threshold"] = threshold
    context["known_inspections"] = int(
        data["AMASSADA_DADO_IDENTIFICADO"].sum()
    )
    context["occurrence_without_quantity"] = int(
        data["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"].sum()
    )
    return data, context


def calculate_damage_kpis(df):
    total_deliveries = int(df["INSPECTION_ID"].nunique())
    occurrences = int(
        df.loc[
            df["TOTAL_LATAS_AMASSADAS"].gt(0), "INSPECTION_ID"
        ].nunique()
    )
    total = float(
        pd.to_numeric(
            df["TOTAL_LATAS_AMASSADAS"], errors="coerce"
        ).fillna(0).sum()
    )
    return {
        "total_deliveries": total_deliveries,
        "known_deliveries": int(df["AMASSADA_DADO_IDENTIFICADO"].sum()),
        "total_damaged": total,
        "occurrence_deliveries": occurrences,
        "occurrence_rate": (
            occurrences / total_deliveries * 100 if total_deliveries else 0.0
        ),
        "average_per_delivery": (
            total / total_deliveries if total_deliveries else 0.0
        ),
        "average_per_occurrence": (
            total / occurrences if occurrences else 0.0
        ),
    }


def aggregate_damage_dimension(df, dimension):
    if df.empty or dimension not in df.columns:
        return pd.DataFrame()
    source = df.copy()
    source["_ENTREGA_COM_AMASSADA_NUMERICA"] = (
        source["TOTAL_LATAS_AMASSADAS"].gt(0).astype("int8")
    )
    result = (
        source.groupby(dimension, dropna=False, as_index=False)
        .agg(
            ENTREGAS=("INSPECTION_ID", "nunique"),
            ENTREGAS_COM_AMASSADAS=(
                "_ENTREGA_COM_AMASSADA_NUMERICA",
                "sum",
            ),
            OCORRENCIAS_SEM_QUANTIDADE=(
                "AMASSADA_OCORRENCIA_SEM_QUANTIDADE",
                "sum",
            ),
            LATAS_AMASSADAS=("TOTAL_LATAS_AMASSADAS", "sum"),
        )
    )
    result["TAXA_AMASSADAS"] = (
        result["ENTREGAS_COM_AMASSADAS"]
        .div(result["ENTREGAS"].where(result["ENTREGAS"].ne(0)))
        .fillna(0)
        * 100
    )
    result["MEDIA_POR_ENTREGA"] = (
        result["LATAS_AMASSADAS"]
        .div(result["ENTREGAS"].where(result["ENTREGAS"].ne(0)))
        .fillna(0)
    )
    result["MEDIA_POR_OCORRENCIA"] = (
        result["LATAS_AMASSADAS"]
        .div(
            result["ENTREGAS_COM_AMASSADAS"].where(
                result["ENTREGAS_COM_AMASSADAS"].ne(0)
            )
        )
        .fillna(0)
    )
    grand_total = result["LATAS_AMASSADAS"].sum()
    result["PARTICIPACAO_TOTAL"] = (
        result["LATAS_AMASSADAS"] / grand_total * 100
        if grand_total
        else 0.0
    )
    return result


def aggregate_damage_month(df):
    result = aggregate_damage_dimension(df, "ANO_MES")
    if result.empty:
        return result
    result = result[result["ANO_MES"] != "SEM DATA"].sort_values("ANO_MES")
    result["VARIACAO_ABSOLUTA"] = result["LATAS_AMASSADAS"].diff()
    result["VARIACAO_PERCENTUAL"] = (
        result["LATAS_AMASSADAS"].pct_change(fill_method=None) * 100
    )
    return result


def _fmt_int(value):
    return f"{value:,.0f}".replace(",", ".")


def _fmt_decimal(value):
    return (
        f"{value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _damage_ranking_chart(
    data,
    dimension,
    title,
    color,
    metric="LATAS_AMASSADAS",
):
    ranking = (
        data.sort_values(metric, ascending=False)
        .head(15)
        .sort_values(metric)
    )
    figure = px.bar(
        ranking,
        x=metric,
        y=dimension,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=[
            "ENTREGAS",
            "ENTREGAS_COM_AMASSADAS",
            "TAXA_AMASSADAS",
            "MEDIA_POR_OCORRENCIA",
        ],
    )
    is_rate = metric == "TAXA_AMASSADAS"
    figure.update_traces(
        text=ranking[metric].map(
            lambda value: f"{value:.2f}%" if is_rate else f"{value:,.0f}"
        ),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            + (
                "Taxa de ocorrência: %{x:.2f}%<br>"
                if is_rate
                else "Latas amassadas: %{x:,.0f}<br>"
            )
            +
            "Entregas: %{customdata[0]:,.0f}<br>"
            "Entregas com amassadas: %{customdata[1]:,.0f}<br>"
            "Taxa: %{customdata[2]:.2f}%<br>"
            "Média por ocorrência: %{customdata[3]:,.2f}<extra></extra>"
        ),
    )
    figure.update_layout(
        height=max(430, len(ranking) * 31),
        yaxis_title=None,
        xaxis_title=(
            "% de entregas com amassadas"
            if is_rate
            else "Latas amassadas"
        ),
        margin={"l": 20, "r": 55, "t": 60, "b": 20},
    )
    if is_rate:
        figure.update_xaxes(ticksuffix="%")
    return figure


def _associated_values(df, group_column, value_column, output_column):
    source = df[df["ENTREGA_COM_AMASSADA"].eq(1)]
    if source.empty:
        return pd.DataFrame(columns=[group_column, output_column])

    def summarize(values):
        values = values.dropna().astype(str)
        values = values[values.ne("(Não informado)")]
        return ", ".join(values.value_counts().head(3).index)

    return (
        source.groupby(group_column, dropna=False)[value_column]
        .apply(summarize)
        .reset_index(name=output_column)
    )


def _render_damage_source_diagnostic(context):
    st.warning(
        "A fonte de amassadas disponível é um resumo de labels, não uma "
        "extração por inspeção. Sem INSPECTION_ID e RESPONSE não é possível "
        "calcular os indicadores sem inventar dados."
    )
    source_name = context.get("source_name") or "não encontrada"
    st.caption(f"Fonte analisada: {source_name}")

    profile = context.get("profile", pd.DataFrame())
    if not profile.empty:
        quantitative = profile[profile["LABEL_QUANTITATIVO"]]
        st.subheader("Labels quantitativos encontrados")
        st.dataframe(
            quantitative,
            hide_index=True,
            width="stretch",
        )
        with st.expander("Outros labels relacionados a amassadas/avarias"):
            st.dataframe(
                profile[~profile["LABEL_QUANTITATIVO"]],
                hide_index=True,
                width="stretch",
            )

    missing = context.get("missing_detail_columns") or []
    st.info(
        "A próxima exportação precisa incluir: "
        + ", ".join(sorted(DAMAGE_REQUIRED_DETAIL_COLUMNS))
        + (f". Ausentes atualmente: {', '.join(missing)}." if missing else ".")
    )
    with st.expander("SQL mínimo para a exportação detalhada"):
        export_sql = get_damage_export_sql()
        st.code(export_sql, language="sql")
        st.download_button(
            "Baixar SQL completo para Snowflake",
            data=export_sql.encode("utf-8"),
            file_name=FULL_EXPORT_SQL_PATH.name,
            mime="text/plain",
            key="download_sql_amassadas",
        )


def _render_damage_quality(df, context):
    cards = st.columns(4)
    cards[0].metric(
        "Inspeções sem destino",
        _fmt_int(int(df["_MISSING_DESTINO_CLIENTE"].sum())),
    )
    cards[1].metric(
        "Sem transportadora",
        _fmt_int(int(df["_MISSING_TRANSPORTADORA"].sum())),
    )
    cards[2].metric(
        "Sem caminhão/placa",
        _fmt_int(int(df["_MISSING_CAMINHAO_OU_PLACA"].sum())),
    )
    cards[3].metric(
        "Sem rota",
        _fmt_int(int(df["_MISSING_ROTA"].sum())),
    )
    st.metric(
        "Inspeções sem quantidade de amassadas identificada",
        _fmt_int(int((~df["AMASSADA_DADO_IDENTIFICADO"]).sum())),
    )
    outlier_threshold = context.get("outlier_threshold", 0)
    outliers = df[df["_OUTLIER_AMASSADAS"]].sort_values(
        "TOTAL_LATAS_AMASSADAS", ascending=False
    )
    outlier_cols = st.columns(2)
    outlier_cols[0].metric(
        "Limite de outlier (P99)",
        _fmt_int(outlier_threshold),
    )
    outlier_cols[1].metric(
        "Inspeções acima do P99",
        _fmt_int(len(outliers)),
    )

    profile = context.get("profile", pd.DataFrame())
    if not profile.empty:
        st.subheader("Labels encontrados relacionados a amassadas/avarias")
        st.dataframe(profile, hide_index=True, width="stretch")

    samples = context.get("non_numeric_samples", pd.DataFrame())
    st.subheader("Respostas não numéricas para revisão")
    if samples.empty:
        st.info("Nenhuma amostra detalhada disponível na fonte atual.")
    else:
        st.dataframe(samples, hide_index=True, width="stretch")

    st.subheader("Casos extremos para auditoria")
    if outliers.empty:
        st.info("Nenhum outlier de amassadas nos filtros atuais.")
    else:
        st.dataframe(
            outliers[
                [
                    "DATA_INSPECAO",
                    "DESTINO_CLIENTE",
                    "TRANSPORTADORA",
                    "CAMINHAO_OU_PLACA",
                    "TOTAL_LATAS_AMASSADAS",
                    "WEBLINK",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "WEBLINK": st.column_config.LinkColumn(
                    "Inspeção", display_text="Abrir"
                )
            },
        )


def _render_damage_analysis_legacy(df, context):
    st.subheader("Análise de Latas Amassadas")
    st.caption(
        "Visão executiva de volume, incidência, severidade e concentração "
        "logística, sempre vinculada ao total de entregas do período."
    )

    if context.get("source_type") in {"none", "summary"}:
        diagnostic_tab, quality_tab = st.tabs(
            ["Diagnóstico da fonte", "Qualidade e validação"]
        )
        with diagnostic_tab:
            _render_damage_source_diagnostic(context)
        with quality_tab:
            _render_damage_quality(df, context)
        return

    kpis = calculate_damage_kpis(df)
    coverage = (
        kpis["known_deliveries"] / kpis["total_deliveries"] * 100
        if kpis["total_deliveries"]
        else 0
    )
    if coverage < 100:
        st.warning(
            f"A quantidade foi identificada em {coverage:.1f}% das entregas "
            "filtradas. Registros não identificados não foram convertidos em zero."
        )

    clients = aggregate_damage_dimension(df, "DESTINO_CLIENTE")
    carriers = aggregate_damage_dimension(df, "TRANSPORTADORA")
    top_client = (
        clients.sort_values("LATAS_AMASSADAS", ascending=False).iloc[0]
        if not clients.empty
        else None
    )
    top_carrier = (
        carriers.sort_values("LATAS_AMASSADAS", ascending=False).iloc[0]
        if not carriers.empty
        else None
    )

    first_cards = st.columns(3)
    second_cards = st.columns(3)
    first_cards[0].metric(
        "Total de latas amassadas", _fmt_int(kpis["total_damaged"])
    )
    first_cards[1].metric(
        "Entregas com amassadas", _fmt_int(kpis["occurrence_deliveries"])
    )
    first_cards[2].metric(
        "% entregas com amassadas",
        f"{_fmt_decimal(kpis['occurrence_rate'])}%",
    )
    second_cards[0].metric(
        "Média por entrega com amassadas",
        _fmt_decimal(kpis["average_per_occurrence"]),
    )
    second_cards[1].metric(
        "Cliente com maior volume",
        str(top_client["DESTINO_CLIENTE"]) if top_client is not None else "-",
        (
            f"{_fmt_int(top_client['LATAS_AMASSADAS'])} latas"
            if top_client is not None
            else None
        ),
        delta_color="off",
    )
    second_cards[2].metric(
        "Transportadora com maior volume",
        str(top_carrier["TRANSPORTADORA"]) if top_carrier is not None else "-",
        (
            f"{_fmt_int(top_carrier['LATAS_AMASSADAS'])} latas"
            if top_carrier is not None
            else None
        ),
        delta_color="off",
    )

    (
        evolution_tab,
        concentration_tab,
        logistics_tab,
        comparison_tab,
        details_tab,
        quality_tab,
    ) = st.tabs(
        [
            "Evolução",
            "Clientes e Transportadoras",
            "Caminhões e Rotas",
            "Faltantes x Amassadas",
            "Detalhamento",
            "Qualidade",
        ]
    )

    with evolution_tab:
        monthly = aggregate_damage_month(df)
        if monthly.empty:
            st.info("Não existem meses válidos nos filtros atuais.")
        else:
            impact = make_subplots(specs=[[{"secondary_y": True}]])
            impact.add_trace(
                go.Bar(
                    x=monthly["ANO_MES"],
                    y=monthly["LATAS_AMASSADAS"],
                    name="Latas amassadas",
                    marker_color="#7B1FA2",
                    customdata=monthly[["ENTREGAS", "ENTREGAS_COM_AMASSADAS"]],
                    hovertemplate=(
                        "<b>%{x}</b><br>Latas amassadas: %{y:,.0f}<br>"
                        "Entregas: %{customdata[0]:,.0f}<br>"
                        "Entregas com amassadas: %{customdata[1]:,.0f}"
                        "<extra></extra>"
                    ),
                ),
                secondary_y=False,
            )
            impact.add_trace(
                go.Scatter(
                    x=monthly["ANO_MES"],
                    y=monthly["MEDIA_POR_OCORRENCIA"],
                    name="Gravidade média",
                    mode="lines+markers",
                    line={"color": "#E65100", "width": 3},
                ),
                secondary_y=True,
            )
            impact.update_layout(
                title="Evolução de Latas Amassadas x Gravidade Média",
                legend={"orientation": "h", "y": 1.12},
                hovermode="x unified",
            )
            impact.update_yaxes(
                title_text="Latas amassadas", secondary_y=False
            )
            impact.update_yaxes(
                title_text="Média por ocorrência", secondary_y=True
            )
            st.plotly_chart(impact, width="stretch")

            incidence = make_subplots(specs=[[{"secondary_y": True}]])
            incidence.add_trace(
                go.Bar(
                    x=monthly["ANO_MES"],
                    y=monthly["ENTREGAS_COM_AMASSADAS"],
                    name="Entregas com amassadas",
                    marker_color="#00838F",
                ),
                secondary_y=False,
            )
            incidence.add_trace(
                go.Scatter(
                    x=monthly["ANO_MES"],
                    y=monthly["TAXA_AMASSADAS"],
                    name="% das entregas",
                    mode="lines+markers",
                    line={"color": "#C62828", "width": 3},
                ),
                secondary_y=True,
            )
            incidence.update_layout(
                title="Incidência de Latas Amassadas nas Entregas",
                legend={"orientation": "h", "y": 1.12},
                hovermode="x unified",
            )
            incidence.update_yaxes(
                title_text="Entregas com amassadas", secondary_y=False
            )
            incidence.update_yaxes(
                title_text="% das entregas",
                ticksuffix="%",
                secondary_y=True,
            )
            st.plotly_chart(incidence, width="stretch")
            st.dataframe(monthly, hide_index=True, width="stretch")

    with concentration_tab:
        carriers = carriers.merge(
            _associated_values(
                df,
                "TRANSPORTADORA",
                "DESTINO_CLIENTE",
                "CLIENTES_MAIS_AFETADOS",
            ),
            on="TRANSPORTADORA",
            how="left",
        ).merge(
            _associated_values(
                df,
                "TRANSPORTADORA",
                "CAMINHAO_OU_PLACA",
                "CAMINHOES_RECORRENTES",
            ),
            on="TRANSPORTADORA",
            how="left",
        )
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                _damage_ranking_chart(
                    clients,
                    "DESTINO_CLIENTE",
                    "Top Clientes por Latas Amassadas",
                    "#1565C0",
                ),
                width="stretch",
            )
        with right:
            st.plotly_chart(
                _damage_ranking_chart(
                    carriers,
                    "TRANSPORTADORA",
                    "Top Transportadoras por Latas Amassadas",
                    "#6A1B9A",
                ),
                width="stretch",
            )
        st.dataframe(
            clients.sort_values("LATAS_AMASSADAS", ascending=False),
            hide_index=True,
            width="stretch",
        )
        st.subheader("Contexto das transportadoras")
        st.dataframe(
            carriers.sort_values("LATAS_AMASSADAS", ascending=False),
            hide_index=True,
            width="stretch",
        )

    with logistics_tab:
        trucks = aggregate_damage_dimension(df, "CAMINHAO_OU_PLACA")
        routes = aggregate_damage_dimension(df, "ROTA")
        trucks = trucks.merge(
            _associated_values(
                df,
                "CAMINHAO_OU_PLACA",
                "TRANSPORTADORA",
                "TRANSPORTADORAS_ASSOCIADAS",
            ),
            on="CAMINHAO_OU_PLACA",
            how="left",
        ).merge(
            _associated_values(
                df,
                "CAMINHAO_OU_PLACA",
                "DESTINO_CLIENTE",
                "CLIENTES_PRINCIPAIS",
            ),
            on="CAMINHAO_OU_PLACA",
            how="left",
        ).merge(
            _associated_values(
                df,
                "CAMINHAO_OU_PLACA",
                "ROTA",
                "ROTAS_PRINCIPAIS",
            ),
            on="CAMINHAO_OU_PLACA",
            how="left",
        )
        routes = routes.merge(
            _associated_values(
                df,
                "ROTA",
                "DESTINO_CLIENTE",
                "CLIENTES_ENVOLVIDOS",
            ),
            on="ROTA",
            how="left",
        ).merge(
            _associated_values(
                df,
                "ROTA",
                "TRANSPORTADORA",
                "TRANSPORTADORAS_ENVOLVIDAS",
            ),
            on="ROTA",
            how="left",
        )
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                _damage_ranking_chart(
                    trucks,
                    "CAMINHAO_OU_PLACA",
                    "Caminhões/Placas com Maior Volume de Amassadas",
                    "#E87722",
                ),
                width="stretch",
            )
        with right:
            st.plotly_chart(
                _damage_ranking_chart(
                    routes,
                    "ROTA",
                    "Rotas com Maior Incidência de Amassadas",
                    "#2E7D32",
                    metric="TAXA_AMASSADAS",
                ),
                width="stretch",
            )
        st.subheader("Caminhões/placas e associações")
        st.dataframe(
            trucks.sort_values("LATAS_AMASSADAS", ascending=False),
            hide_index=True,
            width="stretch",
        )
        st.subheader("Rotas, clientes e transportadoras")
        st.dataframe(
            routes.sort_values("TAXA_AMASSADAS", ascending=False),
            hide_index=True,
            width="stretch",
        )

    with comparison_tab:
        damage_known_no_occurrence = (
            df["AMASSADA_DADO_IDENTIFICADO"]
            & df["ENTREGA_COM_AMASSADA"].eq(0)
        )
        comparison = pd.DataFrame(
            {
                "Situação": [
                    "Apenas faltantes",
                    "Apenas amassadas",
                    "Faltantes e amassadas",
                    "Sem ocorrência",
                    "Amassadas não identificadas",
                ],
                "Entregas": [
                    int(
                        (
                            df["TOTAL_LATAS_FALTANTES"].gt(0)
                            & damage_known_no_occurrence
                        ).sum()
                    ),
                    int(
                        (
                            df["TOTAL_LATAS_FALTANTES"].le(0)
                            & df["ENTREGA_COM_AMASSADA"].eq(1)
                        ).sum()
                    ),
                    int(df["ENTREGA_COM_FALTANTE_E_AMASSADA"].sum()),
                    int(
                        (
                            df["TOTAL_LATAS_FALTANTES"].le(0)
                            & damage_known_no_occurrence
                        ).sum()
                    ),
                    int((~df["AMASSADA_DADO_IDENTIFICADO"]).sum()),
                ],
            }
        )
        correlation_source = df[
            df["AMASSADA_DADO_IDENTIFICADO"]
        ][["TOTAL_LATAS_FALTANTES", "TOTAL_LATAS_AMASSADAS"]].dropna()
        correlation = (
            correlation_source.corr().iloc[0, 1]
            if len(correlation_source) > 1
            else None
        )
        st.metric(
            "Correlação entre faltantes e amassadas",
            f"{correlation:.3f}" if pd.notna(correlation) else "Sem dados",
        )
        st.plotly_chart(
            px.bar(
                comparison,
                x="Situação",
                y="Entregas",
                text="Entregas",
                title="Faltantes x Amassadas",
                color="Situação",
            ),
            width="stretch",
        )
        both = df[df["ENTREGA_COM_FALTANTE_E_AMASSADA"].eq(1)].sort_values(
            ["TOTAL_LATAS_AMASSADAS", "TOTAL_LATAS_FALTANTES"],
            ascending=False,
        )
        st.dataframe(
            both[
                [
                    "DATA_INSPECAO",
                    "DESTINO_CLIENTE",
                    "TRANSPORTADORA",
                    "CAMINHAO_OU_PLACA",
                    "TOTAL_LATAS_FALTANTES",
                    "TOTAL_LATAS_AMASSADAS",
                    "WEBLINK",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "WEBLINK": st.column_config.LinkColumn(
                    "Inspeção", display_text="Abrir"
                )
            },
        )

    with details_tab:
        detail_columns = [
            "DATA_INSPECAO",
            "DESTINO_CLIENTE",
            "CLIENTE_GRUPO",
            "TRANSPORTADORA",
            "CAMINHAO_OU_PLACA",
            "ROTA",
            "TOTAL_LATAS_FALTANTES",
            "TOTAL_LATAS_AMASSADAS",
            "SEVERIDADE_AMASSADAS",
            "TEMPLATE_NAME",
            "FIRSTNAME",
            "EMAIL",
            "WEBLINK",
        ]
        detail = df[detail_columns].sort_values(
            "TOTAL_LATAS_AMASSADAS", ascending=False, na_position="last"
        )
        st.dataframe(
            detail,
            hide_index=True,
            width="stretch",
            column_config={
                "WEBLINK": st.column_config.LinkColumn(
                    "Inspeção", display_text="Abrir"
                )
            },
        )
        st.download_button(
            "Baixar análise de amassadas",
            data=detail.to_csv(index=False).encode("utf-8-sig"),
            file_name="onsite_latas_amassadas.csv",
            mime="text/csv",
        )

    with quality_tab:
        _render_damage_quality(df, context)


def render_damage_analysis(df, context):
    from src.pages.latas_amassadas import render_latas_amassadas

    render_latas_amassadas(
        df,
        context=context,
        quality_renderer=_render_damage_quality,
    )
    if context.get("source_type") in {"none", "summary"}:
        st.divider()
        st.subheader("Diagnóstico da fonte de amassadas")
        _render_damage_source_diagnostic(context)
