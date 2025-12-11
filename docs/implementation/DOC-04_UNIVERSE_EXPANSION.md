# DOC-04: Ampliación del Universo Maestro

> **Prioridad**: 🟢 MEDIA  
> **Esfuerzo estimado**: 2-3 horas  
> **Dependencias**: DOC-01 (UniverseManager debe estar integrado)

## 1. Contexto y Objetivo

### Estado Actual
El archivo `config/symbols.yaml` contiene aproximadamente **85 símbolos** organizados en categorías. Este número es insuficiente para un screening diario efectivo, especialmente en días de baja liquidez o regímenes específicos.

### Objetivo
Ampliar el universo maestro a **~150 símbolos curados** que:
1. Cumplan criterios de liquidez (volumen > $500K/día)
2. Estén disponibles en Interactive Brokers
3. Tengan spreads razonables (< 0.5%)
4. Cubran diversidad de sectores, geografías y tipos de activo
5. Permitan al UniverseManager filtrar a 30-50 símbolos activos diarios

### Distribución Propuesta

| Categoría | Actual | Propuesto | Descripción |
|-----------|--------|-----------|-------------|
| ETFs Core | 15 | 20 | Índices principales, liquidez máxima |
| ETFs Sectoriales | 12 | 20 | Sectores US (XLK, XLF, etc.) |
| ETFs Temáticos | 0 | 10 | Clean energy, AI, Cybersecurity |
| US Large Cap Tech | 15 | 20 | FAANG+, semiconductores |
| US Large Cap Value | 12 | 15 | Financieras, industriales, consumo |
| US Mid Cap Growth | 0 | 15 | Empresas en crecimiento |
| EU Large Cap | 15 | 20 | DAX, CAC, principales europeas |
| Defensivos/Bonds | 8 | 10 | TLT, BND, utilities |
| Commodities | 8 | 10 | Oro, plata, petróleo, agrícolas |
| REITs | 0 | 5 | Real Estate Investment Trusts |
| Crypto ETFs | 0 | 5 | Bitcoin, Ethereum ETFs |
| **TOTAL** | ~85 | **~150** | |

---

## 2. Criterios de Selección

### 2.1. Criterios Obligatorios (Must Have)

```yaml
# Todos los símbolos DEBEN cumplir:
liquidity:
  min_avg_daily_volume_usd: 500000      # $500K mínimo
  min_avg_daily_volume_shares: 100000   # 100K acciones
  
availability:
  broker: "interactive_brokers"          # Disponible en IBKR
  data_source: ["ibkr", "yahoo"]        # Datos accesibles
  
trading:
  max_typical_spread_pct: 0.5           # Spread < 0.5%
  min_price: 5.0                        # No penny stocks
  max_price: 10000                      # Razonable para sizing
  
history:
  min_trading_days: 500                 # ~2 años de historia
```

### 2.2. Criterios Deseables (Nice to Have)

```yaml
# Preferimos símbolos que además:
quality:
  options_available: true               # Tiene opciones (más liquidez)
  in_major_index: true                  # Parte de S&P500, NASDAQ100, etc.
  analyst_coverage: ">5"                # Cobertura de analistas
  
fundamentals:
  market_cap_usd: ">1B"                 # Large/Mid cap
  positive_earnings: true               # Empresa rentable (para stocks)
```

---

## 3. Símbolos Propuestos por Categoría

### 3.1. ETFs Core (20)

Máxima liquidez, ideales para cualquier régimen.

```yaml
# ETFs Core - Índices Principales
etfs_core:
  # US Broad Market
  - ticker: SPY
    name: "SPDR S&P 500 ETF"
    sector: broad_market
    liquidity_tier: 1
    
  - ticker: QQQ
    name: "Invesco NASDAQ-100 ETF"
    sector: technology
    liquidity_tier: 1
    
  - ticker: IWM
    name: "iShares Russell 2000 ETF"
    sector: small_cap
    liquidity_tier: 1
    
  - ticker: DIA
    name: "SPDR Dow Jones Industrial ETF"
    sector: broad_market
    liquidity_tier: 1
    
  - ticker: VTI
    name: "Vanguard Total Stock Market ETF"
    sector: broad_market
    liquidity_tier: 1
    
  - ticker: VOO
    name: "Vanguard S&P 500 ETF"
    sector: broad_market
    liquidity_tier: 1
    
  - ticker: IVV
    name: "iShares Core S&P 500 ETF"
    sector: broad_market
    liquidity_tier: 1

  # US Factors
  - ticker: VUG
    name: "Vanguard Growth ETF"
    sector: growth
    liquidity_tier: 1
    
  - ticker: VTV
    name: "Vanguard Value ETF"
    sector: value
    liquidity_tier: 1
    
  - ticker: MTUM
    name: "iShares MSCI USA Momentum Factor ETF"
    sector: momentum
    liquidity_tier: 2

  # International
  - ticker: VEA
    name: "Vanguard FTSE Developed Markets ETF"
    sector: international
    liquidity_tier: 2
    
  - ticker: VWO
    name: "Vanguard FTSE Emerging Markets ETF"
    sector: emerging_markets
    liquidity_tier: 2
    
  - ticker: EFA
    name: "iShares MSCI EAFE ETF"
    sector: international
    liquidity_tier: 2
    
  - ticker: EEM
    name: "iShares MSCI Emerging Markets ETF"
    sector: emerging_markets
    liquidity_tier: 2

  # Europe Specific
  - ticker: VGK
    name: "Vanguard FTSE Europe ETF"
    sector: europe
    liquidity_tier: 2
    
  - ticker: EZU
    name: "iShares MSCI Eurozone ETF"
    sector: europe
    liquidity_tier: 2
    
  - ticker: FEZ
    name: "SPDR EURO STOXX 50 ETF"
    sector: europe
    liquidity_tier: 2

  # Size/Style
  - ticker: IJH
    name: "iShares Core S&P Mid-Cap ETF"
    sector: mid_cap
    liquidity_tier: 2
    
  - ticker: IJR
    name: "iShares Core S&P Small-Cap ETF"
    sector: small_cap
    liquidity_tier: 2
    
  - ticker: MDY
    name: "SPDR S&P MidCap 400 ETF"
    sector: mid_cap
    liquidity_tier: 2
```

### 3.2. ETFs Sectoriales US (20)

```yaml
# Sectores GICS - Select Sector SPDRs
etfs_sectors:
  - ticker: XLK
    name: "Technology Select Sector SPDR"
    sector: technology
    
  - ticker: XLF
    name: "Financial Select Sector SPDR"
    sector: financials
    
  - ticker: XLV
    name: "Health Care Select Sector SPDR"
    sector: healthcare
    
  - ticker: XLE
    name: "Energy Select Sector SPDR"
    sector: energy
    
  - ticker: XLI
    name: "Industrial Select Sector SPDR"
    sector: industrials
    
  - ticker: XLY
    name: "Consumer Discretionary Select Sector SPDR"
    sector: consumer_discretionary
    
  - ticker: XLP
    name: "Consumer Staples Select Sector SPDR"
    sector: consumer_staples
    
  - ticker: XLU
    name: "Utilities Select Sector SPDR"
    sector: utilities
    
  - ticker: XLB
    name: "Materials Select Sector SPDR"
    sector: materials
    
  - ticker: XLRE
    name: "Real Estate Select Sector SPDR"
    sector: real_estate
    
  - ticker: XLC
    name: "Communication Services Select Sector SPDR"
    sector: communication

  # Subsectores específicos
  - ticker: SMH
    name: "VanEck Semiconductor ETF"
    sector: semiconductors
    
  - ticker: XBI
    name: "SPDR S&P Biotech ETF"
    sector: biotech
    
  - ticker: XHB
    name: "SPDR S&P Homebuilders ETF"
    sector: homebuilders
    
  - ticker: XRT
    name: "SPDR S&P Retail ETF"
    sector: retail
    
  - ticker: KRE
    name: "SPDR S&P Regional Banking ETF"
    sector: regional_banks
    
  - ticker: XOP
    name: "SPDR S&P Oil & Gas Exploration ETF"
    sector: oil_gas
    
  - ticker: ITB
    name: "iShares U.S. Home Construction ETF"
    sector: construction
    
  - ticker: IBB
    name: "iShares Biotechnology ETF"
    sector: biotech
    
  - ticker: IYR
    name: "iShares U.S. Real Estate ETF"
    sector: real_estate
```

### 3.3. ETFs Temáticos (10)

```yaml
# Tendencias y megatendencias
etfs_thematic:
  - ticker: ARKK
    name: "ARK Innovation ETF"
    sector: innovation
    notes: "Alta volatilidad, usar con cuidado"
    
  - ticker: ICLN
    name: "iShares Global Clean Energy ETF"
    sector: clean_energy
    
  - ticker: TAN
    name: "Invesco Solar ETF"
    sector: solar
    
  - ticker: LIT
    name: "Global X Lithium & Battery Tech ETF"
    sector: batteries
    
  - ticker: BOTZ
    name: "Global X Robotics & AI ETF"
    sector: robotics_ai
    
  - ticker: HACK
    name: "ETFMG Prime Cyber Security ETF"
    sector: cybersecurity
    
  - ticker: SKYY
    name: "First Trust Cloud Computing ETF"
    sector: cloud
    
  - ticker: FINX
    name: "Global X FinTech ETF"
    sector: fintech
    
  - ticker: DRIV
    name: "Global X Autonomous & Electric Vehicles ETF"
    sector: ev
    
  - ticker: ESPO
    name: "VanEck Video Gaming and eSports ETF"
    sector: gaming
```

### 3.4. US Large Cap Tech (20)

```yaml
# Mega caps tecnológicos
us_tech_large:
  # Magnificent 7 + Adjacent
  - ticker: AAPL
    name: "Apple Inc."
    sector: technology
    market_cap_tier: mega
    
  - ticker: MSFT
    name: "Microsoft Corporation"
    sector: technology
    market_cap_tier: mega
    
  - ticker: GOOGL
    name: "Alphabet Inc. Class A"
    sector: communication
    market_cap_tier: mega
    
  - ticker: AMZN
    name: "Amazon.com Inc."
    sector: consumer_discretionary
    market_cap_tier: mega
    
  - ticker: NVDA
    name: "NVIDIA Corporation"
    sector: semiconductors
    market_cap_tier: mega
    
  - ticker: META
    name: "Meta Platforms Inc."
    sector: communication
    market_cap_tier: mega
    
  - ticker: TSLA
    name: "Tesla Inc."
    sector: automotive
    market_cap_tier: mega

  # Semiconductores
  - ticker: AMD
    name: "Advanced Micro Devices"
    sector: semiconductors
    
  - ticker: AVGO
    name: "Broadcom Inc."
    sector: semiconductors
    
  - ticker: INTC
    name: "Intel Corporation"
    sector: semiconductors
    
  - ticker: QCOM
    name: "Qualcomm Inc."
    sector: semiconductors
    
  - ticker: MU
    name: "Micron Technology"
    sector: semiconductors

  # Software/Cloud
  - ticker: CRM
    name: "Salesforce Inc."
    sector: software
    
  - ticker: ADBE
    name: "Adobe Inc."
    sector: software
    
  - ticker: ORCL
    name: "Oracle Corporation"
    sector: software
    
  - ticker: NOW
    name: "ServiceNow Inc."
    sector: software
    
  - ticker: SNOW
    name: "Snowflake Inc."
    sector: cloud
    
  - ticker: PLTR
    name: "Palantir Technologies"
    sector: software

  # Internet/E-commerce
  - ticker: NFLX
    name: "Netflix Inc."
    sector: streaming
    
  - ticker: UBER
    name: "Uber Technologies"
    sector: transportation
```

### 3.5. US Large Cap Value (15)

```yaml
# Value stocks - Financieras, Industriales, Consumo
us_value_large:
  # Financieras
  - ticker: JPM
    name: "JPMorgan Chase & Co."
    sector: financials
    
  - ticker: BAC
    name: "Bank of America Corp."
    sector: financials
    
  - ticker: WFC
    name: "Wells Fargo & Co."
    sector: financials
    
  - ticker: GS
    name: "Goldman Sachs Group"
    sector: financials
    
  - ticker: BRK.B
    name: "Berkshire Hathaway Class B"
    sector: financials

  # Industriales
  - ticker: CAT
    name: "Caterpillar Inc."
    sector: industrials
    
  - ticker: DE
    name: "Deere & Company"
    sector: industrials
    
  - ticker: HON
    name: "Honeywell International"
    sector: industrials
    
  - ticker: UNP
    name: "Union Pacific Corporation"
    sector: transportation
    
  - ticker: GE
    name: "General Electric Co."
    sector: industrials

  # Healthcare
  - ticker: JNJ
    name: "Johnson & Johnson"
    sector: healthcare
    
  - ticker: UNH
    name: "UnitedHealth Group"
    sector: healthcare
    
  - ticker: PFE
    name: "Pfizer Inc."
    sector: healthcare

  # Consumo
  - ticker: PG
    name: "Procter & Gamble"
    sector: consumer_staples
    
  - ticker: KO
    name: "Coca-Cola Company"
    sector: consumer_staples
```

### 3.6. US Mid Cap Growth (15)

```yaml
# Mid caps con potencial de crecimiento
us_midcap_growth:
  - ticker: CRWD
    name: "CrowdStrike Holdings"
    sector: cybersecurity
    
  - ticker: DDOG
    name: "Datadog Inc."
    sector: software
    
  - ticker: ZS
    name: "Zscaler Inc."
    sector: cybersecurity
    
  - ticker: NET
    name: "Cloudflare Inc."
    sector: cloud
    
  - ticker: OKTA
    name: "Okta Inc."
    sector: identity
    
  - ticker: TEAM
    name: "Atlassian Corporation"
    sector: software
    
  - ticker: TTD
    name: "The Trade Desk Inc."
    sector: advertising
    
  - ticker: ROKU
    name: "Roku Inc."
    sector: streaming
    
  - ticker: SQ
    name: "Block Inc. (Square)"
    sector: fintech
    
  - ticker: SHOP
    name: "Shopify Inc."
    sector: ecommerce
    
  - ticker: MELI
    name: "MercadoLibre Inc."
    sector: ecommerce
    
  - ticker: SE
    name: "Sea Limited"
    sector: gaming_ecommerce
    
  - ticker: COIN
    name: "Coinbase Global"
    sector: crypto
    
  - ticker: RBLX
    name: "Roblox Corporation"
    sector: gaming
    
  - ticker: DASH
    name: "DoorDash Inc."
    sector: delivery
```

### 3.7. EU Large Cap (20)

```yaml
# Principales empresas europeas (ADRs o listadas en US)
eu_large_cap:
  # Alemania
  - ticker: SAP
    name: "SAP SE (ADR)"
    sector: software
    country: DE
    
  - ticker: SIEGY
    name: "Siemens AG (ADR)"
    sector: industrials
    country: DE

  # Francia
  - ticker: LVMUY
    name: "LVMH (ADR)"
    sector: luxury
    country: FR
    
  - ticker: TTE
    name: "TotalEnergies SE (ADR)"
    sector: energy
    country: FR
    
  - ticker: SNY
    name: "Sanofi (ADR)"
    sector: healthcare
    country: FR

  # Reino Unido
  - ticker: SHEL
    name: "Shell PLC (ADR)"
    sector: energy
    country: UK
    
  - ticker: BP
    name: "BP PLC (ADR)"
    sector: energy
    country: UK
    
  - ticker: AZN
    name: "AstraZeneca PLC (ADR)"
    sector: healthcare
    country: UK
    
  - ticker: GSK
    name: "GSK PLC (ADR)"
    sector: healthcare
    country: UK
    
  - ticker: HSBC
    name: "HSBC Holdings (ADR)"
    sector: financials
    country: UK

  # Suiza
  - ticker: NVS
    name: "Novartis AG (ADR)"
    sector: healthcare
    country: CH
    
  - ticker: UBS
    name: "UBS Group AG"
    sector: financials
    country: CH

  # Holanda
  - ticker: ASML
    name: "ASML Holding NV (ADR)"
    sector: semiconductors
    country: NL
    
  - ticker: NVO
    name: "Novo Nordisk (ADR)"
    sector: healthcare
    country: DK

  # España
  - ticker: TEF
    name: "Telefónica SA (ADR)"
    sector: telecom
    country: ES
    
  - ticker: BBVA
    name: "Banco Bilbao Vizcaya (ADR)"
    sector: financials
    country: ES

  # Italia
  - ticker: ENEL
    name: "Enel SpA (ADR)"
    sector: utilities
    country: IT

  # Otros
  - ticker: TM
    name: "Toyota Motor (ADR)"
    sector: automotive
    country: JP
    
  - ticker: SONY
    name: "Sony Group (ADR)"
    sector: electronics
    country: JP
    
  - ticker: BCS
    name: "Barclays PLC (ADR)"
    sector: financials
    country: UK
```

### 3.8. Defensivos y Bonds (10)

```yaml
# Activos defensivos para regímenes BEAR/VOLATILE
defensives_bonds:
  # Bonos
  - ticker: TLT
    name: "iShares 20+ Year Treasury Bond ETF"
    sector: bonds
    duration: long
    
  - ticker: IEF
    name: "iShares 7-10 Year Treasury Bond ETF"
    sector: bonds
    duration: intermediate
    
  - ticker: SHY
    name: "iShares 1-3 Year Treasury Bond ETF"
    sector: bonds
    duration: short
    
  - ticker: BND
    name: "Vanguard Total Bond Market ETF"
    sector: bonds
    duration: mixed
    
  - ticker: LQD
    name: "iShares iBoxx Investment Grade Corporate Bond ETF"
    sector: corporate_bonds
    
  - ticker: HYG
    name: "iShares iBoxx High Yield Corporate Bond ETF"
    sector: high_yield

  # Utilities (defensivo en equity)
  - ticker: VPU
    name: "Vanguard Utilities ETF"
    sector: utilities
    
  - ticker: NEE
    name: "NextEra Energy Inc."
    sector: utilities

  # Dividend/Low Vol
  - ticker: VIG
    name: "Vanguard Dividend Appreciation ETF"
    sector: dividends
    
  - ticker: USMV
    name: "iShares MSCI USA Min Vol Factor ETF"
    sector: low_volatility
```

### 3.9. Commodities (10)

```yaml
# Materias primas y metales
commodities:
  # Metales preciosos
  - ticker: GLD
    name: "SPDR Gold Shares"
    sector: gold
    
  - ticker: SLV
    name: "iShares Silver Trust"
    sector: silver
    
  - ticker: GDX
    name: "VanEck Gold Miners ETF"
    sector: gold_miners

  # Energía
  - ticker: USO
    name: "United States Oil Fund"
    sector: oil
    
  - ticker: UNG
    name: "United States Natural Gas Fund"
    sector: natural_gas
    notes: "Alta volatilidad, contango risk"

  # Agricultura
  - ticker: DBA
    name: "Invesco DB Agriculture Fund"
    sector: agriculture
    
  - ticker: CORN
    name: "Teucrium Corn Fund"
    sector: grains

  # Broad Commodities
  - ticker: DBC
    name: "Invesco DB Commodity Index Tracking Fund"
    sector: broad_commodities
    
  - ticker: GSG
    name: "iShares S&P GSCI Commodity-Indexed Trust"
    sector: broad_commodities

  # Metales industriales
  - ticker: COPX
    name: "Global X Copper Miners ETF"
    sector: copper
```

### 3.10. REITs (5)

```yaml
# Real Estate Investment Trusts
reits:
  - ticker: VNQ
    name: "Vanguard Real Estate ETF"
    sector: real_estate
    
  - ticker: O
    name: "Realty Income Corporation"
    sector: retail_reit
    notes: "Monthly dividend"
    
  - ticker: AMT
    name: "American Tower Corporation"
    sector: tower_reit
    
  - ticker: PLD
    name: "Prologis Inc."
    sector: industrial_reit
    
  - ticker: EQIX
    name: "Equinix Inc."
    sector: datacenter_reit
```

### 3.11. Crypto ETFs (5)

```yaml
# ETFs de criptomonedas (spot, aprobados 2024)
crypto_etfs:
  - ticker: IBIT
    name: "iShares Bitcoin Trust ETF"
    sector: bitcoin
    notes: "Spot Bitcoin ETF"
    
  - ticker: FBTC
    name: "Fidelity Wise Origin Bitcoin Fund"
    sector: bitcoin
    
  - ticker: GBTC
    name: "Grayscale Bitcoin Trust"
    sector: bitcoin
    notes: "Convertido a ETF"
    
  - ticker: ETHE
    name: "Grayscale Ethereum Trust"
    sector: ethereum
    
  - ticker: BITO
    name: "ProShares Bitcoin Strategy ETF"
    sector: bitcoin_futures
    notes: "Futures-based, contango risk"
```

---

## 4. Archivo YAML Completo

El archivo `config/symbols.yaml` actualizado debe seguir esta estructura:

```yaml
# config/symbols.yaml
#
# Nexus Trading - Master Universe Configuration
# Total: ~150 símbolos curados
#
# Criterios de inclusión:
# - Volumen diario promedio > $500K
# - Disponible en Interactive Brokers
# - Spread típico < 0.5%
# - Historial de al menos 2 años
#
# Actualizado: 2024-XX-XX

# Configuración global
metadata:
  version: "2.0"
  total_symbols: 150
  last_updated: "2024-01-15"
  
# Campos por símbolo:
# - ticker: Símbolo (requerido)
# - name: Nombre completo (requerido)
# - market: US, EU, GLOBAL (requerido)
# - source: ibkr, yahoo (requerido)
# - timezone: America/New_York, Europe/London, etc.
# - currency: USD, EUR, GBP
# - asset_type: etf, stock, reit, commodity
# - sector: Sector/categoría
# - liquidity_tier: 1 (máxima) a 3 (mínima aceptable)
# - notes: Notas adicionales (opcional)

symbols:
  # ===========================================================================
  # ETFs CORE (20)
  # ===========================================================================
  - ticker: SPY
    name: "SPDR S&P 500 ETF Trust"
    market: US
    source: ibkr
    timezone: America/New_York
    currency: USD
    asset_type: etf
    sector: broad_market
    liquidity_tier: 1

  # ... (resto de símbolos según las listas anteriores)
```

---

## 5. Script de Validación

Crear un script para validar que todos los símbolos cumplen criterios:

**Archivo**: `scripts/validate_universe.py`

```python
#!/usr/bin/env python
"""
Validar que todos los símbolos del universo maestro cumplen criterios.

Uso:
    python scripts/validate_universe.py
    python scripts/validate_universe.py --check-liquidity  # Verifica con datos reales
"""

import sys
import yaml
import asyncio
import argparse
from pathlib import Path
from collections import Counter

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SYMBOLS_FILE = project_root / "config" / "symbols.yaml"

# Criterios de validación
REQUIRED_FIELDS = ["ticker", "name", "market", "source", "asset_type", "sector"]
VALID_MARKETS = ["US", "EU", "GLOBAL"]
VALID_SOURCES = ["ibkr", "yahoo"]
VALID_ASSET_TYPES = ["etf", "stock", "reit", "commodity", "bond"]
VALID_LIQUIDITY_TIERS = [1, 2, 3]


def load_symbols():
    """Cargar símbolos desde YAML."""
    with open(SYMBOLS_FILE, 'r') as f:
        data = yaml.safe_load(f)
    return data.get("symbols", [])


def validate_structure(symbols):
    """Validar estructura básica de cada símbolo."""
    errors = []
    warnings = []
    
    tickers = []
    
    for i, sym in enumerate(symbols):
        prefix = f"Symbol #{i+1}"
        
        # Verificar campos requeridos
        for field in REQUIRED_FIELDS:
            if field not in sym:
                errors.append(f"{prefix}: Missing required field '{field}'")
        
        if "ticker" not in sym:
            continue
            
        ticker = sym["ticker"]
        prefix = f"[{ticker}]"
        tickers.append(ticker)
        
        # Validar valores
        if sym.get("market") not in VALID_MARKETS:
            errors.append(f"{prefix}: Invalid market '{sym.get('market')}'")
            
        if sym.get("source") not in VALID_SOURCES:
            errors.append(f"{prefix}: Invalid source '{sym.get('source')}'")
            
        if sym.get("asset_type") not in VALID_ASSET_TYPES:
            warnings.append(f"{prefix}: Unusual asset_type '{sym.get('asset_type')}'")
            
        if sym.get("liquidity_tier") and sym["liquidity_tier"] not in VALID_LIQUIDITY_TIERS:
            warnings.append(f"{prefix}: Invalid liquidity_tier '{sym.get('liquidity_tier')}'")
    
    # Verificar duplicados
    ticker_counts = Counter(tickers)
    for ticker, count in ticker_counts.items():
        if count > 1:
            errors.append(f"[{ticker}]: Duplicate ticker ({count} occurrences)")
    
    return errors, warnings


def print_summary(symbols):
    """Imprimir resumen del universo."""
    print("\n" + "=" * 60)
    print("UNIVERSE SUMMARY")
    print("=" * 60)
    
    print(f"\nTotal symbols: {len(symbols)}")
    
    # Por mercado
    markets = Counter(s.get("market", "UNKNOWN") for s in symbols)
    print("\nBy Market:")
    for market, count in sorted(markets.items()):
        print(f"  {market}: {count}")
    
    # Por tipo de activo
    types = Counter(s.get("asset_type", "UNKNOWN") for s in symbols)
    print("\nBy Asset Type:")
    for atype, count in sorted(types.items()):
        print(f"  {atype}: {count}")
    
    # Por sector (top 10)
    sectors = Counter(s.get("sector", "UNKNOWN") for s in symbols)
    print("\nBy Sector (top 15):")
    for sector, count in sectors.most_common(15):
        print(f"  {sector}: {count}")
    
    # Por tier de liquidez
    tiers = Counter(s.get("liquidity_tier", "N/A") for s in symbols)
    print("\nBy Liquidity Tier:")
    for tier, count in sorted(tiers.items()):
        print(f"  Tier {tier}: {count}")


async def check_liquidity(symbols, sample_size=10):
    """
    Verificar liquidez real de una muestra de símbolos.
    Requiere conexión a datos de mercado.
    """
    print("\n" + "=" * 60)
    print("LIQUIDITY CHECK (sample)")
    print("=" * 60)
    
    try:
        import yfinance as yf
        
        # Tomar muestra aleatoria
        import random
        sample = random.sample(symbols, min(sample_size, len(symbols)))
        
        print(f"\nChecking {len(sample)} symbols...")
        
        low_liquidity = []
        for sym in sample:
            ticker = sym["ticker"]
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                avg_volume = info.get("averageVolume", 0)
                price = info.get("currentPrice", info.get("regularMarketPrice", 0))
                
                volume_usd = avg_volume * price if price else 0
                
                status = "✓" if volume_usd >= 500000 else "✗"
                print(f"  {status} {ticker}: ${volume_usd:,.0f}/day")
                
                if volume_usd < 500000:
                    low_liquidity.append(ticker)
                    
            except Exception as e:
                print(f"  ? {ticker}: Error - {e}")
        
        if low_liquidity:
            print(f"\n⚠️  Low liquidity symbols: {low_liquidity}")
            
    except ImportError:
        print("yfinance not installed. Run: pip install yfinance")


def main():
    parser = argparse.ArgumentParser(description="Validate universe configuration")
    parser.add_argument("--check-liquidity", action="store_true", 
                       help="Check real liquidity data (requires yfinance)")
    args = parser.parse_args()
    
    print("Loading symbols from", SYMBOLS_FILE)
    symbols = load_symbols()
    
    if not symbols:
        print("ERROR: No symbols found!")
        sys.exit(1)
    
    # Validar estructura
    errors, warnings = validate_structure(symbols)
    
    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    
    # Resumen
    print_summary(symbols)
    
    # Check liquidez si se solicita
    if args.check_liquidity:
        asyncio.run(check_liquidity(symbols))
    
    # Exit code
    if errors:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ Validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## 6. Proceso de Actualización del Universo

### 6.1. Actualización Manual (MVP)

1. Revisar rendimiento de símbolos mensualmente
2. Verificar liquidez con el script de validación
3. Añadir/quitar símbolos según criterios
4. Commit del nuevo `symbols.yaml`

### 6.2. Actualización Semi-Automática (Futuro)

Crear servicio que:
1. Descarga datos de liquidez semanalmente
2. Identifica símbolos que ya no cumplen criterios
3. Sugiere nuevos símbolos candidatos
4. Genera PR para revisión humana

**Pseudo-código del servicio futuro:**

```python
class UniverseMaintainer:
    """
    Servicio de mantenimiento del universo maestro.
    
    Ejecutar semanalmente (domingo noche).
    """
    
    async def run_maintenance(self):
        # 1. Cargar universo actual
        current = self.load_current_universe()
        
        # 2. Verificar cada símbolo
        to_remove = []
        for symbol in current:
            metrics = await self.get_symbol_metrics(symbol)
            if not self.meets_criteria(metrics):
                to_remove.append(symbol)
        
        # 3. Buscar candidatos
        candidates = await self.find_candidates()
        to_add = [c for c in candidates if self.meets_criteria(c)]
        
        # 4. Generar reporte
        report = self.generate_report(to_remove, to_add)
        
        # 5. Crear PR o notificar
        await self.notify_admin(report)
    
    def meets_criteria(self, metrics):
        return (
            metrics["avg_volume_usd"] >= 500_000 and
            metrics["spread_pct"] <= 0.5 and
            metrics["price"] >= 5.0 and
            metrics["trading_days"] >= 500
        )
```

---

## 7. Checklist de Implementación

- [ ] Crear nuevo `config/symbols.yaml` con ~150 símbolos
- [ ] Verificar que cada símbolo tiene todos los campos requeridos
- [ ] Crear `scripts/validate_universe.py`
- [ ] Ejecutar validación y corregir errores
- [ ] Verificar liquidez de una muestra con datos reales
- [ ] Actualizar documentación con nueva distribución
- [ ] Probar que UniverseManager carga correctamente el nuevo archivo
- [ ] Verificar que el screening diario funciona con más símbolos
- [ ] Medir tiempo de screening (puede aumentar con más símbolos)

---

## 8. Notas Importantes

### Tiempo de Screening
Con 150 símbolos, el screening secuencial puede tomar 5-10 minutos. Asegurar que la paralelización del DOC-01 está implementada para reducir a <2 minutos.

### ADRs Europeos
Muchos símbolos "europeos" son ADRs listados en US (ej: ASML, SAP). Esto simplifica el trading pero puede haber diferencias de precio/liquidez vs el listado original.

### Crypto ETFs
Los ETFs de Bitcoin son nuevos (2024) y pueden tener comportamiento diferente. Considerar excluirlos inicialmente o darles peso reducido.

### Mantenimiento
El universo debe revisarse al menos mensualmente. Símbolos pueden perder liquidez, ser delisted, o sufrir eventos corporativos.
