import pandas as pd


class MissingDamageColumns(ValueError):
    pass


def _require_columns(df, columns):
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise MissingDamageColumns(
            "Colunas necessárias não encontradas: " + ", ".join(missing)
        )


def _damage_source(df):
    _require_columns(
        df,
        [
            "INSPECTION_ID",
            "TOTAL_LATAS_AMASSADAS",
        ],
    )
    source = df.copy()
    source["TOTAL_LATAS_AMASSADAS"] = pd.to_numeric(
        source["TOTAL_LATAS_AMASSADAS"], errors="coerce"
    )
    source["_COM_AMASSADAS"] = (
        source["TOTAL_LATAS_AMASSADAS"].gt(0).astype("int8")
    )
    return source


def calcular_kpis_amassadas(df):
    source = _damage_source(df)
    total_entregas = int(source["INSPECTION_ID"].nunique())
    entregas_com_amassadas = int(
        source.loc[
            source["_COM_AMASSADAS"].eq(1), "INSPECTION_ID"
        ].nunique()
    )
    total_latas_amassadas = float(
        source["TOTAL_LATAS_AMASSADAS"].fillna(0).sum()
    )
    return {
        "total_entregas": total_entregas,
        "total_latas_amassadas": total_latas_amassadas,
        "entregas_com_amassadas": entregas_com_amassadas,
        "perc_entregas_com_amassadas": (
            entregas_com_amassadas / total_entregas * 100
            if total_entregas
            else 0.0
        ),
        "media_por_entrega": (
            total_latas_amassadas / total_entregas
            if total_entregas
            else 0.0
        ),
        "media_por_entrega_com_amassadas": (
            total_latas_amassadas / entregas_com_amassadas
            if entregas_com_amassadas
            else 0.0
        ),
    }


def _agregar_dimensao(df, dimensions):
    source = _damage_source(df)
    if isinstance(dimensions, str):
        dimensions = [dimensions]
    dimensions = list(dimensions)
    _require_columns(source, dimensions)
    result = (
        source.groupby(dimensions, dropna=False, as_index=False)
        .agg(
            TOTAL_ENTREGAS=("INSPECTION_ID", "nunique"),
            ENTREGAS_COM_AMASSADAS=("_COM_AMASSADAS", "sum"),
            TOTAL_LATAS_AMASSADAS=("TOTAL_LATAS_AMASSADAS", "sum"),
        )
    )
    result["PERC_ENTREGAS_COM_AMASSADAS"] = (
        result["ENTREGAS_COM_AMASSADAS"]
        .div(result["TOTAL_ENTREGAS"].where(result["TOTAL_ENTREGAS"].ne(0)))
        .fillna(0)
        * 100
    )
    result["MEDIA_POR_ENTREGA"] = (
        result["TOTAL_LATAS_AMASSADAS"]
        .div(result["TOTAL_ENTREGAS"].where(result["TOTAL_ENTREGAS"].ne(0)))
        .fillna(0)
    )
    result["MEDIA_POR_ENTREGA_COM_AMASSADAS"] = (
        result["TOTAL_LATAS_AMASSADAS"]
        .div(
            result["ENTREGAS_COM_AMASSADAS"].where(
                result["ENTREGAS_COM_AMASSADAS"].ne(0)
            )
        )
        .fillna(0)
    )
    return result


def agregar_amassadas_por_mes(df):
    result = _agregar_dimensao(df, "ANO_MES")
    result = result[result["ANO_MES"].ne("SEM DATA")].sort_values("ANO_MES")
    result["VARIACAO_ABSOLUTA"] = result["TOTAL_LATAS_AMASSADAS"].diff()
    result["VARIACAO_PERCENTUAL"] = (
        result["TOTAL_LATAS_AMASSADAS"].pct_change(fill_method=None) * 100
    )
    return result


def agregar_severidade_amassadas(df):
    source = _damage_source(df)
    if "SEVERIDADE_AMASSADAS" not in source.columns:
        source["SEVERIDADE_AMASSADAS"] = pd.cut(
            source["TOTAL_LATAS_AMASSADAS"].fillna(-1),
            bins=[-2, -0.1, 0, 10, 50, 200, float("inf")],
            labels=[
                "Não identificado",
                "Sem amassadas",
                "Baixa: 1 a 10",
                "Média: 11 a 50",
                "Alta: 51 a 200",
                "Crítica: acima de 200",
            ],
        ).astype("string")
    result = (
        source.groupby("SEVERIDADE_AMASSADAS", dropna=False, as_index=False)
        .agg(
            ENTREGAS=("INSPECTION_ID", "nunique"),
            TOTAL_LATAS_AMASSADAS=("TOTAL_LATAS_AMASSADAS", "sum"),
        )
    )
    total = result["ENTREGAS"].sum()
    result["PERCENTUAL_ENTREGAS"] = (
        result["ENTREGAS"] / total * 100 if total else 0.0
    )
    return result


def calcular_resumo_gerencial_amassadas(df):
    source = _damage_source(df)
    monthly = agregar_amassadas_por_mes(source)
    latest = monthly.iloc[-1] if not monthly.empty else None
    previous = monthly.iloc[-2] if len(monthly) > 1 else None
    latest_date = (
        pd.to_datetime(source["DATA_INSPECAO"], errors="coerce").max()
        if "DATA_INSPECAO" in source.columns
        else pd.NaT
    )
    latest_month_end = (
        latest_date + pd.offsets.MonthEnd(0)
        if pd.notna(latest_date)
        else pd.NaT
    )

    def percent_change(current, prior):
        if previous is None or prior in (None, 0) or pd.isna(prior):
            return None
        return (current / prior - 1) * 100

    critical = int(
        (
            source.get(
                "SEVERIDADE_AMASSADAS",
                pd.Series("", index=source.index),
            )
            == "Crítica: acima de 200"
        ).sum()
    )
    if not critical:
        critical = int(source["TOTAL_LATAS_AMASSADAS"].gt(200).sum())

    both = 0
    if "TOTAL_LATAS_FALTANTES" in source.columns:
        both = int(
            (
                pd.to_numeric(
                    source["TOTAL_LATAS_FALTANTES"], errors="coerce"
                ).gt(0)
                & source["TOTAL_LATAS_AMASSADAS"].gt(0)
            ).sum()
        )

    identified = (
        int(source["AMASSADA_DADO_IDENTIFICADO"].fillna(False).sum())
        if "AMASSADA_DADO_IDENTIFICADO" in source.columns
        else int(source["TOTAL_LATAS_AMASSADAS"].notna().sum())
    )
    total_deliveries = int(source["INSPECTION_ID"].nunique())

    return {
        "mes_atual": latest["ANO_MES"] if latest is not None else None,
        "mes_anterior": (
            previous["ANO_MES"] if previous is not None else None
        ),
        "data_mais_recente": latest_date,
        "mes_atual_parcial": (
            bool(latest_date.normalize() < latest_month_end.normalize())
            if pd.notna(latest_date)
            else False
        ),
        "latas_mes_atual": (
            float(latest["TOTAL_LATAS_AMASSADAS"])
            if latest is not None
            else 0.0
        ),
        "variacao_latas_percentual": (
            percent_change(
                float(latest["TOTAL_LATAS_AMASSADAS"]),
                float(previous["TOTAL_LATAS_AMASSADAS"]),
            )
            if latest is not None and previous is not None
            else None
        ),
        "entregas_mes_atual": (
            int(latest["ENTREGAS_COM_AMASSADAS"])
            if latest is not None
            else 0
        ),
        "variacao_entregas_percentual": (
            percent_change(
                float(latest["ENTREGAS_COM_AMASSADAS"]),
                float(previous["ENTREGAS_COM_AMASSADAS"]),
            )
            if latest is not None and previous is not None
            else None
        ),
        "incidencia_mes_atual": (
            float(latest["PERC_ENTREGAS_COM_AMASSADAS"])
            if latest is not None
            else 0.0
        ),
        "variacao_incidencia_pp": (
            float(latest["PERC_ENTREGAS_COM_AMASSADAS"])
            - float(previous["PERC_ENTREGAS_COM_AMASSADAS"])
            if latest is not None and previous is not None
            else None
        ),
        "media_mes_atual": (
            float(latest["MEDIA_POR_ENTREGA_COM_AMASSADAS"])
            if latest is not None
            else 0.0
        ),
        "variacao_media_percentual": (
            percent_change(
                float(latest["MEDIA_POR_ENTREGA_COM_AMASSADAS"]),
                float(previous["MEDIA_POR_ENTREGA_COM_AMASSADAS"]),
            )
            if latest is not None and previous is not None
            else None
        ),
        "casos_criticos": critical,
        "faltantes_e_amassadas": both,
        "cobertura_percentual": (
            identified / total_deliveries * 100
            if total_deliveries
            else 0.0
        ),
    }


def agregar_amassadas_por_cliente(df):
    dimensions = ["DESTINO_CLIENTE"]
    if "CLIENTE_GRUPO" in df.columns:
        dimensions.append("CLIENTE_GRUPO")
    return _agregar_dimensao(df, dimensions)


def _principais_valores(
    df,
    group_column,
    value_column,
    output_column,
    limit=3,
):
    _require_columns(df, [group_column, value_column])
    source = _damage_source(df)
    source = source[source["_COM_AMASSADAS"].eq(1)]
    if source.empty:
        return pd.DataFrame(columns=[group_column, output_column])

    def summarize(values):
        values = values.dropna().astype(str)
        values = values[values.ne("(Não informado)")]
        return ", ".join(values.value_counts().head(limit).index)

    return (
        source.groupby(group_column, dropna=False)[value_column]
        .apply(summarize)
        .reset_index(name=output_column)
    )


def agregar_amassadas_por_transportadora(df):
    result = _agregar_dimensao(df, "TRANSPORTADORA")
    if "DESTINO_CLIENTE" in df.columns:
        result = result.merge(
            _principais_valores(
                df,
                "TRANSPORTADORA",
                "DESTINO_CLIENTE",
                "CLIENTES_ENVOLVIDOS",
            ),
            on="TRANSPORTADORA",
            how="left",
        )
    return result


def agregar_amassadas_por_caminhao(df):
    result = _agregar_dimensao(df, "CAMINHAO_OU_PLACA")
    associations = [
        (
            "TRANSPORTADORA",
            "TRANSPORTADORA_ASSOCIADA",
        ),
        ("DESTINO_CLIENTE", "PRINCIPAIS_CLIENTES"),
        ("ROTA", "PRINCIPAIS_ROTAS"),
    ]
    for value_column, output_column in associations:
        if value_column in df.columns:
            result = result.merge(
                _principais_valores(
                    df,
                    "CAMINHAO_OU_PLACA",
                    value_column,
                    output_column,
                ),
                on="CAMINHAO_OU_PLACA",
                how="left",
            )
    return result


def agregar_amassadas_por_rota(df):
    result = _agregar_dimensao(df, "ROTA")
    associations = [
        ("DESTINO_CLIENTE", "CLIENTES_ENVOLVIDOS"),
        ("TRANSPORTADORA", "TRANSPORTADORAS_ENVOLVIDAS"),
    ]
    for value_column, output_column in associations:
        if value_column in df.columns:
            result = result.merge(
                _principais_valores(
                    df,
                    "ROTA",
                    value_column,
                    output_column,
                ),
                on="ROTA",
                how="left",
            )
    return result
