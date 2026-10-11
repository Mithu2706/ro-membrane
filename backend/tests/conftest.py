import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated database and known admin credentials BEFORE the app is imported.
_TMP = Path(tempfile.mkdtemp(prefix="ro_test_"))
os.environ["RO_DATABASE_PATH"] = str(_TMP / "test.db")
os.environ["RO_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["RO_ADMIN_USERNAME"] = "admin"
os.environ["RO_ADMIN_PASSWORD"] = "test-password-123"
os.environ["RO_SECRET_KEY"] = "test-secret-key"
os.environ.pop("RO_ADMIN_PASSWORD_HASH", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.migrations import migrate  # noqa: E402

migrate()


@pytest.fixture(scope="session")
def tmp_dir() -> Path:
    return _TMP


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_client():
    with TestClient(app) as c:
        r = c.post("/api/admin/login", json={"username": "admin", "password": "test-password-123"})
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        yield c


@pytest.fixture()
def membranes():
    from app import db
    from app.services.repository import load_active_membranes

    s = db.SessionLocal()
    try:
        yield load_active_membranes(s)
    finally:
        s.close()


SWRO = dict(application="swro", feed_tds_mg_l=35000, feed_temperature_c=25, available_pressure_bar=70,
            permeate_flow_m3d=5000, recovery_pct=45, target_permeate_tds_mg_l=500, design_flux_lmh=14,
            pressure_loss_allowance_bar=2,
            chemistry=dict(ph=8.1, calcium_mg_l=410, alkalinity_mg_l_caco3=140, sdi=3, turbidity_ntu=0.3,
                           oxidant_exposure="dechlorinated"))
BWRO = dict(application="bwro", feed_tds_mg_l=2500, feed_temperature_c=22, available_pressure_bar=16,
            permeate_flow_m3d=1000, recovery_pct=70, target_permeate_tds_mg_l=150, design_flux_lmh=22,
            chemistry=dict(ph=7.2, calcium_mg_l=60, alkalinity_mg_l_caco3=120, sdi=2.5, silica_mg_l=15,
                           oxidant_exposure="none"))
