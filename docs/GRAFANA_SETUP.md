# Grafana Setup Guide

## Quick Access

**URL:** http://localhost:3000  
**Username:** admin  
**Password:** A8ZXO&bOa9add5A8^!0vREP*

---

## 1. Configure InfluxDB Data Source

1. **Login to Grafana** (http://localhost:3000)

2. **Add Data Source:**
   - Go to: Configuration (⚙️) → Data Sources → Add data source
   - Select: **InfluxDB**

3. **Configure Connection:**
   ```
   Name: InfluxDB (Nexus Trading)
   Query Language: Flux
   URL: http://influxdb:8086
   Organization: nexus-trading
   Token: hA==2h-RnixGFqv7koJDxH4B7w3AcdJlrzq52o3q-mTskoT1Mh
   Default Bucket: trading
   ```

4. **Save & Test**
   - Click "Save & Test"
   - Should see: ✅ "datasource is working"

---

## 2. Import Data Quality Dashboard

### Method 1: Import JSON File

1. **Go to Dashboards:**
   - Click "+" → Import

2. **Upload JSON:**
   - Click "Upload JSON file"
   - Select: `config/grafana/dashboards/data_quality.json`

3. **Configure:**
   - Name: "Nexus Trading - Data Quality"
   - Folder: "General" (or create "Trading")
   - UID: nexus-data-quality

4. **Import**
   - Click "Import"
   - Dashboard should load with 8 panels

### Method 2: Copy-Paste JSON

1. Go to: "+" → Import
2. Paste the contents of `data_quality.json`
3. Click "Load"
4. Click "Import"

---

## 3. Dashboard Panels

### Panel 1: OHLCV Records per Symbol
- **Type:** Bar chart
- **Shows:** Total OHLCV records per symbol (last 30 days)
- **Purpose:** Monitor data coverage

### Panel 2: Daily Ingestion Count
- **Type:** Time series
- **Shows:** Number of records inserted daily
- **Alert:** Triggers if <10 records/day
- **Purpose:** Detect ingestion failures

### Panel 3: Data Quality Violations (24h)
- **Type:** Stat
- **Shows:** Rejected records in last 24h
- **Thresholds:** Green (0-5), Yellow (5-20), Red (>20)
- **Purpose:** Monitor data quality

### Panel 4: Feature NaN Percentage
- **Type:** Gauge
- **Shows:** Average NaN % across features
- **Thresholds:** Green (<3%), Yellow (3-5%), Red (>5%)
- **Purpose:** Feature quality monitoring

### Panel 5: Data Freshness
- **Type:** Stat
- **Shows:** Hours since last update per symbol
- **Thresholds:** Green (<24h), Yellow (24-36h), Red (>36h)
- **Purpose:** Detect stale data

### Panel 6: Indicator Calculation Time
- **Type:** Time series
- **Shows:** Time to calculate indicators (ms)
- **Purpose:** Performance monitoring

### Panel 7: Pipeline Success Rate
- **Type:** Pie chart
- **Shows:** Success vs Failed jobs (last 7 days)
- **Purpose:** Overall pipeline health

### Panel 8: Symbol Coverage
- **Type:** Table
- **Shows:** Latest OHLCV date per symbol
- **Highlights:** Symbols with old data (yellow/red)
- **Purpose:** Per-symbol freshness

---

## 4. Setting Up Alerts

### Configure Alert Notifications (Optional)

1. **Go to:** Alerting → Notification channels

2. **Add Channel:**
   - Type: Email / Slack / Webhook
   - Configure details

3. **Link to Panels:**
   - Edit Panel 2 (Daily Ingestion)
   - Go to Alert tab
   - Add notification channel

---

## 5. Sending Metrics to InfluxDB

The quality module (`src/data/quality.py`) should send metrics to InfluxDB.

**Example InfluxDB write (Python):**

```python
from influx_client import InfluxDBClient

client = InfluxDBClient(
    url="http://127.0.0.1:8086",
    token=os.getenv('INFLUXDB_TOKEN'),
    org="nexus-trading"
)

# Write metric
point = Point("ohlcv_count")\
    .tag("symbol", "AAPL")\
    .field("count", 1234)\
    .time(datetime.utcnow())

write_api = client.write_api()
write_api.write(bucket="trading", record=point)
```

**Metrics to implement:**
- `ohlcv_count` - Total records per symbol
- `ohlcv_daily_insert` - Daily new records
- `quality_rejected` - Rejected records
- `feature_nan_pct` - NaN percentage in features
- `last_update_hours` - Hours since last update
- `indicator_calc_time_ms` - Calculation time
- `job_status` - Pipeline job results
- `latest_ohlcv_date` - Latest data timestamp

---

## 6. Accessing the Dashboard

**Direct URL:** http://localhost:3000/d/nexus-data-quality

**Navigation:**
1. Login to Grafana
2. Dashboards → Browse
3. Select "Nexus Trading - Data Quality"

---

## 7. Customization

### Adding More Panels

1. Click "Add panel" (top right)
2. Select visualization type
3. Configure query:
   ```flux
   from(bucket: "trading")
     |> range(start: -30d)
     |> filter(fn: (r) => r._measurement == "your_measurement")
   ```
4. Set thresholds and alerts
5. Save

### Modifying Refresh Rate

- Dashboard settings (⚙️) → Time options
- Set refresh: 10s, 30s, 1m, etc.

---

## 8. Troubleshooting

### Data Source Not Working

1. **Check InfluxDB is running:**
   ```bash
   docker ps | grep influxdb
   ```

2. **Test connection:**
   ```bash
   curl http://localhost:8086/health
   ```

3. **Verify token:**
   - Check `.env` file for `INFLUXDB_TOKEN`

### No Data in Panels

1. **Check bucket exists:**
   - Login to InfluxDB UI: http://localhost:8086
   - Verify "trading" bucket exists

2. **Check measurements:**
   - Run query in InfluxDB Data Explorer
   - Verify data exists

3. **Verify time range:**
   - Dashboard may be set to wrong time range
   - Try "Last 7 days"

### Panels Showing "No Data"

- Metrics may not be implemented yet
- Add metric writes to `src/data/quality.py`
- Run data pipeline to generate metrics

---

## 9. Next Steps

1. ✅ Configure data source
2. ✅ Import dashboard
3. **Implement metric writes** in quality module
4. **Run pipeline** to generate data
5. **Set up alerts** for critical panels
6. **Create additional dashboards** (trading performance, ML metrics, etc.)

---

*Grafana Dashboard Setup - Nexus Trading*
