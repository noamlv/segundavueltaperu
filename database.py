import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

DB_PATH = Path(__file__).parent / "data" / "electoral.db"


def _load_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st

        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""


def _with_required_ssl(url: str) -> str:
    if not url.startswith(("postgres://", "postgresql://")):
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "sslmode" not in query:
        query["sslmode"] = ["require"]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _safe_dsn_summary(url: str) -> str:
    if not url:
        return "DATABASE_URL no está configurado."
    parsed = urlparse(url)
    return (
        "No se pudo abrir conexión Postgres. "
        f"{_dsn_target_summary(url)} "
        "Verifica que Streamlit Secrets tenga exactamente el mismo DATABASE_URL "
        "que GitHub Actions y que la contraseña esté codificada si contiene "
        "caracteres como @, #, / o :."
    )


def _dsn_target_summary(url: str) -> str:
    if not url:
        return "DATABASE_URL no está configurado."
    parsed = urlparse(url)
    return (
        f"scheme={parsed.scheme or 'vacío'}, "
        f"user={parsed.username or 'vacío'}, "
        f"host={parsed.hostname or 'vacío'}, "
        f"port={parsed.port or 'vacío'}, "
        f"database={parsed.path.lstrip('/') or 'vacío'}, "
        f"sslmode={parse_qs(parsed.query).get('sslmode', ['vacío'])[0]}."
    )


class DbConnection:
    def __init__(self, raw, is_postgres: bool = False):
        self.raw = raw
        self.is_postgres = is_postgres

    def _normalize_sql(self, sql: str) -> str:
        sql = sql.strip()
        if self.is_postgres:
            if sql.upper().startswith("INSERT OR IGNORE INTO"):
                sql = "INSERT INTO" + sql[len("INSERT OR IGNORE INTO"):]
                sql = f"{sql} ON CONFLICT DO NOTHING"
            sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params: tuple = ()):
        sql = self._normalize_sql(sql)
        if self.is_postgres:
            import psycopg2.extras

            cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur
        return self.raw.execute(sql, params)

    def executescript(self, script: str):
        if not self.is_postgres:
            return self.raw.executescript(script)
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def get_conn() -> DbConnection:
    database_url = _with_required_ssl(_load_database_url())
    if database_url.startswith(("postgres://", "postgresql://")):
        import psycopg2

        try:
            conn = psycopg2.connect(database_url, connect_timeout=10)
        except psycopg2.OperationalError as exc:
            detail = str(exc).replace(database_url, "[DATABASE_URL]")
            raise RuntimeError(f"{_safe_dsn_summary(database_url)} Detalle técnico: {detail}") from None
        return DbConnection(conn, is_postgres=True)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return DbConnection(conn)


def insert_scrape_run(conn: DbConnection, source: str, scraped_at: str) -> int:
    if conn.is_postgres:
        row = conn.execute(
            "INSERT INTO scrape_runs (source, scraped_at) VALUES (?, ?) RETURNING id",
            (source, scraped_at),
        ).fetchone()
        return row["id"]
    cur = conn.execute("INSERT INTO scrape_runs (source, scraped_at) VALUES (?, ?)", (source, scraped_at))
    return cur.lastrowid


def init_db():
    conn = get_conn()
    sqlite_schema = """
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT    NOT NULL DEFAULT 'jne',
            scraped_at  TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kpi_measures (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       INTEGER NOT NULL REFERENCES scrape_runs(id),
            measure_name TEXT    NOT NULL,
            value        TEXT    NOT NULL,
            UNIQUE(run_id, measure_name)
        );

        CREATE TABLE IF NOT EXISTS jje_detail (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                          INTEGER NOT NULL REFERENCES scrape_runs(id),
            jee_name                        TEXT    NOT NULL,
            expedientes_completos           INTEGER,
            expedientes_ajustado            INTEGER,
            pct_pronunciamientos_sin_total  REAL,
            cantidad_actas_atendidas        INTEGER,
            UNIQUE(run_id, jee_name)
        );

        CREATE TABLE IF NOT EXISTS actas_by_type (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            tipo_eleccion   TEXT    NOT NULL,
            actas_completas INTEGER,
            UNIQUE(run_id, tipo_eleccion)
        );

        CREATE TABLE IF NOT EXISTS jee_porcentaje (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            jee_name        TEXT    NOT NULL,
            porcentaje      REAL,
            UNIQUE(run_id, jee_name)
        );

        CREATE TABLE IF NOT EXISTS onpe_totals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            actas_contabilizadas REAL,
            contabilizadas  INTEGER,
            total_actas     INTEGER,
            participacion   REAL,
            votos_emitidos  INTEGER,
            votos_validos   INTEGER,
            enviadas_jee    INTEGER,
            actas_enviadas_jee REAL,
            pendientes_jee  INTEGER,
            actas_pendientes_jee REAL,
            porcentaje_votos_validos REAL,
            porcentaje_votos_emitidos REAL,
            fec_actualizacion TEXT
        );

        CREATE TABLE IF NOT EXISTS onpe_mesas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            instaladas      INTEGER,
            no_instaladas   INTEGER,
            pendientes      INTEGER
        );

        CREATE TABLE IF NOT EXISTS onpe_candidates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            nombre_partido  TEXT    NOT NULL,
            codigo_partido  TEXT,
            nombre_candidato TEXT,
            dni_candidato   TEXT,
            votos_validos   INTEGER,
            pct_validos     REAL,
            pct_emitidos    REAL,
            UNIQUE(run_id, nombre_partido, nombre_candidato)
        );

        CREATE INDEX IF NOT EXISTS idx_kpi_measure ON kpi_measures(measure_name, run_id);
        CREATE INDEX IF NOT EXISTS idx_jje_detail_run  ON jje_detail(run_id);
        CREATE INDEX IF NOT EXISTS idx_actas_run       ON actas_by_type(run_id);
        CREATE INDEX IF NOT EXISTS idx_onpe_candidates_run ON onpe_candidates(run_id);
    """
    postgres_schema = """
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id          SERIAL PRIMARY KEY,
            source      TEXT    NOT NULL DEFAULT 'jne',
            scraped_at  TEXT    NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS kpi_measures (
            id           SERIAL PRIMARY KEY,
            run_id       INTEGER NOT NULL REFERENCES scrape_runs(id),
            measure_name TEXT    NOT NULL,
            value        TEXT    NOT NULL,
            UNIQUE(run_id, measure_name)
        );

        CREATE TABLE IF NOT EXISTS jje_detail (
            id                              SERIAL PRIMARY KEY,
            run_id                          INTEGER NOT NULL REFERENCES scrape_runs(id),
            jee_name                        TEXT    NOT NULL,
            expedientes_completos           INTEGER,
            expedientes_ajustado            INTEGER,
            pct_pronunciamientos_sin_total  REAL,
            cantidad_actas_atendidas        INTEGER,
            UNIQUE(run_id, jee_name)
        );

        CREATE TABLE IF NOT EXISTS actas_by_type (
            id              SERIAL PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            tipo_eleccion   TEXT    NOT NULL,
            actas_completas INTEGER,
            UNIQUE(run_id, tipo_eleccion)
        );

        CREATE TABLE IF NOT EXISTS jee_porcentaje (
            id              SERIAL PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            jee_name        TEXT    NOT NULL,
            porcentaje      REAL,
            UNIQUE(run_id, jee_name)
        );

        CREATE TABLE IF NOT EXISTS onpe_totals (
            id              SERIAL PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            actas_contabilizadas REAL,
            contabilizadas  INTEGER,
            total_actas     INTEGER,
            participacion   REAL,
            votos_emitidos  INTEGER,
            votos_validos   INTEGER,
            enviadas_jee    INTEGER,
            actas_enviadas_jee REAL,
            pendientes_jee  INTEGER,
            actas_pendientes_jee REAL,
            porcentaje_votos_validos REAL,
            porcentaje_votos_emitidos REAL,
            fec_actualizacion TEXT
        );

        CREATE TABLE IF NOT EXISTS onpe_mesas (
            id              SERIAL PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            instaladas      INTEGER,
            no_instaladas   INTEGER,
            pendientes      INTEGER
        );

        CREATE TABLE IF NOT EXISTS onpe_candidates (
            id              SERIAL PRIMARY KEY,
            run_id          INTEGER NOT NULL REFERENCES scrape_runs(id),
            nombre_partido  TEXT    NOT NULL,
            codigo_partido  TEXT,
            nombre_candidato TEXT,
            dni_candidato   TEXT,
            votos_validos   INTEGER,
            pct_validos     REAL,
            pct_emitidos    REAL,
            UNIQUE(run_id, nombre_partido, nombre_candidato)
        );

        CREATE INDEX IF NOT EXISTS idx_kpi_measure ON kpi_measures(measure_name, run_id);
        CREATE INDEX IF NOT EXISTS idx_jje_detail_run  ON jje_detail(run_id);
        CREATE INDEX IF NOT EXISTS idx_actas_run       ON actas_by_type(run_id);
        CREATE INDEX IF NOT EXISTS idx_onpe_candidates_run ON onpe_candidates(run_id);
    """
    conn.executescript(postgres_schema if conn.is_postgres else sqlite_schema)
    conn.commit()

    # Migrate existing databases after the base schema exists. PostgreSQL keeps
    # a transaction aborted after a failed DDL statement, so use IF NOT EXISTS
    # there and keep SQLite on the older try/ignore path.
    if conn.is_postgres:
        migrations = [
            "ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'jne'",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS enviadas_jee INTEGER",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS actas_enviadas_jee REAL",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS pendientes_jee INTEGER",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS actas_pendientes_jee REAL",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS porcentaje_votos_validos REAL",
            "ALTER TABLE onpe_totals ADD COLUMN IF NOT EXISTS porcentaje_votos_emitidos REAL",
        ]
        for migration in migrations:
            conn.execute(migration)
    else:
        try:
            conn.execute("ALTER TABLE scrape_runs ADD COLUMN source TEXT NOT NULL DEFAULT 'jne'")
        except Exception:
            pass
        for col in [
            "enviadas_jee INTEGER",
            "actas_enviadas_jee REAL",
            "pendientes_jee INTEGER",
            "actas_pendientes_jee REAL",
            "porcentaje_votos_validos REAL",
            "porcentaje_votos_emitidos REAL",
        ]:
            try:
                conn.execute(f"ALTER TABLE onpe_totals ADD COLUMN {col}")
            except Exception:
                pass

    conn.commit()
    conn.close()


def save_run(raw: dict, source: str = "jne") -> int:
    """Persist a JNE scraper result into the database. Returns the run_id."""
    init_db()
    conn = get_conn()
    ts = raw.get("_meta", {}).get("timestamp", datetime.now().isoformat())

    run_id = insert_scrape_run(conn, source, ts)

    # KPIs (handle duplicates)
    seen: dict[str, int] = {}
    for m in raw.get("measures", []):
        name = m.get("name", "")
        val = str(m.get("value", ""))
        key = name
        seen[key] = seen.get(key, -1) + 1
        if seen[key] > 0:
            key = f"{name}__{seen[key]}"
        try:
            conn.execute(
                "INSERT OR IGNORE INTO kpi_measures (run_id, measure_name, value) VALUES (?, ?, ?)",
                (run_id, key, val),
            )
        except Exception:
            pass

    # Tables
    for table in raw.get("tables", []):
        cols = table.get("columns", [])
        rows = table.get("rows", [])
        tname = table.get("name", "")

        if "ExpedientesCompletos" in tname or "Expedientes_Ajustado" in tname:
            for row in rows:
                conn.execute(
                    """INSERT OR IGNORE INTO jje_detail
                       (run_id, jee_name, expedientes_completos, expedientes_ajustado,
                        pct_pronunciamientos_sin_total, cantidad_actas_atendidas)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (run_id, row[0], row[1], row[2], row[3] if len(row) > 3 else None,
                     row[4] if len(row) > 4 else None),
                )

        elif "PorcentajePronunciamientos" in tname and len(cols) == 2:
            for row in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO jee_porcentaje (run_id, jee_name, porcentaje) VALUES (?, ?, ?)",
                    (run_id, row[0], row[1]),
                )

        elif "ActasCompletas" in tname:
            for row in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO actas_by_type (run_id, tipo_eleccion, actas_completas) VALUES (?, ?, ?)",
                    (run_id, row[0], row[1]),
                )

    conn.commit()
    conn.close()
    return run_id


def get_latest_run() -> int | None:
    conn = get_conn()
    row = conn.execute("SELECT MAX(id) AS id FROM scrape_runs").fetchone()
    conn.close()
    return row["id"] if row and row["id"] else None


def get_run_timestamps() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, scraped_at, source FROM scrape_runs ORDER BY id"
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "scraped_at": r["scraped_at"], "source": r["source"]} for r in rows]


def get_kpis(run_id: int | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if run_id:
        rows = conn.execute(
            "SELECT measure_name, value FROM kpi_measures WHERE run_id = ? ORDER BY measure_name",
            (run_id,),
        ).fetchall()
    else:
        subq = "(SELECT MAX(id) FROM scrape_runs)"
        rows = conn.execute(
            f"SELECT measure_name, value FROM kpi_measures WHERE run_id = {subq} ORDER BY measure_name",
        ).fetchall()
    conn.close()
    return rows


def get_jje_detail(run_id: int | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if run_id:
        rows = conn.execute(
            "SELECT * FROM jje_detail WHERE run_id = ? ORDER BY jee_name", (run_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jje_detail WHERE run_id = (SELECT MAX(id) FROM scrape_runs) ORDER BY jee_name",
        ).fetchall()
    conn.close()
    return rows


def get_actas_by_type(run_id: int | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if run_id:
        rows = conn.execute(
            "SELECT * FROM actas_by_type WHERE run_id = ? ORDER BY tipo_eleccion", (run_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM actas_by_type WHERE run_id = (SELECT MAX(id) FROM scrape_runs) ORDER BY tipo_eleccion",
        ).fetchall()
    conn.close()
    return rows


def get_jee_porcentaje(run_id: int | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if run_id:
        rows = conn.execute(
            "SELECT * FROM jee_porcentaje WHERE run_id = ? ORDER BY jee_name", (run_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jee_porcentaje WHERE run_id = (SELECT MAX(id) FROM scrape_runs) ORDER BY jee_name",
        ).fetchall()
    conn.close()
    return rows


def get_kpi_history(measure_name: str, limit: int = 168) -> list[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at, k.value
           FROM kpi_measures k
           JOIN scrape_runs r ON r.id = k.run_id
           WHERE k.measure_name = ?
           ORDER BY r.id
           LIMIT ?""",
        (measure_name, limit),
    ).fetchall()
    conn.close()
    return rows


def get_jee_detail_history(jee_name: str, limit: int = 168) -> list[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at, d.expedientes_completos, d.expedientes_ajustado,
                  d.pct_pronunciamientos_sin_total, d.cantidad_actas_atendidas
           FROM jje_detail d
           JOIN scrape_runs r ON r.id = d.run_id
           WHERE d.jee_name = ?
           ORDER BY r.id
           LIMIT ?""",
        (jee_name, limit),
    ).fetchall()
    conn.close()
    return rows


def get_jee_totals_history(limit: int = 168) -> list[sqlite3.Row]:
    """Aggregated totals across all JEEs per run for historical view."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at,
                  SUM(d.expedientes_completos)   AS total_expedientes,
                  SUM(d.expedientes_ajustado)    AS total_ajustado,
                  SUM(d.cantidad_actas_atendidas) AS total_atendidas
           FROM jje_detail d
           JOIN scrape_runs r ON r.id = d.run_id
           GROUP BY r.id
           ORDER BY r.id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


# ─── ONPE ─────────────────────────────────────────────────────────────


def save_run_onpe(raw: dict) -> int:
    """Persist ONPE scraper result into the database. Returns the run_id."""
    init_db()
    conn = get_conn()
    ts = raw.get("_meta", {}).get("timestamp", datetime.now().isoformat())

    run_id = insert_scrape_run(conn, "onpe", ts)

    totals = raw.get("totals") or {}
    if totals:
        conn.execute(
            """INSERT INTO onpe_totals
               (run_id, actas_contabilizadas, contabilizadas, total_actas,
                participacion, votos_emitidos, votos_validos,
                enviadas_jee, actas_enviadas_jee, pendientes_jee, actas_pendientes_jee,
                porcentaje_votos_validos, porcentaje_votos_emitidos,
                fec_actualizacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id,
             totals.get("actasContabilizadas"),
             totals.get("contabilizadas"),
             totals.get("totalActas"),
             totals.get("participacionCiudadana"),
             totals.get("totalVotosEmitidos"),
             totals.get("totalVotosValidos"),
             totals.get("enviadasJee"),
             totals.get("actasEnviadasJee"),
             totals.get("pendientesJee"),
             totals.get("actasPendientesJee"),
             totals.get("porcentajeVotosValidos"),
             totals.get("porcentajeVotosEmitidos"),
             totals.get("fechaActualizacion")),
        )

    mesas = raw.get("mesas") or {}
    if mesas:
        conn.execute(
            """INSERT INTO onpe_mesas (run_id, instaladas, no_instaladas, pendientes)
               VALUES (?, ?, ?, ?)""",
            (run_id,
             mesas.get("mesasInstaladas"),
             mesas.get("mesasNoInstaladas"),
             mesas.get("mesasPendientes")),
        )

    for c in (raw.get("candidates") or []):
        if not isinstance(c, dict):
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO onpe_candidates
                   (run_id, nombre_partido, codigo_partido, nombre_candidato,
                    dni_candidato, votos_validos, pct_validos, pct_emitidos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id,
                 c.get("nombreAgrupacionPolitica"),
                 c.get("codigoAgrupacionPolitica"),
                 c.get("nombreCandidato"),
                 c.get("dniCandidato"),
                 c.get("totalVotosValidos"),
                 c.get("porcentajeVotosValidos"),
                 c.get("porcentajeVotosEmitidos")),
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    return run_id


def get_onpe_latest() -> dict:
    """Get latest ONPE totals and candidates."""
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(id) AS id FROM scrape_runs WHERE source = 'onpe'"
    ).fetchone()
    run_id = row["id"] if row and row["id"] else None
    if not run_id:
        conn.close()
        return {}

    totals = conn.execute(
        "SELECT * FROM onpe_totals WHERE run_id = ?", (run_id,)
    ).fetchone()
    mesas = conn.execute(
        "SELECT * FROM onpe_mesas WHERE run_id = ?", (run_id,)
    ).fetchone()
    candidates = conn.execute(
        "SELECT * FROM onpe_candidates WHERE run_id = ? ORDER BY votos_validos DESC", (run_id,)
    ).fetchall()
    conn.close()
    return {
        "totals": dict(totals) if totals else {},
        "mesas": dict(mesas) if mesas else {},
        "candidates": [dict(r) for r in candidates],
    }


def get_onpe_totals_history(limit: int = 500) -> list[sqlite3.Row]:
    """All ONPE totals over time for line charts."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at, t.*
           FROM onpe_totals t
           JOIN scrape_runs r ON r.id = t.run_id
           ORDER BY r.id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def get_onpe_run_summary_history(limit: int = 500) -> list[sqlite3.Row]:
    """One ONPE summary row per run, using totals when present and candidates as fallback."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT
              r.id AS run_id,
              r.scraped_at,
              t.actas_contabilizadas,
              t.contabilizadas,
              t.total_actas,
              t.participacion,
              t.votos_emitidos,
              t.votos_validos,
              COALESCE(t.votos_validos, c.votos_validos_fallback) AS votos_validos_fallback,
              c.votos_blancos,
              c.votos_nulos,
              c.filas_candidaturas
           FROM scrape_runs r
           LEFT JOIN onpe_totals t ON t.run_id = r.id
           LEFT JOIN (
               SELECT
                   run_id,
                   SUM(CASE
                       WHEN UPPER(COALESCE(nombre_partido, '')) NOT LIKE '%BLANCO%'
                        AND UPPER(COALESCE(nombre_partido, '')) NOT LIKE '%NULO%'
                       THEN COALESCE(votos_validos, 0)
                       ELSE 0
                   END) AS votos_validos_fallback,
                   SUM(CASE
                       WHEN UPPER(COALESCE(nombre_partido, '')) LIKE '%BLANCO%'
                       THEN COALESCE(votos_validos, 0)
                       ELSE 0
                   END) AS votos_blancos,
                   SUM(CASE
                       WHEN UPPER(COALESCE(nombre_partido, '')) LIKE '%NULO%'
                       THEN COALESCE(votos_validos, 0)
                       ELSE 0
                   END) AS votos_nulos,
                   COUNT(id) AS filas_candidaturas
               FROM onpe_candidates
               GROUP BY run_id
           ) c ON c.run_id = r.id
           WHERE r.source = 'onpe'
           ORDER BY r.id
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def get_onpe_candidate_history(candidate_name: str, limit: int = 500) -> list[sqlite3.Row]:
    """Vote history for a specific candidate across runs."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at, c.votos_validos, c.pct_validos, c.pct_emitidos
           FROM onpe_candidates c
           JOIN scrape_runs r ON r.id = c.run_id
           WHERE c.nombre_candidato LIKE ? OR c.nombre_partido LIKE ?
           ORDER BY r.id
           LIMIT ?""",
        (f"%{candidate_name}%", f"%{candidate_name}%", limit),
    ).fetchall()
    conn.close()
    return rows


def get_onpe_candidate_history_by_run(limit: int = 500) -> list[sqlite3.Row]:
    """All candidate results per run, pivoted by run_id, for multi-line charts."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.scraped_at, c.nombre_partido, c.nombre_candidato,
                  c.votos_validos, c.pct_validos, c.pct_emitidos
           FROM onpe_candidates c
           JOIN scrape_runs r ON r.id = c.run_id
           WHERE c.nombre_candidato != '' AND c.votos_validos > 0
           ORDER BY r.id, c.votos_validos DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows
