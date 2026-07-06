import io
import re
from pathlib import Path

import pandas as pd


DEFAULT_SAP_NF_PATH = Path("dados-onsite/NF completa.XLSX")
NF_FILE_PATTERNS = ("NF completa*.xls*", "NF Ball*.xls*")


def normalize_nf(value):
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if not text:
        return pd.NA
    before_dash = text.split("-", 1)[0]
    digits = re.sub(r"\D+", "", before_dash)
    if not digits:
        return pd.NA
    return digits.lstrip("0") or digits


def extract_nf_candidates(text):
    if text is None or pd.isna(text):
        return []
    tokens = re.findall(r"(?<!\d)\d{4,}(?!\d)", str(text))
    normalized = []
    seen = set()
    for token in tokens:
        value = normalize_nf(token)
        if pd.isna(value) or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def find_default_sap_nf_path(directory=Path("dados-onsite")):
    candidates = []
    for pattern in NF_FILE_PATTERNS:
        candidates.extend(Path(directory).glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _find_column(columns, *terms):
    normalized_terms = [term.lower() for term in terms]
    for column in columns:
        text = str(column).strip().lower()
        if all(term in text for term in normalized_terms):
            return column
    return None


def _read_sap_nf_file(source, filename=""):
    suffix = Path(filename).suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(source, dtype=str)
    return pd.read_csv(source, dtype=str, encoding="utf-8-sig")


def load_sap_nf_file(path):
    return _read_sap_nf_file(path, str(path))


def load_sap_nf_upload(contents, filename):
    return _read_sap_nf_file(io.BytesIO(contents), filename)


def prepare_sap_nf_data(source_df):
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        return pd.DataFrame(), {
            "raw_rows": 0,
            "unique_rows": 0,
            "exact_duplicate_rows": 0,
            "unique_nfs": 0,
            "duplicate_nf_rows": 0,
            "missing_nf_rows": 0,
            "quantity_total": 0.0,
            "quantity_column": None,
            "value_column": None,
        }

    source = source_df.copy()
    source.columns = [str(column).strip() for column in source.columns]
    nf_column = _find_column(source.columns, "nota", "fiscal")
    if nf_column is None:
        raise ValueError("A planilha SAP precisa ter uma coluna de Nota Fiscal.")

    raw_rows = len(source)
    exact_duplicate_rows = int(source.duplicated().sum())
    source = source.drop_duplicates().reset_index(drop=True)

    quantity_column = _find_column(source.columns, "sales", "quantity")
    if quantity_column is None:
        quantity_column = _find_column(source.columns, "quantidade")
    value_column = _find_column(source.columns, "valor")
    if value_column is None:
        value_column = _find_column(source.columns, "value")
        if value_column == quantity_column:
            value_column = None

    result = pd.DataFrame()
    result["NF_ORIGINAL"] = source[nf_column].astype("string").str.strip()
    result["NF_BASE"] = result["NF_ORIGINAL"].map(normalize_nf)
    result["DATA_FATURA"] = pd.to_datetime(
        source.get("Data da fatura"), errors="coerce"
    )
    result["UNIDADE_SAP"] = source.get("Unidade", pd.NA)
    result["MATERIAL_SAP"] = source.get("Texto breve material", pd.NA)
    result["GRUPO_MATERIAL_SAP"] = source.get("Grupo de material 5", pd.NA)
    result["CENTRO_SAP"] = source.get("Centro", pd.NA)
    result["QUANTIDADE_SAP"] = (
        pd.to_numeric(source[quantity_column], errors="coerce")
        if quantity_column is not None
        else 0.0
    )
    result["VALOR_NF_SAP"] = (
        pd.to_numeric(source[value_column], errors="coerce")
        if value_column is not None
        else pd.NA
    )
    result = result[result["NF_BASE"].notna()].copy()

    summary = {
        "raw_rows": raw_rows,
        "unique_rows": len(source),
        "exact_duplicate_rows": exact_duplicate_rows,
        "unique_nfs": int(result["NF_BASE"].nunique()),
        "duplicate_nf_rows": int(len(result) - result["NF_BASE"].nunique()),
        "missing_nf_rows": int(raw_rows - len(source_df[source_df[nf_column].notna()])),
        "quantity_total": float(result["QUANTIDADE_SAP"].fillna(0).sum()),
        "quantity_column": quantity_column,
        "value_column": value_column,
    }
    return result, summary


def _join_unique(values, limit=5):
    cleaned = [
        str(value).strip()
        for value in values
        if value is not None and not pd.isna(value) and str(value).strip()
    ]
    unique = list(dict.fromkeys(cleaned))
    if len(unique) > limit:
        return "; ".join(unique[:limit]) + f"; +{len(unique) - limit}"
    return "; ".join(unique)


def aggregate_sap_nf(nf_df):
    if nf_df.empty:
        return pd.DataFrame()
    grouped = nf_df.groupby("NF_BASE", dropna=False)
    return grouped.agg(
        NF_ORIGINAL=("NF_ORIGINAL", "first"),
        LINHAS_SAP=("NF_ORIGINAL", "size"),
        DATA_FATURA=("DATA_FATURA", "min"),
        UNIDADES_SAP=("UNIDADE_SAP", _join_unique),
        CENTROS_SAP=("CENTRO_SAP", _join_unique),
        MATERIAIS_SAP=("MATERIAL_SAP", _join_unique),
        GRUPOS_MATERIAL_SAP=("GRUPO_MATERIAL_SAP", _join_unique),
        QUANTIDADE_SAP=("QUANTIDADE_SAP", "sum"),
        VALOR_NF_SAP=("VALOR_NF_SAP", "sum"),
    ).reset_index()


def build_nf_validation(onsite_df, sap_nf_df, sap_summary=None):
    sap_summary = sap_summary or {}
    sap_unique = aggregate_sap_nf(sap_nf_df)
    sap_bases = set(sap_unique["NF_BASE"].dropna().astype(str))

    pair_rows = []
    onsite_columns = [
        "INSPECTION_ID",
        "INSPECTION_NAME",
        "DATA_INSPECAO",
        "DESTINO_CLIENTE",
        "CLIENTE_GRUPO",
        "TRANSPORTADORA",
        "CAMINHAO_OU_PLACA",
        "ROTA",
        "TOTAL_LATAS_FALTANTES",
        "TOTAL_LATAS_AMASSADAS",
        "WEBLINK",
    ]
    available_columns = [
        column for column in onsite_columns if column in onsite_df.columns
    ]
    for row in onsite_df[available_columns].to_dict("records"):
        for nf_base in extract_nf_candidates(row.get("INSPECTION_NAME")):
            if nf_base not in sap_bases:
                continue
            pair = dict(row)
            pair["NF_BASE"] = nf_base
            pair_rows.append(pair)

    pairs = pd.DataFrame(pair_rows).drop_duplicates(
        ["INSPECTION_ID", "NF_BASE"]
    )
    if not pairs.empty:
        pairs = pairs.merge(sap_unique, on="NF_BASE", how="left")

    if pairs.empty:
        matched = pd.DataFrame(
            columns=["NF_BASE", "INSPECOES_I_AUDITOR", "INSPECOES_LISTA"]
        )
    else:
        matched = (
            pairs.groupby("NF_BASE")
            .agg(
                INSPECOES_I_AUDITOR=("INSPECTION_ID", "nunique"),
                INSPECOES_LISTA=("INSPECTION_ID", _join_unique),
            )
            .reset_index()
        )

    status = sap_unique.merge(matched, on="NF_BASE", how="left")
    status["INSPECOES_I_AUDITOR"] = (
        status["INSPECOES_I_AUDITOR"].fillna(0).astype(int)
    )
    status["STATUS_VALIDACAO"] = status["INSPECOES_I_AUDITOR"].map(
        lambda value: "Encontrada no iAuditor" if value else "Nao encontrada"
    )

    unique_nfs = int(sap_summary.get("unique_nfs", len(status)))
    found_nfs = int(status["INSPECOES_I_AUDITOR"].gt(0).sum())
    missing_nfs = unique_nfs - found_nfs
    quantity_total = float(status["QUANTIDADE_SAP"].fillna(0).sum())
    quantity_found = float(
        status.loc[
            status["INSPECOES_I_AUDITOR"].gt(0), "QUANTIDADE_SAP"
        ].fillna(0).sum()
    )

    kpis = {
        "sap_raw_rows": int(sap_summary.get("raw_rows", len(sap_nf_df))),
        "sap_unique_rows": int(sap_summary.get("unique_rows", len(sap_nf_df))),
        "sap_exact_duplicate_rows": int(
            sap_summary.get("exact_duplicate_rows", 0)
        ),
        "sap_unique_nfs": unique_nfs,
        "sap_duplicate_nf_rows": int(sap_summary.get("duplicate_nf_rows", 0)),
        "found_nfs": found_nfs,
        "missing_nfs": missing_nfs,
        "coverage_percent": (found_nfs / unique_nfs * 100 if unique_nfs else 0.0),
        "sap_quantity_total": quantity_total,
        "sap_quantity_found": quantity_found,
        "sap_quantity_missing": quantity_total - quantity_found,
        "inspection_with_nf": (
            int(pairs["INSPECTION_ID"].nunique()) if not pairs.empty else 0
        ),
        "nf_inspection_pairs": len(pairs),
        "nfs_multiple_inspections": int(
            status["INSPECOES_I_AUDITOR"].gt(1).sum()
        ),
        "inspections_multiple_nfs": (
            int(
                pairs.groupby("INSPECTION_ID")["NF_BASE"]
                .nunique()
                .gt(1)
                .sum()
            )
            if not pairs.empty
            else 0
        ),
    }
    return {
        "kpis": kpis,
        "status": status,
        "missing": status[status["INSPECOES_I_AUDITOR"].eq(0)].copy(),
        "pairs": pairs,
        "sap_unique": sap_unique,
    }
