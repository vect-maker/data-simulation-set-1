"""Unit and integration tests for FastAPI service."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.utils import (
    execute_paginated_query,
    sanitize_row,
    validate_identifier,
)


class TestAPIService(unittest.TestCase):
    """Test suite for the FastAPI service endpoints and utilities."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        """Test GET / returns API metadata and case directories."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("name", data)
        self.assertIn("version", data)
        self.assertIn("documentation", data)
        self.assertIn("cases", data)
        self.assertIn("caso_1_antojitos", data["cases"])
        self.assertIn("caso_2_volcan", data["cases"])
        self.assertIn("caso_3_movigo", data["cases"])

    def test_cors_headers(self):
        """Verify CORS headers allow wildcard origin."""
        response = self.client.get("/", headers={"Origin": "http://example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_openapi_spec(self):
        """Verify OpenAPI 3.x schema contains all 29 table collection routes and 3 detail routes across all cases."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        paths = spec.get("paths", {})

        expected_collection_paths = [
            # Caso 1: Antojitos Express (8 tables)
            "/antojitos/zonas",
            "/antojitos/repartidores",
            "/antojitos/categorias",
            "/antojitos/platillos",
            "/antojitos/promociones",
            "/antojitos/clima",
            "/antojitos/ordenes",
            "/antojitos/detalles",
            # Caso 2: Cooperativa El Volcán (9 tables)
            "/volcan/fincas",
            "/volcan/variedades",
            "/volcan/beneficios",
            "/volcan/cuadrillas",
            "/volcan/clima",
            "/volcan/lotes",
            "/volcan/procesamiento",
            "/volcan/subastas",
            "/volcan/embarques",
            # Caso 3: MoviGo (12 tables)
            "/movigo/quadrants",
            "/movigo/zones",
            "/movigo/users",
            "/movigo/drivers",
            "/movigo/vehicles",
            "/movigo/campaigns",
            "/movigo/weather",
            "/movigo/trips",
            "/movigo/payments",
            "/movigo/ratings",
            "/movigo/cancellations",
            "/movigo/telemetry",
            "/movigo/maintenance",
        ]
        for path in expected_collection_paths:
            self.assertIn(path, paths, f"Missing collection endpoint {path} in OpenAPI spec")
            params = {p["name"] for p in paths[path]["get"].get("parameters", [])}
            self.assertIn("sort", params, f"Endpoint {path} is missing 'sort' query parameter")
            self.assertIn("offset", params, f"Endpoint {path} is missing 'offset' query parameter")
            self.assertIn("limit", params, f"Endpoint {path} is missing 'limit' query parameter")

        for detail_path in ["/antojitos/ordenes/{id_orden}", "/volcan/lotes/{id_lote}", "/movigo/trips/{trip_id}"]:
            self.assertIn(detail_path, paths, f"Missing detail endpoint {detail_path} in OpenAPI spec")

    def test_openapi_spanish_documentation(self):
        """Verify OpenAPI schema contains rich Spanish documentation, tags, and field descriptions for all 30 schemas."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()

        # 1. Global metadata & conventions in Spanish
        info = spec.get("info", {})
        self.assertIn("Proyecto Integrador", info.get("title", ""))
        self.assertIn("Portal de Datos", info.get("description", ""))
        self.assertIn("Convenciones de Uso", info.get("description", ""))
        self.assertNotIn("Asignaturas del Ecosistema", info.get("description", ""))

        # 2. Tag descriptions for each case
        tags = {t["name"]: t.get("description", "") for t in spec.get("tags", [])}
        self.assertIn("Root", tags)
        self.assertIn("Caso 1: Antojitos Express", tags)
        self.assertIn("Caso 2: Cooperativa El Volcán", tags)
        self.assertIn("Caso 3: MoviGo", tags)
        self.assertTrue(len(tags["Caso 1: Antojitos Express"]) > 50)
        self.assertTrue(len(tags["Caso 2: Cooperativa El Volcán"]) > 50)
        self.assertTrue(len(tags["Caso 3: MoviGo"]) > 50)
        self.assertNotIn("Aplicaciones por Asignatura", tags["Caso 1: Antojitos Express"])

        # 3. Path documentation, summary, description and responses
        paths = spec.get("paths", {})
        orden_detail = paths.get("/antojitos/ordenes/{id_orden}", {}).get("get", {})
        self.assertIn("summary", orden_detail)
        self.assertIn("description", orden_detail)
        self.assertNotIn("Relevancia Académica", orden_detail.get("description", ""))
        self.assertIn("200", orden_detail.get("responses", {}))
        self.assertIn("404", orden_detail.get("responses", {}))
        self.assertIn("422", orden_detail.get("responses", {}))

        # 4. Pydantic schema field descriptions in Spanish across all 30 output models
        schemas = spec.get("components", {}).get("schemas", {})
        all_model_names = [
            # Caso 1
            "ZonaOut",
            "RepartidorOut",
            "CategoriaPlatilloOut",
            "PlatilloOut",
            "PromocionOut",
            "ClimaDiarioOut",
            "DetalleOrdenOut",
            "OrdenOut",
            "OrdenDetailOut",
            # Caso 2
            "FincaOut",
            "VariedadCafeOut",
            "BeneficioOut",
            "CuadrillaCorteOut",
            "ClimaCafetaleroOut",
            "LoteAcopioOut",
            "ProcesamientoBeneficioOut",
            "SubastaEspecialOut",
            "EmbarqueExportacionOut",
            # Caso 3
            "QuadrantOut",
            "UrbanZoneOut",
            "UserOut",
            "DriverOut",
            "VehicleOut",
            "IncentiveCampaignOut",
            "QuadrantWeatherOut",
            "TripOut",
            "TripPaymentOut",
            "TripRatingOut",
            "TripCancellationOut",
            "DriverTelemetryOut",
            "VehicleMaintenanceOut",
        ]
        for model_name in all_model_names:
            self.assertIn(model_name, schemas, f"Missing schema '{model_name}' in OpenAPI components")
            properties = schemas[model_name].get("properties", {})
            for prop_name, prop_meta in properties.items():
                self.assertIn(
                    "description",
                    prop_meta,
                    f"Property '{prop_name}' in schema '{model_name}' is missing description.",
                )

    @patch("src.api.utils.fetch_all", return_value=[])
    @patch("src.api.utils.fetch_count", return_value=0)
    def test_all_29_table_endpoints_route_to_expected_tables(self, mock_count, mock_all):
        """Verify all 29 collection endpoints execute paginated queries against their exact database schema and table."""
        endpoint_table_map = [
            # Caso 1: Antojitos Express (raw_staging)
            ("/antojitos/zonas", "raw_staging", "zonas"),
            ("/antojitos/repartidores", "raw_staging", "repartidores"),
            ("/antojitos/categorias", "raw_staging", "categorias_platillo"),
            ("/antojitos/platillos", "raw_staging", "platillos"),
            ("/antojitos/promociones", "raw_staging", "promociones"),
            ("/antojitos/clima", "raw_staging", "clima_diario"),
            ("/antojitos/ordenes", "raw_staging", "ordenes"),
            ("/antojitos/detalles", "raw_staging", "detalle_ordenes"),
            # Caso 2: Cooperativa El Volcán (raw_staging_volcan)
            ("/volcan/fincas", "raw_staging_volcan", "fincas"),
            ("/volcan/variedades", "raw_staging_volcan", "variedades_cafe"),
            ("/volcan/beneficios", "raw_staging_volcan", "beneficios"),
            ("/volcan/cuadrillas", "raw_staging_volcan", "cuadrillas_corte"),
            ("/volcan/clima", "raw_staging_volcan", "clima_zonas_cafetaleras"),
            ("/volcan/lotes", "raw_staging_volcan", "lotes_acopio"),
            ("/volcan/procesamiento", "raw_staging_volcan", "procesamiento_beneficio"),
            ("/volcan/subastas", "raw_staging_volcan", "subastas_especiales"),
            ("/volcan/embarques", "raw_staging_volcan", "embarques_exportacion"),
            # Caso 3: MoviGo (raw_staging_movigo)
            ("/movigo/quadrants", "raw_staging_movigo", "quadrants"),
            ("/movigo/zones", "raw_staging_movigo", "urban_zones"),
            ("/movigo/users", "raw_staging_movigo", "users"),
            ("/movigo/drivers", "raw_staging_movigo", "drivers"),
            ("/movigo/vehicles", "raw_staging_movigo", "vehicles"),
            ("/movigo/campaigns", "raw_staging_movigo", "incentive_campaigns"),
            ("/movigo/weather", "raw_staging_movigo", "quadrant_weather"),
            ("/movigo/trips", "raw_staging_movigo", "trips"),
            ("/movigo/payments", "raw_staging_movigo", "trip_payments"),
            ("/movigo/ratings", "raw_staging_movigo", "trip_ratings"),
            ("/movigo/cancellations", "raw_staging_movigo", "trip_cancellations"),
            ("/movigo/telemetry", "raw_staging_movigo", "driver_telemetry"),
            ("/movigo/maintenance", "raw_staging_movigo", "vehicle_maintenance"),
        ]
        for route, expected_schema, expected_table in endpoint_table_map:
            mock_count.reset_mock()
            mock_all.reset_mock()
            response = self.client.get(f"{route}?limit=5&offset=0")
            self.assertEqual(response.status_code, 200, f"GET {route} failed with {response.status_code}")
            count_sql = mock_count.call_args[0][0]
            self.assertIn(f"FROM {expected_schema}.{expected_table}", count_sql)

    def test_health_check_ok(self):
        """Verify /health returns 200 when database check succeeds."""
        with patch("src.api.main.check_db_health", return_value=(True, None)):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")

    def test_health_check_degraded(self):
        """Verify /health returns 503 when database is unreachable."""
        with patch("src.api.main.check_db_health", return_value=(False, "Connection refused")):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 503)
            data = response.json()
            self.assertEqual(data["status"], "degraded")
            self.assertIn("hint", data)

    def test_validate_identifier(self):
        """Ensure SQL injection attempts in identifiers are rejected."""
        self.assertEqual(validate_identifier("valid_table_name"), "valid_table_name")
        self.assertEqual(validate_identifier("raw_staging_volcan"), "raw_staging_volcan")
        with self.assertRaises(ValueError):
            validate_identifier("table; DROP TABLE users;")
        with self.assertRaises(ValueError):
            validate_identifier("schema.table")

    def test_sanitize_row(self):
        """Ensure decimals and time values are transformed to primitives."""
        import datetime
        from decimal import Decimal

        row = {
            "id": 1,
            "monto": Decimal("150.50"),
            "hora": datetime.time(14, 30, 0),
            "nombre": "Managua",
        }
        clean = sanitize_row(row)
        self.assertEqual(clean["monto"], 150.50)
        self.assertEqual(clean["hora"], "14:30:00")
        self.assertEqual(clean["nombre"], "Managua")

    @patch("src.api.utils.fetch_all")
    @patch("src.api.utils.fetch_count")
    def test_paginated_endpoint_flow(self, mock_count, mock_all):
        """Test pagination wrapper and filtering with mocked database."""
        mock_count.return_value = 1
        mock_all.return_value = [{
            "id_zona": 1,
            "nombre_zona": "Zona Central",
            "latitud": 12.1364,
            "longitud": -86.2514,
            "distancia_km": 3.5,
            "tiempo_base_minutos": 15,
            "tarifa_envio_base": 40.0,
        }]

        response = self.client.get("/antojitos/zonas?offset=0&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["offset"], 0)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(data["items"][0]["id_zona"], 1)

    @patch("src.api.routers.antojitos.fetch_all")
    @patch("src.api.routers.antojitos.fetch_single_resource")
    def test_orden_detail_endpoint(self, mock_fetch_single, mock_fetch_items):
        """Test GET /antojitos/ordenes/{id_orden} returns order with nested items."""
        import datetime
        mock_fetch_single.return_value = {
            "id_orden": 1,
            "id_zona": 1,
            "id_repartidor": 1,
            "id_promocion": None,
            "fecha_hora_creacion": datetime.datetime(2024, 1, 15, 12, 30, 0),
            "fecha_hora_entrega": datetime.datetime(2024, 1, 15, 13, 0, 0),
            "metodo_pago": "efectivo",
            "estado_orden": "entregada",
            "total_orden": 350.0,
            "costo_envio": 40.0,
            "propina": 20.0,
            "notas_entrega": None,
            "comentario_cliente": None,
            "motivo_cancelacion": None,
        }
        mock_fetch_items.return_value = [{
            "id_detalle": 1,
            "id_orden": 1,
            "id_platillo": 1,
            "cantidad": 2,
            "precio_unitario": 145.0,
            "subtotal": 290.0,
        }]

        response = self.client.get("/antojitos/ordenes/1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id_orden"], 1)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id_platillo"], 1)

    @patch("src.api.utils.fetch_one", return_value=None)
    def test_not_found_handling(self, mock_fetch_one):
        """Test GET /{case}/{resource}/{id} returns 404 when item does not exist."""
        response = self.client.get("/volcan/lotes/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_invalid_id_type_handling(self):
        """Test GET /{case}/{resource}/{id} returns 422 when id is not an integer."""
        response = self.client.get("/volcan/lotes/NONEXISTENT-LOT")
        self.assertEqual(response.status_code, 422)

    @patch("src.api.utils.fetch_one")
    def test_single_item_lookup_volcan(self, mock_fetch_one):
        """Test GET /volcan/lotes/{id_lote} returns lot details."""
        import datetime
        mock_fetch_one.return_value = {
            "id_lote": 1,
            "id_finca": 1,
            "id_variedad": 1,
            "id_cuadrilla": 1,
            "fecha_corte": datetime.date(2024, 2, 10),
            "peso_cereza_kg": 1500.0,
            "humedad_porcentaje": 55.0,
            "puntaje_catacion_scaa": 86.5,
            "certificacion": "SHG",
            "notas_catacion": "Notas florales y cítricas.",
            "costo_recoleccion_nio": 3200.0,
            "estado_lote": "recolectado",
        }
        response = self.client.get("/volcan/lotes/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_lote"], 1)

    @patch("src.api.utils.fetch_one")
    def test_single_item_lookup_movigo(self, mock_fetch_one):
        """Test GET /movigo/trips/{trip_id} returns 3NF trip details."""
        import datetime
        mock_fetch_one.return_value = {
            "trip_id": 1,
            "user_id": 1,
            "driver_id": 1,
            "origin_quadrant_id": 15,
            "destination_quadrant_id": 8,
            "origin_latitude": 12.1152,
            "origin_longitude": -86.2548,
            "destination_latitude": 12.1054,
            "destination_longitude": -86.2419,
            "requested_at": datetime.datetime(2024, 3, 5, 8, 15, 0),
            "started_at": datetime.datetime(2024, 3, 5, 8, 20, 0),
            "completed_at": datetime.datetime(2024, 3, 5, 8, 45, 0),
            "distance_km": 7.2,
            "duration_minutes": 25.0,
            "trip_status": "completado",
        }
        response = self.client.get("/movigo/trips/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trip_id"], 1)


if __name__ == "__main__":
    unittest.main()
