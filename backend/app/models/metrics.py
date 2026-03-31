from sqlalchemy import Column, Date, Numeric, Text, TIMESTAMP
from sqlalchemy.sql import func
from ..core.database import Base


class HourlyMetric(Base):
    __tablename__ = "tb_hourly_metrics"

    campaign_id = Column(Text, primary_key=True)
    metric_at = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    checkout_conversion = Column(Numeric(12, 2), default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    squad = Column(Text, nullable=False, default="unknown")
    checkout = Column(Text, nullable=False, default="unknown")  # Cartpanda, Clickbank
    product = Column(Text, nullable=False, default="unknown")   # ErosLift, etc.
    cost = Column(Numeric(12, 2), default=0)
    profit = Column(Numeric(12, 2), default=0)
    roi = Column(Numeric(8, 4), default=0)
    revenue = Column(Numeric(8, 2), default=0)


class DailySummary(Base):
    __tablename__ = "tb_daily_metrics_summary"

    metric_date = Column(Date, primary_key=True)
    squad = Column(Text, primary_key=True)
    checkout_conversion = Column(Numeric(12, 2), default=0)
    cost = Column(Numeric(12, 2), default=0)
    profit = Column(Numeric(12, 2), default=0)
    roi = Column(Numeric(8, 4), default=0)
    revenue = Column(Numeric(8, 2), default=0)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyCheckoutSummary(Base):
    """Sumário diário de conversão por checkout (Cartpanda, Clickbank)."""
    __tablename__ = "tb_daily_checkout_summary"

    metric_date = Column(Date, primary_key=True)
    checkout = Column(Text, primary_key=True)  # Cartpanda, Clickbank
    squad = Column(Text, primary_key=True, default="ALL")
    initiate_checkout = Column(Numeric(12, 0), default=0)
    purchase = Column(Numeric(12, 0), default=0)
    checkout_conversion = Column(Numeric(12, 2), default=0)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyProductSummary(Base):
    """Sumário diário de conversão por produto."""
    __tablename__ = "tb_daily_product_summary"

    metric_date = Column(Date, primary_key=True)
    product = Column(Text, primary_key=True)  # ErosLift, etc.
    squad = Column(Text, primary_key=True, default="ALL")
    initiate_checkout = Column(Numeric(12, 0), default=0)
    purchase = Column(Numeric(12, 0), default=0)
    checkout_conversion = Column(Numeric(12, 2), default=0)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


# Alias para manter compatibilidade com imports antigos.
MetricsSnapshot = HourlyMetric
