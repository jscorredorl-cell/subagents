from pathlib import Path

import duckdb
from langchain.tools import tool

MAX_ROWS = 50

READERS = {
    ".csv": "read_csv",
    ".tsv": "read_csv",
    ".parquet": "read_parquet",
    ".json": "read_json"
}


def _load_file(file_path: str) -> duckdb.DuckDBPyConnection:
    """Carga el archivo en una tabla `data` dentro de una base DuckDB en memoria."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(
            f"Formato no soportado: {path.suffix}. Usa uno de: {', '.join(READERS)}"
        )

    con = duckdb.connect()
    getattr(con, reader)(str(path)).create("data")
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def _schema(con: duckdb.DuckDBPyConnection) -> str:
    columns = con.sql("DESCRIBE data").fetchall()
    total = con.sql("SELECT COUNT(*) FROM data").fetchone()[0]
    lines = [f'- "{name}" ({dtype})' for name, dtype, *_ in columns]
    return f"Tabla `data` con {total} filas y estas columnas:\n" + "\n".join(lines)


@tool
def describe_file(file_path: str) -> str:
    """Muestra las columnas, sus tipos y unas filas de ejemplo de un archivo de datos.

    Úsala antes de `query_file` para saber cómo escribir la consulta.

    Args:
        file_path: Ruta del archivo (.csv, .tsv, .parquet .json o .xlsx).
    """
    try:
        con = _load_file(file_path)
    except Exception as e:
        return f"Error al leer el archivo: {e}"

    with con:
        sample = con.sql("SELECT * FROM data LIMIT 5").df().to_string(index=False)
        return f"{_schema(con)}\n\nFilas de ejemplo:\n{sample}"


@tool
def query_file(file_path: str, query: str) -> str:
    """Ejecuta una consulta SQL (dialecto DuckDB) sobre un archivo de datos.

    El archivo se carga como la tabla `data`, por ejemplo: SELECT COUNT(*) FROM data.
    Reglas de SQL:
    - Valores de texto y fechas entre comillas simples: WHERE fecha >= '2020-07-12'.
    - Nombres de columnas con espacios o símbolos entre comillas dobles: "Country/Region".
    - Para convertir texto a fecha usa strptime(col, '%m/%d/%Y')::DATE. Si la columna ya
      es DATE, no uses strptime.
    Solo se devuelven las primeras 50 filas del resultado; agrega o filtra en la consulta.

    Args:
        file_path: Ruta del archivo (.csv, .tsv, .parquet o .json).
        query: Consulta SQL que lee de la tabla `data`.
    """
    try:
        con = _load_file(file_path)
    except Exception as e:
        return f"Error al leer el archivo: {e}"

    with con:
        try:
            result = con.sql(query)
        except duckdb.Error as e:
            return f"Error en la consulta: {e}\n\n{_schema(con)}"

        if result is None:
            return "La consulta no devolvió resultados."

        df = result.limit(MAX_ROWS + 1).df()
        if df.empty:
            return "La consulta no devolvió filas."

        text = df.head(MAX_ROWS).to_string(index=False)
        if len(df) > MAX_ROWS:
            text += f"\n\n(Resultado truncado a {MAX_ROWS} filas.)"
        return text
