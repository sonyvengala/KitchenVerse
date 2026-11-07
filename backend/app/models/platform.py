"""
Notification, Promotion, DemandPrediction, ModelVersion, and AuditLog models.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text, Enum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import RealtimeEventType


def utc_now():
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="notifications")


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(String(255), nullable=True)
    discount_percentage = Column(Float, default=0.0, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    max_discount_amount = Column(Float, nullable=True)
    minimum_order_amount = Column(Float, default=0.0, nullable=False)
    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    per_user_limit = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    start_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=False, index=True)
    training_timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    training_start_week = Column(Integer, nullable=True)
    training_end_week = Column(Integer, nullable=True)
    validation_period = Column(String(100), nullable=True)
    metrics_json = Column(Text, nullable=False)  # JSON: {"mae": ..., "rmse": ..., "rmsle": ..., "wape": ...}
    feature_config_json = Column(Text, nullable=True)
    artifact_path = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    predictions = relationship("DemandPrediction", back_populates="model_version", cascade="all, delete-orphan")


class DemandPrediction(Base):
    __tablename__ = "demand_predictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_version_id = Column(String(36), ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    center_id = Column(Integer, nullable=False, index=True)
    meal_id = Column(Integer, nullable=False, index=True)
    prediction_period = Column(String(50), nullable=False, index=True)  # e.g., "Week 146"
    predicted_demand = Column(Float, nullable=False)
    generated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    model_version = relationship("ModelVersion", back_populates="predictions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_name = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
