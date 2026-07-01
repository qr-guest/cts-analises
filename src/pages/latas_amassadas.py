import pandas as pd
import streamlit as st

from src.charts import (
    chart_evolucao_amassadas,
    chart_faltantes_vs_amassadas,
    chart_incidencia_amassadas,
    chart_rotas_amassadas,
    chart_severidade_amassadas,
    chart_top_caminhoes_amassadas,
    chart_top_clientes_amassadas,
    chart_top_transportadoras_amassadas,
)
from src.metrics import (
    MissingDamageColumns,
    agregar_amassadas_por_cliente,
    agregar_amassadas_por_transportadora,
    calcular_kpis_amassadas,
    calcular_resumo_gerencial_amassadas,
)


CHARTS = [
    (
        "Evolução de Latas Amassadas x Gravidade Média",
        chart_evolucao_amassadas,
    ),
    (
        "Incidência de Latas Amassadas nas Entregas",
        chart_incidencia_amassadas,
    ),
    ("Top Clientes por Latas Amassadas", chart_top_clientes_amassadas),
    (
        "Top Transportadoras por Latas Amassadas",
        chart_top_transportadoras_amassadas,
    ),
    (
        "Caminhões/Placas com Maior Volume de Amassadas",
        chart_top_caminhoes_amassadas,
    ),
    ("Rotas com Maior Incidência de Amassadas", chart_rotas_amassadas),
    ("Faltantes x Amassadas", chart_faltantes_vs_amassadas),
]


CHART_DESCRIPTIONS = {
    chart_evolucao_amassadas: (
        "o volume mensal de latas amassadas está aumentando, diminuindo ou "
        "ficando mais grave por entrega!"
    ),
    chart_incidencia_amassadas: (
        "qual percentual das entregas teve amassadas em cada mês, usando o "
        "total de entregas como denominador!"
    ),
    chart_top_clientes_amassadas: (
        "quais clientes/destinos concentram o maior volume de latas amassadas "
        "e quantas entregas geraram esse volume!"
    ),
    chart_top_transportadoras_amassadas: (
        "quais transportadoras concentram mais latas amassadas e qual é a "
        "incidência dentro das entregas delas!"
    ),
    chart_top_caminhoes_amassadas: (
        "quais caminhões ou placas aparecem com maior volume de latas "
        "amassadas e merecem auditoria operacional!"
    ),
    chart_rotas_amassadas: (
        "quais rotas têm maior incidência proporcional de amassadas, evitando "
        "olhar apenas volume bruto!"
    ),
    chart_faltantes_vs_amassadas: (
        "as entregas com latas faltantes também concentram latas amassadas, "
        "indicando possível problema logístico combinado!"
    ),
    chart_severidade_amassadas: (
        "como as entregas se distribuem entre baixa, média, alta, crítica, sem "
        "amassadas ou sem quantidade identificada!"
    ),
}


def _fmt_int(value):
    return f"{value:,.0f}".replace(",", ".")


def _fmt_decimal(value):
    return (
        f"{value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _fmt_delta(value, suffix="%"):
    if value is None or pd.isna(value):
        return None
    return f"{value:+.1f}{suffix}"


def _compact_ranking(data, category):
    columns = [
        category,
        "TOTAL_LATAS_AMASSADAS",
        "ENTREGAS_COM_AMASSADAS",
        "PERC_ENTREGAS_COM_AMASSADAS",
        "MEDIA_POR_ENTREGA_COM_AMASSADAS",
    ]
    return (
        data.sort_values("TOTAL_LATAS_AMASSADAS", ascending=False)
        .head(5)[columns]
        .rename(
            columns={
                category: "Nome",
                "TOTAL_LATAS_AMASSADAS": "Latas amassadas",
                "ENTREGAS_COM_AMASSADAS": "Entregas com amassadas",
                "PERC_ENTREGAS_COM_AMASSADAS": "Incidência (%)",
                "MEDIA_POR_ENTREGA_COM_AMASSADAS": "Média por ocorrência",
            }
        )
    )


def _has_numeric_damage_data(df):
    if "TOTAL_LATAS_AMASSADAS" not in df.columns:
        return False
    if "AMASSADA_DADO_IDENTIFICADO" in df.columns:
        return bool(df["AMASSADA_DADO_IDENTIFICADO"].fillna(False).any())
    return pd.to_numeric(
        df["TOTAL_LATAS_AMASSADAS"], errors="coerce"
    ).notna().any()


def _render_unavailable_charts(reason):
    st.error(
        "A análise executiva não pode ser calculada com os arquivos atuais."
    )
    st.warning(reason)
    st.dataframe(
        pd.DataFrame(
            {
                "Visualização": [title for title, _ in CHARTS],
                "Pergunta respondida": [
                    CHART_DESCRIPTIONS.get(chart_function, "")
                    for _, chart_function in CHARTS
                ],
                "Status": ["Aguardando base detalhada"] * len(CHARTS),
            }
        ),
        hide_index=True,
        width="stretch",
    )


def _render_chart(chart_function, df):
    description = CHART_DESCRIPTIONS.get(chart_function)
    if description:
        st.caption(f"Este gráfico responde: {description}")
    try:
        fig = chart_function(df)
        st.plotly_chart(fig, width="stretch")
    except (MissingDamageColumns, ValueError, KeyError) as error:
        st.warning(str(error))
    except Exception as error:
        st.warning(f"Não foi possível gerar este gráfico: {error}")


def render_latas_amassadas(df, context=None, quality_renderer=None):
    context = context or {}
    st.subheader("Análise de Latas Amassadas")
    st.caption(
        "Quanto aconteceu, em relação a qual total, onde ocorreu, com quem "
        "ocorreu e se o problema está ficando mais frequente ou mais grave."
    )

    if not _has_numeric_damage_data(df):
        _render_unavailable_charts(
            "O arquivo LT_AMASSADA atual contém somente LABEL, QTD_LINHAS, "
            "QTD_INSPECOES, EXEMPLO_MIN e EXEMPLO_MAX. Ele não possui "
            "INSPECTION_ID nem RESPONSE. O arquivo principal também não "
            "possui TOTAL_LATAS_AMASSADAS. Execute o SQL disponibilizado "
            "abaixo e substitua a exportação principal pelo novo CSV."
        )
        if quality_renderer:
            quality_renderer(df, context)
        return

    kpis = calcular_kpis_amassadas(df)
    management = calcular_resumo_gerencial_amassadas(df)
    clients = agregar_amassadas_por_cliente(df)
    carriers = agregar_amassadas_por_transportadora(df)
    top_client = (
        clients.sort_values("TOTAL_LATAS_AMASSADAS", ascending=False).iloc[0]
        if not clients.empty
        else None
    )
    top_carrier = (
        carriers.sort_values("TOTAL_LATAS_AMASSADAS", ascending=False).iloc[0]
        if not carriers.empty
        else None
    )

    st.markdown("### Visão gerencial")
    cards = st.columns(4)
    cards[0].metric(
        "Total de Latas Amassadas",
        _fmt_int(kpis["total_latas_amassadas"]),
    )
    cards[1].metric(
        "Entregas com Latas Amassadas",
        _fmt_int(kpis["entregas_com_amassadas"]),
    )
    cards[2].metric(
        "% Entregas com Amassadas",
        f"{_fmt_decimal(kpis['perc_entregas_com_amassadas'])}%",
    )
    cards[3].metric(
        "Média por Entrega com Amassadas",
        _fmt_decimal(kpis["media_por_entrega_com_amassadas"]),
    )
    impact_cards = st.columns(4)
    impact_cards[0].metric(
        "Cliente com Maior Volume",
        str(top_client["DESTINO_CLIENTE"]) if top_client is not None else "-",
        (
            f"{_fmt_int(top_client['TOTAL_LATAS_AMASSADAS'])} latas"
            if top_client is not None
            else None
        ),
        delta_color="off",
    )
    impact_cards[1].metric(
        "Transportadora com Maior Volume",
        (
            str(top_carrier["TRANSPORTADORA"])
            if top_carrier is not None
            else "-"
        ),
        (
            f"{_fmt_int(top_carrier['TOTAL_LATAS_AMASSADAS'])} latas"
            if top_carrier is not None
            else None
        ),
        delta_color="off",
    )
    impact_cards[2].metric(
        "Entregas críticas",
        _fmt_int(management["casos_criticos"]),
        help="Entregas com mais de 200 latas amassadas.",
    )
    impact_cards[3].metric(
        "Faltantes + amassadas",
        _fmt_int(management["faltantes_e_amassadas"]),
        help="Entregas que registraram os dois tipos de ocorrência.",
    )

    if management["mes_atual"]:
        period_label = management["mes_atual"]
        if pd.notna(management["data_mais_recente"]):
            period_label += (
                " (até "
                + management["data_mais_recente"].strftime("%d/%m/%Y")
                + ")"
            )
        st.markdown(
            f"### Leitura do mês mais recente: {period_label}"
        )
        if management["mes_atual_parcial"]:
            st.warning(
                "O mês mais recente ainda está parcial. As variações abaixo "
                "comparam o acumulado disponível com o mês anterior completo "
                "e devem ser interpretadas como tendência provisória."
            )
        else:
            st.caption(
                "As variações abaixo comparam o mês mais recente disponível "
                "nos filtros com o mês imediatamente anterior."
            )
        month_cards = st.columns(4)
        month_cards[0].metric(
            "Latas amassadas",
            _fmt_int(management["latas_mes_atual"]),
            _fmt_delta(management["variacao_latas_percentual"]),
            delta_color="inverse",
        )
        month_cards[1].metric(
            "Entregas com amassadas",
            _fmt_int(management["entregas_mes_atual"]),
            _fmt_delta(management["variacao_entregas_percentual"]),
            delta_color="inverse",
        )
        month_cards[2].metric(
            "Incidência",
            f"{_fmt_decimal(management['incidencia_mes_atual'])}%",
            _fmt_delta(management["variacao_incidencia_pp"], " p.p."),
            delta_color="inverse",
        )
        month_cards[3].metric(
            "Gravidade média",
            _fmt_decimal(management["media_mes_atual"]),
            _fmt_delta(management["variacao_media_percentual"]),
            delta_color="inverse",
        )

    st.markdown("### Principais concentrações")
    overview_left, overview_center, overview_right = st.columns(
        [1.15, 1.15, 1.4]
    )
    with overview_left:
        st.markdown("#### Top 5 clientes")
        st.dataframe(
            _compact_ranking(clients, "DESTINO_CLIENTE"),
            hide_index=True,
            width="stretch",
            column_config={
                "Latas amassadas": st.column_config.NumberColumn(
                    format="%.0f"
                ),
                "Incidência (%)": st.column_config.NumberColumn(
                    format="%.2f%%"
                ),
                "Média por ocorrência": st.column_config.NumberColumn(
                    format="%.2f"
                ),
            },
        )
    with overview_center:
        st.markdown("#### Top 5 transportadoras")
        st.dataframe(
            _compact_ranking(carriers, "TRANSPORTADORA"),
            hide_index=True,
            width="stretch",
            column_config={
                "Latas amassadas": st.column_config.NumberColumn(
                    format="%.0f"
                ),
                "Incidência (%)": st.column_config.NumberColumn(
                    format="%.2f%%"
                ),
                "Média por ocorrência": st.column_config.NumberColumn(
                    format="%.2f"
                ),
            },
        )
    with overview_right:
        _render_chart(chart_severidade_amassadas, df)

    st.caption(
        "Cobertura da quantidade de amassadas na base filtrada: "
        f"{_fmt_decimal(management['cobertura_percentual'])}%."
    )

    st.markdown("### Análises complementares")
    evolution_tab, rankings_tab, logistics_tab, comparison_tab = st.tabs(
        [
            "Evolução e Incidência",
            "Clientes e Transportadoras",
            "Caminhões e Rotas",
            "Faltantes x Amassadas",
        ]
    )
    with evolution_tab:
        _render_chart(chart_evolucao_amassadas, df)
        _render_chart(chart_incidencia_amassadas, df)
    with rankings_tab:
        left, right = st.columns(2)
        with left:
            _render_chart(chart_top_clientes_amassadas, df)
        with right:
            _render_chart(chart_top_transportadoras_amassadas, df)
    with logistics_tab:
        left, right = st.columns(2)
        with left:
            _render_chart(chart_top_caminhoes_amassadas, df)
        with right:
            _render_chart(chart_rotas_amassadas, df)
    with comparison_tab:
        _render_chart(chart_faltantes_vs_amassadas, df)

    st.subheader("Detalhamento das inspeções")
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
    available_columns = [
        column for column in detail_columns if column in df.columns
    ]
    missing_columns = [
        column for column in detail_columns if column not in df.columns
    ]
    if missing_columns:
        st.warning(
            "Colunas ausentes no detalhamento: " + ", ".join(missing_columns)
        )
    detail = df[available_columns].sort_values(
        "TOTAL_LATAS_AMASSADAS",
        ascending=False,
        na_position="last",
    )
    st.dataframe(
        detail,
        hide_index=True,
        use_container_width=True,
        column_config={
            "WEBLINK": st.column_config.LinkColumn(
                "Inspeção", display_text="Abrir"
            )
        },
    )
    st.download_button(
        "Baixar detalhamento de latas amassadas",
        data=detail.to_csv(index=False).encode("utf-8-sig"),
        file_name="onsite_latas_amassadas.csv",
        mime="text/csv",
        key="download_latas_amassadas",
    )

    if quality_renderer:
        st.subheader("Qualidade dos dados de amassadas")
        quality_renderer(df, context)
