import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.metrics import (
    agregar_amassadas_por_caminhao,
    agregar_amassadas_por_cliente,
    agregar_amassadas_por_mes,
    agregar_amassadas_por_rota,
    agregar_amassadas_por_transportadora,
    agregar_severidade_amassadas,
)


def _layout_executive(fig, height=500):
    fig.update_layout(
        height=height,
        margin={"l": 20, "r": 55, "t": 70, "b": 35},
        legend={"orientation": "h", "y": 1.12},
        hovermode="closest",
    )
    return fig


def _require_chart_data(data, description):
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError(
            f"Não existem dados para gerar {description} com os filtros atuais."
        )
    return data


def chart_evolucao_amassadas(df):
    monthly = _require_chart_data(
        agregar_amassadas_por_mes(df),
        "a evolução mensal de latas amassadas",
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=monthly["ANO_MES"],
            y=monthly["TOTAL_LATAS_AMASSADAS"],
            name="Latas amassadas",
            marker_color="#7B1FA2",
            text=monthly["TOTAL_LATAS_AMASSADAS"].map(
                lambda value: f"{value:,.0f}"
            ),
            textposition="outside",
            customdata=monthly[
                [
                    "ENTREGAS_COM_AMASSADAS",
                    "MEDIA_POR_ENTREGA_COM_AMASSADAS",
                    "TOTAL_ENTREGAS",
                ]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Latas amassadas: %{y:,.0f}<br>"
                "Entregas com amassadas: %{customdata[0]:,.0f}<br>"
                "Média por ocorrência: %{customdata[1]:,.2f}<br>"
                "Total de entregas: %{customdata[2]:,.0f}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["ANO_MES"],
            y=monthly["MEDIA_POR_ENTREGA_COM_AMASSADAS"],
            name="Gravidade média",
            mode="lines+markers",
            line={"color": "#E65100", "width": 3},
            text=monthly["MEDIA_POR_ENTREGA_COM_AMASSADAS"].map(
                lambda value: f"{value:,.1f}"
            ),
            textposition="top center",
            customdata=monthly[
                ["TOTAL_LATAS_AMASSADAS", "ENTREGAS_COM_AMASSADAS"]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Gravidade média: %{y:,.2f}<br>"
                "Latas amassadas: %{customdata[0]:,.0f}<br>"
                "Entregas com amassadas: %{customdata[1]:,.0f}"
                "<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="Evolução de Latas Amassadas x Gravidade Média",
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Latas amassadas", secondary_y=False)
    fig.update_yaxes(
        title_text="Média por entrega com amassadas", secondary_y=True
    )
    return _layout_executive(fig)


def chart_incidencia_amassadas(df):
    monthly = _require_chart_data(
        agregar_amassadas_por_mes(df),
        "a incidência mensal de latas amassadas",
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=monthly["ANO_MES"],
            y=monthly["ENTREGAS_COM_AMASSADAS"],
            name="Entregas com amassadas",
            marker_color="#00838F",
            text=monthly["ENTREGAS_COM_AMASSADAS"].map(
                lambda value: f"{value:,.0f}"
            ),
            textposition="outside",
            customdata=monthly[["TOTAL_ENTREGAS"]],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Entregas com amassadas: %{y:,.0f}<br>"
                "Total de entregas: %{customdata[0]:,.0f}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["ANO_MES"],
            y=monthly["PERC_ENTREGAS_COM_AMASSADAS"],
            name="% das entregas",
            mode="lines+markers",
            line={"color": "#C62828", "width": 3},
            text=monthly["PERC_ENTREGAS_COM_AMASSADAS"].map(
                lambda value: f"{value:.1f}%"
            ),
            textposition="top center",
            customdata=monthly[
                ["ENTREGAS_COM_AMASSADAS", "TOTAL_ENTREGAS"]
            ],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Incidência: %{y:.2f}%<br>"
                "Entregas com amassadas: %{customdata[0]:,.0f}<br>"
                "Total de entregas: %{customdata[1]:,.0f}<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="Incidência de Latas Amassadas nas Entregas",
        hovermode="x unified",
    )
    fig.update_yaxes(
        title_text="Entregas com amassadas", secondary_y=False
    )
    fig.update_yaxes(
        title_text="% das entregas",
        ticksuffix="%",
        secondary_y=True,
    )
    return _layout_executive(fig)


def chart_severidade_amassadas(df):
    severity = _require_chart_data(
        agregar_severidade_amassadas(df),
        "a distribuição de severidade",
    )
    order = [
        "Crítica: acima de 200",
        "Alta: 51 a 200",
        "Média: 11 a 50",
        "Baixa: 1 a 10",
        "Ocorrência sem quantidade",
        "Sem amassadas",
        "Não identificado",
    ]
    colors = {
        "Crítica: acima de 200": "#B71C1C",
        "Alta: 51 a 200": "#E65100",
        "Média: 11 a 50": "#F9A825",
        "Baixa: 1 a 10": "#2E7D32",
        "Ocorrência sem quantidade": "#6A1B9A",
        "Sem amassadas": "#90A4AE",
        "Não identificado": "#CFD8DC",
    }
    severity["SEVERIDADE_AMASSADAS"] = pd.Categorical(
        severity["SEVERIDADE_AMASSADAS"],
        categories=order,
        ordered=True,
    )
    severity = severity.sort_values("SEVERIDADE_AMASSADAS")
    fig = px.pie(
        severity,
        names="SEVERIDADE_AMASSADAS",
        values="ENTREGAS",
        title="Distribuição das entregas por severidade",
        hole=0.55,
        color="SEVERIDADE_AMASSADAS",
        color_discrete_map=colors,
        custom_data=["TOTAL_LATAS_AMASSADAS", "PERCENTUAL_ENTREGAS"],
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Entregas: %{value:,.0f}<br>"
            "Participação: %{customdata[1]:.2f}%<br>"
            "Latas amassadas: %{customdata[0]:,.0f}<extra></extra>"
        ),
    )
    return _layout_executive(fig, height=470)


def _horizontal_chart(
    data,
    category,
    metric,
    title,
    color,
    hover_fields,
    top_n=10,
    percentage=False,
):
    _require_chart_data(data, title)
    ranking = (
        data.sort_values(metric, ascending=False)
        .head(top_n)
        .sort_values(metric)
    )
    custom_columns = [column for column, _ in hover_fields]
    fig = px.bar(
        ranking,
        x=metric,
        y=category,
        orientation="h",
        title=title,
        color_discrete_sequence=[color],
        custom_data=custom_columns,
    )
    hover_lines = [f"{label}: %{{customdata[{index}]}}" for index, (_, label) in enumerate(hover_fields)]
    value_format = ".2f" if percentage else ",.0f"
    suffix = "%" if percentage else ""
    fig.update_traces(
        text=ranking[metric].map(
            lambda value: f"{value:.2f}%" if percentage else f"{value:,.0f}"
        ),
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            f"<b>%{{y}}</b><br>Valor: %{{x:{value_format}}}{suffix}<br>"
            + "<br>".join(hover_lines)
            + "<extra></extra>"
        ),
    )
    fig.update_layout(
        yaxis_title=None,
        xaxis_title=(
            "% de entregas com amassadas"
            if percentage
            else "Latas amassadas"
        ),
    )
    if percentage:
        fig.update_xaxes(ticksuffix="%")
    return _layout_executive(fig, height=max(430, len(ranking) * 38))


def chart_top_clientes_amassadas(df):
    data = agregar_amassadas_por_cliente(df)
    fields = []
    if "CLIENTE_GRUPO" in data.columns:
        fields.append(("CLIENTE_GRUPO", "Grupo"))
    fields.extend(
        [
            ("TOTAL_LATAS_AMASSADAS", "Latas amassadas"),
            ("TOTAL_ENTREGAS", "Entregas"),
            ("ENTREGAS_COM_AMASSADAS", "Entregas com amassadas"),
            ("PERC_ENTREGAS_COM_AMASSADAS", "Taxa (%)"),
            (
                "MEDIA_POR_ENTREGA_COM_AMASSADAS",
                "Média por ocorrência",
            ),
        ]
    )
    return _horizontal_chart(
        data,
        "DESTINO_CLIENTE",
        "TOTAL_LATAS_AMASSADAS",
        "Top Clientes por Latas Amassadas",
        "#1565C0",
        fields,
    )


def chart_top_transportadoras_amassadas(df):
    data = agregar_amassadas_por_transportadora(df)
    fields = [
        ("TOTAL_LATAS_AMASSADAS", "Latas amassadas"),
        ("TOTAL_ENTREGAS", "Entregas"),
        ("ENTREGAS_COM_AMASSADAS", "Entregas com amassadas"),
        ("PERC_ENTREGAS_COM_AMASSADAS", "Taxa (%)"),
        ("MEDIA_POR_ENTREGA_COM_AMASSADAS", "Média por ocorrência"),
    ]
    if "CLIENTES_ENVOLVIDOS" in data.columns:
        fields.append(("CLIENTES_ENVOLVIDOS", "Clientes envolvidos"))
    return _horizontal_chart(
        data,
        "TRANSPORTADORA",
        "TOTAL_LATAS_AMASSADAS",
        "Top Transportadoras por Latas Amassadas",
        "#6A1B9A",
        fields,
    )


def chart_top_caminhoes_amassadas(df):
    data = agregar_amassadas_por_caminhao(df)
    fields = []
    for column, label in (
        ("TRANSPORTADORA_ASSOCIADA", "Transportadora"),
        ("TOTAL_LATAS_AMASSADAS", "Latas amassadas"),
        ("TOTAL_ENTREGAS", "Entregas"),
        ("ENTREGAS_COM_AMASSADAS", "Entregas com amassadas"),
        ("MEDIA_POR_ENTREGA_COM_AMASSADAS", "Média por ocorrência"),
        ("PRINCIPAIS_CLIENTES", "Principais clientes"),
        ("PRINCIPAIS_ROTAS", "Principais rotas"),
    ):
        if column in data.columns:
            fields.append((column, label))
    return _horizontal_chart(
        data,
        "CAMINHAO_OU_PLACA",
        "TOTAL_LATAS_AMASSADAS",
        "Caminhões/Placas com Maior Volume de Amassadas",
        "#E87722",
        fields,
    )


def chart_rotas_amassadas(df):
    data = agregar_amassadas_por_rota(df)
    fields = [
        ("TOTAL_LATAS_AMASSADAS", "Latas amassadas"),
        ("TOTAL_ENTREGAS", "Entregas"),
        ("ENTREGAS_COM_AMASSADAS", "Entregas com amassadas"),
        ("MEDIA_POR_ENTREGA_COM_AMASSADAS", "Média por ocorrência"),
    ]
    for column, label in (
        ("CLIENTES_ENVOLVIDOS", "Clientes envolvidos"),
        ("TRANSPORTADORAS_ENVOLVIDAS", "Transportadoras envolvidas"),
    ):
        if column in data.columns:
            fields.append((column, label))
    return _horizontal_chart(
        data,
        "ROTA",
        "PERC_ENTREGAS_COM_AMASSADAS",
        "Rotas com Maior Incidência de Amassadas",
        "#2E7D32",
        fields,
        percentage=True,
    )


def chart_faltantes_vs_amassadas(df):
    required = [
        "INSPECTION_ID",
        "TOTAL_LATAS_FALTANTES",
        "TOTAL_LATAS_AMASSADAS",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            "Colunas necessárias não encontradas: " + ", ".join(missing)
        )
    source = df.copy()
    source["TOTAL_LATAS_FALTANTES"] = pd.to_numeric(
        source["TOTAL_LATAS_FALTANTES"], errors="coerce"
    )
    source["TOTAL_LATAS_AMASSADAS"] = pd.to_numeric(
        source["TOTAL_LATAS_AMASSADAS"], errors="coerce"
    )
    source = source.dropna(
        subset=["TOTAL_LATAS_FALTANTES", "TOTAL_LATAS_AMASSADAS"]
    )
    _require_chart_data(source, "o comparativo de faltantes e amassadas")
    color = (
        "CLIENTE_GRUPO"
        if "CLIENTE_GRUPO" in source.columns
        else "TRANSPORTADORA"
        if "TRANSPORTADORA" in source.columns
        else None
    )
    hover_columns = [
        column
        for column in (
            "INSPECTION_ID",
            "DATA_INSPECAO",
            "DESTINO_CLIENTE",
            "TRANSPORTADORA",
            "CAMINHAO_OU_PLACA",
            "ROTA",
            "TOTAL_LATAS_FALTANTES",
            "TOTAL_LATAS_AMASSADAS",
            "WEBLINK",
        )
        if column in source.columns
    ]
    fig = px.scatter(
        source,
        x="TOTAL_LATAS_FALTANTES",
        y="TOTAL_LATAS_AMASSADAS",
        color=color,
        hover_data=hover_columns,
        title="Faltantes x Amassadas",
        labels={
            "TOTAL_LATAS_FALTANTES": "Latas faltantes",
            "TOTAL_LATAS_AMASSADAS": "Latas amassadas",
        },
        opacity=0.75,
    )
    fig.update_traces(marker={"size": 10, "line": {"width": 0.5}})
    return _layout_executive(fig, height=570)
