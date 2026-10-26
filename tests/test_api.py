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
        """Verify OpenAPI 3.x schema contains expected route groups."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        paths = spec.get("paths", {})

        # Verify endpoints for each case exist in spec
        self.assertIn("/antojitos/ordenes", paths)
        self.assertIn("/antojitos/zonas", paths)
        self.assertIn("/volcan/fincas", paths)
        self.assertIn("/volcan/lotes", paths)
        self.assertIn("/movigo/quadrants", paths)
        self.assertIn("/movigo/zones", paths)
        self.assertIn("/movigo/trips", paths)

    def test_openapi_spanish_documentation(self):
        """Verify OpenAPI schema contains rich Spanish documentation, tags, and field descriptions."""
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

        # 4. Pydantic schema field descriptions in Spanish
        schemas = spec.get("components", {}).get("schemas", {})
        for model_name in ["ZonaOut", "PlatilloOut", "FincaOut", "LoteAcopioOut", "QuadrantOut", "QuadrantWeatherOut", "TripOut"]:
            self.assertIn(model_name, schemas)
            properties = schemas[model_name].get("properties", {})
            for prop_name, prop_meta in properties.items():
                self.assertIn(
                    "description",
                    prop_meta,
                    f"Property '{prop_name}' in schema '{model_name}' is missing description.",
                )

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
        """Test GET /movigo/trips/{trip_id} returns trip details."""
        import datetime
        mock_fetch_one.return_value = {
            "trip_id": 1,
            "user_id": 1,
            "driver_id": 1,
            "origin_zone_id": 1,
            "destination_zone_id": 2,
            "origin_quadrant_id": 15,
            "destination_quadrant_id": 8,
            "origin_latitude": 12.1152,
            "origin_longitude": -86.2548,
            "destination_latitude": 12.1054,
            "destination_longitude": -86.2419,
            "requested_at": datetime.datetime(2024, 3, 5, 8, 15, 0),
            "started_at": datetime.datetime(2024, 3, 5, 8, 20, 0),
            "completed_at": datetime.datetime(2024, 3, 5, 8, 45, 0),
            "wait_time_minutes": 5.0,
            "distance_km": 7.2,
            "duration_minutes": 25.0,
            "flag_drop_fare": 70.0,
            "distance_charge": 129.6,
            "time_charge": 112.5,
            "base_fare": 312.1,
            "surge_multiplier": 1.2,
            "final_fare": 374.52,
            "origin_active_requests": 32,
            "origin_available_drivers": 24,
            "payment_method": "tarjeta",
            "trip_status": "completado",
            "user_rating": 5.0,
            "driver_rating": 4.8,
            "tip_amount": 15.0,
            "cancellation_reason": None,
        }
        response = self.client.get("/movigo/trips/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trip_id"], 1)


if __name__ == "__main__":
    unittest.main()
