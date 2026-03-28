from datetime import datetime

from pydantic import BaseModel, Field
from typing import List


class RedtrackReportItem(BaseModel):
    """Schema para um item individual do relatório Redtrack"""
    
    date: datetime = Field(..., description="Data e hora do relatório com timezone (America/Sao_Paulo)")
    cost: float = Field(..., description="Custo em moeda")
    squad: str = Field(..., description="Squad")
    profit: float = Field(..., description="Lucro em moeda")
    revenue: float = Field(..., description="Revenue em moeda")
    roi: float = Field(..., description="ROI (Return on Investment)")

    class Config:
        json_schema_extra = {
            "example": {
                "squad": "YTD",
                "date": "2026-03-20T14:00:00-03:00",
                "cost": 169.21,
                "profit": 60.79,
                "revenue": 45.0,
                "roi": 0.36
            }
        }


# Type alias para lista de itens do relatório
RedtrackResponse = List[RedtrackReportItem]
