from datetime import datetime

from pydantic import BaseModel, Field
from typing import List


class RedtrackReportItem(BaseModel):
    """Schema para um item individual do relatório Redtrack"""

    campaign_id: str = Field(..., description="ID da campanha no Redtrack")
    date: datetime = Field(..., description="Data e hora do relatório com timezone (America/Sao_Paulo)")
    cost: float = Field(..., description="Custo em moeda")
    squad: str = Field(..., description="Squad")
    profit: float = Field(..., description="Lucro em moeda")
    revenue: float = Field(..., description="Revenue em moeda")
    roi: float = Field(..., description="ROI (Return on Investment)")
    conversion: float = Field(..., description="Converssao ")

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "1as23456",
                "squad": "YTD",
                "date": "2026-03-20T14:00:00-03:00",
                "cost": 169.21,
                "profit": 60.79,
                "revenue": 45.0,
                "roi": 0.36,
                "conversion": 99.46
            }
        }


# Type alias para lista de itens do relatório
RedtrackResponse = List[RedtrackReportItem]
