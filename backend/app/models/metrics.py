from sqlalchemy import Column, Integer, Numeric, Text, TIMESTAMP
from sqlalchemy.sql import func
from ..core.database import Base

class MetricsSnapshot(Base):
    __tablename__ = "tb_metrics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    metric_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    source_alias = Column(Text)

    cost = Column(Numeric(12, 2), default=0)
    profit = Column(Numeric(12, 2), default=0)
    roi = Column(Numeric(8, 4), default=0)