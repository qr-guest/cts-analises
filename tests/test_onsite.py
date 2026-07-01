import unittest
from unittest.mock import patch

import pandas as pd

from service.onsite_damage import (
    aggregate_damage_items,
    calculate_damage_kpis,
    classify_damage_label,
    enrich_with_damage,
    parse_damage_response,
)
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
    agregar_amassadas_por_cliente,
    agregar_amassadas_por_mes,
    calcular_resumo_gerencial_amassadas,
    calcular_kpis_amassadas,
)
from service.onsite import (
    aggregate_platform_usage,
    aggregate_onsite_dimension,
    calculate_onsite_kpis,
    find_default_onsite_path,
    prepare_onsite_data,
)


class OnsiteMetricsTests(unittest.TestCase):
    def test_kpis_use_explicit_denominators(self):
        df = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B", "C"],
                "TOTAL_LATAS_FALTANTES": [0, 10, 20],
            }
        )
        result = calculate_onsite_kpis(df)
        self.assertEqual(result["total_deliveries"], 3)
        self.assertEqual(result["loss_deliveries"], 2)
        self.assertAlmostEqual(result["loss_rate"], 66.666666, places=5)
        self.assertEqual(result["total_loss"], 30)
        self.assertEqual(result["average_per_delivery"], 10)
        self.assertEqual(result["average_per_loss"], 15)

    def test_zero_denominators_do_not_break(self):
        df = pd.DataFrame(
            columns=["INSPECTION_ID", "TOTAL_LATAS_FALTANTES"]
        )
        result = calculate_onsite_kpis(df)
        self.assertEqual(result["loss_rate"], 0)
        self.assertEqual(result["average_per_delivery"], 0)
        self.assertEqual(result["average_per_loss"], 0)

    def test_prepare_deduplicates_and_clips_negative_loss(self):
        rows = [
            {
                "INSPECTION_ID": "A",
                "DATA_INSPECAO": "2026-06-01 10:00:00.000 -0300",
                "TOTAL_LATAS_FALTANTES": -2,
                "DESTINO_CLIENTE": " Cliente 1 ",
                "CLIENTE_GRUPO": "Grupo",
                "TRANSPORTADORA": "Transp",
                "CAMINHAO_OU_PLACA": "abc1234",
                "ROTA": None,
            },
            {
                "INSPECTION_ID": "A",
                "DATA_INSPECAO": "2026-06-01 10:00:00.000 -0300",
                "TOTAL_LATAS_FALTANTES": -2,
                "DESTINO_CLIENTE": " Cliente 1 ",
                "CLIENTE_GRUPO": "Grupo",
                "TRANSPORTADORA": "Transp",
                "CAMINHAO_OU_PLACA": "abc1234",
                "ROTA": None,
            },
        ]
        prepared, quality = prepare_onsite_data(pd.DataFrame(rows))
        self.assertEqual(len(prepared), 1)
        self.assertEqual(quality["duplicate_rows"], 1)
        self.assertEqual(quality["negative_loss"], 2)
        self.assertEqual(prepared.iloc[0]["TOTAL_LATAS_FALTANTES"], 0)
        self.assertEqual(prepared.iloc[0]["DESTINO_CLIENTE"], "CLIENTE 1")

    def test_dimension_aggregation_calculates_rate(self):
        df = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B", "C"],
                "DESTINO_CLIENTE": ["X", "X", "Y"],
                "ENTREGA_COM_PERDA": [0, 1, 1],
                "TOTAL_LATAS_FALTANTES": [0, 4, 6],
                "DATA_INSPECAO": pd.to_datetime(
                    ["2026-01-01", "2026-01-02", "2026-01-03"]
                ),
            }
        )
        result = aggregate_onsite_dimension(df, "DESTINO_CLIENTE")
        client_x = result[result["DESTINO_CLIENTE"] == "X"].iloc[0]
        self.assertEqual(client_x["ENTREGAS"], 2)
        self.assertEqual(client_x["ENTREGAS_COM_PERDA"], 1)
        self.assertEqual(client_x["TAXA_PERDA"], 50)

    def test_platform_usage_aggregates_group_and_destination(self):
        df = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B", "C"],
                "CLIENTE_GRUPO": ["G1", "G1", "G2"],
                "DESTINO_CLIENTE": ["D1", "D2", "D3"],
                "USUARIO": ["U1", "U2", "U1"],
                "TEMPLATE_NAME": ["T1", "T1", "T2"],
                "ANO_MES": ["2026-01", "2026-02", "2026-02"],
                "DATA_INSPECAO": pd.to_datetime(
                    ["2026-01-01", "2026-02-01", "2026-02-10"]
                ),
            }
        )
        result = aggregate_platform_usage(df, "CLIENTE_GRUPO")
        group = result[result["CLIENTE_GRUPO"] == "G1"].iloc[0]
        self.assertEqual(group["INSPECOES"], 2)
        self.assertEqual(group["USUARIOS"], 2)
        self.assertEqual(group["DESTINOS"], 2)
        self.assertEqual(group["DIAS_SEM_INSPECAO"], 9)

    def test_damage_label_classification_is_strict(self):
        quantitative = classify_damage_label(
            "Latas avariadas no transporte (Unidades)"
        )
        contextual = classify_damage_label(
            "A parte externa do baú não deve conter amassados"
        )
        self.assertTrue(quantitative["LABEL_QUANTITATIVO"])
        self.assertFalse(contextual["LABEL_RELEVANTE"])

    def test_damage_response_handles_numeric_and_text(self):
        numeric = parse_damage_response(" 1.234 unidades ")
        positive = parse_damage_response("SIM")
        negative = parse_damage_response("NÃO")
        self.assertEqual(numeric["QUANTIDADE"], 1234)
        self.assertTrue(positive["OCORRENCIA"])
        self.assertFalse(positive["QUANTIDADE_IDENTIFICADA"])
        self.assertEqual(negative["QUANTIDADE"], 0)

    def test_damage_items_prefer_specific_categories(self):
        items = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "A", "A", "B"],
                "LABEL": [
                    "Latas avariadas no transporte (Unidades)",
                    "Latas avariadas na descarga (Unidades)",
                    "EXISTEM LATAS AMASSADAS? QUANTAS?",
                    "EXISTEM LATAS AMASSADAS? QUANTAS?",
                ],
                "RESPONSE": ["3", "2", "10", "SIM"],
            }
        )
        aggregated, _ = aggregate_damage_items(items)
        inspection_a = aggregated[
            aggregated["INSPECTION_ID"] == "A"
        ].iloc[0]
        inspection_b = aggregated[
            aggregated["INSPECTION_ID"] == "B"
        ].iloc[0]
        self.assertEqual(inspection_a["TOTAL_LATAS_AMASSADAS"], 5)
        self.assertTrue(
            inspection_b["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"]
        )

    def test_damage_enrichment_does_not_turn_unknown_into_zero(self):
        main = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B"],
                "TOTAL_LATAS_FALTANTES": [1, 0],
            }
        )
        summary = pd.DataFrame(
            {
                "LABEL": ["Latas avariadas no transporte (Unidades)"],
                "QTD_LINHAS": [10],
                "QTD_INSPECOES": [10],
                "EXEMPLO_MIN": ["0"],
                "EXEMPLO_MAX": ["5"],
            }
        )
        enriched, context = enrich_with_damage(main, summary, "summary.csv")
        self.assertEqual(context["source_type"], "summary")
        self.assertTrue(enriched["TOTAL_LATAS_AMASSADAS"].isna().all())
        self.assertTrue(
            enriched["SEVERIDADE_AMASSADAS"]
            .eq("Não identificado")
            .all()
        )
        kpis = calculate_damage_kpis(enriched)
        self.assertEqual(kpis["total_damaged"], 0)

    def test_damage_kpi_does_not_use_text_occurrence_in_numeric_average(self):
        df = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B"],
                "TOTAL_LATAS_AMASSADAS": [10, pd.NA],
                "AMASSADA_DADO_IDENTIFICADO": [True, False],
                "ENTREGA_COM_AMASSADA": [1, 1],
            }
        )
        result = calculate_damage_kpis(df)
        self.assertEqual(result["occurrence_deliveries"], 1)
        self.assertEqual(result["average_per_occurrence"], 10)

    def test_enriched_export_preserves_text_occurrence_flag(self):
        main = pd.DataFrame(
            {
                "INSPECTION_ID": ["A"],
                "TOTAL_LATAS_FALTANTES": [0],
                "TOTAL_LATAS_AMASSADAS": [pd.NA],
                "AMASSADA_DADO_IDENTIFICADO": [0],
                "AMASSADA_OCORRENCIA_SEM_QUANTIDADE": [1],
                "ENTREGA_COM_AMASSADA": [1],
            }
        )
        enriched, context = enrich_with_damage(main)
        self.assertEqual(context["source_type"], "enriched")
        self.assertEqual(enriched.iloc[0]["ENTREGA_COM_AMASSADA"], 1)
        self.assertTrue(
            enriched.iloc[0]["AMASSADA_OCORRENCIA_SEM_QUANTIDADE"]
        )
        self.assertEqual(
            enriched.iloc[0]["SEVERIDADE_AMASSADAS"],
            "Ocorrência sem quantidade",
        )

    def test_modular_damage_metrics_and_charts(self):
        df = pd.DataFrame(
            {
                "INSPECTION_ID": ["A", "B", "C"],
                "ANO_MES": ["2026-01", "2026-01", "2026-02"],
                "DATA_INSPECAO": pd.to_datetime(
                    ["2026-01-01", "2026-01-02", "2026-02-01"]
                ),
                "DESTINO_CLIENTE": ["X", "X", "Y"],
                "CLIENTE_GRUPO": ["G1", "G1", "G2"],
                "TRANSPORTADORA": ["T1", "T1", "T2"],
                "CAMINHAO_OU_PLACA": ["P1", "P2", "P3"],
                "ROTA": ["R1", "R1", "R2"],
                "TOTAL_LATAS_FALTANTES": [0, 2, 3],
                "TOTAL_LATAS_AMASSADAS": [5, 0, 20],
                "WEBLINK": ["https://example.com"] * 3,
            }
        )
        kpis = calcular_kpis_amassadas(df)
        monthly = agregar_amassadas_por_mes(df)
        clients = agregar_amassadas_por_cliente(df)
        self.assertEqual(kpis["total_latas_amassadas"], 25)
        self.assertEqual(kpis["entregas_com_amassadas"], 2)
        self.assertEqual(len(monthly), 2)
        self.assertEqual(len(clients), 2)

        chart_functions = [
            chart_evolucao_amassadas,
            chart_incidencia_amassadas,
            chart_top_clientes_amassadas,
            chart_top_transportadoras_amassadas,
            chart_top_caminhoes_amassadas,
            chart_rotas_amassadas,
            chart_severidade_amassadas,
            chart_faltantes_vs_amassadas,
        ]
        for chart_function in chart_functions:
            figure = chart_function(df)
            self.assertGreater(len(figure.data), 0)

        summary = calcular_resumo_gerencial_amassadas(df)
        self.assertEqual(summary["mes_atual"], "2026-02")
        self.assertTrue(summary["mes_atual_parcial"])
        self.assertEqual(summary["casos_criticos"], 0)
        self.assertEqual(summary["faltantes_e_amassadas"], 1)

    def test_default_onsite_source_is_disabled_by_default(self):
        with patch.dict("os.environ", {"ALLOW_LOCAL_DATA": ""}):
            selected = find_default_onsite_path()
        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
