"""
Seed script for Integris Clinical Platform
Run from /app/backend: python seed.py
"""
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import bcrypt

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import User, ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN, ROLE_VALIDATOR, ROLE_VIEWER
from app.models.study import Study
from app.models.dataset import Dataset

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def seed():
    with Session(engine) as session:

        # --- Tenants ---
        tenant1 = Tenant(
            id=uuid.uuid4(),
            name="Pharma Dynamics Inc.",
            slug="pharma-dynamics",
            plan="professional",
            is_active=True,
        )
        tenant2 = Tenant(
            id=uuid.uuid4(),
            name="BioTrial CRO",
            slug="biotrial-cro",
            plan="trial",
            is_active=True,
        )
        session.add_all([tenant1, tenant2])
        session.flush()

        # --- Users ---
        admin = User(
            id=uuid.uuid4(),
            tenant_id=tenant1.id,
            email="admin@integrisclinical.com",
            full_name="Adrian Pircalaboiu",
            hashed_password=hash_password("Admin2026!"),
            role=ROLE_SUPER_ADMIN,
            is_active=True,
        )
        validator = User(
            id=uuid.uuid4(),
            tenant_id=tenant1.id,
            email="validator@pharmadynamics.com",
            full_name="Sarah Chen",
            hashed_password=hash_password("Validator2026!"),
            role=ROLE_VALIDATOR,
            is_active=True,
        )
        viewer = User(
            id=uuid.uuid4(),
            tenant_id=tenant2.id,
            email="viewer@biotrialcro.com",
            full_name="Marcus Webb",
            hashed_password=hash_password("Viewer2026!"),
            role=ROLE_VIEWER,
            is_active=True,
        )
        session.add_all([admin, validator, viewer])
        session.flush()

        # --- Studies ---
        study1 = Study(
            id=uuid.uuid4(),
            tenant_id=tenant1.id,
            created_by=admin.id,
            study_id="PDYN-2024-001",
            title="Phase III Efficacy Study of PD-001 in Treatment-Resistant Hypertension",
            phase="III",
            therapeutic_area="Cardiovascular",
            sponsor="Pharma Dynamics Inc.",
            status="active",
        )
        study2 = Study(
            id=uuid.uuid4(),
            tenant_id=tenant1.id,
            created_by=admin.id,
            study_id="PDYN-2023-007",
            title="Phase II Safety Study of PD-007 in Type 2 Diabetes",
            phase="II",
            therapeutic_area="Endocrinology",
            sponsor="Pharma Dynamics Inc.",
            status="locked",
        )
        study3 = Study(
            id=uuid.uuid4(),
            tenant_id=tenant2.id,
            created_by=viewer.id,
            study_id="BTCRO-2024-003",
            title="Phase I First-in-Human Study of BT-003",
            phase="I",
            therapeutic_area="Oncology",
            sponsor="BioTrial CRO",
            status="active",
        )
        session.add_all([study1, study2, study3])
        session.flush()

        # --- Datasets ---
        datasets = [
            Dataset(
                id=uuid.uuid4(),
                tenant_id=tenant1.id,
                study_id=study1.id,
                uploaded_by=admin.id,
                domain="DM",
                filename="dm_pdyn2024001.csv",
                storage_uri="gs://integris-clinical-data/pdyn-2024-001/dm_pdyn2024001.csv",
                file_format="csv",
                row_count=245,
            ),
            Dataset(
                id=uuid.uuid4(),
                tenant_id=tenant1.id,
                study_id=study1.id,
                uploaded_by=validator.id,
                domain="VS",
                filename="vs_pdyn2024001.csv",
                storage_uri="gs://integris-clinical-data/pdyn-2024-001/vs_pdyn2024001.csv",
                file_format="csv",
                row_count=1820,
            ),
            Dataset(
                id=uuid.uuid4(),
                tenant_id=tenant1.id,
                study_id=study1.id,
                uploaded_by=validator.id,
                domain="AE",
                filename="ae_pdyn2024001.csv",
                storage_uri="gs://integris-clinical-data/pdyn-2024-001/ae_pdyn2024001.csv",
                file_format="csv",
                row_count=312,
            ),
            Dataset(
                id=uuid.uuid4(),
                tenant_id=tenant1.id,
                study_id=study2.id,
                uploaded_by=admin.id,
                domain="DM",
                filename="dm_pdyn2023007.json",
                storage_uri="gs://integris-clinical-data/pdyn-2023-007/dm_pdyn2023007.json",
                file_format="dataset-json",
                row_count=180,
            ),
            Dataset(
                id=uuid.uuid4(),
                tenant_id=tenant2.id,
                study_id=study3.id,
                uploaded_by=viewer.id,
                domain="CM",
                filename="cm_btcro2024003.csv",
                storage_uri="gs://integris-clinical-data/btcro-2024-003/cm_btcro2024003.csv",
                file_format="csv",
                row_count=96,
            ),
        ]
        session.add_all(datasets)
        session.commit()

        print("Seed complete:")
        print(f"  Tenants:  2")
        print(f"  Users:    3  (admin@integrisclinical.com / Admin2026!)")
        print(f"  Studies:  3")
        print(f"  Datasets: 5")

if __name__ == "__main__":
    seed()
