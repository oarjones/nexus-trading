# 🧠 Fase A2: ML Modular

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fase A1 (Extensiones Base) completada  
**Prerrequisito:** mcp-ml-models funcionando con health_check

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

La Fase A1 ha establecido:
- Servidor mcp-ml-models con estructura base (puerto 3005)
- Tool `regime.py` con placeholder (reglas hardcoded)
- Tablas de métricas en PostgreSQL
- Configuración YAML para modelos en `config/ml_models.yaml`

### 1.2 Objetivo de Esta Fase

Implementar un sistema de detección de régimen de mercado **modular e intercambiable**, donde:
- Diferentes modelos (HMM, reglas, RL futuro) comparten la misma interfaz
- Un Factory selecciona el modelo activo según configuración
- Todo es medible y comparable mediante métricas estandarizadas

```
FILOSOFÍA CLAVE:
═══════════════════════════════════════════════════════════════
1. Interfaces primero - Definir ABC antes de implementar
2. Baseline obligatorio - Rules como comparación de referencia
3. Métricas desde día 1 - Cada predicción genera datos comparables
4. Intercambiable - Cambiar modelo = cambiar config YAML
═══════════════════════════════════════════════════════════════
```

### 1.3 Decisiones de Diseño

| Decisión | Justificación |
|----------|---------------|
| ABC (Abstract Base Class) | Fuerza contrato uniforme, facilita testing |
| Dataclasses para outputs | Inmutabilidad, serialización JSON nativa |
| Factory pattern | Desacopla creación de uso, configurable |
| Singleton para modelo activo | Un solo modelo cargado en memoria |
| Cache Redis para predicciones | Evita recálculos, TTL configurable |

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| Interfaz RegimeDetector | ABC definida, todos los métodos abstractos claros |
| HMM implementado | Entrena con datos históricos, detecta 4 estados |
| Rules Baseline | Funciona sin entrenamiento, comparable con HMM |
| Factory funcional | Crea modelo según `config/ml_models.yaml` |
| Integración mcp-ml-models | `get_regime` usa modelo real, no placeholder |
| Tests unitarios | > 80% cobertura en `src/ml/` |

---

## 3. Arquitectura de ML Modular

### 3.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ML MODULAR SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  config/ml_models.yaml                                                      │
│  ┌─────────────────────────┐                                                │
│  │ regime_detector:        │                                                │
│  │   active: "hmm"         │                                                │
│  │   models:               │                                                │
│  │     hmm: {...}          │                                                │
│  │     rules: {...}        │                                                │
│  └─────────────────────────┘                                                │
│              │                                                              │
│              ▼                                                              │
│  ┌─────────────────────────┐                                                │
│  │   ModelFactory          │                                                │
│  │   .create_regime()      │◄─────── Lee config, instancia modelo           │
│  └─────────────────────────┘                                                │
│              │                                                              │
│      ┌───────┴───────┐                                                      │
│      ▼               ▼                                                      │
│  ┌────────┐     ┌────────────┐     ┌────────────┐                           │
│  │  HMM   │     │   Rules    │     │    PPO     │  ◄── Futuro               │
│  │Detector│     │  Baseline  │     │  Detector  │                           │
│  └────────┘     └────────────┘     └────────────┘                           │
│      │               │                   │                                  │
│      └───────┬───────┴───────────────────┘                                  │
│              │                                                              │
│              ▼                                                              │
│  ┌─────────────────────────┐        ┌─────────────────────────┐             │
│  │  RegimeDetector (ABC)   │◄───────│   RegimePrediction      │             │
│  │  - model_id             │        │   (dataclass output)    │             │
│  │  - fit()                │        └─────────────────────────┘             │
│  │  - predict()            │                                                │
│  │  - save() / load()      │                                                │
│  └─────────────────────────┘                                                │
│              │                                                              │
│              ▼                                                              │
│  ┌─────────────────────────┐                                                │
│  │   mcp-ml-models         │                                                │
│  │   (puerto 3005)         │                                                │
│  │   tools/regime.py       │◄─────── Usa Factory para obtener modelo        │
│  └─────────────────────────┘                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flujo de Predicción

```
                    ┌─────────────────┐
                    │   Estrategia    │
                    │ (ETF Momentum)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  mcp-ml-models  │
                    │  get_regime()   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  Cache   │   │  Factory │   │  Metrics │
        │  Redis   │   │  create  │   │  Logger  │
        └──────────┘   └──────────┘   └──────────┘
              │              │              │
              │      ┌───────▼───────┐     │
              │      │    Modelo     │     │
              │      │ (HMM/Rules)   │     │
              │      └───────┬───────┘     │
              │              │             │
              └──────────────┴─────────────┘
                             │
                    ┌────────▼────────┐
                    │ RegimePrediction│
                    │   (dataclass)   │
                    └─────────────────┘
```

### 3.3 Estructura de Directorios

```
src/ml/
├── __init__.py
├── interfaces.py           # ← NUEVO: ABC + Dataclasses
├── factory.py              # ← NUEVO: Crear modelos según config
├── config.py               # Actualizar con nuevas opciones
├── exceptions.py           # ← NUEVO: Excepciones específicas ML
├── models/
│   ├── __init__.py
│   ├── base.py             # Eliminar (reemplazado por interfaces.py)
│   ├── hmm_regime.py       # ← NUEVO: Implementación HMM
│   ├── rules_baseline.py   # ← NUEVO: Baseline comparación
│   └── registry.py         # Actualizar para usar Factory
└── utils/
    ├── __init__.py
    ├── feature_prep.py     # ← NUEVO: Preparación features para ML
    └── validation.py       # ← NUEVO: Validación de inputs

models/                     # Artefactos persistidos
├── hmm_regime/
│   ├── v1_YYYYMMDD_hash/   # Versión con fecha y hash config
│   │   ├── model.pkl
│   │   ├── config.yaml
│   │   └── metrics.json
│   └── latest -> v1_xxx/   # Symlink a versión activa
└── rules_baseline/
    └── v1_static/          # Rules no necesita entrenamiento
        └── config.yaml

mcp-servers/ml-models/
├── tools/
│   ├── regime.py           # ACTUALIZAR: usar Factory + modelo real
│   └── model_info.py       # ACTUALIZAR: info de modelo cargado
└── __model_cache__.py      # ← NUEVO: Singleton para modelo en memoria
```

---

## 4. Dependencias Entre Tareas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FASE A2: ML MODULAR                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐                                                   │
│  │ A2.1: Interfaces     │                                                   │
│  │ (ABC + Dataclasses)  │◄─────── PRIMERO: Define contrato                  │
│  └──────────────────────┘                                                   │
│              │                                                              │
│      ┌───────┴───────┐                                                      │
│      ▼               ▼                                                      │
│  ┌──────────────┐  ┌──────────────┐                                         │
│  │ A2.2: HMM    │  │ A2.3: Rules  │  ◄── Pueden hacerse en paralelo         │
│  │ Detector     │  │ Baseline     │                                         │
│  └──────────────┘  └──────────────┘                                         │
│      │               │                                                      │
│      └───────┬───────┘                                                      │
│              ▼                                                              │
│  ┌──────────────────────┐                                                   │
│  │ A2.4: Factory +      │                                                   │
│  │ Configuración YAML   │◄─────── Necesita ambas implementaciones           │
│  └──────────────────────┘                                                   │
│              │                                                              │
│              ▼                                                              │
│  ┌──────────────────────┐                                                   │
│  │ A2.5: Integrar       │                                                   │
│  │ mcp-ml-models        │◄─────── Actualizar regime.py                      │
│  └──────────────────────┘                                                   │
│              │                                                              │
│              ▼                                                              │
│  ┌──────────────────────┐                                                   │
│  │ A2.6: Tests +        │                                                   │
│  │ Verificación         │◄─────── Validar todo integrado                    │
│  └──────────────────────┘                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

ESTIMACIÓN DE TIEMPO:
─────────────────────
A2.1: 2 horas    │ Interfaces y dataclasses
A2.2: 4 horas    │ HMM con hmmlearn (más complejo)
A2.3: 2 horas    │ Rules baseline (simple)
A2.4: 2 horas    │ Factory + YAML
A2.5: 2 horas    │ Integración MCP
A2.6: 3 horas    │ Tests y verificación
─────────────────
TOTAL: ~15 horas (2 días de trabajo)
```

---

## 5. Tarea A2.1: Interfaces y Dataclasses

### 5.1 Objetivo

Definir el contrato que TODOS los detectores de régimen deben cumplir, usando Abstract Base Classes de Python.

### 5.2 Archivo: `src/ml/interfaces.py`

```python
# src/ml/interfaces.py
"""
Interfaces base para modelos de Machine Learning.

Define contratos que todas las implementaciones deben seguir,
garantizando intercambiabilidad y consistencia.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import numpy as np
import json


class RegimeType(str, Enum):
    """
    Tipos de régimen de mercado detectables.
    
    Basado en: handoff_document sección 4.2
    """
    BULL = "BULL"           # Mercado alcista, tendencia clara
    BEAR = "BEAR"           # Mercado bajista, tendencia clara
    SIDEWAYS = "SIDEWAYS"   # Mercado lateral, sin tendencia
    VOLATILE = "VOLATILE"   # Alta volatilidad, régimen incierto
    UNKNOWN = "UNKNOWN"     # No determinado (error o sin datos)
    
    @classmethod
    def from_string(cls, value: str) -> "RegimeType":
        """Convierte string a RegimeType, con fallback a UNKNOWN."""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class RegimePrediction:
    """
    Resultado de una predicción de régimen de mercado.
    
    Inmutable (frozen=True) para seguridad y hashability.
    Serializable a JSON para almacenamiento y APIs.
    
    Atributos:
        regime: Régimen detectado
        confidence: Confianza en la predicción (0.0 - 1.0)
        probabilities: Probabilidades para cada régimen
        model_id: Identificador del modelo usado
        inference_time_ms: Tiempo de inferencia en milisegundos
        timestamp: Momento de la predicción
        features_used: Features usados para la predicción
        metadata: Información adicional específica del modelo
    """
    regime: RegimeType
    confidence: float
    probabilities: Dict[str, float]
    model_id: str
    inference_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    features_used: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validaciones post-inicialización."""
        # Validar confidence en rango
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence debe estar entre 0 y 1, recibido: {self.confidence}")
        
        # Validar que probabilities suman ~1.0
        prob_sum = sum(self.probabilities.values())
        if not 0.99 <= prob_sum <= 1.01:
            raise ValueError(f"probabilities deben sumar ~1.0, suman: {prob_sum}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización."""
        result = asdict(self)
        result['regime'] = self.regime.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Serializa a JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegimePrediction":
        """Reconstruye desde diccionario."""
        data = data.copy()
        data['regime'] = RegimeType.from_string(data['regime'])
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    @property
    def is_tradeable(self) -> bool:
        """
        Indica si el régimen permite operar.
        
        VOLATILE y UNKNOWN no son tradeables.
        """
        return self.regime in (RegimeType.BULL, RegimeType.BEAR, RegimeType.SIDEWAYS)
    
    @property
    def is_high_confidence(self) -> bool:
        """Indica si la confianza supera umbral (0.6)."""
        return self.confidence >= 0.6


@dataclass
class ModelMetrics:
    """
    Métricas de rendimiento de un modelo.
    
    Usado para comparar modelos y tracking de performance.
    """
    model_id: str
    version: str
    trained_at: Optional[datetime] = None
    train_samples: int = 0
    log_likelihood: Optional[float] = None  # Para HMM
    aic: Optional[float] = None             # Akaike Information Criterion
    bic: Optional[float] = None             # Bayesian Information Criterion
    accuracy_validation: Optional[float] = None
    regime_distribution: Optional[Dict[str, float]] = None
    inference_time_avg_ms: float = 0.0
    last_prediction_at: Optional[datetime] = None
    predictions_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.trained_at:
            result['trained_at'] = self.trained_at.isoformat()
        if self.last_prediction_at:
            result['last_prediction_at'] = self.last_prediction_at.isoformat()
        return result


class RegimeDetector(ABC):
    """
    Interfaz abstracta para detectores de régimen de mercado.
    
    Todas las implementaciones (HMM, Rules, PPO, etc.) DEBEN
    heredar de esta clase e implementar todos los métodos abstractos.
    
    Ejemplo de uso:
        detector = HMMRegimeDetector(config)
        detector.fit(training_data)
        prediction = detector.predict(current_features)
        detector.save("models/hmm_regime/v1")
    """
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Identificador único del modelo.
        
        Formato recomendado: "{tipo}_{version}_{hash_config}"
        Ejemplo: "hmm_v1_abc123"
        """
        pass
    
    @property
    @abstractmethod
    def is_fitted(self) -> bool:
        """Indica si el modelo ha sido entrenado/configurado."""
        pass
    
    @property
    @abstractmethod
    def required_features(self) -> List[str]:
        """
        Lista de features requeridos para predicción.
        
        Ejemplo: ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
        """
        pass
    
    @abstractmethod
    def fit(
        self, 
        X: np.ndarray, 
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "RegimeDetector":
        """
        Entrena el modelo con datos históricos.
        
        Args:
            X: Matriz de features (n_samples, n_features)
            y: Labels opcionales (para modelos supervisados)
            feature_names: Nombres de las columnas de features
        
        Returns:
            self (para encadenamiento)
        
        Raises:
            ValueError: Si datos inválidos
            RuntimeError: Si falla entrenamiento
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predice el régimen actual dado un vector de features.
        
        Args:
            X: Vector de features (1, n_features) o (n_features,)
        
        Returns:
            RegimePrediction con el régimen y metadatos
        
        Raises:
            ValueError: Si features inválidos
            RuntimeError: Si modelo no fitted
        """
        pass
    
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        """
        Obtiene probabilidades de cada régimen.
        
        Args:
            X: Vector de features
        
        Returns:
            Dict con probabilidad para cada RegimeType
        """
        pass
    
    @abstractmethod
    def save(self, path: str) -> None:
        """
        Persiste el modelo y su configuración.
        
        Args:
            path: Directorio donde guardar (se crean subdirectorios)
        
        Files creados:
            - model.pkl: Modelo serializado
            - config.yaml: Configuración usada
            - metrics.json: Métricas de entrenamiento
        """
        pass
    
    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "RegimeDetector":
        """
        Carga un modelo previamente guardado.
        
        Args:
            path: Directorio con los archivos del modelo
        
        Returns:
            Instancia del detector cargado
        
        Raises:
            FileNotFoundError: Si no existe el path
            ValueError: Si archivos corruptos o incompatibles
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> ModelMetrics:
        """
        Obtiene métricas del modelo.
        
        Returns:
            ModelMetrics con información de rendimiento
        """
        pass
    
    def validate_features(self, X: np.ndarray) -> bool:
        """
        Valida que el input tenga el formato correcto.
        
        Args:
            X: Array de features
        
        Returns:
            True si válido
        
        Raises:
            ValueError: Con descripción del problema
        """
        if X is None:
            raise ValueError("Features no pueden ser None")
        
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Features deben ser np.ndarray, recibido: {type(X)}")
        
        # Reshape si es 1D
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] != len(self.required_features):
            raise ValueError(
                f"Se esperan {len(self.required_features)} features, "
                f"recibidos: {X.shape[1]}"
            )
        
        if np.isnan(X).any():
            raise ValueError("Features contienen NaN")
        
        if np.isinf(X).any():
            raise ValueError("Features contienen Inf")
        
        return True


class ModelFactory(ABC):
    """
    Factory abstracta para crear detectores de régimen.
    
    Implementaciones concretas leen configuración y crean
    el modelo apropiado.
    """
    
    @abstractmethod
    def create_regime_detector(
        self, 
        model_type: Optional[str] = None
    ) -> RegimeDetector:
        """
        Crea un detector de régimen según configuración.
        
        Args:
            model_type: Tipo de modelo ("hmm", "rules", etc.)
                       Si None, usa el modelo activo en config
        
        Returns:
            Instancia de RegimeDetector
        
        Raises:
            ValueError: Si tipo desconocido
            RuntimeError: Si falla la creación
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Lista tipos de modelos disponibles."""
        pass
    
    @abstractmethod
    def get_active_model_type(self) -> str:
        """Retorna el tipo de modelo activo según config."""
        pass
```

### 5.3 Archivo: `src/ml/exceptions.py`

```python
# src/ml/exceptions.py
"""
Excepciones específicas para el módulo de ML.

Permite manejo granular de errores en diferentes capas.
"""


class MLError(Exception):
    """Excepción base para errores de ML."""
    pass


class ModelNotFittedError(MLError):
    """El modelo no ha sido entrenado aún."""
    pass


class InvalidFeaturesError(MLError):
    """Features de entrada inválidos."""
    pass


class ModelLoadError(MLError):
    """Error al cargar modelo desde disco."""
    pass


class ModelSaveError(MLError):
    """Error al guardar modelo a disco."""
    pass


class TrainingError(MLError):
    """Error durante entrenamiento."""
    pass


class ConfigurationError(MLError):
    """Error en configuración del modelo."""
    pass


class InferenceError(MLError):
    """Error durante inferencia/predicción."""
    pass
```

### 5.4 Archivo: `src/ml/__init__.py`

```python
# src/ml/__init__.py
"""
Módulo de Machine Learning para Nexus Trading.

Exporta interfaces principales y factory.
"""

from .interfaces import (
    RegimeType,
    RegimePrediction,
    ModelMetrics,
    RegimeDetector,
    ModelFactory,
)

from .exceptions import (
    MLError,
    ModelNotFittedError,
    InvalidFeaturesError,
    ModelLoadError,
    ModelSaveError,
    TrainingError,
    ConfigurationError,
    InferenceError,
)

__all__ = [
    # Interfaces
    "RegimeType",
    "RegimePrediction",
    "ModelMetrics",
    "RegimeDetector",
    "ModelFactory",
    # Exceptions
    "MLError",
    "ModelNotFittedError",
    "InvalidFeaturesError",
    "ModelLoadError",
    "ModelSaveError",
    "TrainingError",
    "ConfigurationError",
    "InferenceError",
]
```

### 5.5 Validación de Tarea A2.1

```bash
# Verificar que interfaces se importan correctamente
python -c "
from src.ml import RegimeDetector, RegimePrediction, RegimeType
from src.ml import ModelNotFittedError, InvalidFeaturesError

# Verificar enum
assert RegimeType.BULL.value == 'BULL'
assert RegimeType.from_string('bear') == RegimeType.BEAR
assert RegimeType.from_string('invalid') == RegimeType.UNKNOWN

# Verificar dataclass
pred = RegimePrediction(
    regime=RegimeType.BULL,
    confidence=0.85,
    probabilities={'BULL': 0.85, 'BEAR': 0.05, 'SIDEWAYS': 0.05, 'VOLATILE': 0.05},
    model_id='test_v1',
    inference_time_ms=15.5
)
assert pred.is_high_confidence
assert pred.is_tradeable

# Verificar serialización
json_str = pred.to_json()
recovered = RegimePrediction.from_dict(json.loads(json_str))
assert recovered.regime == pred.regime

print('✓ Todas las interfaces funcionan correctamente')
"
```

### 5.6 Checklist Tarea A2.1

```
TAREA A2.1: INTERFACES Y DATACLASSES
═════════════════════════════════════════════════════════════════════
[ ] src/ml/interfaces.py creado
[ ] RegimeType enum definido (BULL, BEAR, SIDEWAYS, VOLATILE, UNKNOWN)
[ ] RegimePrediction dataclass con validaciones
[ ] ModelMetrics dataclass para tracking
[ ] RegimeDetector ABC con todos los métodos abstractos
[ ] ModelFactory ABC definida
[ ] src/ml/exceptions.py con excepciones específicas
[ ] src/ml/__init__.py actualizado con exports
[ ] Validación de imports ejecuta sin error
═════════════════════════════════════════════════════════════════════
```

---

## 6. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Definición de régimen original | nexus_trading_handoff.md | 4 |
| Estados de régimen | 01_arquitectura_vision_general.md | 4.6 |
| mcp-ml-models base | fase_a1_extensiones_base.md | Tarea A1.4 |
| HMM detalle técnico | 05_machine_learning.md | 2.2 |
| Feature Store | fase_1_data_pipeline.md | Tarea 1.4 |
| Tablas métricas | fase_a1_extensiones_base.md | Tarea A1.1 |

---

*Fin de Parte 1 - Contexto, Objetivos, Arquitectura e Interfaces*

**Siguiente:** Parte 2 - Implementación HMM con hmmlearn

---
# 🧠 Fase A2: ML Modular - Parte 2

## Implementación HMM con hmmlearn

---

## 7. Tarea A2.2: HMM Regime Detector

### 7.1 Objetivo

Implementar un detector de régimen de mercado usando Hidden Markov Models (HMM) con la librería `hmmlearn`. El modelo detectará 4 estados ocultos que representan diferentes condiciones de mercado.

### 7.2 Teoría Básica HMM

```
HIDDEN MARKOV MODEL PARA TRADING:
═══════════════════════════════════════════════════════════════════

Estados Ocultos (no observables directamente):
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  BULL   │────▶│  BEAR   │────▶│SIDEWAYS │────▶│VOLATILE │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     ▲               │               │               │
     └───────────────┴───────────────┴───────────────┘
                (transiciones entre estados)

Observaciones (features que medimos):
- returns_5d:     Retorno acumulado 5 días
- volatility_20d: Volatilidad rolling 20 días
- adx_14:         Average Directional Index
- volume_ratio:   Volumen vs media 20 días

El HMM aprende:
1. Probabilidades de transición entre estados
2. Distribución de observaciones para cada estado
3. Probabilidades iniciales de cada estado

Inferencia:
- Dado un vector de observaciones → estado más probable
- Algoritmo de Viterbi para secuencia óptima
═══════════════════════════════════════════════════════════════════
```

### 7.3 Archivo: `src/ml/models/hmm_regime.py`

```python
# src/ml/models/hmm_regime.py
"""
Detector de régimen de mercado usando Hidden Markov Models.

Implementa la interfaz RegimeDetector usando hmmlearn.GaussianHMM
para detectar 4 estados de mercado: BULL, BEAR, SIDEWAYS, VOLATILE.
"""

import logging
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import joblib
import yaml
from hmmlearn import hmm

from ..interfaces import (
    RegimeDetector,
    RegimePrediction,
    RegimeType,
    ModelMetrics,
)
from ..exceptions import (
    ModelNotFittedError,
    InvalidFeaturesError,
    ModelLoadError,
    ModelSaveError,
    TrainingError,
)

logger = logging.getLogger(__name__)


@dataclass
class HMMConfig:
    """
    Configuración para el modelo HMM.
    
    Atributos:
        n_states: Número de estados ocultos (default: 4)
        n_iter: Iteraciones máximas del algoritmo EM
        covariance_type: Tipo de matriz de covarianza
        features: Lista de features a usar
        random_state: Semilla para reproducibilidad
        tol: Tolerancia para convergencia
        min_covar: Covarianza mínima (evita singularidad)
    """
    n_states: int = 4
    n_iter: int = 100
    covariance_type: str = "full"  # "full", "diag", "tied", "spherical"
    features: List[str] = None
    random_state: int = 42
    tol: float = 1e-4
    min_covar: float = 1e-3
    
    def __post_init__(self):
        if self.features is None:
            self.features = [
                "returns_5d",
                "volatility_20d",
                "adx_14",
                "volume_ratio"
            ]
        
        # Validaciones
        if self.n_states < 2:
            raise ValueError("n_states debe ser >= 2")
        if self.n_iter < 10:
            raise ValueError("n_iter debe ser >= 10")
        if self.covariance_type not in ["full", "diag", "tied", "spherical"]:
            raise ValueError(f"covariance_type inválido: {self.covariance_type}")
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HMMConfig":
        return cls(**data)
    
    def config_hash(self) -> str:
        """Hash corto de la config para versionado."""
        content = str(sorted(self.to_dict().items()))
        return hashlib.md5(content.encode()).hexdigest()[:6]


class HMMRegimeDetector(RegimeDetector):
    """
    Detector de régimen de mercado basado en Hidden Markov Model.
    
    Usa GaussianHMM de hmmlearn para modelar los estados ocultos
    del mercado basándose en features técnicos observables.
    
    Ejemplo:
        config = HMMConfig(n_states=4, features=["returns_5d", "volatility_20d"])
        detector = HMMRegimeDetector(config)
        
        # Entrenar
        detector.fit(X_train, feature_names=["returns_5d", "volatility_20d"])
        
        # Predecir
        prediction = detector.predict(X_current)
        print(f"Régimen: {prediction.regime}, Confianza: {prediction.confidence}")
    """
    
    # Mapeo de índices de estado a RegimeType
    # Se ajusta después del entrenamiento basándose en características
    DEFAULT_STATE_MAPPING = {
        0: RegimeType.BULL,
        1: RegimeType.BEAR,
        2: RegimeType.SIDEWAYS,
        3: RegimeType.VOLATILE,
    }
    
    def __init__(self, config: Optional[HMMConfig] = None):
        """
        Inicializa el detector HMM.
        
        Args:
            config: Configuración del modelo. Si None, usa defaults.
        """
        self.config = config or HMMConfig()
        self._model: Optional[hmm.GaussianHMM] = None
        self._state_mapping: Dict[int, RegimeType] = {}
        self._is_fitted: bool = False
        self._version: str = "v0"
        self._trained_at: Optional[datetime] = None
        self._train_metrics: Dict[str, Any] = {}
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None
        self._predictions_count: int = 0
        self._inference_times: List[float] = []
        
        logger.info(f"HMMRegimeDetector inicializado con config: {self.config.to_dict()}")
    
    @property
    def model_id(self) -> str:
        """Identificador único del modelo."""
        return f"hmm_{self._version}_{self.config.config_hash()}"
    
    @property
    def is_fitted(self) -> bool:
        """Indica si el modelo ha sido entrenado."""
        return self._is_fitted and self._model is not None
    
    @property
    def required_features(self) -> List[str]:
        """Lista de features requeridos para predicción."""
        return self.config.features.copy()
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "HMMRegimeDetector":
        """
        Entrena el modelo HMM con datos históricos.
        
        El entrenamiento usa el algoritmo Expectation-Maximization (EM)
        para aprender los parámetros del HMM:
        - Matriz de transición entre estados
        - Medias y covarianzas de emisión por estado
        - Probabilidades iniciales
        
        Args:
            X: Matriz de features (n_samples, n_features)
            y: Ignorado (HMM es no supervisado)
            feature_names: Nombres de features para logging
        
        Returns:
            self para encadenamiento
        
        Raises:
            TrainingError: Si el entrenamiento falla
            InvalidFeaturesError: Si los datos son inválidos
        """
        logger.info(f"Iniciando entrenamiento HMM con {len(X)} muestras")
        start_time = time.time()
        
        try:
            # Validar input
            X = self._validate_and_prepare_input(X)
            
            # Normalizar features (importante para HMM)
            X_normalized, self._feature_means, self._feature_stds = self._normalize_features(X)
            
            logger.info(f"Features normalizados. Shape: {X_normalized.shape}")
            
            # Crear modelo HMM
            self._model = hmm.GaussianHMM(
                n_components=self.config.n_states,
                covariance_type=self.config.covariance_type,
                n_iter=self.config.n_iter,
                random_state=self.config.random_state,
                tol=self.config.tol,
                verbose=False,
                init_params="stmc",  # Inicializar startprob, transmat, means, covars
            )
            
            # Establecer covarianza mínima
            self._model.min_covar = self.config.min_covar
            
            # Entrenar
            logger.info("Ejecutando algoritmo EM...")
            self._model.fit(X_normalized)
            
            # Verificar convergencia
            if not self._model.monitor_.converged:
                logger.warning(
                    f"HMM no convergió en {self.config.n_iter} iteraciones. "
                    f"Considerar aumentar n_iter."
                )
            
            # Mapear estados a regímenes basándose en características aprendidas
            self._state_mapping = self._infer_state_mapping(X_normalized)
            
            # Calcular métricas de entrenamiento
            self._calculate_train_metrics(X_normalized)
            
            # Marcar como entrenado
            self._is_fitted = True
            self._trained_at = datetime.now()
            self._version = f"v1_{self._trained_at.strftime('%Y%m%d')}"
            
            elapsed = time.time() - start_time
            logger.info(
                f"Entrenamiento completado en {elapsed:.2f}s. "
                f"Log-likelihood: {self._train_metrics.get('log_likelihood', 'N/A')}"
            )
            
            return self
            
        except Exception as e:
            logger.error(f"Error en entrenamiento HMM: {e}")
            raise TrainingError(f"Fallo en entrenamiento HMM: {e}") from e
    
    def _validate_and_prepare_input(self, X: np.ndarray) -> np.ndarray:
        """Valida y prepara el input para entrenamiento/predicción."""
        if X is None:
            raise InvalidFeaturesError("Input X no puede ser None")
        
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] != len(self.config.features):
            raise InvalidFeaturesError(
                f"Se esperan {len(self.config.features)} features, "
                f"recibidos: {X.shape[1]}"
            )
        
        # Verificar NaN/Inf
        if np.isnan(X).any():
            nan_count = np.isnan(X).sum()
            raise InvalidFeaturesError(f"Input contiene {nan_count} valores NaN")
        
        if np.isinf(X).any():
            inf_count = np.isinf(X).sum()
            raise InvalidFeaturesError(f"Input contiene {inf_count} valores Inf")
        
        return X
    
    def _normalize_features(
        self,
        X: np.ndarray,
        fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Normaliza features usando z-score.
        
        Args:
            X: Features a normalizar
            fit: Si True, calcula media/std. Si False, usa existentes.
        
        Returns:
            Tuple de (X_normalized, means, stds)
        """
        if fit:
            means = X.mean(axis=0)
            stds = X.std(axis=0)
            # Evitar división por cero
            stds = np.where(stds < 1e-8, 1.0, stds)
        else:
            if self._feature_means is None or self._feature_stds is None:
                raise ModelNotFittedError("Modelo no entrenado, no hay parámetros de normalización")
            means = self._feature_means
            stds = self._feature_stds
        
        X_normalized = (X - means) / stds
        return X_normalized, means, stds
    
    def _infer_state_mapping(self, X_normalized: np.ndarray) -> Dict[int, RegimeType]:
        """
        Infiere el mapeo de índices de estado a RegimeType.
        
        Analiza las características de cada estado (medias de features)
        para asignar el régimen más apropiado.
        
        Lógica:
        - BULL: Alto retorno, baja volatilidad
        - BEAR: Bajo retorno, alta volatilidad
        - SIDEWAYS: Retorno cercano a cero, baja volatilidad
        - VOLATILE: Alta volatilidad independiente del retorno
        """
        state_mapping = {}
        
        # Obtener predicciones de estado para todos los datos
        states = self._model.predict(X_normalized)
        
        # Calcular características promedio por estado
        state_characteristics = {}
        for state_idx in range(self.config.n_states):
            mask = states == state_idx
            if mask.sum() == 0:
                continue
            
            state_data = X_normalized[mask]
            state_characteristics[state_idx] = {
                'mean_returns': state_data[:, 0].mean() if 'returns' in self.config.features[0] else 0,
                'mean_volatility': state_data[:, 1].mean() if len(self.config.features) > 1 else 0,
                'count': mask.sum(),
                'proportion': mask.sum() / len(states)
            }
        
        logger.info(f"Características por estado: {state_characteristics}")
        
        # Asignar regímenes basándose en características
        # Ordenar estados por volatilidad (índice 1 típicamente)
        states_by_vol = sorted(
            state_characteristics.keys(),
            key=lambda s: state_characteristics[s].get('mean_volatility', 0)
        )
        
        # El estado con mayor volatilidad es VOLATILE
        if len(states_by_vol) >= 1:
            state_mapping[states_by_vol[-1]] = RegimeType.VOLATILE
        
        # De los restantes, clasificar por retorno
        remaining = [s for s in states_by_vol[:-1]] if len(states_by_vol) > 1 else []
        
        if remaining:
            # Ordenar por retorno
            states_by_return = sorted(
                remaining,
                key=lambda s: state_characteristics[s].get('mean_returns', 0)
            )
            
            # Mayor retorno = BULL
            state_mapping[states_by_return[-1]] = RegimeType.BULL
            
            # Menor retorno = BEAR
            if len(states_by_return) > 1:
                state_mapping[states_by_return[0]] = RegimeType.BEAR
            
            # Intermedio = SIDEWAYS
            if len(states_by_return) > 2:
                for s in states_by_return[1:-1]:
                    state_mapping[s] = RegimeType.SIDEWAYS
        
        # Llenar estados no asignados con default
        for i in range(self.config.n_states):
            if i not in state_mapping:
                state_mapping[i] = self.DEFAULT_STATE_MAPPING.get(i, RegimeType.UNKNOWN)
        
        logger.info(f"Mapeo de estados inferido: {state_mapping}")
        return state_mapping
    
    def _calculate_train_metrics(self, X_normalized: np.ndarray) -> None:
        """Calcula métricas de entrenamiento."""
        self._train_metrics = {
            'n_samples': len(X_normalized),
            'n_features': X_normalized.shape[1],
            'n_states': self.config.n_states,
            'converged': self._model.monitor_.converged,
            'n_iter_actual': self._model.monitor_.iter,
            'log_likelihood': float(self._model.score(X_normalized)),
        }
        
        # AIC y BIC
        n_params = self._count_parameters()
        n_samples = len(X_normalized)
        log_likelihood = self._train_metrics['log_likelihood']
        
        self._train_metrics['aic'] = 2 * n_params - 2 * log_likelihood
        self._train_metrics['bic'] = n_params * np.log(n_samples) - 2 * log_likelihood
        
        # Distribución de estados
        states = self._model.predict(X_normalized)
        state_counts = np.bincount(states, minlength=self.config.n_states)
        state_dist = {
            self._state_mapping.get(i, RegimeType.UNKNOWN).value: int(count)
            for i, count in enumerate(state_counts)
        }
        self._train_metrics['state_distribution'] = state_dist
        
        logger.info(f"Métricas de entrenamiento: {self._train_metrics}")
    
    def _count_parameters(self) -> int:
        """Cuenta el número de parámetros libres del modelo."""
        n_states = self.config.n_states
        n_features = len(self.config.features)
        
        # Probabilidades iniciales: n_states - 1 (suman 1)
        n_params = n_states - 1
        
        # Matriz de transición: n_states * (n_states - 1)
        n_params += n_states * (n_states - 1)
        
        # Medias de emisión: n_states * n_features
        n_params += n_states * n_features
        
        # Covarianzas según tipo
        if self.config.covariance_type == "full":
            n_params += n_states * n_features * (n_features + 1) // 2
        elif self.config.covariance_type == "diag":
            n_params += n_states * n_features
        elif self.config.covariance_type == "tied":
            n_params += n_features * (n_features + 1) // 2
        elif self.config.covariance_type == "spherical":
            n_params += n_states
        
        return n_params
    
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predice el régimen actual dado un vector de features.
        
        Args:
            X: Vector de features (1, n_features) o (n_features,)
        
        Returns:
            RegimePrediction con el régimen detectado y metadatos
        
        Raises:
            ModelNotFittedError: Si modelo no entrenado
            InvalidFeaturesError: Si features inválidos
        """
        if not self.is_fitted:
            raise ModelNotFittedError("Modelo HMM no ha sido entrenado")
        
        start_time = time.time()
        
        try:
            # Validar y preparar input
            X = self._validate_and_prepare_input(X)
            
            # Normalizar usando parámetros de entrenamiento
            X_normalized, _, _ = self._normalize_features(X, fit=False)
            
            # Obtener probabilidades de cada estado
            log_probs = self._model.score_samples(X_normalized)
            posteriors = self._model.predict_proba(X_normalized)
            
            # Tomar última observación si hay múltiples
            if len(posteriors) > 1:
                posteriors = posteriors[-1:]
            
            posterior = posteriors[0]
            
            # Estado más probable
            state_idx = np.argmax(posterior)
            regime = self._state_mapping.get(state_idx, RegimeType.UNKNOWN)
            confidence = float(posterior[state_idx])
            
            # Construir diccionario de probabilidades
            probabilities = {
                self._state_mapping.get(i, RegimeType.UNKNOWN).value: float(p)
                for i, p in enumerate(posterior)
            }
            
            inference_time = (time.time() - start_time) * 1000  # ms
            self._inference_times.append(inference_time)
            self._predictions_count += 1
            
            # Features usados (denormalizar para legibilidad)
            features_used = {
                name: float(X[0, i])
                for i, name in enumerate(self.config.features)
            }
            
            prediction = RegimePrediction(
                regime=regime,
                confidence=confidence,
                probabilities=probabilities,
                model_id=self.model_id,
                inference_time_ms=inference_time,
                features_used=features_used,
                metadata={
                    'state_index': int(state_idx),
                    'log_likelihood': float(log_probs[-1]) if len(log_probs) > 0 else None,
                }
            )
            
            logger.debug(
                f"Predicción: {regime.value} (confianza: {confidence:.2%}, "
                f"tiempo: {inference_time:.1f}ms)"
            )
            
            return prediction
            
        except (ModelNotFittedError, InvalidFeaturesError):
            raise
        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            raise InvalidFeaturesError(f"Error en predicción: {e}") from e
    
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        """
        Obtiene probabilidades de cada régimen.
        
        Args:
            X: Vector de features
        
        Returns:
            Dict con probabilidad para cada RegimeType
        """
        prediction = self.predict(X)
        return prediction.probabilities
    
    def predict_sequence(
        self,
        X: np.ndarray,
        return_proba: bool = False
    ) -> Tuple[List[RegimeType], Optional[np.ndarray]]:
        """
        Predice secuencia de regímenes para múltiples observaciones.
        
        Usa el algoritmo de Viterbi para encontrar la secuencia
        más probable de estados.
        
        Args:
            X: Matriz de features (n_samples, n_features)
            return_proba: Si True, retorna también probabilidades
        
        Returns:
            Tuple de (lista de regímenes, probabilidades opcionales)
        """
        if not self.is_fitted:
            raise ModelNotFittedError("Modelo HMM no ha sido entrenado")
        
        X = self._validate_and_prepare_input(X)
        X_normalized, _, _ = self._normalize_features(X, fit=False)
        
        # Viterbi para secuencia óptima
        _, states = self._model.decode(X_normalized, algorithm="viterbi")
        
        regimes = [self._state_mapping.get(s, RegimeType.UNKNOWN) for s in states]
        
        if return_proba:
            proba = self._model.predict_proba(X_normalized)
            return regimes, proba
        
        return regimes, None
    
    def get_transition_matrix(self) -> pd.DataFrame:
        """
        Obtiene la matriz de transición entre estados.
        
        Returns:
            DataFrame con probabilidades de transición
        """
        if not self.is_fitted:
            raise ModelNotFittedError("Modelo no entrenado")
        
        labels = [
            self._state_mapping.get(i, RegimeType.UNKNOWN).value
            for i in range(self.config.n_states)
        ]
        
        return pd.DataFrame(
            self._model.transmat_,
            index=labels,
            columns=labels
        )
    
    def save(self, path: str) -> None:
        """
        Guarda el modelo y su configuración.
        
        Args:
            path: Directorio base donde guardar
        
        Estructura creada:
            {path}/
            ├── model.pkl       # Modelo serializado
            ├── config.yaml     # Configuración
            ├── metrics.json    # Métricas de entrenamiento
            └── normalization.npz  # Parámetros de normalización
        """
        if not self.is_fitted:
            raise ModelNotFittedError("No se puede guardar modelo no entrenado")
        
        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            
            # Guardar modelo
            model_path = path / "model.pkl"
            joblib.dump(self._model, model_path)
            logger.info(f"Modelo guardado en {model_path}")
            
            # Guardar configuración
            config_path = path / "config.yaml"
            config_data = {
                'hmm_config': self.config.to_dict(),
                'version': self._version,
                'trained_at': self._trained_at.isoformat() if self._trained_at else None,
                'state_mapping': {
                    k: v.value for k, v in self._state_mapping.items()
                },
            }
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            logger.info(f"Configuración guardada en {config_path}")
            
            # Guardar métricas
            metrics_path = path / "metrics.json"
            import json
            with open(metrics_path, 'w') as f:
                json.dump(self._train_metrics, f, indent=2)
            logger.info(f"Métricas guardadas en {metrics_path}")
            
            # Guardar parámetros de normalización
            norm_path = path / "normalization.npz"
            np.savez(
                norm_path,
                means=self._feature_means,
                stds=self._feature_stds
            )
            logger.info(f"Normalización guardada en {norm_path}")
            
            logger.info(f"Modelo completo guardado en {path}")
            
        except Exception as e:
            logger.error(f"Error guardando modelo: {e}")
            raise ModelSaveError(f"Error guardando modelo: {e}") from e
    
    @classmethod
    def load(cls, path: str) -> "HMMRegimeDetector":
        """
        Carga un modelo previamente guardado.
        
        Args:
            path: Directorio con los archivos del modelo
        
        Returns:
            Instancia del detector cargado
        """
        try:
            path = Path(path)
            
            if not path.exists():
                raise ModelLoadError(f"Path no existe: {path}")
            
            # Cargar configuración
            config_path = path / "config.yaml"
            if not config_path.exists():
                raise ModelLoadError(f"Archivo config.yaml no encontrado en {path}")
            
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Crear instancia con config
            hmm_config = HMMConfig.from_dict(config_data['hmm_config'])
            detector = cls(hmm_config)
            
            # Cargar modelo
            model_path = path / "model.pkl"
            if not model_path.exists():
                raise ModelLoadError(f"Archivo model.pkl no encontrado en {path}")
            
            detector._model = joblib.load(model_path)
            
            # Cargar state mapping
            detector._state_mapping = {
                int(k): RegimeType.from_string(v)
                for k, v in config_data.get('state_mapping', {}).items()
            }
            
            # Cargar metadata
            detector._version = config_data.get('version', 'v0')
            if config_data.get('trained_at'):
                detector._trained_at = datetime.fromisoformat(config_data['trained_at'])
            
            # Cargar métricas si existen
            metrics_path = path / "metrics.json"
            if metrics_path.exists():
                import json
                with open(metrics_path, 'r') as f:
                    detector._train_metrics = json.load(f)
            
            # Cargar normalización
            norm_path = path / "normalization.npz"
            if norm_path.exists():
                norm_data = np.load(norm_path)
                detector._feature_means = norm_data['means']
                detector._feature_stds = norm_data['stds']
            
            detector._is_fitted = True
            
            logger.info(f"Modelo cargado desde {path}: {detector.model_id}")
            return detector
            
        except ModelLoadError:
            raise
        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            raise ModelLoadError(f"Error cargando modelo: {e}") from e
    
    def get_metrics(self) -> ModelMetrics:
        """Obtiene métricas del modelo."""
        return ModelMetrics(
            model_id=self.model_id,
            version=self._version,
            trained_at=self._trained_at,
            train_samples=self._train_metrics.get('n_samples', 0),
            log_likelihood=self._train_metrics.get('log_likelihood'),
            aic=self._train_metrics.get('aic'),
            bic=self._train_metrics.get('bic'),
            regime_distribution=self._train_metrics.get('state_distribution'),
            inference_time_avg_ms=np.mean(self._inference_times) if self._inference_times else 0.0,
            predictions_count=self._predictions_count,
            last_prediction_at=datetime.now() if self._predictions_count > 0 else None,
        )
```

### 7.4 Archivo: `src/ml/utils/feature_prep.py`

```python
# src/ml/utils/feature_prep.py
"""
Utilidades para preparación de features para modelos ML.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FeaturePreparator:
    """
    Prepara features para entrenamiento e inferencia de modelos ML.
    
    Funcionalidades:
    - Selección de features relevantes
    - Manejo de valores faltantes
    - Winsorización de outliers
    - Conversión a formato numpy
    """
    
    def __init__(
        self,
        features: List[str],
        winsorize_percentile: float = 0.01,
        fill_method: str = "ffill"
    ):
        """
        Args:
            features: Lista de columnas a extraer
            winsorize_percentile: Percentil para winsorización (0.01 = 1%)
            fill_method: Método para valores faltantes ('ffill', 'drop', 'zero')
        """
        self.features = features
        self.winsorize_percentile = winsorize_percentile
        self.fill_method = fill_method
        self._winsorize_bounds: Optional[dict] = None
    
    def prepare(
        self,
        df: pd.DataFrame,
        fit_winsorize: bool = True
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Prepara DataFrame para uso en modelos ML.
        
        Args:
            df: DataFrame con features
            fit_winsorize: Si True, calcula bounds de winsorización
        
        Returns:
            Tuple de (numpy array, lista de features válidos)
        """
        # Verificar que features existen
        missing = [f for f in self.features if f not in df.columns]
        if missing:
            raise ValueError(f"Features no encontrados en DataFrame: {missing}")
        
        # Extraer features
        data = df[self.features].copy()
        
        # Manejar valores faltantes
        if self.fill_method == "ffill":
            data = data.ffill().bfill()
        elif self.fill_method == "drop":
            data = data.dropna()
        elif self.fill_method == "zero":
            data = data.fillna(0)
        
        # Winsorizar outliers
        if fit_winsorize:
            self._winsorize_bounds = {}
            for col in self.features:
                lower = data[col].quantile(self.winsorize_percentile)
                upper = data[col].quantile(1 - self.winsorize_percentile)
                self._winsorize_bounds[col] = (lower, upper)
                data[col] = data[col].clip(lower, upper)
        elif self._winsorize_bounds:
            for col in self.features:
                lower, upper = self._winsorize_bounds[col]
                data[col] = data[col].clip(lower, upper)
        
        # Verificar que no quedan NaN
        if data.isna().any().any():
            nan_cols = data.columns[data.isna().any()].tolist()
            logger.warning(f"Aún hay NaN en columnas: {nan_cols}")
            data = data.fillna(0)
        
        X = data.values.astype(np.float64)
        
        logger.info(f"Features preparados: shape={X.shape}, features={self.features}")
        return X, self.features
    
    def prepare_single(self, features_dict: dict) -> np.ndarray:
        """
        Prepara un solo vector de features desde diccionario.
        
        Args:
            features_dict: Dict con nombre -> valor de feature
        
        Returns:
            Array numpy (1, n_features)
        """
        values = []
        for f in self.features:
            if f not in features_dict:
                raise ValueError(f"Feature '{f}' no encontrado en input")
            values.append(features_dict[f])
        
        X = np.array(values, dtype=np.float64).reshape(1, -1)
        
        # Aplicar winsorización si existe
        if self._winsorize_bounds:
            for i, col in enumerate(self.features):
                if col in self._winsorize_bounds:
                    lower, upper = self._winsorize_bounds[col]
                    X[0, i] = np.clip(X[0, i], lower, upper)
        
        return X
```

### 7.5 Script de Entrenamiento: `scripts/train_hmm.py`

```python
#!/usr/bin/env python
# scripts/train_hmm.py
"""
Script para entrenar el modelo HMM de detección de régimen.

Uso:
    python scripts/train_hmm.py --config config/ml_models.yaml --output models/hmm_regime/
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import yaml

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.models.hmm_regime import HMMRegimeDetector, HMMConfig
from src.ml.utils.feature_prep import FeaturePreparator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_training_data(
    db_connection_string: str,
    symbols: list,
    start_date: str,
    end_date: str,
    features: list
) -> pd.DataFrame:
    """
    Carga datos de entrenamiento desde TimescaleDB.
    
    Para desarrollo/testing, genera datos sintéticos si no hay BD.
    """
    try:
        # Intentar cargar desde BD
        import psycopg2
        # ... implementación real de carga desde BD
        raise NotImplementedError("Implementar carga desde BD")
    except Exception as e:
        logger.warning(f"No se pudo conectar a BD: {e}. Usando datos sintéticos.")
        return generate_synthetic_data(start_date, end_date, features)


def generate_synthetic_data(
    start_date: str,
    end_date: str,
    features: list
) -> pd.DataFrame:
    """
    Genera datos sintéticos para testing del pipeline.
    
    Simula 4 regímenes de mercado con características distintas.
    """
    np.random.seed(42)
    
    dates = pd.date_range(start_date, end_date, freq='D')
    n_days = len(dates)
    
    # Simular cambios de régimen
    regime_length = n_days // 8  # ~8 cambios de régimen
    regimes = []
    for _ in range(8):
        regime = np.random.choice([0, 1, 2, 3])  # BULL, BEAR, SIDEWAYS, VOLATILE
        regimes.extend([regime] * regime_length)
    regimes = regimes[:n_days]
    
    # Generar features según régimen
    data = {'timestamp': dates[:len(regimes)]}
    
    for i, r in enumerate(regimes):
        if r == 0:  # BULL
            returns = np.random.normal(0.002, 0.01)
            vol = np.random.uniform(0.10, 0.15)
            adx = np.random.uniform(25, 40)
        elif r == 1:  # BEAR
            returns = np.random.normal(-0.002, 0.015)
            vol = np.random.uniform(0.20, 0.30)
            adx = np.random.uniform(25, 40)
        elif r == 2:  # SIDEWAYS
            returns = np.random.normal(0, 0.005)
            vol = np.random.uniform(0.08, 0.12)
            adx = np.random.uniform(10, 20)
        else:  # VOLATILE
            returns = np.random.normal(0, 0.03)
            vol = np.random.uniform(0.30, 0.50)
            adx = np.random.uniform(20, 35)
        
        for j, f in enumerate(features):
            if f not in data:
                data[f] = []
            
            if 'returns' in f:
                data[f].append(returns * 5)  # 5-day returns
            elif 'volatility' in f:
                data[f].append(vol)
            elif 'adx' in f:
                data[f].append(adx)
            elif 'volume' in f:
                data[f].append(np.random.uniform(0.8, 1.5))
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    
    logger.info(f"Datos sintéticos generados: {len(df)} muestras")
    return df


def main():
    parser = argparse.ArgumentParser(description='Entrenar modelo HMM')
    parser.add_argument('--config', default='config/ml_models.yaml', help='Archivo de configuración')
    parser.add_argument('--output', default='models/hmm_regime/', help='Directorio de salida')
    parser.add_argument('--start-date', default='2020-01-01', help='Fecha inicio entrenamiento')
    parser.add_argument('--end-date', default='2024-01-01', help='Fecha fin entrenamiento')
    args = parser.parse_args()
    
    # Cargar configuración
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        hmm_config_dict = config.get('regime_detector', {}).get('models', {}).get('hmm', {})
    else:
        logger.warning(f"Config no encontrada en {config_path}, usando defaults")
        hmm_config_dict = {}
    
    # Crear configuración HMM
    hmm_config = HMMConfig(
        n_states=hmm_config_dict.get('n_states', 4),
        n_iter=hmm_config_dict.get('n_iter', 100),
        covariance_type=hmm_config_dict.get('covariance_type', 'full'),
        features=hmm_config_dict.get('features', [
            'returns_5d', 'volatility_20d', 'adx_14', 'volume_ratio'
        ])
    )
    
    logger.info(f"Configuración HMM: {hmm_config.to_dict()}")
    
    # Cargar datos
    df = load_training_data(
        db_connection_string="",  # Placeholder
        symbols=["SPY"],  # Placeholder
        start_date=args.start_date,
        end_date=args.end_date,
        features=hmm_config.features
    )
    
    # Preparar features
    preparator = FeaturePreparator(
        features=hmm_config.features,
        winsorize_percentile=0.01
    )
    X, _ = preparator.prepare(df, fit_winsorize=True)
    
    logger.info(f"Features preparados: {X.shape}")
    
    # Crear y entrenar modelo
    detector = HMMRegimeDetector(hmm_config)
    detector.fit(X)
    
    # Guardar modelo
    version = f"v1_{datetime.now().strftime('%Y%m%d')}_{hmm_config.config_hash()}"
    output_path = Path(args.output) / version
    detector.save(str(output_path))
    
    # Crear symlink 'latest'
    latest_link = Path(args.output) / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(version)
    
    logger.info(f"Modelo guardado en {output_path}")
    logger.info(f"Symlink 'latest' actualizado")
    
    # Mostrar métricas
    metrics = detector.get_metrics()
    print("\n" + "="*60)
    print("MÉTRICAS DE ENTRENAMIENTO")
    print("="*60)
    print(f"Model ID: {metrics.model_id}")
    print(f"Samples: {metrics.train_samples}")
    print(f"Log-likelihood: {metrics.log_likelihood:.2f}")
    print(f"AIC: {metrics.aic:.2f}")
    print(f"BIC: {metrics.bic:.2f}")
    print(f"Distribución de estados: {metrics.regime_distribution}")
    print("="*60)
    
    # Test de predicción
    print("\nTEST DE PREDICCIÓN:")
    test_features = X[-1:].copy()
    prediction = detector.predict(test_features)
    print(f"Régimen: {prediction.regime.value}")
    print(f"Confianza: {prediction.confidence:.2%}")
    print(f"Probabilidades: {prediction.probabilities}")
    print(f"Tiempo inferencia: {prediction.inference_time_ms:.2f}ms")


if __name__ == "__main__":
    main()
```

### 7.6 Checklist Tarea A2.2

```
TAREA A2.2: HMM REGIME DETECTOR
═════════════════════════════════════════════════════════════════════
[ ] src/ml/models/hmm_regime.py creado
[ ] HMMConfig dataclass con validaciones
[ ] HMMRegimeDetector implementa RegimeDetector ABC
[ ] Método fit() entrena con hmmlearn.GaussianHMM
[ ] Método predict() retorna RegimePrediction
[ ] Mapeo automático de estados a RegimeType
[ ] save() guarda model.pkl, config.yaml, metrics.json, normalization.npz
[ ] load() reconstruye modelo completo
[ ] get_metrics() retorna ModelMetrics
[ ] src/ml/utils/feature_prep.py creado
[ ] scripts/train_hmm.py funcional
[ ] Test con datos sintéticos pasa
═════════════════════════════════════════════════════════════════════
```

---

## 8. Test de Validación HMM

### 8.1 Archivo: `tests/ml/test_hmm_regime.py`

```python
# tests/ml/test_hmm_regime.py
"""
Tests para HMMRegimeDetector.
"""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from src.ml.models.hmm_regime import HMMRegimeDetector, HMMConfig
from src.ml.interfaces import RegimeType, RegimePrediction
from src.ml.exceptions import ModelNotFittedError, InvalidFeaturesError


class TestHMMConfig:
    """Tests para HMMConfig."""
    
    def test_default_config(self):
        config = HMMConfig()
        assert config.n_states == 4
        assert config.n_iter == 100
        assert len(config.features) == 4
    
    def test_custom_config(self):
        config = HMMConfig(n_states=3, n_iter=50, features=["a", "b"])
        assert config.n_states == 3
        assert config.features == ["a", "b"]
    
    def test_invalid_n_states(self):
        with pytest.raises(ValueError):
            HMMConfig(n_states=1)
    
    def test_config_hash(self):
        config1 = HMMConfig(n_states=4)
        config2 = HMMConfig(n_states=4)
        config3 = HMMConfig(n_states=3)
        
        assert config1.config_hash() == config2.config_hash()
        assert config1.config_hash() != config3.config_hash()


class TestHMMRegimeDetector:
    """Tests para HMMRegimeDetector."""
    
    @pytest.fixture
    def sample_data(self):
        """Genera datos de prueba."""
        np.random.seed(42)
        n_samples = 500
        
        X = np.column_stack([
            np.random.randn(n_samples) * 0.02,   # returns_5d
            np.random.uniform(0.1, 0.3, n_samples),  # volatility_20d
            np.random.uniform(15, 35, n_samples),    # adx_14
            np.random.uniform(0.8, 1.2, n_samples),  # volume_ratio
        ])
        return X
    
    @pytest.fixture
    def trained_detector(self, sample_data):
        """Crea detector entrenado."""
        config = HMMConfig(n_states=4, n_iter=50)
        detector = HMMRegimeDetector(config)
        detector.fit(sample_data)
        return detector
    
    def test_init(self):
        detector = HMMRegimeDetector()
        assert not detector.is_fitted
        assert detector.model_id.startswith("hmm_")
    
    def test_fit(self, sample_data):
        detector = HMMRegimeDetector()
        detector.fit(sample_data)
        
        assert detector.is_fitted
        assert detector._trained_at is not None
    
    def test_predict_not_fitted(self):
        detector = HMMRegimeDetector()
        X = np.array([[0.01, 0.15, 25, 1.0]])
        
        with pytest.raises(ModelNotFittedError):
            detector.predict(X)
    
    def test_predict(self, trained_detector):
        X = np.array([[0.01, 0.15, 25, 1.0]])
        prediction = trained_detector.predict(X)
        
        assert isinstance(prediction, RegimePrediction)
        assert prediction.regime in RegimeType
        assert 0 <= prediction.confidence <= 1
        assert len(prediction.probabilities) == 4
        assert abs(sum(prediction.probabilities.values()) - 1.0) < 0.01
    
    def test_predict_invalid_features(self, trained_detector):
        X = np.array([[0.01, 0.15]])  # Solo 2 features, espera 4
        
        with pytest.raises(InvalidFeaturesError):
            trained_detector.predict(X)
    
    def test_predict_with_nan(self, trained_detector):
        X = np.array([[np.nan, 0.15, 25, 1.0]])
        
        with pytest.raises(InvalidFeaturesError):
            trained_detector.predict(X)
    
    def test_save_load(self, trained_detector):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "model"
            
            # Guardar
            trained_detector.save(str(save_path))
            
            # Verificar archivos
            assert (save_path / "model.pkl").exists()
            assert (save_path / "config.yaml").exists()
            assert (save_path / "metrics.json").exists()
            assert (save_path / "normalization.npz").exists()
            
            # Cargar
            loaded = HMMRegimeDetector.load(str(save_path))
            
            assert loaded.is_fitted
            assert loaded.model_id == trained_detector.model_id
    
    def test_predict_after_load(self, trained_detector):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "model"
            trained_detector.save(str(save_path))
            
            loaded = HMMRegimeDetector.load(str(save_path))
            
            X = np.array([[0.01, 0.15, 25, 1.0]])
            pred_original = trained_detector.predict(X)
            pred_loaded = loaded.predict(X)
            
            # Deben dar el mismo régimen
            assert pred_original.regime == pred_loaded.regime
    
    def test_get_metrics(self, trained_detector):
        metrics = trained_detector.get_metrics()
        
        assert metrics.model_id == trained_detector.model_id
        assert metrics.train_samples > 0
        assert metrics.log_likelihood is not None
    
    def test_transition_matrix(self, trained_detector):
        trans_matrix = trained_detector.get_transition_matrix()
        
        assert trans_matrix.shape == (4, 4)
        # Cada fila debe sumar ~1
        for row in trans_matrix.values:
            assert abs(row.sum() - 1.0) < 0.01
    
    def test_predict_sequence(self, trained_detector, sample_data):
        regimes, proba = trained_detector.predict_sequence(
            sample_data[:10],
            return_proba=True
        )
        
        assert len(regimes) == 10
        assert all(r in RegimeType for r in regimes)
        assert proba.shape == (10, 4)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

*Fin de Parte 2 - Implementación HMM con hmmlearn*

**Siguiente:** Parte 3 - Rules Baseline, Factory, Configuración YAML

---
# 🧠 Fase A2: ML Modular - Parte 3

## Rules Baseline, Factory y Configuración

---

## 9. Tarea A2.3: Rules Baseline Detector

### 9.1 Objetivo

Implementar un detector de régimen basado en reglas simples que sirva como **baseline de comparación**. Este modelo:
- No requiere entrenamiento
- Es completamente interpretable
- Sirve para validar que el HMM añade valor

### 9.2 Lógica de Reglas

```
REGLAS DE DETECCIÓN DE RÉGIMEN:
═══════════════════════════════════════════════════════════════════

Input: returns_5d, volatility_20d, adx_14, volume_ratio

VOLATILE (prioridad máxima):
├── volatility_20d > 0.25 (volatilidad > 25%)
└── O adx_14 > 40 AND volatility_20d > 0.20

BULL:
├── returns_5d > 0.02 (retorno > 2%)
├── AND volatility_20d < 0.20
└── AND adx_14 > 20 (tendencia presente)

BEAR:
├── returns_5d < -0.02 (retorno < -2%)
├── AND volatility_20d < 0.30
└── AND adx_14 > 20 (tendencia presente)

SIDEWAYS (default):
├── |returns_5d| <= 0.02
├── AND volatility_20d < 0.20
└── AND adx_14 < 25 (sin tendencia fuerte)

Confianza:
├── Si cumple todos los criterios: 0.8
├── Si cumple criterios principales: 0.6
└── Default (no cumple bien ninguno): 0.4
═══════════════════════════════════════════════════════════════════
```

### 9.3 Archivo: `src/ml/models/rules_baseline.py`

```python
# src/ml/models/rules_baseline.py
"""
Detector de régimen basado en reglas simples.

Sirve como baseline para comparar con modelos ML más complejos.
No requiere entrenamiento, es completamente interpretable.
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import numpy as np

from ..interfaces import (
    RegimeDetector,
    RegimePrediction,
    RegimeType,
    ModelMetrics,
)
from ..exceptions import InvalidFeaturesError

logger = logging.getLogger(__name__)


@dataclass
class RulesConfig:
    """
    Configuración para el detector basado en reglas.
    
    Define los umbrales para cada régimen.
    """
    # Features esperados (orden importa)
    features: List[str] = None
    
    # Umbrales para VOLATILE
    volatile_vol_threshold: float = 0.25
    volatile_adx_threshold: float = 40
    volatile_vol_with_adx: float = 0.20
    
    # Umbrales para BULL
    bull_return_threshold: float = 0.02
    bull_max_vol: float = 0.20
    bull_min_adx: float = 20
    
    # Umbrales para BEAR
    bear_return_threshold: float = -0.02
    bear_max_vol: float = 0.30
    bear_min_adx: float = 20
    
    # Umbrales para SIDEWAYS
    sideways_return_range: float = 0.02
    sideways_max_vol: float = 0.20
    sideways_max_adx: float = 25
    
    def __post_init__(self):
        if self.features is None:
            self.features = [
                "returns_5d",
                "volatility_20d",
                "adx_14",
                "volume_ratio"
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RulesConfig":
        return cls(**data)


class RulesBaselineDetector(RegimeDetector):
    """
    Detector de régimen basado en reglas determinísticas.
    
    Este modelo no aprende de datos, sino que aplica reglas
    predefinidas basadas en conocimiento de dominio.
    
    Ventajas:
    - No requiere entrenamiento
    - Completamente interpretable
    - Sirve como baseline para comparar modelos ML
    - Rápido en inferencia
    
    Ejemplo:
        detector = RulesBaselineDetector()
        prediction = detector.predict(np.array([[0.03, 0.15, 28, 1.1]]))
        # Resultado: BULL con alta confianza
    """
    
    VERSION = "v1_static"
    
    def __init__(self, config: Optional[RulesConfig] = None):
        """
        Inicializa el detector de reglas.
        
        Args:
            config: Configuración con umbrales. Si None, usa defaults.
        """
        self.config = config or RulesConfig()
        self._predictions_count: int = 0
        self._inference_times: List[float] = []
        self._regime_counts: Dict[str, int] = {r.value: 0 for r in RegimeType}
        
        logger.info(f"RulesBaselineDetector inicializado con config: {self.config.to_dict()}")
    
    @property
    def model_id(self) -> str:
        return f"rules_baseline_{self.VERSION}"
    
    @property
    def is_fitted(self) -> bool:
        # Las reglas no necesitan entrenamiento
        return True
    
    @property
    def required_features(self) -> List[str]:
        return self.config.features.copy()
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "RulesBaselineDetector":
        """
        No-op para reglas. Mantiene interfaz compatible.
        
        Opcionalmente puede usarse para calcular estadísticas
        de referencia de los datos.
        """
        logger.info("RulesBaselineDetector.fit() - No requiere entrenamiento")
        return self
    
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predice el régimen usando reglas determinísticas.
        
        Args:
            X: Vector de features [returns_5d, volatility_20d, adx_14, volume_ratio]
        
        Returns:
            RegimePrediction con régimen y confianza
        """
        start_time = time.time()
        
        # Validar input
        X = self._validate_input(X)
        
        # Extraer features (última fila si hay múltiples)
        if X.ndim == 2:
            features = X[-1]
        else:
            features = X
        
        returns_5d = features[0]
        volatility_20d = features[1]
        adx_14 = features[2]
        volume_ratio = features[3] if len(features) > 3 else 1.0
        
        # Aplicar reglas
        regime, confidence, reasoning = self._apply_rules(
            returns_5d, volatility_20d, adx_14, volume_ratio
        )
        
        # Calcular pseudo-probabilidades
        probabilities = self._calculate_probabilities(
            regime, confidence, returns_5d, volatility_20d, adx_14
        )
        
        inference_time = (time.time() - start_time) * 1000
        self._inference_times.append(inference_time)
        self._predictions_count += 1
        self._regime_counts[regime.value] += 1
        
        prediction = RegimePrediction(
            regime=regime,
            confidence=confidence,
            probabilities=probabilities,
            model_id=self.model_id,
            inference_time_ms=inference_time,
            features_used={
                "returns_5d": float(returns_5d),
                "volatility_20d": float(volatility_20d),
                "adx_14": float(adx_14),
                "volume_ratio": float(volume_ratio),
            },
            metadata={
                "reasoning": reasoning,
                "rules_version": self.VERSION,
            }
        )
        
        logger.debug(
            f"Predicción Rules: {regime.value} ({confidence:.0%}) - {reasoning}"
        )
        
        return prediction
    
    def _validate_input(self, X: np.ndarray) -> np.ndarray:
        """Valida el input."""
        if X is None:
            raise InvalidFeaturesError("Input no puede ser None")
        
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] < 3:
            raise InvalidFeaturesError(
                f"Se requieren al menos 3 features, recibidos: {X.shape[1]}"
            )
        
        if np.isnan(X).any() or np.isinf(X).any():
            raise InvalidFeaturesError("Input contiene NaN o Inf")
        
        return X
    
    def _apply_rules(
        self,
        returns_5d: float,
        volatility_20d: float,
        adx_14: float,
        volume_ratio: float
    ) -> tuple:
        """
        Aplica las reglas de detección de régimen.
        
        Returns:
            Tuple de (RegimeType, confidence, reasoning)
        """
        cfg = self.config
        
        # Regla 1: VOLATILE (prioridad máxima)
        if volatility_20d > cfg.volatile_vol_threshold:
            return (
                RegimeType.VOLATILE,
                0.85,
                f"Alta volatilidad ({volatility_20d:.1%} > {cfg.volatile_vol_threshold:.0%})"
            )
        
        if adx_14 > cfg.volatile_adx_threshold and volatility_20d > cfg.volatile_vol_with_adx:
            return (
                RegimeType.VOLATILE,
                0.75,
                f"ADX extremo ({adx_14:.0f}) con volatilidad elevada ({volatility_20d:.1%})"
            )
        
        # Regla 2: BULL
        if (returns_5d > cfg.bull_return_threshold and 
            volatility_20d < cfg.bull_max_vol and 
            adx_14 > cfg.bull_min_adx):
            
            # Calcular confianza basada en qué tan fuerte es la señal
            strength = min(returns_5d / cfg.bull_return_threshold, 2.0) / 2.0
            confidence = 0.6 + (0.25 * strength)
            
            return (
                RegimeType.BULL,
                confidence,
                f"Retornos positivos ({returns_5d:.1%}), baja vol ({volatility_20d:.1%}), "
                f"tendencia presente (ADX={adx_14:.0f})"
            )
        
        # Regla 3: BEAR
        if (returns_5d < cfg.bear_return_threshold and 
            volatility_20d < cfg.bear_max_vol and 
            adx_14 > cfg.bear_min_adx):
            
            strength = min(abs(returns_5d) / abs(cfg.bear_return_threshold), 2.0) / 2.0
            confidence = 0.6 + (0.25 * strength)
            
            return (
                RegimeType.BEAR,
                confidence,
                f"Retornos negativos ({returns_5d:.1%}), vol controlada ({volatility_20d:.1%}), "
                f"tendencia presente (ADX={adx_14:.0f})"
            )
        
        # Regla 4: SIDEWAYS
        if (abs(returns_5d) <= cfg.sideways_return_range and 
            volatility_20d < cfg.sideways_max_vol and 
            adx_14 < cfg.sideways_max_adx):
            
            # Mayor confianza si ADX es muy bajo (sin tendencia clara)
            confidence = 0.7 if adx_14 < 15 else 0.55
            
            return (
                RegimeType.SIDEWAYS,
                confidence,
                f"Sin tendencia clara (ret={returns_5d:.1%}, ADX={adx_14:.0f}), "
                f"baja volatilidad ({volatility_20d:.1%})"
            )
        
        # Default: SIDEWAYS con baja confianza
        return (
            RegimeType.SIDEWAYS,
            0.4,
            f"No cumple criterios claros (ret={returns_5d:.1%}, vol={volatility_20d:.1%}, "
            f"ADX={adx_14:.0f})"
        )
    
    def _calculate_probabilities(
        self,
        regime: RegimeType,
        confidence: float,
        returns_5d: float,
        volatility_20d: float,
        adx_14: float
    ) -> Dict[str, float]:
        """
        Calcula pseudo-probabilidades basadas en la regla aplicada.
        
        Las reglas no dan probabilidades reales, pero estimamos
        una distribución razonable para mantener la interfaz.
        """
        # Inicializar con pequeñas probabilidades base
        probs = {
            RegimeType.BULL.value: 0.05,
            RegimeType.BEAR.value: 0.05,
            RegimeType.SIDEWAYS.value: 0.05,
            RegimeType.VOLATILE.value: 0.05,
        }
        
        # Asignar la confianza al régimen detectado
        probs[regime.value] = confidence
        
        # Distribuir el resto proporcionalmente
        remaining = 1.0 - confidence - sum(0.05 for _ in range(3))
        
        # Ajustar basado en features
        if regime != RegimeType.VOLATILE:
            # Si hay alta volatilidad, dar algo de probabilidad a VOLATILE
            vol_prob = min(volatility_20d / 0.30, 0.3) * remaining
            probs[RegimeType.VOLATILE.value] += vol_prob
            remaining -= vol_prob
        
        if regime != RegimeType.BULL and returns_5d > 0:
            bull_prob = min(returns_5d / 0.05, 0.5) * remaining
            probs[RegimeType.BULL.value] += bull_prob
            remaining -= bull_prob
        
        if regime != RegimeType.BEAR and returns_5d < 0:
            bear_prob = min(abs(returns_5d) / 0.05, 0.5) * remaining
            probs[RegimeType.BEAR.value] += bear_prob
            remaining -= bear_prob
        
        # Asignar resto a SIDEWAYS
        probs[RegimeType.SIDEWAYS.value] += max(0, remaining)
        
        # Normalizar para que sume 1
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}
        
        return probs
    
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        """Obtiene pseudo-probabilidades."""
        prediction = self.predict(X)
        return prediction.probabilities
    
    def save(self, path: str) -> None:
        """
        Guarda la configuración de reglas.
        
        Las reglas no tienen estado aprendido, solo se guarda config.
        """
        import yaml
        from pathlib import Path
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        config_path = path / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump({
                'rules_config': self.config.to_dict(),
                'version': self.VERSION,
                'model_type': 'rules_baseline',
            }, f, default_flow_style=False)
        
        logger.info(f"Configuración de reglas guardada en {config_path}")
    
    @classmethod
    def load(cls, path: str) -> "RulesBaselineDetector":
        """Carga configuración de reglas."""
        import yaml
        from pathlib import Path
        
        path = Path(path)
        config_path = path / "config.yaml"
        
        if not config_path.exists():
            logger.warning(f"Config no encontrada en {config_path}, usando defaults")
            return cls()
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        config = RulesConfig.from_dict(data.get('rules_config', {}))
        return cls(config)
    
    def get_metrics(self) -> ModelMetrics:
        """Obtiene métricas del modelo de reglas."""
        total_predictions = sum(self._regime_counts.values())
        
        return ModelMetrics(
            model_id=self.model_id,
            version=self.VERSION,
            trained_at=None,  # No se entrena
            train_samples=0,
            regime_distribution=self._regime_counts if total_predictions > 0 else None,
            inference_time_avg_ms=np.mean(self._inference_times) if self._inference_times else 0.0,
            predictions_count=self._predictions_count,
            last_prediction_at=datetime.now() if self._predictions_count > 0 else None,
        )
```

### 9.4 Checklist Tarea A2.3

```
TAREA A2.3: RULES BASELINE DETECTOR
═════════════════════════════════════════════════════════════════════
[ ] src/ml/models/rules_baseline.py creado
[ ] RulesConfig dataclass con umbrales configurables
[ ] RulesBaselineDetector implementa RegimeDetector ABC
[ ] Lógica de reglas con prioridades (VOLATILE > BULL/BEAR > SIDEWAYS)
[ ] Cálculo de pseudo-probabilidades
[ ] save() guarda config.yaml
[ ] load() reconstruye desde config
[ ] No requiere fit() para funcionar
[ ] Test de predicción pasa
═════════════════════════════════════════════════════════════════════
```

---

## 10. Tarea A2.4: Factory y Configuración

### 10.1 Objetivo

Implementar un Factory que cree el modelo correcto según configuración YAML, permitiendo cambiar de modelo sin modificar código.

### 10.2 Archivo: `src/ml/factory.py`

```python
# src/ml/factory.py
"""
Factory para crear modelos de ML según configuración.

Permite instanciar el modelo correcto basándose en archivos YAML,
facilitando cambiar entre implementaciones sin modificar código.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Type
import yaml

from .interfaces import RegimeDetector, ModelFactory
from .models.hmm_regime import HMMRegimeDetector, HMMConfig
from .models.rules_baseline import RulesBaselineDetector, RulesConfig
from .exceptions import ConfigurationError, ModelLoadError

logger = logging.getLogger(__name__)


# Registro de modelos disponibles
MODEL_REGISTRY: Dict[str, Type[RegimeDetector]] = {
    "hmm": HMMRegimeDetector,
    "rules": RulesBaselineDetector,
    # Futuro: "ppo": PPORegimeDetector,
}


class RegimeDetectorFactory(ModelFactory):
    """
    Factory para crear detectores de régimen.
    
    Lee configuración de YAML y crea el modelo apropiado.
    Mantiene un cache del modelo activo para evitar recargas.
    
    Ejemplo:
        factory = RegimeDetectorFactory("config/ml_models.yaml")
        
        # Crear modelo activo según config
        detector = factory.create_regime_detector()
        
        # Crear modelo específico
        hmm_detector = factory.create_regime_detector("hmm")
    """
    
    _instance: Optional["RegimeDetectorFactory"] = None
    _active_detector: Optional[RegimeDetector] = None
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        """
        Inicializa el factory.
        
        Args:
            config_path: Ruta al archivo de configuración YAML
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
        
        logger.info(f"RegimeDetectorFactory inicializado con config: {self.config_path}")
    
    @classmethod
    def get_instance(cls, config_path: str = "config/ml_models.yaml") -> "RegimeDetectorFactory":
        """
        Obtiene instancia singleton del factory.
        
        Args:
            config_path: Ruta a configuración (solo se usa en primera llamada)
        
        Returns:
            Instancia única del factory
        """
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Resetea el singleton (útil para tests)."""
        cls._instance = None
        cls._active_detector = None
    
    def _load_config(self) -> None:
        """Carga configuración desde YAML."""
        if not self.config_path.exists():
            logger.warning(f"Config no encontrada en {self.config_path}, usando defaults")
            self._config = self._get_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"Configuración cargada desde {self.config_path}")
        except Exception as e:
            logger.error(f"Error cargando config: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna configuración por defecto."""
        return {
            "regime_detector": {
                "active": "rules",  # Default seguro
                "models_dir": "models",
                "models": {
                    "hmm": {
                        "n_states": 4,
                        "n_iter": 100,
                        "covariance_type": "full",
                        "features": ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
                    },
                    "rules": {
                        "volatile_vol_threshold": 0.25,
                        "bull_return_threshold": 0.02,
                        "bear_return_threshold": -0.02
                    }
                }
            }
        }
    
    def reload_config(self) -> None:
        """Recarga configuración desde archivo."""
        self._load_config()
        # Invalidar detector cacheado
        RegimeDetectorFactory._active_detector = None
        logger.info("Configuración recargada, detector cacheado invalidado")
    
    def get_regime_config(self) -> Dict[str, Any]:
        """Obtiene configuración de regime_detector."""
        return self._config.get("regime_detector", {})
    
    def get_active_model_type(self) -> str:
        """Retorna el tipo de modelo activo según config."""
        return self.get_regime_config().get("active", "rules")
    
    def get_available_models(self) -> list:
        """Lista tipos de modelos disponibles."""
        return list(MODEL_REGISTRY.keys())
    
    def get_models_dir(self) -> Path:
        """Obtiene directorio de modelos."""
        models_dir = self.get_regime_config().get("models_dir", "models")
        return Path(models_dir)
    
    def create_regime_detector(
        self,
        model_type: Optional[str] = None,
        load_trained: bool = True
    ) -> RegimeDetector:
        """
        Crea un detector de régimen.
        
        Args:
            model_type: Tipo de modelo. Si None, usa el activo en config.
            load_trained: Si True, intenta cargar modelo entrenado.
        
        Returns:
            Instancia de RegimeDetector
        
        Raises:
            ConfigurationError: Si tipo desconocido o config inválida
        """
        if model_type is None:
            model_type = self.get_active_model_type()
        
        model_type = model_type.lower()
        
        if model_type not in MODEL_REGISTRY:
            available = ", ".join(MODEL_REGISTRY.keys())
            raise ConfigurationError(
                f"Tipo de modelo desconocido: '{model_type}'. "
                f"Disponibles: {available}"
            )
        
        logger.info(f"Creando detector de tipo: {model_type}")
        
        # Obtener configuración específica del modelo
        model_config = self.get_regime_config().get("models", {}).get(model_type, {})
        
        if model_type == "hmm":
            return self._create_hmm_detector(model_config, load_trained)
        elif model_type == "rules":
            return self._create_rules_detector(model_config)
        else:
            # Extensibilidad para futuros modelos
            raise ConfigurationError(f"Creación de '{model_type}' no implementada")
    
    def _create_hmm_detector(
        self,
        config: Dict[str, Any],
        load_trained: bool
    ) -> HMMRegimeDetector:
        """Crea detector HMM."""
        hmm_config = HMMConfig(
            n_states=config.get("n_states", 4),
            n_iter=config.get("n_iter", 100),
            covariance_type=config.get("covariance_type", "full"),
            features=config.get("features"),
            random_state=config.get("random_state", 42),
        )
        
        detector = HMMRegimeDetector(hmm_config)
        
        if load_trained:
            # Intentar cargar modelo entrenado
            model_path = self.get_models_dir() / "hmm_regime" / "latest"
            
            if model_path.exists():
                try:
                    detector = HMMRegimeDetector.load(str(model_path))
                    logger.info(f"Modelo HMM cargado desde {model_path}")
                except Exception as e:
                    logger.warning(f"No se pudo cargar modelo HMM: {e}")
            else:
                logger.warning(
                    f"No hay modelo HMM entrenado en {model_path}. "
                    "Se retorna modelo sin entrenar."
                )
        
        return detector
    
    def _create_rules_detector(self, config: Dict[str, Any]) -> RulesBaselineDetector:
        """Crea detector de reglas."""
        rules_config = RulesConfig(
            volatile_vol_threshold=config.get("volatile_vol_threshold", 0.25),
            bull_return_threshold=config.get("bull_return_threshold", 0.02),
            bear_return_threshold=config.get("bear_return_threshold", -0.02),
            # ... otros parámetros
        )
        
        return RulesBaselineDetector(rules_config)
    
    def get_active_detector(self) -> RegimeDetector:
        """
        Obtiene el detector activo (con cache).
        
        Usa patrón singleton para evitar recargar el modelo
        en cada llamada.
        
        Returns:
            Detector de régimen cacheado
        """
        if RegimeDetectorFactory._active_detector is None:
            RegimeDetectorFactory._active_detector = self.create_regime_detector()
        
        return RegimeDetectorFactory._active_detector
    
    def invalidate_cache(self) -> None:
        """Invalida el detector cacheado."""
        RegimeDetectorFactory._active_detector = None
        logger.info("Cache de detector invalidado")


# Función de conveniencia para obtener detector
def get_regime_detector(
    config_path: str = "config/ml_models.yaml",
    model_type: Optional[str] = None
) -> RegimeDetector:
    """
    Función de conveniencia para obtener un detector de régimen.
    
    Args:
        config_path: Ruta a configuración
        model_type: Tipo específico o None para usar activo
    
    Returns:
        Detector de régimen configurado
    """
    factory = RegimeDetectorFactory.get_instance(config_path)
    
    if model_type:
        return factory.create_regime_detector(model_type)
    
    return factory.get_active_detector()
```

### 10.3 Archivo: `config/ml_models.yaml`

```yaml
# config/ml_models.yaml
# Configuración de modelos de Machine Learning para Nexus Trading

# =============================================================================
# DETECTOR DE RÉGIMEN
# =============================================================================
regime_detector:
  # Modelo activo: "hmm" o "rules"
  # Cambiar este valor para usar diferente modelo
  active: "hmm"
  
  # Directorio donde se guardan los modelos entrenados
  models_dir: "models"
  
  # Configuración por tipo de modelo
  models:
    # -------------------------------------------------------------------------
    # Hidden Markov Model
    # -------------------------------------------------------------------------
    hmm:
      # Número de estados ocultos (regímenes)
      n_states: 4
      
      # Iteraciones máximas del algoritmo EM
      n_iter: 100
      
      # Tipo de matriz de covarianza: "full", "diag", "tied", "spherical"
      covariance_type: "full"
      
      # Features usados para detección
      features:
        - "returns_5d"
        - "volatility_20d"
        - "adx_14"
        - "volume_ratio"
      
      # Semilla para reproducibilidad
      random_state: 42
      
      # Tolerancia para convergencia
      tol: 0.0001
    
    # -------------------------------------------------------------------------
    # Baseline de Reglas
    # -------------------------------------------------------------------------
    rules:
      # Umbrales para régimen VOLATILE
      volatile_vol_threshold: 0.25
      volatile_adx_threshold: 40
      volatile_vol_with_adx: 0.20
      
      # Umbrales para régimen BULL
      bull_return_threshold: 0.02
      bull_max_vol: 0.20
      bull_min_adx: 20
      
      # Umbrales para régimen BEAR
      bear_return_threshold: -0.02
      bear_max_vol: 0.30
      bear_min_adx: 20
      
      # Umbrales para régimen SIDEWAYS
      sideways_return_range: 0.02
      sideways_max_vol: 0.20
      sideways_max_adx: 25

# =============================================================================
# CACHE DE PREDICCIONES
# =============================================================================
prediction_cache:
  enabled: true
  ttl_seconds: 300  # 5 minutos
  redis_key_prefix: "ml:regime"

# =============================================================================
# MONITOREO
# =============================================================================
monitoring:
  # Log de predicciones
  log_predictions: true
  
  # Métricas a Prometheus
  export_metrics: true
  
  # Alertas si confianza baja
  low_confidence_threshold: 0.5
```

### 10.4 Archivo: `src/ml/models/__init__.py`

```python
# src/ml/models/__init__.py
"""
Modelos de ML para detección de régimen.
"""

from .hmm_regime import HMMRegimeDetector, HMMConfig
from .rules_baseline import RulesBaselineDetector, RulesConfig

__all__ = [
    "HMMRegimeDetector",
    "HMMConfig",
    "RulesBaselineDetector",
    "RulesConfig",
]
```

### 10.5 Checklist Tarea A2.4

```
TAREA A2.4: FACTORY Y CONFIGURACIÓN
═════════════════════════════════════════════════════════════════════
[ ] src/ml/factory.py creado
[ ] MODEL_REGISTRY con hmm y rules
[ ] RegimeDetectorFactory implementa ModelFactory ABC
[ ] Lectura de config desde YAML
[ ] Método create_regime_detector() funcional
[ ] Cache de detector activo (singleton)
[ ] config/ml_models.yaml creado con todas las opciones
[ ] Función de conveniencia get_regime_detector()
[ ] Tests de factory pasan
═════════════════════════════════════════════════════════════════════
```

---

## 11. Test del Factory

### 11.1 Archivo: `tests/ml/test_factory.py`

```python
# tests/ml/test_factory.py
"""
Tests para el Factory de modelos ML.
"""

import pytest
import tempfile
from pathlib import Path
import yaml

from src.ml.factory import RegimeDetectorFactory, get_regime_detector
from src.ml.models.hmm_regime import HMMRegimeDetector
from src.ml.models.rules_baseline import RulesBaselineDetector
from src.ml.exceptions import ConfigurationError


class TestRegimeDetectorFactory:
    """Tests para RegimeDetectorFactory."""
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset singleton antes de cada test."""
        RegimeDetectorFactory.reset_instance()
        yield
        RegimeDetectorFactory.reset_instance()
    
    @pytest.fixture
    def config_file(self):
        """Crea archivo de configuración temporal."""
        config = {
            "regime_detector": {
                "active": "rules",
                "models_dir": "models",
                "models": {
                    "hmm": {
                        "n_states": 4,
                        "n_iter": 50,
                        "features": ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
                    },
                    "rules": {
                        "volatile_vol_threshold": 0.25
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return f.name
    
    def test_factory_singleton(self, config_file):
        factory1 = RegimeDetectorFactory.get_instance(config_file)
        factory2 = RegimeDetectorFactory.get_instance(config_file)
        
        assert factory1 is factory2
    
    def test_load_config(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        assert factory.get_active_model_type() == "rules"
        assert "hmm" in factory.get_available_models()
        assert "rules" in factory.get_available_models()
    
    def test_create_rules_detector(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        detector = factory.create_regime_detector("rules")
        
        assert isinstance(detector, RulesBaselineDetector)
        assert detector.is_fitted  # Rules siempre está "fitted"
    
    def test_create_hmm_detector_not_trained(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        detector = factory.create_regime_detector("hmm", load_trained=False)
        
        assert isinstance(detector, HMMRegimeDetector)
        assert not detector.is_fitted  # No hay modelo entrenado
    
    def test_create_invalid_model(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        with pytest.raises(ConfigurationError):
            factory.create_regime_detector("invalid_model")
    
    def test_get_active_detector_cached(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        detector1 = factory.get_active_detector()
        detector2 = factory.get_active_detector()
        
        assert detector1 is detector2  # Mismo objeto (cacheado)
    
    def test_invalidate_cache(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        detector1 = factory.get_active_detector()
        factory.invalidate_cache()
        detector2 = factory.get_active_detector()
        
        assert detector1 is not detector2  # Objetos diferentes
    
    def test_default_config_if_file_missing(self):
        factory = RegimeDetectorFactory("nonexistent.yaml")
        
        # Debe usar config por defecto
        assert factory.get_active_model_type() == "rules"
    
    def test_convenience_function(self, config_file):
        detector = get_regime_detector(config_file)
        
        assert isinstance(detector, RulesBaselineDetector)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

*Fin de Parte 3 - Rules Baseline, Factory, Configuración YAML*

**Siguiente:** Parte 4 - Integración con mcp-ml-models, Tests, Verificación, Checklist Final

---
# 🧠 Fase A2: ML Modular - Parte 4

## Integración, Tests y Verificación Final

---

## 12. Tarea A2.5: Integración con mcp-ml-models

### 12.1 Objetivo

Actualizar el servidor MCP `mcp-ml-models` para usar el Factory y modelos reales en lugar de los placeholders de Fase A1.

### 12.2 Actualizar: `mcp-servers/ml-models/tools/regime.py`

```python
# mcp-servers/ml-models/tools/regime.py
"""
Tool de predicción de régimen para mcp-ml-models.

Actualizado en Fase A2 para usar modelos reales via Factory.
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Optional, Any, Dict
from pathlib import Path

# Asegurar que src está en el path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ml.factory import RegimeDetectorFactory, get_regime_detector
from src.ml.interfaces import RegimePrediction, RegimeType
from src.ml.exceptions import (
    ModelNotFittedError,
    InvalidFeaturesError,
    MLError
)

logger = logging.getLogger(__name__)

# Cache simple en memoria
_prediction_cache: Dict[str, tuple] = {}  # key -> (prediction, timestamp)
CACHE_TTL_SECONDS = 300  # 5 minutos


class RegimeTool:
    """
    Tool para obtener predicción de régimen de mercado.
    
    Integra con el Factory de ML para usar el modelo configurado.
    Incluye cache para evitar predicciones repetidas.
    """
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        """
        Inicializa el tool.
        
        Args:
            config_path: Ruta a configuración de modelos ML
        """
        self.config_path = config_path
        self._factory: Optional[RegimeDetectorFactory] = None
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Inicializa el factory si no lo está."""
        if not self._initialized:
            try:
                self._factory = RegimeDetectorFactory.get_instance(self.config_path)
                self._initialized = True
                logger.info("RegimeTool inicializado correctamente")
            except Exception as e:
                logger.error(f"Error inicializando RegimeTool: {e}")
                raise
    
    async def predict(
        self,
        features: Optional[Dict[str, float]] = None,
        symbol: Optional[str] = None,
        use_cache: bool = True,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predice el régimen actual del mercado.
        
        Args:
            features: Dict con features {nombre: valor}
                     Si None, intenta obtener features actuales
            symbol: Símbolo específico (para cache key)
            use_cache: Si usar cache de predicciones
            model_type: Tipo de modelo específico (None = activo)
        
        Returns:
            Dict con predicción y metadata
        """
        self._ensure_initialized()
        
        try:
            # Generar cache key
            cache_key = self._generate_cache_key(features, symbol, model_type)
            
            # Verificar cache
            if use_cache and cache_key in _prediction_cache:
                cached_pred, cached_time = _prediction_cache[cache_key]
                age = (datetime.now() - cached_time).total_seconds()
                
                if age < CACHE_TTL_SECONDS:
                    logger.debug(f"Cache hit para {cache_key} (age: {age:.0f}s)")
                    return {
                        **cached_pred,
                        "cached": True,
                        "cache_age_seconds": age
                    }
            
            # Obtener detector
            if model_type:
                detector = self._factory.create_regime_detector(model_type)
            else:
                detector = self._factory.get_active_detector()
            
            # Validar que modelo está listo
            if not detector.is_fitted:
                return {
                    "error": "Modelo no entrenado",
                    "regime": RegimeType.UNKNOWN.value,
                    "confidence": 0.0,
                    "model_id": detector.model_id,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Preparar features
            if features is None:
                features = await self._get_current_features(symbol)
            
            # Convertir dict a array
            import numpy as np
            feature_names = detector.required_features
            X = np.array([[features.get(f, 0.0) for f in feature_names]])
            
            # Predecir
            prediction = detector.predict(X)
            
            # Formatear resultado
            result = {
                "regime": prediction.regime.value,
                "confidence": prediction.confidence,
                "probabilities": prediction.probabilities,
                "model_id": prediction.model_id,
                "inference_time_ms": prediction.inference_time_ms,
                "features_used": prediction.features_used,
                "timestamp": prediction.timestamp.isoformat(),
                "is_tradeable": prediction.is_tradeable,
                "is_high_confidence": prediction.is_high_confidence,
                "cached": False
            }
            
            # Añadir metadata si existe
            if prediction.metadata:
                result["metadata"] = prediction.metadata
            
            # Guardar en cache
            if use_cache:
                _prediction_cache[cache_key] = (result, datetime.now())
            
            logger.info(
                f"Predicción: {prediction.regime.value} "
                f"(confianza: {prediction.confidence:.0%}, "
                f"modelo: {prediction.model_id})"
            )
            
            return result
            
        except ModelNotFittedError as e:
            logger.warning(f"Modelo no entrenado: {e}")
            return {
                "error": str(e),
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        
        except InvalidFeaturesError as e:
            logger.warning(f"Features inválidos: {e}")
            return {
                "error": str(e),
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error en predicción: {e}", exc_info=True)
            return {
                "error": f"Error interno: {str(e)}",
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
    
    def _generate_cache_key(
        self,
        features: Optional[Dict],
        symbol: Optional[str],
        model_type: Optional[str]
    ) -> str:
        """Genera key única para cache."""
        parts = [
            model_type or "active",
            symbol or "market",
        ]
        
        if features:
            # Hash simplificado de features
            feature_str = "_".join(f"{k}:{v:.4f}" for k, v in sorted(features.items()))
            parts.append(feature_str[:50])
        
        return ":".join(parts)
    
    async def _get_current_features(self, symbol: Optional[str] = None) -> Dict[str, float]:
        """
        Obtiene features actuales desde el sistema.
        
        En producción, esto conectaría con mcp-market-data y mcp-technical.
        Por ahora retorna valores de ejemplo.
        """
        # TODO: Integrar con mcp-market-data y mcp-technical
        # Por ahora, valores de ejemplo para testing
        logger.warning("Usando features de ejemplo - implementar integración real")
        
        return {
            "returns_5d": 0.015,
            "volatility_20d": 0.18,
            "adx_14": 28.5,
            "volume_ratio": 1.1
        }
    
    def clear_cache(self) -> int:
        """
        Limpia el cache de predicciones.
        
        Returns:
            Número de entradas eliminadas
        """
        global _prediction_cache
        count = len(_prediction_cache)
        _prediction_cache = {}
        logger.info(f"Cache limpiado: {count} entradas eliminadas")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        return {
            "entries": len(_prediction_cache),
            "ttl_seconds": CACHE_TTL_SECONDS,
            "keys": list(_prediction_cache.keys())
        }


# Instancia global del tool
_regime_tool: Optional[RegimeTool] = None


def get_regime_tool(config_path: str = "config/ml_models.yaml") -> RegimeTool:
    """Obtiene instancia singleton del tool."""
    global _regime_tool
    if _regime_tool is None:
        _regime_tool = RegimeTool(config_path)
    return _regime_tool


# Función para el handler MCP
async def handle_get_regime(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler para el tool MCP get_regime.
    
    Args:
        args: Argumentos del tool:
            - features: Dict opcional con features
            - symbol: Símbolo opcional
            - model_type: Tipo de modelo opcional
            - use_cache: Si usar cache (default True)
    
    Returns:
        Resultado de la predicción
    """
    tool = get_regime_tool()
    
    return await tool.predict(
        features=args.get("features"),
        symbol=args.get("symbol"),
        use_cache=args.get("use_cache", True),
        model_type=args.get("model_type")
    )
```

### 12.3 Actualizar: `mcp-servers/ml-models/tools/model_info.py`

```python
# mcp-servers/ml-models/tools/model_info.py
"""
Tool para obtener información de modelos ML.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ml.factory import RegimeDetectorFactory

logger = logging.getLogger(__name__)


async def handle_get_model_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Obtiene información del modelo de ML.
    
    Args:
        args:
            - model_type: Tipo de modelo (opcional, default = activo)
    
    Returns:
        Dict con información del modelo
    """
    try:
        factory = RegimeDetectorFactory.get_instance()
        model_type = args.get("model_type")
        
        if model_type:
            detector = factory.create_regime_detector(model_type, load_trained=True)
        else:
            detector = factory.get_active_detector()
        
        metrics = detector.get_metrics()
        
        return {
            "model_id": metrics.model_id,
            "version": metrics.version,
            "model_type": model_type or factory.get_active_model_type(),
            "is_fitted": detector.is_fitted,
            "required_features": detector.required_features,
            "trained_at": metrics.trained_at.isoformat() if metrics.trained_at else None,
            "train_samples": metrics.train_samples,
            "predictions_count": metrics.predictions_count,
            "inference_time_avg_ms": metrics.inference_time_avg_ms,
            "regime_distribution": metrics.regime_distribution,
            "metrics": {
                "log_likelihood": metrics.log_likelihood,
                "aic": metrics.aic,
                "bic": metrics.bic,
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo info de modelo: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def handle_list_models(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lista modelos disponibles.
    
    Returns:
        Dict con modelos disponibles y modelo activo
    """
    try:
        factory = RegimeDetectorFactory.get_instance()
        
        return {
            "available_models": factory.get_available_models(),
            "active_model": factory.get_active_model_type(),
            "models_dir": str(factory.get_models_dir()),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listando modelos: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
```

### 12.4 Actualizar: `mcp-servers/ml-models/server.py`

```python
# mcp-servers/ml-models/server.py
"""
Servidor MCP para modelos de Machine Learning.

Expone tools para:
- get_regime: Obtener régimen actual del mercado
- get_model_info: Información del modelo activo
- list_models: Listar modelos disponibles
- clear_cache: Limpiar cache de predicciones
"""

import asyncio
import logging
import json
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Imports de tools
from tools.regime import handle_get_regime, get_regime_tool
from tools.model_info import handle_get_model_info, handle_list_models
from tools.health import handle_health_check


# Definición de tools MCP
TOOLS = [
    {
        "name": "get_regime",
        "description": "Obtiene el régimen actual del mercado (BULL, BEAR, SIDEWAYS, VOLATILE)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "object",
                    "description": "Features para predicción {nombre: valor}. Si no se provee, usa valores actuales.",
                    "additionalProperties": {"type": "number"}
                },
                "symbol": {
                    "type": "string",
                    "description": "Símbolo específico (opcional)"
                },
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Tipo de modelo a usar (opcional, default: activo)"
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Si usar cache de predicciones (default: true)"
                }
            }
        }
    },
    {
        "name": "get_model_info",
        "description": "Obtiene información del modelo de ML activo o especificado",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Tipo de modelo (opcional)"
                }
            }
        }
    },
    {
        "name": "list_models",
        "description": "Lista los modelos de ML disponibles",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "clear_cache",
        "description": "Limpia el cache de predicciones",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "health_check",
        "description": "Verifica el estado del servidor ML",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


async def handle_tool_call(name: str, args: dict) -> dict:
    """
    Dispatcher de llamadas a tools.
    
    Args:
        name: Nombre del tool
        args: Argumentos del tool
    
    Returns:
        Resultado del tool
    """
    handlers = {
        "get_regime": handle_get_regime,
        "get_model_info": handle_get_model_info,
        "list_models": handle_list_models,
        "clear_cache": lambda _: {"cleared": get_regime_tool().clear_cache()},
        "health_check": handle_health_check,
    }
    
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Tool desconocido: {name}"}
    
    return await handler(args)


async def main():
    """Entry point del servidor MCP."""
    logger.info("Iniciando mcp-ml-models server...")
    
    # En producción, aquí iría la integración con MCP SDK
    # Por ahora, modo de prueba standalone
    
    print(json.dumps({
        "status": "ready",
        "tools": [t["name"] for t in TOOLS],
        "version": "1.0.0"
    }))
    
    # Mantener servidor corriendo
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Servidor detenido")


if __name__ == "__main__":
    asyncio.run(main())
```

### 12.5 Checklist Tarea A2.5

```
TAREA A2.5: INTEGRACIÓN MCP-ML-MODELS
═════════════════════════════════════════════════════════════════════
[ ] tools/regime.py actualizado para usar Factory
[ ] Cache de predicciones implementado
[ ] tools/model_info.py actualizado
[ ] server.py con handlers correctos
[ ] Tool get_regime funciona con modelo real
[ ] Tool get_model_info retorna métricas
[ ] Tool list_models lista opciones
[ ] Tool clear_cache funciona
[ ] Health check verifica modelo cargado
═════════════════════════════════════════════════════════════════════
```

---

## 13. Tarea A2.6: Tests y Verificación

### 13.1 Script de Verificación: `scripts/verify_fase_a2.py`

```python
#!/usr/bin/env python
# scripts/verify_fase_a2.py
"""
Script de verificación para Fase A2: ML Modular.

Verifica que todos los componentes están correctamente implementados.
"""

import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_check(name: str, passed: bool, detail: str = "") -> None:
    status = "✓" if passed else "✗"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    
    if detail:
        print(f"  {color}{status}{reset} {name}: {detail}")
    else:
        print(f"  {color}{status}{reset} {name}")


def verify_imports() -> bool:
    """Verifica que todos los imports funcionan."""
    print_header("VERIFICANDO IMPORTS")
    
    all_passed = True
    
    # Interfaces
    try:
        from src.ml import (
            RegimeType, RegimePrediction, ModelMetrics,
            RegimeDetector, ModelFactory
        )
        print_check("Interfaces", True)
    except Exception as e:
        print_check("Interfaces", False, str(e))
        all_passed = False
    
    # Excepciones
    try:
        from src.ml import (
            MLError, ModelNotFittedError, InvalidFeaturesError,
            ModelLoadError, TrainingError
        )
        print_check("Excepciones", True)
    except Exception as e:
        print_check("Excepciones", False, str(e))
        all_passed = False
    
    # Modelos
    try:
        from src.ml.models import HMMRegimeDetector, HMMConfig
        print_check("HMMRegimeDetector", True)
    except Exception as e:
        print_check("HMMRegimeDetector", False, str(e))
        all_passed = False
    
    try:
        from src.ml.models import RulesBaselineDetector, RulesConfig
        print_check("RulesBaselineDetector", True)
    except Exception as e:
        print_check("RulesBaselineDetector", False, str(e))
        all_passed = False
    
    # Factory
    try:
        from src.ml.factory import RegimeDetectorFactory, get_regime_detector
        print_check("Factory", True)
    except Exception as e:
        print_check("Factory", False, str(e))
        all_passed = False
    
    return all_passed


def verify_interfaces() -> bool:
    """Verifica funcionamiento de interfaces."""
    print_header("VERIFICANDO INTERFACES")
    
    all_passed = True
    
    from src.ml import RegimeType, RegimePrediction
    
    # RegimeType
    try:
        assert RegimeType.BULL.value == "BULL"
        assert RegimeType.from_string("bear") == RegimeType.BEAR
        assert RegimeType.from_string("invalid") == RegimeType.UNKNOWN
        print_check("RegimeType enum", True)
    except Exception as e:
        print_check("RegimeType enum", False, str(e))
        all_passed = False
    
    # RegimePrediction
    try:
        pred = RegimePrediction(
            regime=RegimeType.BULL,
            confidence=0.85,
            probabilities={"BULL": 0.85, "BEAR": 0.05, "SIDEWAYS": 0.05, "VOLATILE": 0.05},
            model_id="test_v1",
            inference_time_ms=10.5
        )
        assert pred.is_high_confidence
        assert pred.is_tradeable
        
        # Serialización
        json_str = pred.to_json()
        recovered = RegimePrediction.from_dict(eval(json_str.replace('true', 'True').replace('false', 'False')))
        assert recovered.regime == pred.regime
        
        print_check("RegimePrediction", True)
    except Exception as e:
        print_check("RegimePrediction", False, str(e))
        all_passed = False
    
    return all_passed


def verify_rules_baseline() -> bool:
    """Verifica el detector de reglas."""
    print_header("VERIFICANDO RULES BASELINE")
    
    all_passed = True
    
    from src.ml.models import RulesBaselineDetector
    from src.ml import RegimeType
    
    detector = RulesBaselineDetector()
    
    # Siempre fitted
    try:
        assert detector.is_fitted
        print_check("is_fitted = True", True)
    except Exception as e:
        print_check("is_fitted = True", False, str(e))
        all_passed = False
    
    # Predicción BULL
    try:
        X_bull = np.array([[0.03, 0.15, 28, 1.1]])  # Alto retorno, baja vol, ADX presente
        pred = detector.predict(X_bull)
        
        assert pred.regime == RegimeType.BULL
        print_check("Detecta BULL", True, f"confianza: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detecta BULL", False, str(e))
        all_passed = False
    
    # Predicción BEAR
    try:
        X_bear = np.array([[-0.03, 0.18, 30, 1.0]])  # Retorno negativo
        pred = detector.predict(X_bear)
        
        assert pred.regime == RegimeType.BEAR
        print_check("Detecta BEAR", True, f"confianza: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detecta BEAR", False, str(e))
        all_passed = False
    
    # Predicción VOLATILE
    try:
        X_vol = np.array([[0.01, 0.35, 25, 1.2]])  # Alta volatilidad
        pred = detector.predict(X_vol)
        
        assert pred.regime == RegimeType.VOLATILE
        print_check("Detecta VOLATILE", True, f"confianza: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detecta VOLATILE", False, str(e))
        all_passed = False
    
    # Predicción SIDEWAYS
    try:
        X_side = np.array([[0.005, 0.12, 15, 1.0]])  # Sin tendencia
        pred = detector.predict(X_side)
        
        assert pred.regime == RegimeType.SIDEWAYS
        print_check("Detecta SIDEWAYS", True, f"confianza: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detecta SIDEWAYS", False, str(e))
        all_passed = False
    
    return all_passed


def verify_hmm_detector() -> bool:
    """Verifica el detector HMM."""
    print_header("VERIFICANDO HMM DETECTOR")
    
    all_passed = True
    
    from src.ml.models import HMMRegimeDetector, HMMConfig
    
    # Crear con config
    try:
        config = HMMConfig(n_states=4, n_iter=50)
        detector = HMMRegimeDetector(config)
        
        assert not detector.is_fitted
        print_check("Inicialización", True)
    except Exception as e:
        print_check("Inicialización", False, str(e))
        all_passed = False
        return False
    
    # Generar datos sintéticos
    np.random.seed(42)
    n_samples = 300
    X_train = np.column_stack([
        np.random.randn(n_samples) * 0.02,
        np.random.uniform(0.1, 0.3, n_samples),
        np.random.uniform(15, 35, n_samples),
        np.random.uniform(0.8, 1.2, n_samples),
    ])
    
    # Entrenar
    try:
        detector.fit(X_train)
        
        assert detector.is_fitted
        print_check("Entrenamiento", True, f"samples: {n_samples}")
    except Exception as e:
        print_check("Entrenamiento", False, str(e))
        all_passed = False
        return False
    
    # Predecir
    try:
        X_test = np.array([[0.02, 0.15, 28, 1.1]])
        pred = detector.predict(X_test)
        
        assert pred.confidence > 0
        assert sum(pred.probabilities.values()) > 0.99
        print_check("Predicción", True, f"{pred.regime.value} ({pred.confidence:.0%})")
    except Exception as e:
        print_check("Predicción", False, str(e))
        all_passed = False
    
    # Guardar y cargar
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_model"
            detector.save(str(save_path))
            
            # Verificar archivos
            assert (save_path / "model.pkl").exists()
            assert (save_path / "config.yaml").exists()
            
            # Cargar
            loaded = HMMRegimeDetector.load(str(save_path))
            assert loaded.is_fitted
            
            # Predecir con modelo cargado
            pred2 = loaded.predict(X_test)
            assert pred2.regime == pred.regime
            
        print_check("Save/Load", True)
    except Exception as e:
        print_check("Save/Load", False, str(e))
        all_passed = False
    
    # Métricas
    try:
        metrics = detector.get_metrics()
        
        assert metrics.train_samples > 0
        assert metrics.log_likelihood is not None
        print_check("Métricas", True, f"LL: {metrics.log_likelihood:.2f}")
    except Exception as e:
        print_check("Métricas", False, str(e))
        all_passed = False
    
    return all_passed


def verify_factory() -> bool:
    """Verifica el Factory."""
    print_header("VERIFICANDO FACTORY")
    
    all_passed = True
    
    from src.ml.factory import RegimeDetectorFactory
    from src.ml.models import RulesBaselineDetector, HMMRegimeDetector
    
    # Reset singleton
    RegimeDetectorFactory.reset_instance()
    
    # Crear factory (usará config default si no existe archivo)
    try:
        factory = RegimeDetectorFactory("config/ml_models.yaml")
        print_check("Inicialización", True)
    except Exception as e:
        print_check("Inicialización", False, str(e))
        all_passed = False
        return False
    
    # Listar modelos
    try:
        models = factory.get_available_models()
        
        assert "hmm" in models
        assert "rules" in models
        print_check("Lista modelos", True, str(models))
    except Exception as e:
        print_check("Lista modelos", False, str(e))
        all_passed = False
    
    # Crear Rules
    try:
        rules_detector = factory.create_regime_detector("rules")
        
        assert isinstance(rules_detector, RulesBaselineDetector)
        print_check("Crear Rules", True)
    except Exception as e:
        print_check("Crear Rules", False, str(e))
        all_passed = False
    
    # Crear HMM (sin modelo entrenado)
    try:
        hmm_detector = factory.create_regime_detector("hmm", load_trained=False)
        
        assert isinstance(hmm_detector, HMMRegimeDetector)
        print_check("Crear HMM", True, "(no entrenado)")
    except Exception as e:
        print_check("Crear HMM", False, str(e))
        all_passed = False
    
    return all_passed


def verify_config_file() -> bool:
    """Verifica que existe archivo de configuración."""
    print_header("VERIFICANDO CONFIGURACIÓN")
    
    config_path = Path("config/ml_models.yaml")
    
    if config_path.exists():
        print_check("config/ml_models.yaml existe", True)
        
        import yaml
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            assert "regime_detector" in config
            assert "active" in config["regime_detector"]
            print_check("Estructura válida", True)
            return True
        except Exception as e:
            print_check("Estructura válida", False, str(e))
            return False
    else:
        print_check("config/ml_models.yaml existe", False, "Crear archivo")
        return False


def main():
    """Ejecuta todas las verificaciones."""
    print("\n" + "="*60)
    print("   VERIFICACIÓN FASE A2: ML MODULAR")
    print("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    results = {
        "imports": verify_imports(),
        "interfaces": verify_interfaces(),
        "rules_baseline": verify_rules_baseline(),
        "hmm_detector": verify_hmm_detector(),
        "factory": verify_factory(),
        "config_file": verify_config_file(),
    }
    
    # Resumen
    print_header("RESUMEN")
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        print_check(name, result)
    
    print(f"\n  Total: {passed}/{total} verificaciones pasaron")
    
    if passed == total:
        print("\n  ✓ FASE A2 COMPLETADA EXITOSAMENTE")
        return 0
    else:
        print("\n  ✗ HAY VERIFICACIONES PENDIENTES")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 13.2 Ejecutar Tests

```bash
# Tests unitarios
pytest tests/ml/ -v

# Verificación de fase
python scripts/verify_fase_a2.py

# Test de integración con MCP
python -c "
from mcp_servers.ml_models.tools.regime import get_regime_tool
import asyncio

async def test():
    tool = get_regime_tool()
    result = await tool.predict(
        features={'returns_5d': 0.02, 'volatility_20d': 0.15, 'adx_14': 28, 'volume_ratio': 1.1}
    )
    print(f'Régimen: {result[\"regime\"]}')
    print(f'Confianza: {result[\"confidence\"]:.0%}')

asyncio.run(test())
"
```

---

## 14. Checklist Final Fase A2

```
═══════════════════════════════════════════════════════════════════════════════
                          FASE A2: ML MODULAR - CHECKLIST FINAL
═══════════════════════════════════════════════════════════════════════════════

TAREA A2.1: INTERFACES Y DATACLASSES
─────────────────────────────────────────────────────────────────────────────
[ ] src/ml/interfaces.py creado
[ ] RegimeType enum con 5 valores (BULL, BEAR, SIDEWAYS, VOLATILE, UNKNOWN)
[ ] RegimePrediction dataclass con validaciones
[ ] ModelMetrics dataclass
[ ] RegimeDetector ABC con todos los métodos abstractos
[ ] ModelFactory ABC definida
[ ] src/ml/exceptions.py con 7 excepciones
[ ] src/ml/__init__.py con exports correctos

TAREA A2.2: HMM REGIME DETECTOR
─────────────────────────────────────────────────────────────────────────────
[ ] src/ml/models/hmm_regime.py creado
[ ] HMMConfig dataclass con validaciones
[ ] HMMRegimeDetector implementa RegimeDetector
[ ] fit() entrena con GaussianHMM
[ ] predict() retorna RegimePrediction
[ ] Normalización de features (z-score)
[ ] Mapeo automático de estados a regímenes
[ ] save() crea 4 archivos (model.pkl, config.yaml, metrics.json, normalization.npz)
[ ] load() reconstruye modelo completo
[ ] scripts/train_hmm.py funcional

TAREA A2.3: RULES BASELINE DETECTOR
─────────────────────────────────────────────────────────────────────────────
[ ] src/ml/models/rules_baseline.py creado
[ ] RulesConfig dataclass con umbrales
[ ] RulesBaselineDetector implementa RegimeDetector
[ ] is_fitted siempre True
[ ] Lógica de reglas con prioridades
[ ] Cálculo de pseudo-probabilidades
[ ] Reasoning en metadata

TAREA A2.4: FACTORY Y CONFIGURACIÓN
─────────────────────────────────────────────────────────────────────────────
[ ] src/ml/factory.py creado
[ ] MODEL_REGISTRY con hmm y rules
[ ] RegimeDetectorFactory implementa ModelFactory
[ ] Singleton pattern
[ ] Cache de detector activo
[ ] config/ml_models.yaml creado y completo
[ ] get_regime_detector() función de conveniencia

TAREA A2.5: INTEGRACIÓN MCP-ML-MODELS
─────────────────────────────────────────────────────────────────────────────
[ ] tools/regime.py usa Factory real
[ ] Cache de predicciones con TTL
[ ] tools/model_info.py actualizado
[ ] server.py con handlers correctos
[ ] Tool get_regime funciona
[ ] Tool get_model_info funciona
[ ] Tool list_models funciona
[ ] Tool clear_cache funciona

TAREA A2.6: TESTS Y VERIFICACIÓN
─────────────────────────────────────────────────────────────────────────────
[ ] tests/ml/test_hmm_regime.py creado
[ ] tests/ml/test_factory.py creado  
[ ] scripts/verify_fase_a2.py creado
[ ] python scripts/verify_fase_a2.py retorna 0
[ ] pytest tests/ml/ pasa

═══════════════════════════════════════════════════════════════════════════════

GATE DE AVANCE A FASE B1:
─────────────────────────────────────────────────────────────────────────────
[ ] python scripts/verify_fase_a2.py retorna 0 (éxito)
[ ] Modelo Rules predice correctamente los 4 regímenes
[ ] Modelo HMM entrena sin errores (con datos sintéticos)
[ ] Factory crea ambos modelos correctamente
[ ] mcp-ml-models responde a get_regime

═══════════════════════════════════════════════════════════════════════════════
```

---

## 15. Troubleshooting

### Error: "hmmlearn no instalado"

```bash
pip install hmmlearn
# O con todas las dependencias ML:
pip install -r requirements-ml.txt
```

### Error: "Modelo no converge"

```python
# Aumentar iteraciones
config = HMMConfig(n_iter=200)

# O cambiar tipo de covarianza
config = HMMConfig(covariance_type="diag")  # Más simple, menos parámetros

# Verificar datos
print(f"NaN: {np.isnan(X).sum()}")
print(f"Inf: {np.isinf(X).sum()}")
print(f"Var por feature: {X.var(axis=0)}")
```

### Error: "Config no encontrada"

```bash
# Crear directorio y archivo
mkdir -p config
# Copiar contenido de sección 10.3 a config/ml_models.yaml
```

### Error: "Factory singleton no reseteado"

```python
# En tests, resetear antes de cada test
from src.ml.factory import RegimeDetectorFactory
RegimeDetectorFactory.reset_instance()
```

### Predicción muy lenta

```python
# Verificar que cache está activo
tool = get_regime_tool()
stats = tool.get_cache_stats()
print(f"Cache entries: {stats['entries']}")

# Si no hay cache, verificar TTL
print(f"TTL: {stats['ttl_seconds']}s")
```

---

## 16. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| mcp-ml-models base | fase_a1_extensiones_base.md | Tarea A1.4 |
| HMM teoría | 05_machine_learning.md | 2.2 |
| Estados de régimen | 01_arquitectura_vision_general.md | 4.6 |
| Feature Store | fase_1_data_pipeline.md | Tarea 1.4 |
| Handoff interfaces | nexus_trading_handoff.md | Sección 3 |
| Estrategias que usan régimen | fase_b1_estrategias_swing.md | (próximo) |

---

## 17. Siguiente Fase

Una vez completada la Fase A2:

1. **Verificar:** `python scripts/verify_fase_a2.py` retorna 0
2. **Verificar:** Modelo Rules detecta los 4 regímenes
3. **Opcional:** Entrenar HMM con datos reales si hay BD disponible
4. **Siguiente documento:** `fase_b1_estrategias_swing.md`
5. **Contenido Fase B1:**
   - Interfaces TradingStrategy ABC
   - ETF Momentum strategy
   - Integración con régimen detector
   - Generación de señales

---

*Fin de Parte 4 - Integración, Tests, Verificación, Checklist Final*

---

*Documento de Implementación - Fase A2: ML Modular*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
