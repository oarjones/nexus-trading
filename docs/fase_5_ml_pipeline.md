# 🧠 Fase 5: ML Pipeline

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 4 semanas  
**Dependencias:** Fase 1 (Feature Store), Fase 3 (Agentes Core)  
**Docs técnicos:** Doc 5 (secciones 1-8), Doc 1 (sec 4.6), Doc 3 (sec 7.4)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| HMM para régimen operativo | Detecta 4 estados con probabilidad > 0.6 |
| Pipeline de labeling | Triple Barrier genera labels correctos |
| División temporal correcta | Train/Val/Test con embargo de 5 días |
| Versionado de modelos | Estructura `models/` con metadata JSON |
| mcp-ml-models desplegado | Tools `get_regime`, `predict`, `get_model_info` responden |
| Calibración monitoreada | ECE < 0.10 en validación |
| Feature drift detection | Alerta si KS test p < 0.01 en >20% features |

---

## 2. Arquitectura del ML Pipeline

### 2.1 Componentes Principales

Referencia: Doc 5, secciones 1-2

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Feature Store  │────▶│  Training       │────▶│  Model Store    │
│  (Fase 1)       │     │  Pipeline       │     │  (Versionado)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │  mcp-ml-models  │◀─────────────┘
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
       │  Technical  │   │    Risk     │   │ Orchestrator│
       │   Agent     │   │   Manager   │   │             │
       └─────────────┘   └─────────────┘   └─────────────┘
```

### 2.2 Modelos a Implementar

| Modelo | Prioridad | Fase 5 | Uso |
|--------|-----------|--------|-----|
| HMM (Régimen) | Alta | ✅ Completo | Detección de estado de mercado |
| Meta-labeling | Media | ⬜ Estructura | Filtro de señales (Fase 6+) |
| TFT | Baja | ⬜ Placeholder | Predicción retornos (futuro) |

**Nota:** Esta fase se centra en HMM. Meta-labeling y TFT quedan preparados estructuralmente.

### 2.3 Estados de Régimen

Referencia: Doc 1, sección 4.6

| Estado | Características | Estrategias activas |
|--------|-----------------|---------------------|
| `trending_bull` | ADX alto, retornos +, vol baja | swing_momentum_eu |
| `trending_bear` | ADX alto, retornos -, vol alta | Solo cierres |
| `range_bound` | ADX bajo, retornos ~0, vol baja | mean_reversion_pairs |
| `high_volatility` | VIX elevado, vol alta | Ninguna nueva entrada |

### 2.4 Estructura de Directorios

```
src/ml/
├── __init__.py
├── config.py                # Configuración global ML
├── features/
│   ├── __init__.py
│   ├── loader.py            # Carga desde Feature Store
│   ├── transformer.py       # Z-score, winsorization
│   └── labeler.py           # Triple Barrier Method
├── models/
│   ├── __init__.py
│   ├── base.py              # Clase base Model
│   ├── hmm_regime.py        # Hidden Markov Model
│   ├── metalabel.py         # LightGBM (placeholder)
│   └── registry.py          # Model registry local
├── training/
│   ├── __init__.py
│   ├── splitter.py          # División temporal con embargo
│   ├── validator.py         # Purged CV, Walk-Forward
│   └── trainer.py           # Pipeline de entrenamiento
├── serving/
│   ├── __init__.py
│   ├── predictor.py         # Inferencia en producción
│   └── cache.py             # Cache Redis de predicciones
└── monitoring/
    ├── __init__.py
    ├── calibration.py       # ECE, reliability diagrams
    └── drift.py             # Feature drift detection

models/                       # Artefactos (fuera de src/)
├── hmm_regime/
│   └── v1_YYYYMMDD_hash/
│       ├── model.pkl
│       ├── config.yaml
│       └── metrics.json
├── metalabel/
└── tft_1d/

mcp-servers/
└── mcp-ml-models/
    ├── src/
    │   ├── index.ts
    │   └── tools/
    │       ├── get_regime.ts
    │       ├── predict.ts
    │       └── get_model_info.ts
    ├── package.json
    └── Dockerfile

tests/ml/
├── __init__.py
├── test_labeler.py
├── test_splitter.py
├── test_hmm.py
├── test_calibration.py
└── test_mcp_ml_models.py
```

---

## 3. Tareas

### Tarea 5.1: Configurar estructura y dependencias ML

**Estado:** ⬜ Pendiente

**Objetivo:** Crear estructura de directorios y configurar dependencias Python para ML.

**Referencias:** Doc 5 sec 2, Doc 1 sec 9

**Subtareas:**
- [ ] Crear estructura de directorios según sección 2.4
- [ ] Crear `requirements-ml.txt` con dependencias
- [ ] Crear `src/ml/config.py` con configuración base
- [ ] Crear `src/ml/__init__.py` con exports
- [ ] Verificar imports funcionan correctamente

**Input:** Estructura de proyecto existente (Fase 1-4)

**Output:** Directorios creados, dependencias instalables

**Validación:** `python -c "from src.ml import config"` ejecuta sin error

**Dependencias Python (requirements-ml.txt):**
```
# Core ML
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
scipy>=1.11.0

# HMM
hmmlearn>=0.3.0

# Gradient Boosting (para meta-labeling futuro)
lightgbm>=4.0.0

# Optimización
optuna>=3.4.0

# Serialización
joblib>=1.3.0
pyyaml>=6.0

# Monitoreo
matplotlib>=3.7.0  # Para reliability diagrams
```

**Pseudocódigo config.py:**
```python
# src/ml/config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MLConfig:
    # Paths
    models_dir: Path = Path("models")
    
    # División temporal
    train_start: str = "2018-01-01"
    train_end: str = "2021-12-31"
    val_start: str = "2022-01-01"
    val_end: str = "2023-12-31"
    test_start: str = "2024-01-01"
    embargo_days: int = 5
    
    # HMM
    hmm_n_states: int = 4
    hmm_n_iter: int = 100
    hmm_features: list = None
    
    # Calibración
    ece_target: float = 0.10
    calibration_window_days: int = 30
    
    # Cache
    prediction_cache_ttl: int = 300  # 5 min
    
    def __post_init__(self):
        if self.hmm_features is None:
            self.hmm_features = ["adx_14", "returns_20d", "volatility_20d"]
        self.models_dir.mkdir(parents=True, exist_ok=True)

# Singleton
config = MLConfig()
```

---

### Tarea 5.2: Implementar cargador de features para ML

**Estado:** ⬜ Pendiente

**Objetivo:** Cargar features desde Feature Store (Fase 1) en formato apto para entrenamiento.

**Referencias:** Doc 2 sec 6, Doc 5 sec 3.1

**Subtareas:**
- [ ] Crear `src/ml/features/loader.py`
- [ ] Implementar carga desde TimescaleDB
- [ ] Implementar carga desde Redis (tiempo real)
- [ ] Agregar filtrado por período y símbolos
- [ ] Manejar valores faltantes (forward fill, drop)

**Input:** Conexión a TimescaleDB/Redis, rango de fechas, lista de símbolos

**Output:** DataFrame con features alineados por timestamp

**Validación:** Carga 1 año de features para 5 símbolos en < 5 segundos

**Pseudocódigo:**
```python
# src/ml/features/loader.py
import pandas as pd
from typing import List, Optional
from datetime import datetime

class FeatureLoader:
    def __init__(self, db_connection, redis_client=None):
        self.db = db_connection
        self.redis = redis_client
    
    def load_training_features(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        features: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Carga features históricos para entrenamiento.
        
        1. Query a market_data.features con filtros
        2. Pivot para tener features como columnas
        3. Forward fill para gaps (max 5 días)
        4. Drop rows con NaN restantes
        5. Retornar DataFrame indexado por (timestamp, symbol)
        """
        pass
    
    def load_realtime_features(
        self,
        symbol: str,
        features: Optional[List[str]] = None
    ) -> dict:
        """
        Carga features actuales desde Redis para inferencia.
        
        1. HGETALL features:{symbol}:1d
        2. Parsear valores a float
        3. Retornar dict {feature_name: value}
        """
        pass
    
    def validate_features(self, df: pd.DataFrame) -> dict:
        """
        Valida calidad de features cargados.
        
        Retorna: {
            'total_rows': N,
            'nan_pct': X.X,
            'date_range': (min, max),
            'symbols': [...],
            'warnings': [...]
        }
        """
        pass
```

**SQL de carga:**
```sql
SELECT 
    f.time,
    f.symbol,
    f.feature_name,
    f.value
FROM market_data.features f
WHERE f.symbol = ANY($1)
  AND f.time BETWEEN $2 AND $3
  AND f.feature_name = ANY($4)
ORDER BY f.time, f.symbol;
```

---

### Tarea 5.3: Implementar transformaciones de features

**Estado:** ⬜ Pendiente

**Objetivo:** Aplicar transformaciones necesarias para ML (z-score rolling, winsorization).

**Referencias:** Doc 5 sec 3.2

**Subtareas:**
- [ ] Crear `src/ml/features/transformer.py`
- [ ] Implementar z-score rolling (ventana 60 días)
- [ ] Implementar winsorization (1%, 99%)
- [ ] Implementar log transform para volumen
- [ ] Guardar parámetros de transformación para inferencia

**Input:** DataFrame de features crudos

**Output:** DataFrame transformado + objeto transformer serializable

**Validación:** Features transformados tienen media ~0 y std ~1

**Pseudocódigo:**
```python
# src/ml/features/transformer.py
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict
import joblib

@dataclass
class TransformParams:
    """Parámetros guardados para aplicar en inferencia."""
    rolling_means: Dict[str, float]  # Últimos valores conocidos
    rolling_stds: Dict[str, float]
    winsor_bounds: Dict[str, tuple]  # (lower, upper) por feature

class FeatureTransformer:
    def __init__(self, rolling_window: int = 60):
        self.rolling_window = rolling_window
        self.params: TransformParams = None
    
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajusta y transforma features (para training).
        
        1. Winsorization: clip a percentiles 1% y 99%
        2. Log transform: aplicar a columnas de volumen
        3. Z-score rolling: (x - rolling_mean) / rolling_std
        4. Guardar últimos parámetros en self.params
        5. Retornar DataFrame transformado
        
        CRÍTICO: Z-score debe ser rolling, NO global (evita leakage)
        """
        pass
    
    def transform(self, features: dict) -> dict:
        """
        Transforma features nuevos usando parámetros guardados (inferencia).
        
        1. Aplicar winsorization con bounds guardados
        2. Aplicar log si corresponde
        3. Z-score con últimos mean/std conocidos
        4. Retornar dict transformado
        """
        pass
    
    def save(self, path: str):
        """Serializa transformer con joblib."""
        joblib.dump(self.params, path)
    
    def load(self, path: str):
        """Carga transformer serializado."""
        self.params = joblib.load(path)
```

---

### Tarea 5.4: Implementar Triple Barrier Labeling

**Estado:** ⬜ Pendiente

**Objetivo:** Generar labels usando Triple Barrier Method en lugar de retornos simples.

**Referencias:** Doc 5 sec 3.3

**Subtareas:**
- [ ] Crear `src/ml/features/labeler.py`
- [ ] Implementar cálculo de barreras (upper, lower, time)
- [ ] Determinar qué barrera se toca primero
- [ ] Generar labels: +1 (profit), -1 (stop), 0 (timeout)
- [ ] Calcular estadísticas de distribución de labels

**Input:** DataFrame OHLCV, parámetros de barreras

**Output:** Serie de labels alineada con timestamps de entrada

**Validación:** Distribución de labels razonable (~40% +1, ~40% -1, ~20% 0)

**Pseudocódigo:**
```python
# src/ml/features/labeler.py
import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass
class BarrierConfig:
    profit_target: float = 0.02    # 2%
    stop_loss: float = 0.01        # 1%
    max_holding_days: int = 5

class TripleBarrierLabeler:
    def __init__(self, config: BarrierConfig = None):
        self.config = config or BarrierConfig()
    
    def generate_labels(self, df: pd.DataFrame) -> pd.Series:
        """
        Genera labels usando Triple Barrier.
        
        Para cada punto t:
        1. upper_barrier = close[t] * (1 + profit_target)
        2. lower_barrier = close[t] * (1 - stop_loss)
        3. time_barrier = t + max_holding_days
        
        4. Buscar en ventana [t+1, time_barrier]:
           - Si high >= upper primero → label = +1
           - Si low <= lower primero → label = -1
           - Si ninguno en tiempo → label = 0
        
        5. Retornar Series con labels
        
        Nota: Últimos max_holding_days no tienen label (NaN)
        """
        labels = []
        
        for i in range(len(df) - self.config.max_holding_days):
            entry_price = df['close'].iloc[i]
            upper = entry_price * (1 + self.config.profit_target)
            lower = entry_price * (1 - self.config.stop_loss)
            
            # Ventana de búsqueda
            window = df.iloc[i+1 : i+1+self.config.max_holding_days]
            
            label = self._find_first_barrier(window, upper, lower)
            labels.append(label)
        
        # Padding para mantener alineación
        labels.extend([np.nan] * self.config.max_holding_days)
        
        return pd.Series(labels, index=df.index)
    
    def _find_first_barrier(
        self, 
        window: pd.DataFrame, 
        upper: float, 
        lower: float
    ) -> int:
        """
        Determina qué barrera se toca primero.
        
        Iterar día por día:
        - Si high >= upper → return +1
        - Si low <= lower → return -1
        Al final de ventana → return 0
        """
        for _, row in window.iterrows():
            if row['high'] >= upper:
                return 1
            if row['low'] <= lower:
                return -1
        return 0
    
    def get_label_distribution(self, labels: pd.Series) -> dict:
        """Retorna distribución de labels para validación."""
        counts = labels.value_counts(normalize=True)
        return {
            'positive': counts.get(1, 0),
            'negative': counts.get(-1, 0),
            'neutral': counts.get(0, 0),
            'total_samples': len(labels.dropna())
        }
```

---

### Tarea 5.5: Implementar división temporal con embargo

**Estado:** ⬜ Pendiente

**Objetivo:** Dividir datos en Train/Val/Test respetando temporalidad y embargo.

**Referencias:** Doc 5 sec 4.1-4.2

**Subtareas:**
- [ ] Crear `src/ml/training/splitter.py`
- [ ] Implementar split temporal básico (60/20/20)
- [ ] Implementar embargo entre splits (5 días)
- [ ] Implementar Purged K-Fold para CV en training
- [ ] Validar que no hay leakage temporal

**Input:** DataFrame con features y labels, configuración de fechas

**Output:** Tuplas (X_train, y_train), (X_val, y_val), (X_test, y_test)

**Validación:** Fechas no se solapan, embargo respetado

**Pseudocódigo:**
```python
# src/ml/training/splitter.py
import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Tuple, Generator
from dataclasses import dataclass

@dataclass
class SplitConfig:
    train_end: str = "2021-12-31"
    val_end: str = "2023-12-31"
    embargo_days: int = 5
    purge_days: int = 20  # max(feature_lookback)

class TemporalSplitter:
    def __init__(self, config: SplitConfig = None):
        self.config = config or SplitConfig()
    
    def split(
        self, 
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Divide datos en Train/Val/Test con embargo.
        
        Timeline:
        |----TRAIN----|--embargo--|----VAL----|--embargo--|----TEST----|
        
        1. Train: todo antes de train_end
        2. Embargo: train_end + embargo_days (excluir)
        3. Val: desde fin embargo hasta val_end
        4. Embargo: val_end + embargo_days (excluir)
        5. Test: desde fin embargo hasta final
        
        Retorna: (train_df, val_df, test_df)
        """
        train_end = pd.Timestamp(self.config.train_end)
        val_end = pd.Timestamp(self.config.val_end)
        embargo = timedelta(days=self.config.embargo_days)
        
        train = df[df.index <= train_end]
        val = df[(df.index > train_end + embargo) & (df.index <= val_end)]
        test = df[df.index > val_end + embargo]
        
        return train, val, test
    
    def purged_kfold(
        self, 
        df: pd.DataFrame, 
        n_splits: int = 5
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        Purged K-Fold para cross-validation en training set.
        
        Para cada fold:
        1. Dividir en k partes temporales
        2. Usar k-1 para train, 1 para val
        3. Purge: eliminar purge_days antes del inicio de val
        4. Embargo: eliminar embargo_days después del fin de train
        
        Yield: (train_fold, val_fold) para cada split
        """
        # Dividir en n_splits partes iguales temporales
        splits = np.array_split(df, n_splits)
        
        for i in range(n_splits):
            val_fold = splits[i]
            train_parts = [s for j, s in enumerate(splits) if j != i]
            train_fold = pd.concat(train_parts)
            
            # Aplicar purge y embargo
            val_start = val_fold.index.min()
            val_end = val_fold.index.max()
            
            purge_start = val_start - timedelta(days=self.config.purge_days)
            embargo_end = val_end + timedelta(days=self.config.embargo_days)
            
            # Eliminar zona de purge/embargo de train
            train_fold = train_fold[
                (train_fold.index < purge_start) | 
                (train_fold.index > embargo_end)
            ]
            
            yield train_fold, val_fold
    
    def validate_no_leakage(
        self, 
        train: pd.DataFrame, 
        val: pd.DataFrame, 
        test: pd.DataFrame
    ) -> dict:
        """
        Verifica que no hay leakage temporal.
        
        Checks:
        - max(train.index) < min(val.index) - embargo
        - max(val.index) < min(test.index) - embargo
        - No hay índices duplicados entre sets
        """
        embargo = timedelta(days=self.config.embargo_days)
        
        checks = {
            'train_before_val': train.index.max() < val.index.min() - embargo,
            'val_before_test': val.index.max() < test.index.min() - embargo,
            'no_overlap': len(set(train.index) & set(val.index) & set(test.index)) == 0
        }
        
        checks['all_passed'] = all(checks.values())
        return checks
```

---

### Tarea 5.6: Implementar Hidden Markov Model para régimen

**Estado:** ⬜ Pendiente

**Objetivo:** Entrenar HMM que detecta 4 estados de mercado.

**Referencias:** Doc 5 sec 2.2, Doc 1 sec 4.6

**Subtareas:**
- [ ] Crear `src/ml/models/hmm_regime.py`
- [ ] Implementar clase HMMRegimeDetector
- [ ] Configurar 4 estados (trending_bull, trending_bear, range_bound, high_vol)
- [ ] Entrenar con features: ADX, returns_20d, volatility_20d
- [ ] Implementar predicción de estado actual
- [ ] Mapear estados numéricos a nombres

**Input:** Features transformados (ADX, returns, volatility)

**Output:** Estado actual con probabilidad, histórico de transiciones

**Validación:** Modelo detecta régimen correctamente en períodos conocidos (ej: marzo 2020 = high_volatility)

**Pseudocódigo:**
```python
# src/ml/models/hmm_regime.py
import numpy as np
import pandas as pd
from hmmlearn import hmm
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import joblib
from pathlib import Path
import hashlib
import yaml
from datetime import datetime

@dataclass
class HMMConfig:
    n_states: int = 4
    n_iter: int = 100
    covariance_type: str = "full"
    features: list = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = ["adx_14", "returns_20d", "volatility_20d"]
    
    def to_dict(self) -> dict:
        return {
            'n_states': self.n_states,
            'n_iter': self.n_iter,
            'covariance_type': self.covariance_type,
            'features': self.features
        }
    
    def hash(self) -> str:
        """Hash corto de config para versionado."""
        content = str(sorted(self.to_dict().items()))
        return hashlib.md5(content.encode()).hexdigest()[:6]

# Mapeo de estados
REGIME_NAMES = {
    0: "trending_bull",
    1: "trending_bear", 
    2: "range_bound",
    3: "high_volatility"
}

class HMMRegimeDetector:
    def __init__(self, config: HMMConfig = None):
        self.config = config or HMMConfig()
        self.model: hmm.GaussianHMM = None
        self.state_mapping: Dict[int, str] = {}
        self.trained_at: datetime = None
        self.metrics: dict = {}
    
    def train(self, df: pd.DataFrame) -> dict:
        """
        Entrena HMM con datos históricos.
        
        1. Extraer features relevantes
        2. Inicializar GaussianHMM con n_states
        3. Fit con algoritmo EM
        4. Mapear estados a nombres basado en características
        5. Calcular métricas de ajuste
        6. Retornar métricas
        """
        # Extraer features
        X = df[self.config.features].values
        
        # Inicializar modelo
        self.model = hmm.GaussianHMM(
            n_components=self.config.n_states,
            covariance_type=self.config.covariance_type,
            n_iter=self.config.n_iter,
            random_state=42
        )
        
        # Entrenar
        self.model.fit(X)
        
        # Mapear estados a nombres
        self._map_states_to_names(df)
        
        # Calcular métricas
        self.metrics = self._calculate_metrics(X)
        self.trained_at = datetime.utcnow()
        
        return self.metrics
    
    def _map_states_to_names(self, df: pd.DataFrame):
        """
        Mapea estados numéricos a nombres basado en medias.
        
        Lógica:
        - Estado con mayor media de returns y ADX alto → trending_bull
        - Estado con menor media de returns y ADX alto → trending_bear
        - Estado con ADX bajo → range_bound
        - Estado con mayor volatilidad → high_volatility
        """
        X = df[self.config.features].values
        states = self.model.predict(X)
        
        # Calcular medias por estado
        state_stats = {}
        for state in range(self.config.n_states):
            mask = states == state
            state_stats[state] = {
                'adx_mean': df.loc[mask, 'adx_14'].mean() if 'adx_14' in df else 0,
                'returns_mean': df.loc[mask, 'returns_20d'].mean() if 'returns_20d' in df else 0,
                'vol_mean': df.loc[mask, 'volatility_20d'].mean() if 'volatility_20d' in df else 0
            }
        
        # Asignar nombres (heurística simple)
        # En producción, ajustar basado en análisis de datos reales
        sorted_by_vol = sorted(state_stats.keys(), 
                               key=lambda s: state_stats[s]['vol_mean'], 
                               reverse=True)
        sorted_by_returns = sorted(state_stats.keys(), 
                                   key=lambda s: state_stats[s]['returns_mean'], 
                                   reverse=True)
        
        self.state_mapping = {}
        assigned = set()
        
        # High volatility: mayor volatilidad
        self.state_mapping[sorted_by_vol[0]] = "high_volatility"
        assigned.add(sorted_by_vol[0])
        
        # Trending bull: mejores retornos (no asignado)
        for s in sorted_by_returns:
            if s not in assigned:
                self.state_mapping[s] = "trending_bull"
                assigned.add(s)
                break
        
        # Trending bear: peores retornos (no asignado)
        for s in reversed(sorted_by_returns):
            if s not in assigned:
                self.state_mapping[s] = "trending_bear"
                assigned.add(s)
                break
        
        # Range bound: el restante
        for s in range(self.config.n_states):
            if s not in assigned:
                self.state_mapping[s] = "range_bound"
    
    def _calculate_metrics(self, X: np.ndarray) -> dict:
        """Calcula métricas de ajuste del modelo."""
        log_likelihood = self.model.score(X)
        aic = -2 * log_likelihood + 2 * self._count_params()
        bic = -2 * log_likelihood + np.log(len(X)) * self._count_params()
        
        return {
            'log_likelihood': log_likelihood,
            'aic': aic,
            'bic': bic,
            'n_samples': len(X),
            'converged': self.model.monitor_.converged
        }
    
    def _count_params(self) -> int:
        """Cuenta parámetros del modelo para AIC/BIC."""
        n = self.config.n_states
        k = len(self.config.features)
        # Transiciones + medias + covarianzas
        return n * (n - 1) + n * k + n * k * (k + 1) // 2
    
    def predict(self, features: dict) -> Tuple[str, float]:
        """
        Predice régimen actual.
        
        1. Extraer features en orden correcto
        2. Predict con HMM
        3. Obtener probabilidades de cada estado
        4. Retornar (nombre_estado, probabilidad)
        
        Si probabilidad < 0.6, retornar "range_bound" como default
        """
        if self.model is None:
            raise ValueError("Modelo no entrenado")
        
        # Preparar input
        X = np.array([[features[f] for f in self.config.features]])
        
        # Predecir
        state = self.model.predict(X)[0]
        probs = self.model.predict_proba(X)[0]
        
        max_prob = probs[state]
        regime_name = self.state_mapping.get(state, "range_bound")
        
        # Threshold de confianza
        if max_prob < 0.6:
            regime_name = "range_bound"
        
        return regime_name, float(max_prob)
    
    def get_regime_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """Genera histórico de regímenes para análisis."""
        X = df[self.config.features].values
        states = self.model.predict(X)
        probs = self.model.predict_proba(X)
        
        result = pd.DataFrame(index=df.index)
        result['state_num'] = states
        result['regime'] = [self.state_mapping.get(s, 'unknown') for s in states]
        result['probability'] = probs.max(axis=1)
        
        for i, name in enumerate(REGIME_NAMES.values()):
            result[f'prob_{name}'] = probs[:, i] if i < probs.shape[1] else 0
        
        return result
    
    def save(self, base_path: str, version: int = 1):
        """
        Guarda modelo con versionado.
        
        Estructura:
        models/hmm_regime/v{N}_{YYYYMMDD}_{hash}/
        ├── model.pkl
        ├── config.yaml
        └── metrics.json
        """
        date_str = datetime.utcnow().strftime("%Y%m%d")
        config_hash = self.config.hash()
        version_name = f"v{version}_{date_str}_{config_hash}"
        
        path = Path(base_path) / "hmm_regime" / version_name
        path.mkdir(parents=True, exist_ok=True)
        
        # Guardar modelo
        joblib.dump({
            'model': self.model,
            'state_mapping': self.state_mapping
        }, path / "model.pkl")
        
        # Guardar config
        with open(path / "config.yaml", 'w') as f:
            yaml.dump(self.config.to_dict(), f)
        
        # Guardar métricas
        import json
        metrics_to_save = {
            **self.metrics,
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'state_mapping': self.state_mapping
        }
        with open(path / "metrics.json", 'w') as f:
            json.dump(metrics_to_save, f, indent=2)
        
        return str(path)
    
    def load(self, model_path: str):
        """Carga modelo desde disco."""
        path = Path(model_path)
        
        # Cargar modelo
        data = joblib.load(path / "model.pkl")
        self.model = data['model']
        self.state_mapping = data['state_mapping']
        
        # Cargar config
        with open(path / "config.yaml") as f:
            config_dict = yaml.safe_load(f)
            self.config = HMMConfig(**config_dict)
        
        # Cargar métricas
        import json
        with open(path / "metrics.json") as f:
            self.metrics = json.load(f)
```

---

### Tarea 5.7: Implementar pipeline de entrenamiento

**Estado:** ⬜ Pendiente

**Objetivo:** Crear pipeline end-to-end para entrenar modelos.

**Referencias:** Doc 5 sec 4.4

**Subtareas:**
- [ ] Crear `src/ml/training/trainer.py`
- [ ] Implementar clase TrainingPipeline
- [ ] Integrar loader → transformer → splitter → model
- [ ] Agregar logging de experimentos
- [ ] Implementar comparación con modelo anterior

**Input:** Configuración de entrenamiento, conexión a BD

**Output:** Modelo entrenado y guardado, métricas en JSON

**Validación:** Pipeline ejecuta sin errores, modelo guardado correctamente

**Pseudocódigo:**
```python
# src/ml/training/trainer.py
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..features.loader import FeatureLoader
from ..features.transformer import FeatureTransformer
from ..features.labeler import TripleBarrierLabeler
from ..models.hmm_regime import HMMRegimeDetector, HMMConfig
from .splitter import TemporalSplitter, SplitConfig

logger = logging.getLogger(__name__)

@dataclass
class TrainingConfig:
    models_dir: str = "models"
    symbols: list = None
    start_date: str = "2018-01-01"
    end_date: str = "2024-01-01"
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["SPY", "QQQ", "IWM"]  # Default para entrenamiento

class TrainingPipeline:
    def __init__(
        self, 
        db_connection,
        config: TrainingConfig = None
    ):
        self.db = db_connection
        self.config = config or TrainingConfig()
        self.loader = FeatureLoader(db_connection)
        self.transformer = FeatureTransformer()
        self.splitter = TemporalSplitter()
    
    def train_hmm(self, hmm_config: HMMConfig = None) -> dict:
        """
        Pipeline completo para entrenar HMM de régimen.
        
        1. Cargar features históricos
        2. Transformar features
        3. Dividir en train/val/test
        4. Entrenar HMM en train
        5. Evaluar en validation
        6. Guardar modelo si métricas OK
        7. Retornar resumen
        """
        logger.info("Iniciando entrenamiento HMM")
        
        # 1. Cargar features
        logger.info(f"Cargando features para {self.config.symbols}")
        df = self.loader.load_training_features(
            symbols=self.config.symbols,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            features=hmm_config.features if hmm_config else None
        )
        logger.info(f"Cargados {len(df)} registros")
        
        # 2. Transformar
        logger.info("Transformando features")
        df_transformed = self.transformer.fit_transform(df)
        
        # 3. Split
        logger.info("Dividiendo datos")
        train, val, test = self.splitter.split(df_transformed)
        
        # Validar no leakage
        leakage_check = self.splitter.validate_no_leakage(train, val, test)
        if not leakage_check['all_passed']:
            raise ValueError(f"Leakage detectado: {leakage_check}")
        
        logger.info(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
        
        # 4. Entrenar
        logger.info("Entrenando HMM")
        detector = HMMRegimeDetector(hmm_config)
        train_metrics = detector.train(train)
        logger.info(f"Métricas train: {train_metrics}")
        
        # 5. Evaluar en validation
        logger.info("Evaluando en validation")
        val_metrics = self._evaluate_hmm(detector, val)
        logger.info(f"Métricas val: {val_metrics}")
        
        # 6. Guardar
        version = self._get_next_version("hmm_regime")
        model_path = detector.save(self.config.models_dir, version)
        logger.info(f"Modelo guardado en {model_path}")
        
        # Guardar transformer
        self.transformer.save(f"{model_path}/transformer.pkl")
        
        return {
            'model_path': model_path,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'version': version,
            'trained_at': datetime.utcnow().isoformat()
        }
    
    def _evaluate_hmm(self, detector: HMMRegimeDetector, df: pd.DataFrame) -> dict:
        """
        Evalúa HMM en conjunto de validación.
        
        Métricas:
        - Log likelihood en val
        - Distribución de estados
        - Estabilidad de transiciones
        """
        X = df[detector.config.features].values
        
        log_likelihood = detector.model.score(X)
        regime_history = detector.get_regime_history(df)
        
        # Distribución de estados
        state_dist = regime_history['regime'].value_counts(normalize=True).to_dict()
        
        # Estabilidad: % de días sin cambio de régimen
        changes = (regime_history['regime'] != regime_history['regime'].shift()).sum()
        stability = 1 - (changes / len(regime_history))
        
        return {
            'log_likelihood': log_likelihood,
            'state_distribution': state_dist,
            'stability': stability,
            'avg_probability': regime_history['probability'].mean()
        }
    
    def _get_next_version(self, model_name: str) -> int:
        """Obtiene siguiente número de versión."""
        model_dir = Path(self.config.models_dir) / model_name
        if not model_dir.exists():
            return 1
        
        existing = list(model_dir.glob("v*"))
        if not existing:
            return 1
        
        versions = [int(p.name.split('_')[0][1:]) for p in existing]
        return max(versions) + 1
```

**Script de entrenamiento (scripts/train_hmm.py):**
```python
#!/usr/bin/env python
"""Script para entrenar HMM de régimen."""
import argparse
import logging
from src.ml.training.trainer import TrainingPipeline, TrainingConfig
from src.ml.models.hmm_regime import HMMConfig
from src.data.database import get_db_connection

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ', 'IWM'])
    parser.add_argument('--start', default='2018-01-01')
    parser.add_argument('--end', default='2024-01-01')
    args = parser.parse_args()
    
    db = get_db_connection()
    
    config = TrainingConfig(
        symbols=args.symbols,
        start_date=args.start,
        end_date=args.end
    )
    
    pipeline = TrainingPipeline(db, config)
    result = pipeline.train_hmm()
    
    print(f"\n✅ Entrenamiento completado")
    print(f"Modelo: {result['model_path']}")
    print(f"Log-likelihood (val): {result['val_metrics']['log_likelihood']:.2f}")
    print(f"Estabilidad: {result['val_metrics']['stability']:.2%}")

if __name__ == "__main__":
    main()
```

---

### Tarea 5.8: Implementar mcp-ml-models server

**Estado:** ⬜ Pendiente

**Objetivo:** Crear MCP server que sirve predicciones de modelos ML.

**Referencias:** Doc 3 sec 7.4, Doc 5 sec 7.1

**Subtareas:**
- [ ] Crear estructura de mcp-ml-models
- [ ] Implementar tool `get_regime`
- [ ] Implementar tool `predict` (preparado para futuro)
- [ ] Implementar tool `get_model_info`
- [ ] Agregar cache Redis para predicciones
- [ ] Tests de integración

**Input:** Requests MCP con features o queries

**Output:** Predicciones con confianza y metadata

**Validación:** `get_regime` retorna estado válido con probabilidad

**Estructura:**
```
mcp-servers/mcp-ml-models/
├── src/
│   ├── index.ts
│   ├── config.ts
│   ├── models/
│   │   ├── loader.ts        # Carga modelos Python vía subprocess
│   │   └── types.ts
│   ├── tools/
│   │   ├── get_regime.ts
│   │   ├── predict.ts
│   │   └── get_model_info.ts
│   └── cache.ts             # Redis cache
├── python/
│   └── serve.py             # Script Python para inferencia
├── package.json
├── tsconfig.json
└── Dockerfile
```

**Pseudocódigo index.ts:**
```typescript
// mcp-servers/mcp-ml-models/src/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { getRegimeTool } from "./tools/get_regime.js";
import { predictTool } from "./tools/predict.js";
import { getModelInfoTool } from "./tools/get_model_info.js";

const server = new Server(
  { name: "mcp-ml-models", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Registrar tools
server.setRequestHandler("tools/list", async () => ({
  tools: [
    {
      name: "get_regime",
      description: "Obtiene el régimen de mercado actual",
      inputSchema: {
        type: "object",
        properties: {
          symbol: { type: "string", description: "Símbolo para contexto (opcional)" }
        }
      }
    },
    {
      name: "predict",
      description: "Genera predicción de modelo ML",
      inputSchema: {
        type: "object",
        properties: {
          model_name: { type: "string" },
          features: { type: "object" },
          symbol: { type: "string" }
        },
        required: ["model_name", "features"]
      }
    },
    {
      name: "get_model_info",
      description: "Obtiene información de un modelo",
      inputSchema: {
        type: "object",
        properties: {
          model_name: { type: "string" }
        },
        required: ["model_name"]
      }
    }
  ]
}));

server.setRequestHandler("tools/call", async (request) => {
  const { name, arguments: args } = request.params;
  
  switch (name) {
    case "get_regime":
      return await getRegimeTool(args);
    case "predict":
      return await predictTool(args);
    case "get_model_info":
      return await getModelInfoTool(args);
    default:
      throw new Error(`Tool desconocido: ${name}`);
  }
});

// Iniciar
const transport = new StdioServerTransport();
await server.connect(transport);
```

**Pseudocódigo get_regime.ts:**
```typescript
// mcp-servers/mcp-ml-models/src/tools/get_regime.ts
import { spawn } from "child_process";
import { RedisCache } from "../cache.js";

const cache = new RedisCache("ml:regime", 300); // TTL 5 min

interface RegimeResult {
  regime: string;
  probability: number;
  since: string;
  all_probabilities: Record<string, number>;
}

export async function getRegimeTool(args: { symbol?: string }): Promise<RegimeResult> {
  // 1. Check cache
  const cached = await cache.get("current");
  if (cached) {
    return JSON.parse(cached);
  }
  
  // 2. Llamar a Python para inferencia
  const result = await callPythonPredictor("get_regime", args);
  
  // 3. Cache result
  await cache.set("current", JSON.stringify(result));
  
  return result;
}

async function callPythonPredictor(method: string, args: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const python = spawn("python", [
      "python/serve.py",
      method,
      JSON.stringify(args)
    ]);
    
    let output = "";
    python.stdout.on("data", (data) => { output += data; });
    python.stderr.on("data", (data) => { console.error(data.toString()); });
    
    python.on("close", (code) => {
      if (code === 0) {
        resolve(JSON.parse(output));
      } else {
        reject(new Error(`Python exited with code ${code}`));
      }
    });
  });
}
```

**Python serve.py:**
```python
#!/usr/bin/env python
"""Servidor de inferencia ML para mcp-ml-models."""
import sys
import json
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ml.models.hmm_regime import HMMRegimeDetector
from src.ml.features.loader import FeatureLoader
from src.data.database import get_db_connection
from src.data.redis_client import get_redis_client

# Cargar modelo al inicio
MODEL_PATH = "models/hmm_regime/latest"  # Symlink a versión activa
detector = HMMRegimeDetector()
detector.load(MODEL_PATH)

loader = FeatureLoader(get_db_connection(), get_redis_client())

def get_regime(args: dict) -> dict:
    """Obtiene régimen actual."""
    # Cargar features actuales desde Redis
    symbol = args.get('symbol', 'SPY')
    features = loader.load_realtime_features(symbol)
    
    # Predecir
    regime, probability = detector.predict(features)
    
    # Obtener histórico reciente para "since"
    # (simplificado: usar último cambio conocido)
    
    return {
        'regime': regime,
        'probability': probability,
        'since': '2024-01-15T09:30:00Z',  # TODO: calcular real
        'all_probabilities': {
            'trending_bull': 0.1,
            'trending_bear': 0.1,
            'range_bound': 0.7,
            'high_volatility': 0.1
        }
    }

def get_model_info(args: dict) -> dict:
    """Obtiene información del modelo."""
    model_name = args.get('model_name', 'hmm_regime')
    
    if model_name == 'hmm_regime':
        return {
            'name': 'hmm_regime',
            'version': detector.metrics.get('version', 'v1'),
            'trained_at': detector.metrics.get('trained_at'),
            'metrics': {
                'log_likelihood': detector.metrics.get('log_likelihood'),
                'stability': detector.metrics.get('stability')
            },
            'features': detector.config.features
        }
    
    return {'error': f'Modelo {model_name} no encontrado'}

def main():
    method = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    
    if method == 'get_regime':
        result = get_regime(args)
    elif method == 'get_model_info':
        result = get_model_info(args)
    else:
        result = {'error': f'Método {method} no soportado'}
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

---

### Tarea 5.9: Implementar monitoreo de calibración

**Estado:** ⬜ Pendiente

**Objetivo:** Monitorear calibración de predicciones en producción.

**Referencias:** Doc 5 sec 5.3, sec 8.1

**Subtareas:**
- [ ] Crear `src/ml/monitoring/calibration.py`
- [ ] Implementar cálculo de ECE (Expected Calibration Error)
- [ ] Implementar reliability diagram
- [ ] Crear job de monitoreo diario
- [ ] Configurar alertas si ECE > 0.10

**Input:** Predicciones históricas con outcomes reales

**Output:** ECE métrica, gráfico de calibración, alertas si umbral excedido

**Validación:** ECE calculado correctamente, alerta dispara si ECE > 0.10

**Pseudocódigo:**
```python
# src/ml/monitoring/calibration.py
import numpy as np
import pandas as pd
from typing import Tuple, List
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

class CalibrationMonitor:
    def __init__(self, n_bins: int = 10, ece_threshold: float = 0.10):
        self.n_bins = n_bins
        self.ece_threshold = ece_threshold
    
    def calculate_ece(
        self, 
        predictions: np.ndarray, 
        outcomes: np.ndarray
    ) -> float:
        """
        Calcula Expected Calibration Error.
        
        ECE = Σ (|accuracy_bin - confidence_bin| * samples_bin / total)
        
        1. Dividir predicciones en n_bins por confianza
        2. Para cada bin: calcular accuracy real vs confianza media
        3. Ponderar por número de muestras
        4. Sumar diferencias absolutas
        """
        bin_boundaries = np.linspace(0, 1, self.n_bins + 1)
        ece = 0.0
        
        for i in range(self.n_bins):
            # Máscara para este bin
            in_bin = (predictions >= bin_boundaries[i]) & \
                     (predictions < bin_boundaries[i + 1])
            
            if in_bin.sum() == 0:
                continue
            
            # Accuracy real en este bin
            accuracy = outcomes[in_bin].mean()
            
            # Confianza media en este bin
            confidence = predictions[in_bin].mean()
            
            # Contribución al ECE
            ece += np.abs(accuracy - confidence) * in_bin.sum() / len(predictions)
        
        return ece
    
    def generate_reliability_diagram(
        self,
        predictions: np.ndarray,
        outcomes: np.ndarray,
        save_path: str = None
    ) -> plt.Figure:
        """
        Genera diagrama de fiabilidad (reliability diagram).
        
        Eje X: Confianza predicha
        Eje Y: Accuracy real
        Línea diagonal = calibración perfecta
        """
        fig, ax = plt.subplots(figsize=(8, 8))
        
        bin_boundaries = np.linspace(0, 1, self.n_bins + 1)
        bin_centers = []
        bin_accuracies = []
        bin_counts = []
        
        for i in range(self.n_bins):
            in_bin = (predictions >= bin_boundaries[i]) & \
                     (predictions < bin_boundaries[i + 1])
            
            if in_bin.sum() > 0:
                bin_centers.append((bin_boundaries[i] + bin_boundaries[i + 1]) / 2)
                bin_accuracies.append(outcomes[in_bin].mean())
                bin_counts.append(in_bin.sum())
        
        # Barras de accuracy
        ax.bar(bin_centers, bin_accuracies, width=1/self.n_bins, 
               alpha=0.7, edgecolor='black', label='Accuracy')
        
        # Línea diagonal (calibración perfecta)
        ax.plot([0, 1], [0, 1], 'r--', label='Perfecta calibración')
        
        # Etiquetas
        ax.set_xlabel('Confianza predicha')
        ax.set_ylabel('Accuracy real')
        ax.set_title(f'Reliability Diagram (ECE={self.calculate_ece(predictions, outcomes):.3f})')
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        if save_path:
            fig.savefig(save_path)
        
        return fig
    
    def check_calibration(
        self,
        predictions: np.ndarray,
        outcomes: np.ndarray
    ) -> dict:
        """
        Verifica calibración y genera alerta si necesario.
        
        Retorna:
        - ece: valor calculado
        - is_calibrated: bool (ECE < threshold)
        - alert: mensaje si mal calibrado
        - recommendation: acción sugerida
        """
        ece = self.calculate_ece(predictions, outcomes)
        is_calibrated = ece < self.ece_threshold
        
        result = {
            'ece': ece,
            'threshold': self.ece_threshold,
            'is_calibrated': is_calibrated,
            'checked_at': datetime.utcnow().isoformat(),
            'n_samples': len(predictions)
        }
        
        if not is_calibrated:
            result['alert'] = f"ECE ({ece:.3f}) excede umbral ({self.ece_threshold})"
            result['recommendation'] = "Considerar re-calibración con Platt scaling o isotonic regression"
        
        return result


class CalibrationJob:
    """Job diario de monitoreo de calibración."""
    
    def __init__(self, db_connection, redis_client, window_days: int = 30):
        self.db = db_connection
        self.redis = redis_client
        self.window_days = window_days
        self.monitor = CalibrationMonitor()
    
    def run(self, model_name: str = "hmm_regime") -> dict:
        """
        Ejecuta verificación de calibración.
        
        1. Cargar predicciones de últimos N días
        2. Cargar outcomes reales (régimen detectado vs performance)
        3. Calcular ECE
        4. Guardar en Redis/InfluxDB
        5. Disparar alerta si necesario
        """
        # Cargar datos
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=self.window_days)
        
        predictions, outcomes = self._load_prediction_outcomes(
            model_name, start_date, end_date
        )
        
        if len(predictions) < 100:
            return {
                'status': 'skipped',
                'reason': f'Insuficientes muestras ({len(predictions)})'
            }
        
        # Verificar calibración
        result = self.monitor.check_calibration(predictions, outcomes)
        result['model_name'] = model_name
        result['window_days'] = self.window_days
        
        # Guardar en Redis
        self.redis.hset(
            f"ml:calibration:{model_name}",
            mapping={
                'ece': str(result['ece']),
                'is_calibrated': str(result['is_calibrated']),
                'checked_at': result['checked_at']
            }
        )
        
        # Alerta si necesario
        if not result['is_calibrated']:
            self._send_alert(result)
        
        return result
    
    def _load_prediction_outcomes(
        self,
        model_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Carga predicciones y outcomes desde BD."""
        # TODO: Implementar query real
        # Por ahora, placeholder
        return np.array([]), np.array([])
    
    def _send_alert(self, result: dict):
        """Envía alerta de calibración."""
        # Publicar en Redis para que Telegram bot recoja
        import json
        self.redis.publish(
            "alerts:ml",
            json.dumps({
                'type': 'calibration_warning',
                'model': result['model_name'],
                'ece': result['ece'],
                'message': result.get('alert', '')
            })
        )
```

---

### Tarea 5.10: Implementar feature drift detection

**Estado:** ⬜ Pendiente

**Objetivo:** Detectar cuando distribución de features en producción difiere de entrenamiento.

**Referencias:** Doc 5 sec 8.2

**Subtareas:**
- [ ] Crear `src/ml/monitoring/drift.py`
- [ ] Implementar test KS (Kolmogorov-Smirnov) por feature
- [ ] Guardar distribuciones de referencia (training)
- [ ] Job de detección diario
- [ ] Alerta si > 20% features con drift

**Input:** Features actuales, distribuciones de referencia

**Output:** Report de drift por feature, alertas si umbral excedido

**Validación:** Drift detectado en datos sintéticos con distribución alterada

**Pseudocódigo:**
```python
# src/ml/monitoring/drift.py
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List
from datetime import datetime
import json

class DriftDetector:
    def __init__(
        self, 
        p_value_threshold: float = 0.01,
        drift_pct_threshold: float = 0.20
    ):
        self.p_value_threshold = p_value_threshold
        self.drift_pct_threshold = drift_pct_threshold
        self.reference_distributions: Dict[str, np.ndarray] = {}
    
    def set_reference(self, feature_name: str, values: np.ndarray):
        """Guarda distribución de referencia (training)."""
        self.reference_distributions[feature_name] = values
    
    def set_references_from_df(self, df: pd.DataFrame, features: List[str]):
        """Guarda distribuciones de referencia desde DataFrame de training."""
        for feature in features:
            if feature in df.columns:
                self.reference_distributions[feature] = df[feature].dropna().values
    
    def detect_drift(self, feature_name: str, current_values: np.ndarray) -> dict:
        """
        Detecta drift en un feature usando test KS.
        
        H0: Las dos muestras vienen de la misma distribución
        Si p-value < threshold: rechazar H0 → drift detectado
        """
        if feature_name not in self.reference_distributions:
            return {
                'feature': feature_name,
                'drift_detected': False,
                'error': 'No hay distribución de referencia'
            }
        
        reference = self.reference_distributions[feature_name]
        
        # Test Kolmogorov-Smirnov
        ks_stat, p_value = stats.ks_2samp(reference, current_values)
        
        drift_detected = p_value < self.p_value_threshold
        
        return {
            'feature': feature_name,
            'ks_statistic': float(ks_stat),
            'p_value': float(p_value),
            'drift_detected': drift_detected,
            'reference_mean': float(reference.mean()),
            'reference_std': float(reference.std()),
            'current_mean': float(current_values.mean()),
            'current_std': float(current_values.std())
        }
    
    def detect_all_drift(self, current_df: pd.DataFrame) -> dict:
        """
        Detecta drift en todos los features.
        
        Retorna resumen con:
        - features_with_drift: lista de features con drift
        - drift_percentage: % de features con drift
        - should_retrain: bool si > threshold
        - details: dict por feature
        """
        results = {}
        features_with_drift = []
        
        for feature in self.reference_distributions.keys():
            if feature not in current_df.columns:
                continue
            
            current_values = current_df[feature].dropna().values
            
            if len(current_values) < 30:  # Mínimo para KS test
                continue
            
            result = self.detect_drift(feature, current_values)
            results[feature] = result
            
            if result['drift_detected']:
                features_with_drift.append(feature)
        
        total_features = len(results)
        drift_pct = len(features_with_drift) / total_features if total_features > 0 else 0
        
        return {
            'checked_at': datetime.utcnow().isoformat(),
            'total_features': total_features,
            'features_with_drift': features_with_drift,
            'drift_percentage': drift_pct,
            'should_retrain': drift_pct > self.drift_pct_threshold,
            'details': results
        }
    
    def save_references(self, path: str):
        """Guarda distribuciones de referencia."""
        # Guardar como numpy arrays
        np.savez(path, **self.reference_distributions)
    
    def load_references(self, path: str):
        """Carga distribuciones de referencia."""
        data = np.load(path)
        self.reference_distributions = {k: data[k] for k in data.files}


class DriftMonitoringJob:
    """Job diario de monitoreo de drift."""
    
    def __init__(self, db_connection, redis_client, model_path: str):
        self.db = db_connection
        self.redis = redis_client
        self.detector = DriftDetector()
        
        # Cargar distribuciones de referencia
        self.detector.load_references(f"{model_path}/reference_distributions.npz")
    
    def run(self, days_to_check: int = 7) -> dict:
        """
        Ejecuta verificación de drift.
        
        1. Cargar features de últimos N días
        2. Comparar con distribución de referencia
        3. Generar reporte
        4. Alertar si necesario
        """
        from src.ml.features.loader import FeatureLoader
        
        loader = FeatureLoader(self.db, self.redis)
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_to_check)
        
        # Cargar features recientes
        df = loader.load_training_features(
            symbols=['SPY', 'QQQ', 'IWM'],  # Símbolos de referencia
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )
        
        # Detectar drift
        result = self.detector.detect_all_drift(df)
        
        # Guardar en Redis
        self.redis.set(
            "ml:drift:latest",
            json.dumps(result),
            ex=86400  # TTL 1 día
        )
        
        # Alertar si necesario
        if result['should_retrain']:
            self._send_alert(result)
        
        return result
    
    def _send_alert(self, result: dict):
        """Envía alerta de drift."""
        self.redis.publish(
            "alerts:ml",
            json.dumps({
                'type': 'feature_drift',
                'drift_percentage': result['drift_percentage'],
                'features_affected': result['features_with_drift'],
                'recommendation': 'Considerar reentrenamiento del modelo'
            })
        )
```

---

### Tarea 5.11: Crear script de verificación completo

**Estado:** ⬜ Pendiente

**Objetivo:** Script que valida toda la fase 5 está funcionando correctamente.

**Referencias:** Todas las tareas anteriores

**Subtareas:**
- [ ] Crear `scripts/verify_ml.py`
- [ ] Verificar estructura de directorios
- [ ] Verificar modelo HMM cargable
- [ ] Verificar mcp-ml-models responde
- [ ] Verificar calibración y drift jobs funcionan
- [ ] Generar reporte de estado

**Input:** Ninguno (verificación automática)

**Output:** Reporte de estado con checks pass/fail

**Validación:** Todos los checks pasan

**Script:**
```python
#!/usr/bin/env python
"""
Verificación completa de Fase 5: ML Pipeline

Ejecutar: python scripts/verify_ml.py
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

class MLVerification:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def check(self, name: str, condition: bool, details: str = ""):
        status = "✅" if condition else "❌"
        self.results.append({
            'name': name,
            'passed': condition,
            'details': details
        })
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status} {name}")
        if details and not condition:
            print(f"   └─ {details}")
    
    def run_all(self):
        print("\n" + "="*60)
        print("VERIFICACIÓN FASE 5: ML PIPELINE")
        print("="*60 + "\n")
        
        # 1. Estructura de directorios
        print("📁 Estructura de directorios")
        print("-" * 40)
        self._check_directories()
        
        # 2. Dependencias
        print("\n📦 Dependencias Python")
        print("-" * 40)
        self._check_dependencies()
        
        # 3. Modelo HMM
        print("\n🧠 Modelo HMM")
        print("-" * 40)
        self._check_hmm_model()
        
        # 4. MCP Server
        print("\n🔌 MCP Server mcp-ml-models")
        print("-" * 40)
        self._check_mcp_server()
        
        # 5. Monitoreo
        print("\n📊 Monitoreo")
        print("-" * 40)
        self._check_monitoring()
        
        # Resumen
        print("\n" + "="*60)
        print(f"RESUMEN: {self.passed} passed, {self.failed} failed")
        print("="*60)
        
        return self.failed == 0
    
    def _check_directories(self):
        required_dirs = [
            "src/ml",
            "src/ml/features",
            "src/ml/models",
            "src/ml/training",
            "src/ml/serving",
            "src/ml/monitoring",
            "models",
            "mcp-servers/mcp-ml-models"
        ]
        
        for dir_path in required_dirs:
            exists = Path(dir_path).exists()
            self.check(f"Directorio {dir_path}", exists)
    
    def _check_dependencies(self):
        required_packages = [
            "numpy",
            "pandas",
            "scikit-learn",
            "hmmlearn",
            "scipy",
            "joblib"
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self.check(f"Package {package}", True)
            except ImportError:
                self.check(f"Package {package}", False, "No instalado")
    
    def _check_hmm_model(self):
        # Verificar que existe modelo
        model_dir = Path("models/hmm_regime")
        has_model = model_dir.exists() and any(model_dir.iterdir())
        self.check("Modelo HMM existe", has_model)
        
        if not has_model:
            return
        
        # Verificar que carga correctamente
        try:
            from src.ml.models.hmm_regime import HMMRegimeDetector
            
            # Encontrar última versión
            versions = sorted(model_dir.glob("v*"))
            if versions:
                latest = versions[-1]
                
                detector = HMMRegimeDetector()
                detector.load(str(latest))
                
                self.check("Modelo HMM carga", True)
                self.check(
                    "Modelo tiene 4 estados", 
                    detector.config.n_states == 4
                )
                
                # Verificar predicción funciona
                test_features = {
                    'adx_14': 25.0,
                    'returns_20d': 0.02,
                    'volatility_20d': 0.15
                }
                regime, prob = detector.predict(test_features)
                self.check(
                    "Predicción funciona",
                    regime in ['trending_bull', 'trending_bear', 'range_bound', 'high_volatility']
                )
                self.check(
                    "Probabilidad válida",
                    0 <= prob <= 1
                )
        except Exception as e:
            self.check("Modelo HMM carga", False, str(e))
    
    def _check_mcp_server(self):
        mcp_dir = Path("mcp-servers/mcp-ml-models")
        
        # Verificar archivos
        self.check(
            "package.json existe",
            (mcp_dir / "package.json").exists()
        )
        self.check(
            "src/index.ts existe",
            (mcp_dir / "src/index.ts").exists()
        )
        
        # Verificar tools
        tools_dir = mcp_dir / "src/tools"
        for tool in ["get_regime.ts", "predict.ts", "get_model_info.ts"]:
            self.check(
                f"Tool {tool} existe",
                (tools_dir / tool).exists()
            )
        
        # Verificar que compila (si node disponible)
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(mcp_dir),
                capture_output=True,
                timeout=30
            )
            self.check("MCP server compila", result.returncode == 0)
        except Exception as e:
            self.check("MCP server compila", False, str(e))
    
    def _check_monitoring(self):
        # Verificar módulos de monitoreo
        try:
            from src.ml.monitoring.calibration import CalibrationMonitor
            self.check("CalibrationMonitor importable", True)
            
            # Test rápido de ECE
            import numpy as np
            monitor = CalibrationMonitor()
            preds = np.array([0.7, 0.8, 0.6, 0.9])
            outcomes = np.array([1, 1, 0, 1])
            ece = monitor.calculate_ece(preds, outcomes)
            self.check("ECE calculable", 0 <= ece <= 1)
            
        except Exception as e:
            self.check("CalibrationMonitor importable", False, str(e))
        
        try:
            from src.ml.monitoring.drift import DriftDetector
            self.check("DriftDetector importable", True)
        except Exception as e:
            self.check("DriftDetector importable", False, str(e))


def main():
    verification = MLVerification()
    success = verification.run_all()
    
    # Guardar reporte
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'passed': verification.passed,
        'failed': verification.failed,
        'results': verification.results
    }
    
    with open('reports/ml_verification.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Reporte guardado en reports/ml_verification.json")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

---

## 4. Tests de Integración

### 4.1 Test de Pipeline Completo

```python
# tests/ml/test_integration.py
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class TestMLPipelineIntegration:
    """Tests de integración para el pipeline ML completo."""
    
    @pytest.fixture
    def sample_data(self):
        """Genera datos de prueba."""
        dates = pd.date_range('2020-01-01', '2023-12-31', freq='D')
        np.random.seed(42)
        
        df = pd.DataFrame({
            'timestamp': dates,
            'symbol': 'SPY',
            'close': 100 + np.cumsum(np.random.randn(len(dates)) * 0.5),
            'high': 0,  # Se calculará
            'low': 0,
            'volume': np.random.randint(1e6, 1e7, len(dates)),
            'adx_14': np.random.uniform(15, 40, len(dates)),
            'returns_20d': np.random.randn(len(dates)) * 0.05,
            'volatility_20d': np.abs(np.random.randn(len(dates)) * 0.02) + 0.1
        })
        
        df['high'] = df['close'] * (1 + np.abs(np.random.randn(len(dates)) * 0.01))
        df['low'] = df['close'] * (1 - np.abs(np.random.randn(len(dates)) * 0.01))
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def test_triple_barrier_labeling(self, sample_data):
        """Verifica que Triple Barrier genera labels válidos."""
        from src.ml.features.labeler import TripleBarrierLabeler, BarrierConfig
        
        labeler = TripleBarrierLabeler(BarrierConfig(
            profit_target=0.02,
            stop_loss=0.01,
            max_holding_days=5
        ))
        
        labels = labeler.generate_labels(sample_data)
        
        # Verificar distribución razonable
        dist = labeler.get_label_distribution(labels)
        assert dist['total_samples'] > 0
        assert 0 < dist['positive'] < 1
        assert 0 < dist['negative'] < 1
    
    def test_temporal_split_no_leakage(self, sample_data):
        """Verifica que split temporal no tiene leakage."""
        from src.ml.training.splitter import TemporalSplitter, SplitConfig
        
        splitter = TemporalSplitter(SplitConfig(
            train_end="2021-12-31",
            val_end="2023-06-30",
            embargo_days=5
        ))
        
        train, val, test = splitter.split(sample_data)
        
        # Verificar no overlap
        checks = splitter.validate_no_leakage(train, val, test)
        assert checks['all_passed']
        
        # Verificar tamaños razonables
        assert len(train) > len(val)
        assert len(val) > 0
        assert len(test) > 0
    
    def test_hmm_training_and_prediction(self, sample_data):
        """Verifica que HMM entrena y predice correctamente."""
        from src.ml.models.hmm_regime import HMMRegimeDetector, HMMConfig
        
        config = HMMConfig(
            n_states=4,
            n_iter=50,
            features=['adx_14', 'returns_20d', 'volatility_20d']
        )
        
        detector = HMMRegimeDetector(config)
        
        # Entrenar
        metrics = detector.train(sample_data)
        
        assert metrics['converged']
        assert 'log_likelihood' in metrics
        
        # Predecir
        test_features = {
            'adx_14': 25.0,
            'returns_20d': 0.02,
            'volatility_20d': 0.15
        }
        
        regime, prob = detector.predict(test_features)
        
        assert regime in ['trending_bull', 'trending_bear', 'range_bound', 'high_volatility']
        assert 0 <= prob <= 1
    
    def test_calibration_monitoring(self):
        """Verifica que monitoreo de calibración funciona."""
        from src.ml.monitoring.calibration import CalibrationMonitor
        
        monitor = CalibrationMonitor(n_bins=10, ece_threshold=0.10)
        
        # Modelo bien calibrado
        np.random.seed(42)
        n = 1000
        probs = np.random.uniform(0, 1, n)
        outcomes = (np.random.uniform(0, 1, n) < probs).astype(int)
        
        ece = monitor.calculate_ece(probs, outcomes)
        assert ece < 0.15  # Debería estar bien calibrado
        
        # Modelo mal calibrado (overconfident)
        bad_probs = np.clip(probs + 0.3, 0, 1)
        bad_ece = monitor.calculate_ece(bad_probs, outcomes)
        assert bad_ece > ece  # ECE debería ser mayor
    
    def test_drift_detection(self, sample_data):
        """Verifica que detección de drift funciona."""
        from src.ml.monitoring.drift import DriftDetector
        
        detector = DriftDetector(p_value_threshold=0.01)
        
        # Establecer referencia
        detector.set_references_from_df(
            sample_data.iloc[:500],
            ['adx_14', 'returns_20d', 'volatility_20d']
        )
        
        # Sin drift (mismo período)
        result_no_drift = detector.detect_all_drift(sample_data.iloc[500:700])
        assert result_no_drift['drift_percentage'] < 0.5
        
        # Con drift (datos alterados)
        drifted_data = sample_data.iloc[700:900].copy()
        drifted_data['adx_14'] = drifted_data['adx_14'] + 20  # Shift significativo
        
        result_drift = detector.detect_all_drift(drifted_data)
        assert 'adx_14' in result_drift['features_with_drift']
```

---

## 5. Troubleshooting

### HMM no converge

```python
# Verificar datos de entrada
print(f"Samples: {len(X)}")
print(f"NaN count: {np.isnan(X).sum()}")
print(f"Inf count: {np.isinf(X).sum()}")

# Aumentar iteraciones
config = HMMConfig(n_iter=200)

# Verificar varianza de features
for i, f in enumerate(features):
    print(f"{f}: mean={X[:, i].mean():.4f}, std={X[:, i].std():.4f}")
```

### ECE muy alto

```python
# Verificar distribución de predicciones
import matplotlib.pyplot as plt

plt.hist(predictions, bins=20)
plt.title("Distribución de predicciones")
plt.show()

# Si muy concentradas en extremos, considerar temperature scaling
# Si uniformes pero mal calibradas, usar Platt scaling
```

### Feature drift detectado incorrectamente

```python
# Verificar tamaño de muestras
print(f"Reference samples: {len(reference)}")
print(f"Current samples: {len(current)}")

# KS test necesita al menos 30+ samples
# Aumentar window_days si hay pocos datos

# Verificar que features son comparables (mismo preprocesamiento)
```

### mcp-ml-models no responde

```bash
# Verificar que Python serve.py funciona standalone
python mcp-servers/mcp-ml-models/python/serve.py get_regime '{}'

# Verificar modelo cargado
ls -la models/hmm_regime/latest/

# Verificar Redis disponible
redis-cli ping
```

### Predicción muy lenta

```python
# Verificar cache Redis
redis-cli GET "ml:regime:current"

# Si no hay cache, verificar TTL
# Si hay cache pero lento, verificar conexión Redis

# Profiling de predicción
import time
start = time.time()
regime, prob = detector.predict(features)
print(f"Prediction time: {time.time() - start:.3f}s")
```

---

## 6. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Catálogo de features | Doc 2 | 6.2 |
| Feature Store | Doc 2 | 6 |
| Régimen detection uso | Doc 1 | 4.6 |
| Calibration-aware throttle | Doc 1 | 4.5 |
| MCP server tools | Doc 3 | 7.4 |
| Métricas de trading | Doc 4 | 3.5 |
| Estrategias que usan ML | Doc 4 | 1 |
| Modelos ML detalle | Doc 5 | 2 |
| Training pipeline | Doc 5 | 4 |
| Validación anti-overfitting | Doc 5 | 5 |
| MLOps fases | Doc 5 | 6 |

---

## 7. Siguiente Fase

Una vez completada la Fase 5:

**Verificar:**
- `python scripts/verify_ml.py` pasa 100%
- HMM detecta régimen correctamente en datos históricos conocidos
- mcp-ml-models responde a `get_regime` con latencia < 500ms
- ECE < 0.10 en validación

**Siguiente:** `fase_6_integracion.md`

**Contenido Fase 6:**
- Integración de todos los componentes (Fases 0-5)
- Kill switch y circuit breakers completos
- Dashboard Grafana con todas las métricas
- Alertas Telegram configuradas
- 30 días de paper trading validado
- Runbooks de operación

---

*Fase 5 - ML Pipeline*  
*Bot de Trading Autónomo con IA*
