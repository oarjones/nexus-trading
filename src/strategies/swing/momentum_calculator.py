"""
Calculador de momentum para ranking de ETFs.

El momentum score combina múltiples timeframes para
capturar tendencia de corto, medio y largo plazo.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class MomentumScore:
    """Resultado del cálculo de momentum."""
    symbol: str
    score: float                    # Score combinado (0-100)
    return_1m: float               # Retorno 1 mes (%)
    return_3m: float               # Retorno 3 meses (%)
    return_6m: float               # Retorno 6 meses (%)
    return_12m: float              # Retorno 12 meses (%)
    volatility_adjusted_score: float  # Score ajustado por volatilidad
    rank: Optional[int] = None     # Ranking dentro del universo


class MomentumCalculator:
    """
    Calculador de momentum multi-timeframe.
    
    Fórmula del score:
    score = w1*ret_1m + w2*ret_3m + w3*ret_6m + w4*ret_12m
    
    Donde los pesos por defecto son:
    - 1 mes: 0.40 (más reciente, más peso)
    - 3 meses: 0.30
    - 6 meses: 0.20
    - 12 meses: 0.10
    """
    
    DEFAULT_WEIGHTS = {
        "1m": 0.40,
        "3m": 0.30,
        "6m": 0.20,
        "12m": 0.10,
    }
    
    def __init__(self, weights: dict = None):
        """
        Inicializar calculador.
        
        Args:
            weights: Pesos personalizados para cada timeframe
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        
        # Validar que pesos sumen 1.0
        total = sum(self.weights.values())
        if not np.isclose(total, 1.0):
            raise ValueError(f"Pesos deben sumar 1.0, suman {total}")
    
    def calculate(
        self,
        symbol: str,
        prices: list[float],
        volatility: Optional[float] = None
    ) -> MomentumScore:
        """
        Calcular momentum score para un símbolo.
        
        Args:
            symbol: Símbolo del ETF
            prices: Lista de precios históricos (más reciente al final)
                   Mínimo 252 precios (1 año de trading days)
            volatility: Volatilidad anualizada (opcional, para ajuste)
            
        Returns:
            MomentumScore con todos los componentes
        """
        if len(prices) < 252:
            raise ValueError(f"Se requieren mínimo 252 precios, recibidos {len(prices)}")
        
        current_price = prices[-1]
        
        # Calcular retornos por periodo
        # Aproximaciones: 1m=21 días, 3m=63, 6m=126, 12m=252
        ret_1m = self._calculate_return(prices, 21)
        ret_3m = self._calculate_return(prices, 63)
        ret_6m = self._calculate_return(prices, 126)
        ret_12m = self._calculate_return(prices, 252)
        
        # Score ponderado
        score = (
            self.weights["1m"] * ret_1m +
            self.weights["3m"] * ret_3m +
            self.weights["6m"] * ret_6m +
            self.weights["12m"] * ret_12m
        )
        
        # Normalizar score a escala 0-100
        # Asumiendo retornos típicos entre -50% y +50%
        normalized_score = self._normalize_score(score)
        
        # Ajuste por volatilidad (opcional)
        vol_adjusted = normalized_score
        if volatility and volatility > 0:
            # Penalizar alta volatilidad: score / sqrt(volatility)
            vol_adjusted = normalized_score / np.sqrt(volatility)
        
        return MomentumScore(
            symbol=symbol,
            score=normalized_score,
            return_1m=ret_1m * 100,  # Convertir a porcentaje
            return_3m=ret_3m * 100,
            return_6m=ret_6m * 100,
            return_12m=ret_12m * 100,
            volatility_adjusted_score=vol_adjusted,
        )
    
    def _calculate_return(self, prices: list[float], lookback: int) -> float:
        """Calcular retorno para un período."""
        if len(prices) < lookback:
            return 0.0
        
        current = prices[-1]
        past = prices[-lookback]
        
        if past == 0:
            return 0.0
        
        return (current - past) / past
    
    def _normalize_score(self, raw_score: float) -> float:
        """
        Normalizar score a escala 0-100.
        
        Usa función sigmoidea para manejar valores extremos.
        """
        # Sigmoid centrada en 0, escalada para que ±30% → ~15-85
        normalized = 50 + 50 * np.tanh(raw_score * 3)
        return np.clip(normalized, 0, 100)
    
    def rank_universe(
        self, 
        scores: list[MomentumScore],
        use_vol_adjusted: bool = True
    ) -> list[MomentumScore]:
        """
        Rankear universo de ETFs por momentum.
        
        Args:
            scores: Lista de MomentumScore calculados
            use_vol_adjusted: Usar score ajustado por volatilidad
            
        Returns:
            Lista ordenada de mayor a menor momentum con ranks asignados
        """
        key = "volatility_adjusted_score" if use_vol_adjusted else "score"
        
        sorted_scores = sorted(
            scores,
            key=lambda x: getattr(x, key),
            reverse=True
        )
        
        # Asignar rankings
        for i, score in enumerate(sorted_scores, 1):
            # Crear nuevo objeto con rank (dataclass es inmutable por campos)
            object.__setattr__(score, 'rank', i)
        
        return sorted_scores
