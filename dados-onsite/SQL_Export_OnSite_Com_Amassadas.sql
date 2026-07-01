WITH INSPECOES_PERIODO AS (
    SELECT
        ID AS INSPECTION_ID,
        NAME AS INSPECTION_NAME,
        TEMPLATE_ID,
        TEMPLATE_NAME,
        CREATOR_ID,
        SITE_ID,
        ASSET_ID,
        COALESCE(CONDUCTED_DATE, COMPLETED_DATE, CREATED_DATE) AS DATA_INSPECAO,
        WEBLINK
    FROM DW_STAGING.SAFETY_CULTURE.INSPECTIONS
    WHERE COALESCE(CONDUCTED_DATE, COMPLETED_DATE, CREATED_DATE)
        >= DATEADD(MONTH, -12, CURRENT_DATE())
),
ITENS_RELEVANTES AS (
    SELECT
        ii.INSPECTION_ID,
        ii.LABEL,
        LOWER(TRIM(ii.LABEL)) AS LABEL_LOWER,
        TRIM(ii.RESPONSE) AS RESPONSE,
        TRY_TO_DECIMAL(
            REPLACE(
                REGEXP_REPLACE(TRIM(ii.RESPONSE), '[^0-9,.-]', ''),
                ',',
                '.'
            ),
            18,
            2
        ) AS RESPONSE_NUMERICA
    FROM DW_STAGING.SAFETY_CULTURE.INSPECTION_ITEMS ii
    INNER JOIN INSPECOES_PERIODO ip
        ON ii.INSPECTION_ID = ip.INSPECTION_ID
    WHERE ii.RESPONSE IS NOT NULL
      AND (
            LOWER(ii.LABEL) LIKE '%destino%'
         OR LOWER(ii.LABEL) LIKE '%cliente%'
         OR LOWER(ii.LABEL) LIKE '%latas faltantes%'
         OR LOWER(ii.LABEL) LIKE '%transportadora%'
         OR LOWER(ii.LABEL) LIKE '%caminh%'
         OR LOWER(ii.LABEL) LIKE '%placa%'
         OR LOWER(ii.LABEL) LIKE '%rota%'
         OR LOWER(ii.LABEL) LIKE 'latas avariadas no transporte%'
         OR LOWER(ii.LABEL) LIKE 'latas avariadas na descarga%'
         OR LOWER(ii.LABEL) LIKE 'latas avariadas na movimentação externa%'
         OR LOWER(ii.LABEL) LIKE 'existem latas amassadas%quantas%'
      )
),
CAMPOS_POR_INSPECAO AS (
    SELECT
        INSPECTION_ID,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%destino%' THEN RESPONSE END
        ) AS DESTINO_CLIENTE,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%cliente%' THEN RESPONSE END
        ) AS CLIENTE_INFORMADO,
        SUM(
            CASE
                WHEN LABEL_LOWER LIKE '%latas faltantes%'
                    THEN COALESCE(RESPONSE_NUMERICA, 0)
                ELSE 0
            END
        ) AS TOTAL_LATAS_FALTANTES,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%transportadora%' THEN RESPONSE END
        ) AS TRANSPORTADORA,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%caminh%' THEN RESPONSE END
        ) AS CAMINHAO,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%placa%' THEN RESPONSE END
        ) AS PLACA,
        MAX(
            CASE WHEN LABEL_LOWER LIKE '%rota%' THEN RESPONSE END
        ) AS ROTA,
        COUNT_IF(
               LABEL_LOWER LIKE 'latas avariadas no transporte%'
            OR LABEL_LOWER LIKE 'latas avariadas na descarga%'
            OR LABEL_LOWER LIKE 'latas avariadas na movimentação externa%'
        ) AS QTD_LABELS_AMASSADAS_ESPECIFICOS,
        COUNT_IF(
            (
                   LABEL_LOWER LIKE 'latas avariadas no transporte%'
                OR LABEL_LOWER LIKE 'latas avariadas na descarga%'
                OR LABEL_LOWER LIKE 'latas avariadas na movimentação externa%'
            )
            AND RESPONSE_NUMERICA IS NOT NULL
        ) AS QTD_RESPOSTAS_AMASSADAS_ESPECIFICAS_VALIDAS,
        SUM(
            CASE
                WHEN (
                       LABEL_LOWER LIKE 'latas avariadas no transporte%'
                    OR LABEL_LOWER LIKE 'latas avariadas na descarga%'
                    OR LABEL_LOWER LIKE 'latas avariadas na movimentação externa%'
                )
                    THEN COALESCE(RESPONSE_NUMERICA, 0)
                ELSE 0
            END
        ) AS TOTAL_AMASSADAS_ESPECIFICAS,
        MAX(
            CASE
                WHEN LABEL_LOWER LIKE 'existem latas amassadas%quantas%'
                    THEN RESPONSE_NUMERICA
            END
        ) AS TOTAL_AMASSADAS_GERAL,
        COUNT_IF(
            LABEL_LOWER LIKE 'existem latas amassadas%quantas%'
            AND RESPONSE_NUMERICA IS NOT NULL
        ) AS QTD_RESPOSTAS_AMASSADAS_GERAIS_VALIDAS,
        MAX(
            CASE
                WHEN LABEL_LOWER LIKE 'existem latas amassadas%quantas%'
                 AND UPPER(
                        TRANSLATE(
                            RESPONSE,
                            'ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇÑ',
                            'AAAAEEEIIIOOOOUUUCN'
                        )
                     ) IN (
                        'SIM',
                        'YES',
                        'REPROVADO',
                        'NOK',
                        'NAO OK',
                        'N/OK',
                        'NAO CONFORME'
                     )
                    THEN 1
                ELSE 0
            END
        ) AS OCORRENCIA_AMASSADA_TEXTUAL
    FROM ITENS_RELEVANTES
    GROUP BY INSPECTION_ID
),
BASE_CALCULADA AS (
    SELECT
        ip.INSPECTION_ID,
        ip.INSPECTION_NAME,
        DATE_TRUNC('MONTH', ip.DATA_INSPECAO) AS INICIO_MES,
        TO_CHAR(DATE_TRUNC('MONTH', ip.DATA_INSPECAO), 'YYYY-MM') AS ANO_MES,
        ip.DATA_INSPECAO,
        COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO) AS DESTINO_CLIENTE,
        CASE
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%ambev%' THEN 'AMBEV'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%heineken%' THEN 'HEINEKEN'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%coca%' THEN 'COCA'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%femsa%' THEN 'FEMSA'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%solar%' THEN 'SOLAR'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%frutal%' THEN 'FRUTAL'
            WHEN LOWER(COALESCE(c.DESTINO_CLIENTE, c.CLIENTE_INFORMADO, ''))
                LIKE '%bebidas%' THEN 'BEBIDAS'
            ELSE 'OUTROS'
        END AS CLIENTE_GRUPO,
        c.TRANSPORTADORA,
        COALESCE(c.CAMINHAO, c.PLACA) AS CAMINHAO_OU_PLACA,
        c.ROTA,
        COALESCE(c.TOTAL_LATAS_FALTANTES, 0) AS TOTAL_LATAS_FALTANTES,
        CASE
            WHEN COALESCE(c.TOTAL_LATAS_FALTANTES, 0) > 0 THEN 1
            ELSE 0
        END AS ENTREGA_COM_PERDA,
        CASE
            WHEN c.QTD_LABELS_AMASSADAS_ESPECIFICOS > 0
             AND c.QTD_RESPOSTAS_AMASSADAS_ESPECIFICAS_VALIDAS > 0
                THEN c.TOTAL_AMASSADAS_ESPECIFICAS
            WHEN c.QTD_RESPOSTAS_AMASSADAS_GERAIS_VALIDAS > 0
                THEN c.TOTAL_AMASSADAS_GERAL
            ELSE NULL
        END AS TOTAL_LATAS_AMASSADAS,
        CASE
            WHEN c.QTD_RESPOSTAS_AMASSADAS_ESPECIFICAS_VALIDAS > 0
              OR c.QTD_RESPOSTAS_AMASSADAS_GERAIS_VALIDAS > 0
                THEN 1
            ELSE 0
        END AS AMASSADA_DADO_IDENTIFICADO,
        CASE
            WHEN (
                    CASE
                        WHEN c.QTD_LABELS_AMASSADAS_ESPECIFICOS > 0
                         AND c.QTD_RESPOSTAS_AMASSADAS_ESPECIFICAS_VALIDAS > 0
                            THEN c.TOTAL_AMASSADAS_ESPECIFICAS
                        WHEN c.QTD_RESPOSTAS_AMASSADAS_GERAIS_VALIDAS > 0
                            THEN c.TOTAL_AMASSADAS_GERAL
                    END
                 ) > 0
              OR c.OCORRENCIA_AMASSADA_TEXTUAL = 1
                THEN 1
            ELSE 0
        END AS ENTREGA_COM_AMASSADA,
        CASE
            WHEN c.OCORRENCIA_AMASSADA_TEXTUAL = 1
             AND c.QTD_RESPOSTAS_AMASSADAS_ESPECIFICAS_VALIDAS = 0
             AND c.QTD_RESPOSTAS_AMASSADAS_GERAIS_VALIDAS = 0
                THEN 1
            ELSE 0
        END AS AMASSADA_OCORRENCIA_SEM_QUANTIDADE,
        ip.TEMPLATE_ID,
        ip.TEMPLATE_NAME,
        ip.CREATOR_ID,
        u.FIRSTNAME,
        u.LASTNAME,
        u.EMAIL,
        ip.SITE_ID,
        ip.ASSET_ID,
        ip.WEBLINK
    FROM INSPECOES_PERIODO ip
    LEFT JOIN CAMPOS_POR_INSPECAO c
        ON ip.INSPECTION_ID = c.INSPECTION_ID
    LEFT JOIN DW_STAGING.SAFETY_CULTURE.USERS u
        ON ip.CREATOR_ID = u.ID
)
SELECT
    *,
    CASE
        WHEN ENTREGA_COM_PERDA = 1 AND ENTREGA_COM_AMASSADA = 1 THEN 1
        ELSE 0
    END AS ENTREGA_COM_FALTANTE_E_AMASSADA
FROM BASE_CALCULADA
WHERE DESTINO_CLIENTE IS NOT NULL
   OR TOTAL_LATAS_FALTANTES > 0
   OR ENTREGA_COM_AMASSADA = 1
ORDER BY DATA_INSPECAO DESC;
